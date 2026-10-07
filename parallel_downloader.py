"""
High-Speed Parallel MTProto File Downloader for Telethon
Bypasses single-connection speed limits by downloading chunks
in parallel across multiple MTProto connections to Telegram datacenters.
"""

import asyncio
import inspect
import logging
import math
import os
from typing import Any, AsyncGenerator, BinaryIO, Callable, Dict, Optional, Tuple, Union

from telethon import TelegramClient, errors, utils
from telethon.crypto import AuthKey
from telethon.network import MTProtoSender
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.auth import ExportAuthorizationRequest, ImportAuthorizationRequest
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import TypeInputFileLocation

logger = logging.getLogger(__name__)

# Global cache for foreign DC auth keys to avoid repeated ExportAuthorizationRequest FloodWait
_GLOBAL_DC_AUTH_KEYS: Dict[Tuple[int, int], AuthKey] = {}
_GLOBAL_DC_AUTH_LOCK = asyncio.Lock()


class DownloadSender:
    """Handles downloading specific striped chunks on a dedicated MTProto connection."""

    def __init__(
        self,
        client: TelegramClient,
        sender: MTProtoSender,
        file: TypeInputFileLocation,
        offset: int,
        limit: int,
        stride: int,
        count: int,
    ) -> None:
        self.client = client
        self.sender = sender
        self.request = GetFileRequest(file, offset=offset, limit=limit)
        self.stride = stride
        self.remaining = count

    async def next(self) -> Optional[bytes]:
        if self.remaining <= 0:
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await self.client._call(self.sender, self.request)
                self.remaining -= 1
                self.request.offset += self.stride
                return result.bytes
            except Exception as exc:
                if attempt == max_retries - 1:
                    logger.error(f"Chunk request failed after {max_retries} attempts: {exc}")
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        return None

    async def disconnect(self) -> None:
        try:
            await self.sender.disconnect()
        except Exception:
            pass


class ParallelTransferrer:
    """Manages a pool of parallel MTProto senders for high-speed transfers."""

    def __init__(self, client: TelegramClient, dc_id: Optional[int] = None) -> None:
        self.client = client
        self.loop = self.client.loop
        self.dc_id = dc_id or self.client.session.dc_id
        session_dc = self.client.session.dc_id
        if self.dc_id == session_dc:
            self.auth_key = self.client.session.auth_key
        else:
            self.auth_key = _GLOBAL_DC_AUTH_KEYS.get((session_dc, self.dc_id))
        self.senders = []

    async def _cleanup(self) -> None:
        if self.senders:
            await asyncio.gather(*[sender.disconnect() for sender in self.senders], return_exceptions=True)
            self.senders = []

    async def _create_sender(self) -> MTProtoSender:
        dc = await self.client._get_dc(self.dc_id)
        session_dc = self.client.session.dc_id
        cache_key = (session_dc, self.dc_id)

        # If connecting to a foreign DC and we don't have a cached auth key yet,
        # acquire lock and export authorization ONCE for the entire application session.
        if not self.auth_key and cache_key not in _GLOBAL_DC_AUTH_KEYS:
            async with _GLOBAL_DC_AUTH_LOCK:
                if cache_key in _GLOBAL_DC_AUTH_KEYS:
                    self.auth_key = _GLOBAL_DC_AUTH_KEYS[cache_key]
                else:
                    sender = MTProtoSender(None, loggers=self.client._log)
                    await sender.connect(
                        self.client._connection(
                            dc.ip_address,
                            dc.port,
                            dc.id,
                            loggers=self.client._log,
                            proxy=self.client._proxy,
                        )
                    )
                    try:
                        auth = await self.client(ExportAuthorizationRequest(self.dc_id))
                        self.client._init_request.query = ImportAuthorizationRequest(
                            id=auth.id, bytes=auth.bytes
                        )
                        req = InvokeWithLayerRequest(LAYER, self.client._init_request)
                        await sender.send(req)
                        self.auth_key = sender.auth_key
                        _GLOBAL_DC_AUTH_KEYS[cache_key] = sender.auth_key
                        return sender
                    except Exception:
                        await sender.disconnect()
                        raise

        # When auth_key is known (home DC or already cached foreign DC), connect with it directly
        auth_key_to_use = self.auth_key or _GLOBAL_DC_AUTH_KEYS.get(cache_key)
        sender = MTProtoSender(auth_key_to_use, loggers=self.client._log)
        await sender.connect(
            self.client._connection(
                dc.ip_address,
                dc.port,
                dc.id,
                loggers=self.client._log,
                proxy=self.client._proxy,
            )
        )
        return sender

    async def _create_download_sender(
        self,
        file: TypeInputFileLocation,
        index: int,
        part_size: int,
        stride: int,
        part_count: int,
    ) -> DownloadSender:
        sender = await self._create_sender()
        return DownloadSender(
            self.client,
            sender,
            file,
            offset=index * part_size,
            limit=part_size,
            stride=stride,
            count=part_count,
        )

    async def _init_download(
        self,
        connections: int,
        file: TypeInputFileLocation,
        part_count: int,
        part_size: int,
    ) -> None:
        minimum, remainder = divmod(part_count, connections)

        def get_part_count() -> int:
            nonlocal remainder
            if remainder > 0:
                remainder -= 1
                return minimum + 1
            return minimum

        # First sender handles cross-DC auth export/import if needed
        first_count = get_part_count()
        first_sender = await self._create_download_sender(
            file, 0, part_size, connections * part_size, first_count
        )
        self.senders = [first_sender]

        if connections > 1:
            rest_senders = await asyncio.gather(
                *[
                    self._create_download_sender(
                        file, i, part_size, connections * part_size, get_part_count()
                    )
                    for i in range(1, connections)
                ]
            )
            self.senders.extend(rest_senders)

    async def download(
        self,
        file: TypeInputFileLocation,
        file_size: int,
        part_size_kb: int = 512,
        max_connections: int = 16,
    ) -> AsyncGenerator[bytes, None]:
        part_size = part_size_kb * 1024
        part_count = math.ceil(file_size / part_size)
        connections = max(1, min(max_connections, part_count))

        await self._init_download(connections, file, part_count, part_size)

        part = 0
        try:
            while part < part_count:
                # Active senders that still have remaining parts
                active_senders = [s for s in self.senders if s.remaining > 0]
                if not active_senders:
                    break

                tasks = [self.loop.create_task(s.next()) for s in active_senders]
                for task in tasks:
                    chunk = await task
                    if chunk is not None:
                        yield chunk
                        part += 1
        finally:
            await self._cleanup()


