"""Live Telemetry HUD component displaying real-time speed (MB/s), ETA, and progress bar."""

from __future__ import annotations

import flet as ft
from typing import Callable, Optional

from queue_manager import DownloadTask, TaskStatus
from ui.theme import AppColors


class SpeedHUD(ft.Container):
    """Real-time download speed graph, ETA, and progress HUD."""

    def __init__(self, on_pause: Optional[Callable[[], None]] = None, on_cancel: Optional[Callable[[], None]] = None):
        super().__init__()
        self.on_pause = on_pause
        self.on_cancel = on_cancel

        # UI elements
        self.speed_text = ft.Text("0.0 MB/s", size=24, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)
        self.filename_text = ft.Text("No active download", size=14, weight=ft.FontWeight.W_500, color=AppColors.TEXT_WHITE)
        self.progress_bar = ft.ProgressBar(value=0.0, height=8, color=AppColors.PRIMARY, bgcolor=AppColors.SURFACE_DARK)
        self.stats_text = ft.Text("Ready • 16-Worker Engine Standby", size=12, color=AppColors.TEXT_MUTED)
        self.eta_text = ft.Text("--:--", size=13, weight=ft.FontWeight.W_500, color=AppColors.TEXT_WHITE)

        self.pause_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_CIRCLE_FILLED,
            icon_color=AppColors.WARNING,
            icon_size=28,
            visible=False,
            on_click=lambda _: self.on_pause() if self.on_pause else None,
        )

        self.cancel_btn = ft.IconButton(
            icon=ft.Icons.CANCEL,
            icon_color=AppColors.ERROR,
            icon_size=28,
            visible=False,
            on_click=lambda _: self.on_cancel() if self.on_cancel else None,
        )

        # Worker indicators (16 dots)
        self.worker_dots = ft.Row(
            [
                ft.Container(
                    width=8,
                    height=8,
                    border_radius=4,
                    bgcolor=AppColors.PRIMARY if i < 16 else AppColors.BORDER_DARK,
                    tooltip=f"MTProto Worker #{i+1}",
                )
                for i in range(16)
            ],
            spacing=4,
        )

        self.padding = ft.padding.all(16)
        self.bgcolor = AppColors.SURFACE_DARK
        self.border_radius = 12
        self.border = ft.border.all(1, AppColors.BORDER_DARK)

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.SPEED, color=AppColors.PRIMARY, size=24),
                                self.speed_text,
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Text("ETA:", size=12, color=AppColors.TEXT_MUTED),
                                        self.eta_text,
                                    ],
                                    spacing=4,
                                ),
                                self.pause_btn,
                                self.cancel_btn,
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.filename_text,
                self.progress_bar,
                ft.Row(
                    [
                        self.stats_text,
                        ft.Row(
                            [
                                ft.Text("Workers:", size=11, color=AppColors.TEXT_MUTED),
                                self.worker_dots,
                            ],
                            spacing=6,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
        )

    def update_task(self, task: Optional[DownloadTask]) -> None:
        """Update live HUD with current task telemetry."""
        if task is None or task.status != TaskStatus.DOWNLOADING:
            self.speed_text.value = "0.0 MB/s"
            self.filename_text.value = "Ready • 16-Worker Engine Standby"
            self.stats_text.value = "Select or forward a file to start high-speed download"
            self.eta_text.value = "--:--"
            self.progress_bar.value = 0.0
            self.pause_btn.visible = False
            self.cancel_btn.visible = False
        else:
            self.speed_text.value = f"{task.speed_mbps:.1f} MB/s"
            self.filename_text.value = task.title
            self.stats_text.value = f"{task.formatted_downloaded} / {task.formatted_size} ({task.progress_percentage}%)"
            self.eta_text.value = task.formatted_eta
            self.progress_bar.value = task.progress_fraction
            self.pause_btn.visible = True
            self.cancel_btn.visible = True

        try:
            self.update()
        except Exception:
            pass
