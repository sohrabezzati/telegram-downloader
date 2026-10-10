"""QR Code Modal Dialog for Telegram Device Linking & 1-Tap Mobile Login."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional
import flet as ft

from ui.theme import AppColors

# 1x1 transparent PNG data URI to prevent Flet "A valid src value must be specified." error
TRANSPARENT_1X1_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class QRLoginDialog(ft.AlertDialog):
    """Modal dialog displaying dynamic Telegram QR Code for device linking and 1-tap mobile login."""

    def __init__(
        self,
        on_submit_2fa: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.on_submit_2fa = on_submit_2fa
        self.on_cancel = on_cancel
        self.raw_url: Optional[str] = None

        self.modal = True
        self.title = ft.Row(
            [
                ft.Icon(ft.Icons.QR_CODE_2, color=AppColors.PRIMARY, size=24),
                ft.Text("Link Telegram Account", size=18, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        )

        # -------------------------------------------------------------------
        # Mobile 1-Tap Fast Login Section (for same phone)
        # -------------------------------------------------------------------
        self.mobile_open_btn = ft.FilledButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.PHONE_ANDROID, size=18),
                    ft.Text("Open Telegram App (1-Tap Login)", weight=ft.FontWeight.BOLD, size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            visible=False,
            height=46,
            style=ft.ButtonStyle(
                bgcolor=AppColors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        self.link_field = ft.TextField(
            label="Direct Login Deep Link",
            value="",
            read_only=True,
            dense=True,
            text_size=11,
            visible=False,
            expand=True,
            prefix_icon=ft.Icons.LINK,
        )

        self.copy_btn = ft.IconButton(
            icon=ft.Icons.COPY,
            tooltip="Copy login link",
            visible=False,
            on_click=lambda _: self._on_copy_click(),
        )

        self.mobile_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TOUCH_APP, color=AppColors.PRIMARY, size=16),
                            ft.Text(
                                "Using this phone right now?",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=AppColors.TEXT_WHITE,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        "Tap below to switch to Telegram and approve in 1 tap:",
                        size=11,
                        color=AppColors.TEXT_MUTED,
                    ),
                    self.mobile_open_btn,
                    ft.Row(
                        [
                            self.link_field,
                            self.copy_btn,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=AppColors.CARD_DARK,
            padding=ft.padding.all(12),
            border_radius=10,
            border=ft.border.all(1, AppColors.BORDER_DARK),
        )

        # -------------------------------------------------------------------
        # QR Code Section (for PC / 2nd device camera scan)
        # -------------------------------------------------------------------
        self.qr_placeholder = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=36, height=36, stroke_width=3, color=AppColors.PRIMARY),
                    ft.Text("Generating secure QR code...", size=12, color=AppColors.TEXT_MUTED),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            width=220,
            height=220,
            alignment=ft.alignment.center,
        )

        self.qr_image = ft.Image(
            src=TRANSPARENT_1X1_PNG,
            width=220,
            height=220,
            fit="contain",
            border_radius=8,
            visible=False,
        )

        self.qr_box = ft.Container(
            content=ft.Stack(
                [
                    self.qr_placeholder,
                    self.qr_image,
                ],
                alignment=ft.alignment.center,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.all(10),
            bgcolor="#FFFFFF",
            border_radius=12,
            width=240,
            height=240,
        )

        self.status_text = ft.Text(
            "Connecting to Telegram servers...",
            size=12,
            color=AppColors.TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
        )

        # -------------------------------------------------------------------
        # 2FA Cloud Password Section
        # -------------------------------------------------------------------
        self.password_field = ft.TextField(
            label="2FA Cloud Password",
            password=True,
            can_reveal_password=True,
            visible=False,
            width=280,
        )

        self.submit_2fa_btn = ft.FilledButton(
            text="Verify 2FA Password",
            visible=False,
            on_click=lambda _: self._on_password_click(),
        )

        self.content = ft.Container(
            content=ft.Column(
                [
                    # 1-Tap Mobile Card
                    self.mobile_card,

                    # Divider
                    ft.Row(
                        [
                            ft.Divider(expand=True, color=AppColors.BORDER_DARK),
                            ft.Text("OR SCAN WITH CAMERA", size=10, color=AppColors.TEXT_MUTED, weight=ft.FontWeight.BOLD),
                            ft.Divider(expand=True, color=AppColors.BORDER_DARK),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),

                    # QR instructions & box
                    ft.Text(
                        "Settings ➔ Devices ➔ Link Desktop Device",
                        size=11,
                        color=AppColors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    self.qr_box,

                    self.status_text,
                    self.password_field,
                    self.submit_2fa_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=320,
        )

        self.actions = [
            ft.TextButton(
                "Cancel",
                on_click=lambda _: self._on_cancel_click(),
            )
        ]

    def set_qr(self, base64_src: str, raw_url: Optional[str] = None) -> None:
        """Update QR code image and 1-tap mobile deep link."""
        self.raw_url = raw_url

        # Show QR image and hide loader
        self.qr_image.src = base64_src
        self.qr_image.visible = True
        self.qr_placeholder.visible = False

        # Update 1-tap mobile button & link
        if raw_url:
            self.mobile_open_btn.url = raw_url
            self.mobile_open_btn.visible = True
            self.link_field.value = raw_url
            self.link_field.visible = True
            self.copy_btn.visible = True

        self.status_text.value = "Waiting for Telegram authorization..."
        self.update()

    def show_2fa_prompt(self) -> None:
        """Reveal 2FA password field."""
        self.status_text.value = "Two-Step Verification required. Enter your password:"
        self.password_field.visible = True
        self.submit_2fa_btn.visible = True
        self.update()

    def _on_copy_click(self) -> None:
        """Copy login link to clipboard."""
        if not self.raw_url:
            return

        async def _do_copy():
            copied = False
            if self.page:
                try:
                    for s in getattr(self.page, "services", []):
                        if isinstance(s, ft.Clipboard):
                            await s.set(self.raw_url)
                            copied = True
                            break
                except Exception:
                    pass
            self.status_text.value = "Link ready! Paste into Telegram to confirm." if not copied else "Link copied to clipboard!"
            self.update()

        asyncio.create_task(_do_copy())

    def _on_password_click(self) -> None:
        pwd = self.password_field.value or ""
        if self.on_submit_2fa:
            self.on_submit_2fa(pwd)

    def _on_cancel_click(self) -> None:
        self.open = False
        if self.on_cancel:
            self.on_cancel()
        self.update()
