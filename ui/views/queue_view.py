"""Download Manager View displaying queued, active, and completed downloads."""

from __future__ import annotations

import flet as ft
from typing import Callable, List, Optional

from queue_manager import DownloadTask, TaskStatus, queue_mgr
from ui.components.media_card import MediaCard
from ui.components.speed_hud import SpeedHUD
from ui.theme import AppColors


class QueueView(ft.Container):
    """View managing active downloads, queued items, and completed history."""

    def __init__(
        self,
        speed_hud: SpeedHUD,
        on_download_task: Optional[Callable[[DownloadTask], None]] = None,
        on_download_all: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.speed_hud = speed_hud
        self.on_download_task = on_download_task
        self.on_download_all = on_download_all

        self.expand = True
        self.padding = ft.padding.all(20)

        # Filter states
        self.current_filter = "ALL"  # "ALL", "QUEUED", "COMPLETED"

        # Action bar
        self.filter_buttons = ft.SegmentedButton(
            selected=["ALL"],
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="ALL", label=ft.Text("All Tasks")),
                ft.Segment(value="QUEUED", label=ft.Text("Ready")),
                ft.Segment(value="COMPLETED", label=ft.Text("Completed")),
            ],
            on_change=self._on_filter_changed,
        )

        self.download_all_btn = ft.FilledButton(
            text="Download All Ready",
            icon=ft.Icons.FLASH_ON,
            style=ft.ButtonStyle(
                bgcolor=AppColors.PRIMARY,
                color=AppColors.TEXT_WHITE,
            ),
            on_click=lambda _: self.on_download_all() if self.on_download_all else None,
        )

        self.clear_completed_btn = ft.OutlinedButton(
            text="Clear Finished",
            icon=ft.Icons.CLEANING_SERVICES,
            on_click=self._on_clear_completed,
        )

        # Task list column
        self.task_list_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self.empty_state = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.INBOX, size=48, color=AppColors.TEXT_MUTED),
                    ft.Text("Queue is empty", size=16, weight=ft.FontWeight.BOLD, color=AppColors.TEXT_MUTED),
                    ft.Text(
                        "Forward files to your Telegram Bot or select a channel in Explorer.",
                        size=13,
                        color=AppColors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.all(40),
        )

        self.content = ft.Column(
            [
                self.speed_hud,
                ft.Divider(height=10, color="transparent"),
                ft.Row(
                    [
                        self.filter_buttons,
                        ft.Row([self.download_all_btn, self.clear_completed_btn], spacing=10),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.task_list_column,
            ],
            spacing=14,
            expand=True,
        )

        self.refresh_tasks()

    def _on_filter_changed(self, e) -> None:
        selected = list(e.control.selected)
        if selected:
            self.current_filter = selected[0]
            self.refresh_tasks()

    def _on_clear_completed(self, _) -> None:
        queue_mgr.clear_completed()
        self.refresh_tasks()

    def _remove_task(self, task: DownloadTask) -> None:
        queue_mgr.remove_task(task.id)
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        """Re-render the task list based on current filter."""
        tasks = queue_mgr.tasks

        if self.current_filter == "QUEUED":
            tasks = [t for t in tasks if t.status in (TaskStatus.QUEUED, TaskStatus.DOWNLOADING, TaskStatus.PAUSED)]
        elif self.current_filter == "COMPLETED":
            tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]

        self.task_list_column.controls.clear()

        if not tasks:
            self.task_list_column.controls.append(self.empty_state)
        else:
            for task in reversed(tasks):
                card = MediaCard(
                    task=task,
                    on_download=self.on_download_task,
                    on_remove=self._remove_task,
                )
                self.task_list_column.controls.append(card)

        try:
            self.update()
        except Exception:
            pass
