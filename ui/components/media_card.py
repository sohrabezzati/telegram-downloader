"""Media Card component representing an individual downloadable item."""

from __future__ import annotations

import flet as ft
from typing import Callable, Optional

from queue_manager import DownloadTask, TaskStatus
from ui.theme import AppColors


class MediaCard(ft.Container):
    """Visual card for a downloadable file with status badge and 1-click action."""

    def __init__(
        self,
        task: DownloadTask,
        on_download: Optional[Callable[[DownloadTask], None]] = None,
        on_remove: Optional[Callable[[DownloadTask], None]] = None,
    ):
        super().__init__()
        self.task = task
        self.on_download = on_download
        self.on_remove = on_remove

        self.padding = ft.padding.all(12)
        self.bgcolor = AppColors.CARD_DARK
        self.border_radius = 10
        self.border = ft.border.all(1, AppColors.BORDER_DARK)

        self._build_card()

    def _get_icon(self) -> ft.Icon:
        ext = self.task.title.lower().split(".")[-1] if "." in self.task.title else ""
        if ext in ("mp4", "mkv", "avi", "mov", "webm"):
            return ft.Icon(ft.Icons.MOVIE_OUTLINED, color=AppColors.PRIMARY, size=28)
        elif ext in ("mp3", "flac", "wav", "m4a", "ogg"):
            return ft.Icon(ft.Icons.MUSIC_NOTE, color="#B388FF", size=28)
        elif ext in ("jpg", "jpeg", "png", "webp", "gif"):
            return ft.Icon(ft.Icons.IMAGE_OUTLINED, color="#00E5FF", size=28)
        elif ext in ("zip", "rar", "7z", "tar", "gz"):
            return ft.Icon(ft.Icons.FOLDER_ZIP_OUTLINED, color=AppColors.WARNING, size=28)
        return ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color="#B0BEC5", size=28)

    def _get_status_badge(self) -> ft.Container:
        status = self.task.status
        if status == TaskStatus.COMPLETED:
            color = AppColors.SUCCESS
            text = "✓ Downloaded"
        elif status == TaskStatus.DOWNLOADING:
            color = AppColors.INFO
            text = f"⬇️ {self.task.progress_percentage}%"
        elif status == TaskStatus.PAUSED:
            color = AppColors.WARNING
            text = "⏸️ Paused"
        elif status == TaskStatus.FAILED:
            color = AppColors.ERROR
            text = "⚠️ Failed"
        else:
            color = AppColors.PRIMARY
            text = "⏳ Ready"

        return ft.Container(
            content=ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=color),
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            border_radius=6,
            bgcolor=f"{color}22",  # Subtle tint
        )

    def _build_card(self) -> None:
        action_btn = None
        if self.task.status == TaskStatus.COMPLETED:
            action_btn = ft.IconButton(
                icon=ft.Icons.CHECK_CIRCLE,
                icon_color=AppColors.SUCCESS,
                tooltip="Completed",
                disabled=True,
            )
        elif self.task.status == TaskStatus.DOWNLOADING:
            action_btn = ft.ProgressRing(width=20, height=20, stroke_width=2, color=AppColors.PRIMARY)
        else:
            action_btn = ft.FilledButton(
                text="Download",
                icon=ft.Icons.FLASH_ON,
                style=ft.ButtonStyle(
                    bgcolor=AppColors.PRIMARY,
                    color=AppColors.TEXT_WHITE,
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=lambda _: self.on_download(self.task) if self.on_download else None,
            )

        delete_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=18,
            icon_color=AppColors.TEXT_MUTED,
            tooltip="Remove from queue",
            on_click=lambda _: self.on_remove(self.task) if self.on_remove else None,
        )

        self.content = ft.Row(
            [
                ft.Row(
                    [
                        self._get_icon(),
                        ft.Column(
                            [
                                ft.Text(
                                    self.task.title,
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppColors.TEXT_WHITE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    width=400,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(self.task.formatted_size, size=12, color=AppColors.TEXT_MUTED),
                                        ft.Text("•", size=12, color=AppColors.TEXT_MUTED),
                                        ft.Text(self.task.channel_title or "Direct", size=12, color=AppColors.TEXT_MUTED),
                                        self._get_status_badge(),
                                    ],
                                    spacing=6,
                                ),
                            ],
                            spacing=3,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Row([action_btn, delete_btn], spacing=6),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
