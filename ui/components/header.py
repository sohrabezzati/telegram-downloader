"""Header component displaying app identity, account profile badge, bot status, and storage HUD."""

from __future__ import annotations

import flet as ft
from typing import Callable, Optional

from ui.theme import AppColors


class AppHeader(ft.Container):
    """Top bar containing brand title, account badge, bot status, and drive HUD."""

    def __init__(
        self,
        on_account_click: Optional[Callable[[], None]] = None,
        on_bot_click: Optional[Callable[[], None]] = None,
        on_drive_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_account_click = on_account_click
        self.on_bot_click = on_bot_click
        self.on_drive_click = on_drive_click

        # Dynamic state controls
        self.account_btn = ft.OutlinedButton(
            text="Link Account (QR)",
            icon=ft.Icons.QR_CODE_SCANNER,
            on_click=lambda _: self.on_account_click() if self.on_account_click else None,
            style=ft.ButtonStyle(
                color=AppColors.PRIMARY,
                side=ft.BorderSide(1, AppColors.PRIMARY),
            ),
        )

        self.bot_chip = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=16, color=AppColors.TEXT_MUTED),
                    ft.Text("Bot Off", size=12, color=AppColors.TEXT_MUTED),
                ],
                spacing=5,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=15,
            bgcolor=AppColors.CARD_DARK,
            on_click=lambda _: self.on_bot_click() if self.on_bot_click else None,
            ink=True,
        )

        self.storage_chip = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.STORAGE, size=16, color=AppColors.PRIMARY),
                    ft.Text("Storage: Checking...", size=12, color=AppColors.TEXT_WHITE),
                ],
                spacing=5,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=15,
            bgcolor=AppColors.CARD_DARK,
            on_click=lambda _: self.on_drive_click() if self.on_drive_click else None,
            ink=True,
        )

        self.padding = ft.padding.symmetric(horizontal=20, vertical=12)
        self.bgcolor = AppColors.SURFACE_DARK
        self.border = ft.border.only(bottom=ft.BorderSide(1, AppColors.BORDER_DARK))

        self.content = ft.Row(
            [
                # Left: Brand identity
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FLASH_ON, color=AppColors.PRIMARY, size=28),
                        ft.Text("TG Downloader", size=20, weight=ft.FontWeight.BOLD, color=AppColors.TEXT_WHITE),
                        ft.Container(
                            content=ft.Text("PRO", size=10, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                            bgcolor="#1E384D",
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                # Right: Status HUD items
                ft.Row(
                    [
                        self.storage_chip,
                        self.bot_chip,
                        self.account_btn,
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def update_account(self, name: Optional[str] = None, username: Optional[str] = None) -> None:
        """Update account button when user logs in or out."""
        if name:
            display = f"👤 {name}"
            if username:
                display += f" (@{username})"
            self.account_btn.text = display
            self.account_btn.icon = ft.Icons.ACCOUNT_CIRCLE
            self.account_btn.style.color = AppColors.SUCCESS
            self.account_btn.style.side = ft.BorderSide(1, AppColors.SUCCESS)
        else:
            self.account_btn.text = "Link Account (QR)"
            self.account_btn.icon = ft.Icons.QR_CODE_SCANNER
            self.account_btn.style.color = AppColors.PRIMARY
            self.account_btn.style.side = ft.BorderSide(1, AppColors.PRIMARY)
        try:
            self.update()
        except Exception:
            pass

    def update_bot_status(self, is_running: bool, bot_username: Optional[str] = None) -> None:
        """Update the bot status chip."""
        if is_running:
            label = f"@{bot_username}" if bot_username else "Bot Active"
            self.bot_chip.content = ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY, size=16, color=AppColors.SUCCESS),
                    ft.Text(label, size=12, color=AppColors.SUCCESS, weight=ft.FontWeight.W_500),
                ],
                spacing=5,
            )
        else:
            self.bot_chip.content = ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=16, color=AppColors.TEXT_MUTED),
                    ft.Text("Bot Off", size=12, color=AppColors.TEXT_MUTED),
                ],
                spacing=5,
            )
        try:
            self.update()
        except Exception:
            pass

    def update_storage(self, free_text: str) -> None:
        """Update drive free space label."""
        self.storage_chip.content = ft.Row(
            [
                ft.Icon(ft.Icons.STORAGE, size=16, color=AppColors.PRIMARY),
                ft.Text(f"Disk: {free_text}", size=12, color=AppColors.TEXT_WHITE),
            ],
            spacing=5,
        )
        try:
            self.update()
        except Exception:
            pass
