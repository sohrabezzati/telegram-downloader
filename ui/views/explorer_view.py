"""Channel and Chat Explorer View for browsing media directly within Telegram."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import flet as ft
from telethon.tl.types import (
    Channel,
    Chat,
    DocumentAttributeFilename,
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
)

from auth_manager import auth_mgr
from config import config
from queue_manager import DownloadTask, TaskStatus, queue_mgr
from storage_manager import storage_mgr
from ui.theme import AppColors


class ExplorerView(ft.Container):
    """View allowing direct browsing of joined channels, groups, and Saved Messages."""

    def __init__(self, on_queue_updated: Optional[Callable[[], None]] = None):
        super().__init__()
        self.on_queue_updated = on_queue_updated

        self.expand = True
        self.padding = ft.padding.all(20)

        self.dialogs: List[Any] = []
        self.selected_dialog = None
        self.channel_messages: List[Any] = []

        # Left Column: Chat selector
        self.chat_search = ft.TextField(
            hint_text="Search channels & chats...",
            prefix_icon=ft.Icons.SEARCH,
            height=40,
            on_change=self._on_search_chats,
        )

        self.chat_list_column = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        # Direct Link Resolver bar
        self.link_input = ft.TextField(
            hint_text="Paste Telegram link (https://t.me/channel or t.me/channel/123)...",
            expand=True,
            height=40,
        )
        self.resolve_btn = ft.FilledButton(
            text="Load Link",
            icon=ft.Icons.TRAVEL_EXPLORE,
            on_click=self._on_resolve_link,
        )

        # Right Column: Media Browser
        self.channel_title_text = ft.Text("Select a channel to browse files", size=18, weight=ft.FontWeight.BOLD)
        self.download_all_btn = ft.FilledButton(
            text="Download All Pending",
            icon=ft.Icons.FLASH_ON,
            visible=False,
            style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color=AppColors.TEXT_WHITE),
            on_click=self._on_download_all_pending,
        )

        self.media_list_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        self.loading_ring = ft.ProgressRing(width=24, height=24, stroke_width=2, visible=False)

        # Build layout
        self.content = ft.Column(
            [
                # Top Link Bar
                ft.Row([self.link_input, self.resolve_btn], spacing=10),
                ft.Divider(height=1, color=AppColors.BORDER_DARK),
                # Main 2-column layout
                ft.Row(
                    [
                        # Left chat explorer
                        ft.Container(
                            content=ft.Column(
                                [
                                    self.chat_search,
                                    self.chat_list_column,
                                ],
                                spacing=10,
                                expand=True,
                            ),
                            width=280,
                            padding=ft.padding.all(12),
                            bgcolor=AppColors.SURFACE_DARK,
                            border_radius=12,
                            border=ft.border.all(1, AppColors.BORDER_DARK),
                        ),
                        # Right media viewer
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Row([self.channel_title_text, self.loading_ring], spacing=10),
                                            self.download_all_btn,
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    self.media_list_column,
                                ],
                                spacing=12,
                                expand=True,
                            ),
                            expand=True,
                            padding=ft.padding.all(16),
                            bgcolor=AppColors.SURFACE_DARK,
                            border_radius=12,
                            border=ft.border.all(1, AppColors.BORDER_DARK),
                        ),
                    ],
                    spacing=16,
                    expand=True,
                ),
            ],
            spacing=12,
            expand=True,
        )

    async def load_dialogs(self) -> None:
        """Fetch joined dialogs from Telegram client."""
        client = auth_mgr.get_client()
        if not client.is_connected() or not await auth_mgr.is_authorized():
            self.chat_list_column.controls = [
                ft.Text("Please link your Telegram account in the top bar to view channels.", color=AppColors.TEXT_MUTED)
            ]
            self.update()
            return

        self.loading_ring.visible = True
        self.update()

        try:
            dialogs = await client.get_dialogs(limit=50)
            self.dialogs = dialogs
            self._render_chat_list(dialogs)
        except Exception as e:
            self.chat_list_column.controls = [ft.Text(f"Failed to load chats: {e}", color=AppColors.ERROR)]
        finally:
            self.loading_ring.visible = False
            self.update()

    def _render_chat_list(self, dialogs: List[Any]) -> None:
        self.chat_list_column.controls.clear()
        for d in dialogs:
            title = d.name or "Unnamed Chat"
            is_saved = d.is_user and getattr(d.entity, "is_self", False)
            if is_saved:
                title = "📌 Saved Messages"

            tile = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.BOOKMARK if is_saved else (ft.Icons.CAMPAIGN if d.is_channel else ft.Icons.GROUP),
                            size=20,
                            color=AppColors.PRIMARY,
                        ),
                        ft.Text(title, size=13, weight=ft.FontWeight.W_500, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                border_radius=8,
                bgcolor=AppColors.CARD_DARK,
                ink=True,
                on_click=lambda _, dlg=d: asyncio.create_task(self._select_dialog(dlg)),
            )
            self.chat_list_column.controls.append(tile)
        self.update()

    def _on_search_chats(self, e) -> None:
        query = (e.control.value or "").strip().lower()
        if not query:
            self._render_chat_list(self.dialogs)
            return
        filtered = [d for d in self.dialogs if query in (d.name or "").lower()]
        self._render_chat_list(filtered)

    async def _select_dialog(self, dialog: Any) -> None:
        self.selected_dialog = dialog
        title = dialog.name or "Saved Messages"
        self.channel_title_text.value = f"Browsing: {title}"
        self.loading_ring.visible = True
        self.media_list_column.controls.clear()
        self.update()

        client = auth_mgr.get_client()
        try:
            # Fetch recent media messages
            messages = await client.get_messages(dialog.entity, limit=40)
            self.channel_messages = [m for m in messages if m.media is not None]
            self._render_media_list()
        except Exception as e:
            self.media_list_column.controls.append(ft.Text(f"Error loading messages: {e}", color=AppColors.ERROR))
        finally:
            self.loading_ring.visible = False
            self.download_all_btn.visible = len(self.channel_messages) > 0
            self.update()

    def _render_media_list(self) -> None:
        self.media_list_column.controls.clear()
        if not self.channel_messages:
            self.media_list_column.controls.append(
                ft.Text("No media files found in this channel.", color=AppColors.TEXT_MUTED)
            )
            return

        base_dir = config.download_dir
        channel_name = self.selected_dialog.name if self.selected_dialog else ""

        for msg in self.channel_messages:
            filename = "media_file"
            size = 0
            if isinstance(msg.media, MessageMediaDocument):
                doc = msg.media.document
                size = getattr(doc, "size", 0)
                if hasattr(doc, "attributes"):
                    for attr in doc.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            filename = attr.file_name
                            break
            elif isinstance(msg.media, MessageMediaPhoto):
                filename = f"photo_{msg.id}.jpg"
                size = 1024 * 500

            # Check duplicate status on disk
            dest = storage_mgr.resolve_destination(
                base_dir=base_dir,
                template=config.get("organization_template", "channel"),
                filename=filename,
                channel_title=channel_name,
            )
            file_status = storage_mgr.inspect_file_status(dest, size)

            status_badge = ft.Container(
                content=ft.Text(
                    "✓ Downloaded" if file_status == "DOWNLOADED" else "⏳ Pending",
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.SUCCESS if file_status == "DOWNLOADED" else AppColors.WARNING,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                border_radius=6,
                bgcolor=f"{AppColors.SUCCESS if file_status == 'DOWNLOADED' else AppColors.WARNING}22",
            )

            download_action_btn = ft.FilledButton(
                text="Download",
                icon=ft.Icons.FLASH_ON,
                disabled=file_status == "DOWNLOADED",
                style=ft.ButtonStyle(
                    bgcolor=AppColors.PRIMARY if file_status != "DOWNLOADED" else AppColors.BORDER_DARK,
                    color=AppColors.TEXT_WHITE,
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=lambda _, m=msg, f=filename, s=size: self._queue_single_file(m, f, s),
            )

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.MOVIE if "mp4" in filename.lower() else ft.Icons.DESCRIPTION, color=AppColors.PRIMARY),
                                ft.Column(
                                    [
                                        ft.Text(filename, size=13, weight=ft.FontWeight.BOLD, max_lines=1, width=350),
                                        ft.Row([ft.Text(f"{size / (1024*1024):.1f} MB", size=11, color=AppColors.TEXT_MUTED), status_badge], spacing=8),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=10,
                        ),
                        download_action_btn,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.all(10),
                bgcolor=AppColors.CARD_DARK,
                border_radius=8,
            )
            self.media_list_column.controls.append(row)

    def _queue_single_file(self, msg: Any, filename: str, size: int) -> None:
        task = DownloadTask(
            title=filename,
            total_bytes=size,
            source="CHANNEL_EXPLORER",
            channel_title=self.selected_dialog.name if self.selected_dialog else "Channel",
            chat_id=msg.chat_id,
            message_id=msg.id,
            media_obj=msg,
            status=TaskStatus.QUEUED,
        )
        queue_mgr.add_task(task)
        if self.on_queue_updated:
            self.on_queue_updated()

    def _on_download_all_pending(self, _) -> None:
        base_dir = config.download_dir
        channel_name = self.selected_dialog.name if self.selected_dialog else ""

        for msg in self.channel_messages:
            filename = "media_file"
            size = 0
            if isinstance(msg.media, MessageMediaDocument):
                doc = msg.media.document
                size = getattr(doc, "size", 0)
                if hasattr(doc, "attributes"):
                    for attr in doc.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            filename = attr.file_name
                            break

            dest = storage_mgr.resolve_destination(
                base_dir=base_dir,
                template=config.get("organization_template", "channel"),
                filename=filename,
                channel_title=channel_name,
            )
            if storage_mgr.inspect_file_status(dest, size) != "DOWNLOADED":
                self._queue_single_file(msg, filename, size)

        if self.on_queue_updated:
            self.on_queue_updated()

    async def _on_resolve_link(self, _) -> None:
        url = (self.link_input.value or "").strip()
        if not url:
            return

        client = auth_mgr.get_client()
        self.loading_ring.visible = True
        self.update()

        try:
            entity = await client.get_entity(url)
            self.channel_title_text.value = f"Browsing: {getattr(entity, 'title', url)}"
            messages = await client.get_messages(entity, limit=40)
            self.channel_messages = [m for m in messages if m.media is not None]
            self._render_media_list()
        except Exception as e:
            self.media_list_column.controls = [ft.Text(f"Failed to resolve link: {e}", color=AppColors.ERROR)]
        finally:
            self.loading_ring.visible = False
            self.update()
