"""Bot Forwarding Center View for managing Telegram Bot automation and access control."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import flet as ft

from bot_manager import bot_mgr
from config import config
from ui.theme import AppColors


class BotView(ft.Container):
    """View managing Telegram Bot token, forwarding rules, whitelists, and automation."""

    def __init__(self, on_bot_state_changed: Optional[Callable[[], None]] = None):
        super().__init__()
        self.on_bot_state_changed = on_bot_state_changed

        self.expand = True
        self.padding = ft.padding.all(20)

        # Token input
        self.token_input = ft.TextField(
            label="Telegram Bot Token",
            hint_text="Paste token from @BotFather (e.g. 123456:ABC-DEF...)",
            value=config.bot_token,
            password=True,
            can_reveal_password=True,
            expand=True,
        )

        self.bot_toggle_btn = ft.FilledButton(
            text="Start Bot" if not bot_mgr.is_running else "Stop Bot",
            icon=ft.Icons.PLAY_ARROW if not bot_mgr.is_running else ft.Icons.STOP,
            style=ft.ButtonStyle(
                bgcolor=AppColors.PRIMARY if not bot_mgr.is_running else AppColors.ERROR,
                color=AppColors.TEXT_WHITE,
            ),
            on_click=self._on_toggle_bot,
        )

        self.status_banner = ft.Text(
            "Bot is currently inactive." if not bot_mgr.is_running else f"Bot is active: @{getattr(bot_mgr.bot_me, 'username', 'bot')}",
            color=AppColors.TEXT_MUTED if not bot_mgr.is_running else AppColors.SUCCESS,
            weight=ft.FontWeight.W_500,
        )

        # Automation switches
        self.auto_download_switch = ft.Switch(
            label="Auto-Download: Immediately download forwarded files at 16x speed",
            value=config.get("bot_auto_download", False),
            on_change=self._on_auto_download_changed,
        )

        self.notify_switch = ft.Switch(
            label="Telegram Receipt: Send message back to user in Telegram when download finishes",
            value=config.get("notify_bot", True),
            on_change=self._on_notify_changed,
        )

        # Whitelist manager
        self.whitelist_input = ft.TextField(
            label="Allowed Telegram User ID",
            hint_text="e.g. 123456789",
            width=240,
        )
        self.add_whitelist_btn = ft.OutlinedButton(
            text="Add to Whitelist",
            icon=ft.Icons.PERSON_ADD,
            on_click=self._on_add_whitelist,
        )
        self.whitelist_chips = ft.Row(wrap=True, spacing=8)
        self._render_whitelist_chips()

        # Layout
        self.content = ft.Column(
            [
                ft.Text("🤖 Telegram Bot Forwarding Center", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Forward any video, audio, or document to your personal Telegram Bot.\n"
                    "It will automatically appear in your Downloader App ready for 1-click download at maximum speed.",
                    size=13,
                    color=AppColors.TEXT_MUTED,
                ),
                ft.Divider(height=1, color=AppColors.BORDER_DARK),
                # Bot Connection Card
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Bot Authentication", size=15, weight=ft.FontWeight.BOLD),
                            ft.Row([self.token_input, self.bot_toggle_btn], spacing=10),
                            self.status_banner,
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=AppColors.SURFACE_DARK,
                    border_radius=12,
                    border=ft.border.all(1, AppColors.BORDER_DARK),
                ),
                # Automation Settings Card
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Automation Rules", size=15, weight=ft.FontWeight.BOLD),
                            self.auto_download_switch,
                            self.notify_switch,
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.all(16),
                    bgcolor=AppColors.SURFACE_DARK,
                    border_radius=12,
                    border=ft.border.all(1, AppColors.BORDER_DARK),
                ),
                # Whitelist Security Card
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Security & User Whitelist", size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Leave empty to allow only yourself or enter specific Telegram IDs to restrict access.",
                                size=12,
                                color=AppColors.TEXT_MUTED,
                            ),
                            ft.Row([self.whitelist_input, self.add_whitelist_btn], spacing=10),
                            self.whitelist_chips,
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

    def _render_whitelist_chips(self) -> None:
        self.whitelist_chips.controls.clear()
        whitelist = config.bot_whitelist
        if not whitelist:
            self.whitelist_chips.controls.append(
                ft.Text("Whitelist is empty (Open to authorized bot users)", size=12, color=AppColors.TEXT_MUTED)
            )
            return

        for uid in whitelist:
            chip = ft.Chip(
                label=ft.Text(f"ID: {uid}"),
                on_delete=lambda _, u=uid: self._on_delete_whitelist(u),
            )
            self.whitelist_chips.controls.append(chip)

    def _on_add_whitelist(self, _) -> None:
        val = (self.whitelist_input.value or "").strip()
        if val.isdigit():
            config.add_whitelist_user(int(val))
            self.whitelist_input.value = ""
            self._render_whitelist_chips()
            self.update()

    def _on_delete_whitelist(self, uid: int) -> None:
        wl = [u for u in config.bot_whitelist if u != uid]
        config.set("bot_whitelist", wl)
        self._render_whitelist_chips()
        self.update()

    def _on_auto_download_changed(self, e) -> None:
        config.set("bot_auto_download", e.control.value)

    def _on_notify_changed(self, e) -> None:
        config.set("notify_bot", e.control.value)

    def _on_toggle_bot(self, _) -> None:
        token = (self.token_input.value or "").strip()
        config.set("bot_token", token)

        if bot_mgr.is_running:
            asyncio.create_task(self._stop_bot_async())
        else:
            asyncio.create_task(self._start_bot_async(token))

    async def _start_bot_async(self, token: str) -> None:
        self.status_banner.value = "Starting bot..."
        self.status_banner.color = AppColors.WARNING
        self.update()

        success = await bot_mgr.start(token)
        if success:
            self.bot_toggle_btn.text = "Stop Bot"
            self.bot_toggle_btn.icon = ft.Icons.STOP
            self.bot_toggle_btn.style.bgcolor = AppColors.ERROR
            username = getattr(bot_mgr.bot_me, "username", "bot")
            self.status_banner.value = f"Bot is online: @{username}"
            self.status_banner.color = AppColors.SUCCESS
        else:
            self.status_banner.value = "Failed to start bot. Check bot token from @BotFather."
            self.status_banner.color = AppColors.ERROR

        if self.on_bot_state_changed:
            self.on_bot_state_changed()
        self.update()

    async def _stop_bot_async(self) -> None:
        await bot_mgr.stop()
        self.bot_toggle_btn.text = "Start Bot"
        self.bot_toggle_btn.icon = ft.Icons.PLAY_ARROW
        self.bot_toggle_btn.style.bgcolor = AppColors.PRIMARY
        self.status_banner.value = "Bot is currently stopped."
        self.status_banner.color = AppColors.TEXT_MUTED

        if self.on_bot_state_changed:
            self.on_bot_state_changed()
        self.update()