async def download_file_parallel(
    client: TelegramClient,
    location: Any,
    out_file: Union[str, BinaryIO],
    file_size: int,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    connections: int = 16,
    part_size_kb: int = 512,
) -> str:
    """
    Downloads a Telegram file using parallel connections directly to the DC.
    """
    dc_id, input_location = utils.get_input_location(location)
    downloader = ParallelTransferrer(client, dc_id=dc_id)

    is_path = isinstance(out_file, str)
    file_obj = open(out_file, "wb") if is_path else out_file

    downloaded_bytes = 0
    try:
        async for chunk in downloader.download(
            file=input_location,
            file_size=file_size,
            part_size_kb=part_size_kb,
            max_connections=connections,
        ):
            file_obj.write(chunk)
            downloaded_bytes += len(chunk)
            if progress_callback:
                res = progress_callback(downloaded_bytes, file_size)
                if inspect.isawaitable(res):
                    await res
    finally:
        if is_path:
            file_obj.close()

    return out_file if is_path else getattr(out_file, "name", "file")


async def download_media_fast(
    client: TelegramClient,
    message,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    connections: int = 16,
) -> str:
    """
    Smart high-speed media downloader:
    - Small files (< 1MB) or unsupported types: uses standard download_media
    - Large files (>= 1MB): uses parallel MTProto chunk downloader
    - Graceful fallback to standard download if any parallel error occurs
    """
    file_size = message.file.size if message.file else 0
    document = getattr(message.media, "document", None)

    # Use parallel downloading for documents/videos/large files
    if document and file_size >= 1024 * 1024:
        try:
            return await download_file_parallel(
                client=client,
                location=document,
                out_file=dest_path,
                file_size=file_size,
                progress_callback=progress_callback,
                connections=connections,
                part_size_kb=512,
            )
        except errors.FloodWaitError:
            # Re-raise FloodWaitError immediately so UI can display cooldown and pause
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            raise
        except Exception as exc:
            logger.warning(f"Parallel download failed ({exc}), falling back to standard download...")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass

    # Standard fallback
    return await client.download_media(
        message,
        file=dest_path,
        progress_callback=progress_callback,
    )
