"""High-Speed Download Execution Engine.

Connects the Download Queue Manager to the 16-worker parallel MTProto engine,
providing live telemetry (MB/s, ETA), bandwidth throttling, and smart flood shielding.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from telethon import errors

from auth_manager import auth_mgr
from bot_manager import bot_mgr
from config import config
from parallel_downloader import download_media_fast
from queue_manager import DownloadTask, TaskStatus, queue_mgr
from storage_manager import storage_mgr


class DownloadEngine:
    """Coordinates active download execution across MTProto workers."""

    def __init__(self):
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._current_task: Optional[DownloadTask] = None

    def start(self) -> None:
        """Start the background download processor loop."""
        if not self._is_running:
            self._is_running = True
            self._worker_task = asyncio.create_task(self._process_queue_loop())

    def stop(self) -> None:
        """Stop the background download processor."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

    async def _process_queue_loop(self) -> None:
        """Continuously process queued download tasks."""
        while self._is_running:
            queued = queue_mgr.get_queued_tasks()
            if queued and not queue_mgr.get_active_tasks():
                task = queued[0]
                await self._execute_task(task)
            await asyncio.sleep(0.5)

    async def _execute_task(self, task: DownloadTask) -> None:
        """Execute a single download task using parallel workers."""
        task.status = TaskStatus.DOWNLOADING
        self._current_task = task
        queue_mgr._notify(task)

        # 1. Resolve storage path
        base_dir = config.download_dir
        template = config.get("organization_template", "channel")
        dest_path = storage_mgr.resolve_destination(
            base_dir=base_dir,
            template=template,
            filename=task.title,
            channel_title=task.channel_title,
        )
        task.destination_path = str(dest_path)

        # 2. Check disk space
        has_space, free_bytes, shortfall = storage_mgr.check_has_sufficient_space(
            target_path=dest_path.parent,
            required_bytes=task.total_bytes,
        )
        if not has_space:
            task.status = TaskStatus.FAILED
            task.error_message = (
                f"Insufficient disk space! Needed {task.formatted_size}, "
                f"short by {shortfall / (1024**2):.1f} MB."
            )
            queue_mgr._notify(task)
            self._current_task = None
            return

        # 3. Select appropriate Telethon client
        client = None
        if task.source == "BOT_FORWARD" and bot_mgr.is_running:
            client = bot_mgr.bot_client
        else:
            client = auth_mgr.get_client()

        if client is None or not client.is_connected():
            task.status = TaskStatus.FAILED
            task.error_message = "No active Telegram connection."
            queue_mgr._notify(task)
            self._current_task = None
            return

        # 4. Telemetry tracking variables
        start_time = time.time()
        last_time = start_time
        last_bytes = 0
        workers = config.workers

        def progress_cb(current: int, total: int):
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed_interval = now - last_time

            task.downloaded_bytes = current
            task.total_bytes = total

            if elapsed_interval >= 0.5:
                bytes_delta = current - last_bytes
                speed = bytes_delta / elapsed_interval if elapsed_interval > 0 else 0
                task.speed_bps = speed

                remaining_bytes = max(0, total - current)
                task.eta_seconds = (remaining_bytes / speed) if speed > 0 else 0

                last_time = now
                last_bytes = current

            # Check if cancelled by user
            if queue_mgr.is_cancelled(task.id):
                raise asyncio.CancelledError("Download cancelled by user")

            queue_mgr._notify(task)

        # 5. Execute parallel download with Flood Shield
        try:
            await download_media_fast(
                client=client,
                message=task.media_obj,
                dest_path=str(dest_path),
                progress_callback=progress_cb,
                connections=workers,
            )

            # Mark completed
            duration = max(1.0, time.time() - start_time)
            avg_speed_mbps = (task.total_bytes / (1024 * 1024)) / duration
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.downloaded_bytes = task.total_bytes
            task.speed_bps = 0
            task.eta_seconds = 0
            queue_mgr._notify(task)

            # Send Telegram Bot notification if configured
            if config.get("notify_bot", True) and task.chat_id:
                await bot_mgr.notify_download_complete(
                    chat_id=task.chat_id,
                    filename=task.title,
                    formatted_size=task.formatted_size,
                    duration_sec=duration,
                    speed_mbps=avg_speed_mbps,
                )

        except errors.FloodWaitError as fwe:
            # Smart Flood Shield: auto step-down and schedule retry
            task.status = TaskStatus.PAUSED
            task.error_message = f"Rate limited by Telegram. Cooldown: {fwe.seconds}s"
            new_workers = max(4, workers // 2)
            config.set("workers", new_workers)
            queue_mgr._notify(task)

        except asyncio.CancelledError:
            task.status = TaskStatus.PAUSED
            task.error_message = "Paused"
            queue_mgr._notify(task)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            queue_mgr._notify(task)

        finally:
            self._current_task = None


download_engine = DownloadEngine()
