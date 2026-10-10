"""QR Code Modal Dialog for Telegram Device Linking."""

from __future__ import annotations

import flet as ft
from typing import Callable, Optional

from ui.theme import AppColors


class QRLoginDialog(ft.AlertDialog):
    """Modal dialog displaying dynamic Telegram QR Code for device linking."""

    def __init__(
        self,
        on_submit_2fa: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_submit_2fa = on_submit_2fa
        self.on_cancel = on_cancel

        self.modal = True
        self.title = ft.Row(
            [
                ft.Icon(ft.Icons.QR_CODE_2, color=AppColors.PRIMARY, size=24),
                ft.Text("Link Telegram Account", size=18, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        )

        self.qr_image = ft.Image(
            src="",
            width=220,
            height=220,
            fit="contain",
            border_radius=10,
        )

        self.status_text = ft.Text(
            "Generating QR code...",
            size=12,
            color=AppColors.TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
        )

        self.password_field = ft.TextField(
            label="2FA Cloud Password",
            password=True,
            can_reveal_password=True,
            visible=False,
            width=260,
        )

        self.submit_2fa_btn = ft.FilledButton(
            text="Verify Password",
            visible=False,
            on_click=lambda _: self._on_password_click(),
        )

        self.content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "1. Open Telegram on your phone\n"
                        "2. Go to Settings ➔ Devices\n"
                        "3. Tap 'Link Desktop Device' and scan below",
                        size=13,
                        color=AppColors.TEXT_MUTED,
                    ),
                    ft.Container(
                        content=self.qr_image,
                        alignment=ft.alignment.center,
                        padding=ft.padding.all(10),
                        bgcolor="#FFFFFF",
                        border_radius=12,
                    ),
                    self.status_text,
                    self.password_field,
                    self.submit_2fa_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
            ),
            width=320,
        )

        self.actions = [
            ft.TextButton(
                "Cancel",
                on_click=lambda _: self._on_cancel_click(),
            )
        ]

    def set_qr(self, base64_src: str) -> None:
        """Update QR code image."""
        self.qr_image.src = base64_src
        self.status_text.value = "Scan with your phone to log in instantly"
        self.update()

    def show_2fa_prompt(self) -> None:
        """Reveal 2FA password field."""
        self.status_text.value = "Two-step verification required. Enter password:"
        self.password_field.visible = True
        self.submit_2fa_btn.visible = True
        self.update()

    def _on_password_click(self) -> None:
        pwd = self.password_field.value or ""
        if self.on_submit_2fa:
            self.on_submit_2fa(pwd)

    def _on_cancel_click(self) -> None:
        self.open = False
        if self.on_cancel:
            self.on_cancel()
        self.update()
