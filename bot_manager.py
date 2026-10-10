"""Telegram Bot Manager for High-Speed Downloader.

Runs an asynchronous bot listener that accepts forwarded media, verifies
user whitelists, queues files for 1-click high-speed downloading, and sends
completion notifications.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from config import config
from queue_manager import DownloadTask, TaskStatus, queue_mgr

load_dotenv()

TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")


class BotManager:
    """Manages the Telegram Bot listener, forwarding queue, and notifications."""

    def __init__(self, session_name: str = "bot_session"):
        self.session_name = session_name
        self.bot_client: Optional[TelegramClient] = None
        self.bot_me = None
        self._is_running = False
        self._on_message_callback: Optional[Callable[[DownloadTask], None]] = None

    @property
    def is_running(self) -> bool:
        return self._is_running and self.bot_client is not None and self.bot_client.is_connected()

    def set_callback(self, cb: Callable[[DownloadTask], None]) -> None:
        self._on_message_callback = cb

    async def start(self, token: Optional[str] = None) -> bool:
        """Start the bot client with the specified token."""
        bot_token = token or config.bot_token
        if not bot_token:
            print("[BotManager] No bot token configured.")
            return False

        if not TG_API_ID or not TG_API_HASH:
            print("[BotManager] TG_API_ID and TG_API_HASH are missing.")
            return False

        try:
            if self.bot_client is not None and self.bot_client.is_connected():
                await self.bot_client.disconnect()

            self.bot_client = TelegramClient(self.session_name, int(TG_API_ID), TG_API_HASH)
            await self.bot_client.start(bot_token=bot_token)
            self.bot_me = await self.bot_client.get_me()
            self._is_running = True

            # Register message event listener
            self.bot_client.add_event_handler(self._handle_new_message, events.NewMessage)
            print(f"[BotManager] Bot @{self.bot_me.username} started successfully.")
            return True
        except Exception as e:
            print(f"[BotManager] Failed to start bot: {e}")
            self._is_running = False
            return False

    async def stop(self) -> None:
        """Stop and disconnect the bot."""
        if self.bot_client is not None:
            try:
                await self.bot_client.disconnect()
            except Exception:
                pass
            self.bot_client = None
        self._is_running = False

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        """Handle incoming messages and forwarded media."""
        sender = await event.get_sender()
        sender_id = event.sender_id
        sender_name = getattr(sender, "first_name", "User") or "User"

        # Check whitelist if configured
        if not config.is_user_allowed(sender_id):
            await event.reply(
                f"⚠️ **Access Restricted**\n\n"
                f"Your Telegram ID is `{sender_id}`.\n"
                f"To use this bot, add your ID to the Whitelist in the Downloader App Settings."
            )
            return

        text = (event.raw_text or "").strip()

        # Handle commands
        if text.startswith("/start"):
            await event.reply(
                f"🚀 **Telegram High-Speed Downloader Bot**\n\n"
                f"Hello {sender_name}! I am connected to your Downloader App.\n\n"
                f"📥 **How to download anything:**\n"
                f"1. **Forward any file, video, or audio** from any channel or chat to me.\n"
                f"2. Or send any **public channel link** (`https://t.me/...`).\n"
                f"3. It will instantly appear in your Downloader App ready for 1-click 16x download!"
            )
            return

        # Check for media
        if event.message.media:
            filename = "media_file"
            size = 0

            if isinstance(event.message.media, MessageMediaDocument):
                doc = event.message.media.document
                size = getattr(doc, "size", 0)
                # Extract filename from attributes
                if hasattr(doc, "attributes"):
                    for attr in doc.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            filename = attr.file_name
                            break
                        elif isinstance(attr, DocumentAttributeVideo):
                            filename = "video.mp4"
                        elif isinstance(attr, DocumentAttributeAudio):
                            filename = f"{attr.performer or 'audio'} - {attr.title or 'track'}.mp3"

            elif isinstance(event.message.media, MessageMediaPhoto):
                filename = f"photo_{event.message.id}.jpg"
                size = 1024 * 500  # Estimate

            # Create download task
            task = DownloadTask(
                title=filename,
                total_bytes=size,
                source="BOT_FORWARD",
                channel_title=f"Forwarded ({sender_name})",
                chat_id=event.chat_id,
                message_id=event.message.id,
                media_obj=event.message,
                status=TaskStatus.QUEUED,
            )

            queue_mgr.add_task(task)

            # Reply to user
            await event.reply(
                f"✅ **Added to App Queue!**\n\n"
                f"📁 **File:** `{filename}`\n"
                f"📦 **Size:** `{task.formatted_size}`\n\n"
                f"⚡ Check your Downloader App to download at 16x speed!"
            )

            if self._on_message_callback:
                self._on_message_callback(task)

    async def notify_download_complete(
        self, chat_id: int, filename: str, formatted_size: str, duration_sec: float, speed_mbps: float
    ) -> None:
        """Send a receipt notification to user when download finishes."""
        if not self.is_running or not self.bot_client:
            return
        try:
            mins, secs = divmod(int(duration_sec), 60)
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            await self.bot_client.send_message(
                chat_id,
                f"🎉 **Download Finished!**\n\n"
                f"📁 `{filename}`\n"
                f"📦 Size: {formatted_size}\n"
                f"⚡ Time: {time_str} ({speed_mbps:.1f} MB/s)\n"
                f"💾 Saved to your storage folder."
            )
        except Exception as e:
            print(f"[BotManager] Failed to send completion notification: {e}")


bot_mgr = BotManager()
