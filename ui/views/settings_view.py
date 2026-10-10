"""Settings & Preferences View for storage, workers, and drive detection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Optional

import flet as ft

from auth_manager import auth_mgr
from config import config
from storage_manager import StorageDrive, storage_mgr
from ui.theme import AppColors


class SettingsView(ft.Container):
    """View managing download paths, external drives, worker concurrency, and themes."""

    def __init__(
        self,
        on_settings_saved: Optional[Callable[[], None]] = None,
        on_logout: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_settings_saved = on_settings_saved
        self.on_logout = on_logout

        self.expand = True
        self.padding = ft.padding.all(20)

        # File picker for folder selection
        self.folder_picker = ft.FilePicker(on_result=self._on_folder_picked)

        # Storage directory controls
        self.path_input = ft.TextField(
            label="Download Destination Directory",
            value=str(config.download_dir),
            expand=True,
            read_only=True,
        )

        self.browse_btn = ft.OutlinedButton(
            text="Browse...",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda _: self.folder_picker.get_directory_path(dialog_title="Select Download Folder"),
        )

        # Template dropdown
        self.template_dropdown = ft.Dropdown(
            label="Subfolder Organization Rule",
            value=config.get("organization_template", "channel"),
            options=[
                ft.DropdownOption("channel", "Organize by Channel: <Folder>/<Channel_Name>/<File>"),
                ft.DropdownOption("media_type", "Organize by Media Type: <Folder>/<Videos|Audio|Docs>/<File>"),
                ft.DropdownOption("flat", "Flat Directory: <Folder>/<File>"),
            ],
            on_change=self._on_template_changed,
        )

        # External Drives Row
        self.drives_column = ft.Column(spacing=8)

        # Workers Slider (Concurrency)
        self.workers_slider = ft.Slider(
            min=4,
            max=32,
            divisions=7,
            value=float(config.workers),
            label="{value} workers",
            on_change=self._on_workers_changed,
        )
        self.workers_label = ft.Text(f"{config.workers} MTProto Workers (Recommended: 16)", size=13, weight=ft.FontWeight.W_500)

        # Bandwidth limiter slider
        self.bandwidth_slider = ft.Slider(
            min=0,
            max=50,
            divisions=10,
            value=float(config.get("bandwidth_limit_mb", 0)),
            label="{value} MB/s",
            on_change=self._on_bandwidth_changed,
        )
        self.bandwidth_label = ft.Text(
            "Unlimited Bandwidth" if config.get("bandwidth_limit_mb", 0) == 0 else f"{config.get('bandwidth_limit_mb')} MB/s Cap",
            size=13,
            weight=ft.FontWeight.W_500,
        )

        # Logout button
        self.logout_btn = ft.OutlinedButton(
            text="Unlink Telegram Account",
            icon=ft.Icons.LOGOUT,
            style=ft.ButtonStyle(color=AppColors.ERROR, side=ft.BorderSide(1, AppColors.ERROR)),
            on_click=self._on_logout_click,
        )

        # Content Layout
        self.content = ft.Column(
            [
                ft.Text("⚙️ Application Preferences", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1, color=AppColors.BORDER_DARK),
                # Storage Section
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("📁 Storage & Organization", size=15, weight=ft.FontWeight.BOLD),
                            ft.Row([self.path_input, self.browse_btn], spacing=10),
                            self.template_dropdown,
                            ft.Divider(height=5, color="transparent"),
                            ft.Text("Detected USB Drives & Volumes:", size=13, color=AppColors.TEXT_MUTED),
                            self.drives_column,
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=AppColors.SURFACE_DARK,
                    border_radius=12,
                    border=ft.border.all(1, AppColors.BORDER_DARK),
                ),
                # Performance Section
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("⚡ Speed & Concurrency Tuning", size=15, weight=ft.FontWeight.BOLD),
                            ft.Text("Parallel MTProto Connections:", size=13, color=AppColors.TEXT_MUTED),
                            self.workers_slider,
                            self.workers_label,
                            ft.Divider(height=5, color="transparent"),
                            ft.Text("Bandwidth Limiter (0 = Unlimited):", size=13, color=AppColors.TEXT_MUTED),
                            self.bandwidth_slider,
                            self.bandwidth_label,
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=AppColors.SURFACE_DARK,
                    border_radius=12,
                    border=ft.border.all(1, AppColors.BORDER_DARK),
                ),
                # Account Section
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("👤 Account Security", size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Disconnect your Telegram account and clear session tokens safely.",
                                size=12,
                                color=AppColors.TEXT_MUTED,
                            ),
                            self.logout_btn,
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=AppColors.SURFACE_DARK,
                    border_radius=12,
                    border=ft.border.all(1, AppColors.BORDER_DARK),
                ),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.refresh_drives()

    def refresh_drives(self) -> None:
        """Detect and display system and USB storage drives."""
        self.drives_column.controls.clear()
        drives = storage_mgr.get_available_drives()

        for drive in drives:
            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.USB if drive.is_removable else ft.Icons.HARD_DRIVE, color=AppColors.PRIMARY),
                                ft.Column(
                                    [
                                        ft.Text(drive.name, size=13, weight=ft.FontWeight.BOLD),
                                        ft.Text(f"{drive.path} • {drive.free_formatted}", size=11, color=AppColors.TEXT_MUTED),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.FilledButton(
                            text="Select",
                            height=32,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                            on_click=lambda _, d=drive: self._set_active_drive(d),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.all(10),
                bgcolor=AppColors.CARD_DARK,
                border_radius=8,
            )
            self.drives_column.controls.append(row)

    def _set_active_drive(self, drive: StorageDrive) -> None:
        target = Path(drive.path) / "TelegramDownloader" if drive.is_removable else Path(drive.path)
        config.set("download_dir", str(target))
        self.path_input.value = str(target)
        if self.on_settings_saved:
            self.on_settings_saved()
        self.update()

    def _on_folder_picked(self, e: ft.FilePickerResultEvent) -> None:
        if e.path:
            config.set("download_dir", e.path)
            self.path_input.value = e.path
            if self.on_settings_saved:
                self.on_settings_saved()
            self.update()

    def _on_template_changed(self, e) -> None:
        config.set("organization_template", e.control.value)

    def _on_workers_changed(self, e) -> None:
        val = int(e.control.value)
        config.set("workers", val)
        self.workers_label.value = f"{val} MTProto Workers (Recommended: 16)"
        self.update()

    def _on_bandwidth_changed(self, e) -> None:
        val = int(e.control.value)
        config.set("bandwidth_limit_mb", val)
        self.bandwidth_label.value = "Unlimited Bandwidth" if val == 0 else f"{val} MB/s Cap"
        self.update()

    def _on_logout_click(self, _) -> None:
        if self.on_logout:
            self.on_logout()
