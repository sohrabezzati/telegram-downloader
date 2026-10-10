"""Main Application Entry Point for Telegram High-Speed Downloader Pro.

Built with Flet (Python + Flutter), featuring Dual Login (Bot Forwarding + QR Code Device Link),
16-Worker Parallel MTProto Chunk Downloading, and Smart Storage Management.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

import flet as ft
from dotenv import load_dotenv

from auth_manager import UserProfile, auth_mgr
from bot_manager import bot_mgr
from config import config
from download_engine import download_engine
from queue_manager import DownloadTask, TaskStatus, queue_mgr
from storage_manager import storage_mgr
from ui.components.header import AppHeader
from ui.components.qr_dialog import QRLoginDialog
from ui.components.speed_hud import SpeedHUD
from ui.theme import AppColors, get_theme
from ui.views.bot_view import BotView
from ui.views.explorer_view import ExplorerView
from ui.views.queue_view import QueueView
from ui.views.settings_view import SettingsView

load_dotenv()


async def main(page: ft.Page) -> None:
    page.title = "Telegram High-Speed Downloader Pro"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = get_theme("dark")
    page.window.width = 1100
    page.window.height = 760
    page.window.min_width = 850
    page.window.min_height = 600
    page.padding = 0

    # Start the parallel download engine loop
    download_engine.start()

    # Create Speed HUD
    speed_hud = SpeedHUD(
        on_pause=lambda: queue_mgr.pause_task(download_engine._current_task.id) if download_engine._current_task else None,
        on_cancel=lambda: queue_mgr.cancel_task(download_engine._current_task.id) if download_engine._current_task else None,
    )

    # QR Dialog
    qr_dialog: Optional[QRLoginDialog] = None

    async def open_qr_dialog():
        nonlocal qr_dialog
        qr_dialog = QRLoginDialog(
            on_submit_2fa=on_submit_2fa,
            on_cancel=lambda: None,
        )
        page.overlay.append(qr_dialog)
        qr_dialog.open = True
        page.update()

        def on_qr_url(url: str, b64_img: str):
            if qr_dialog:
                qr_dialog.set_qr(b64_img)

        def on_success(profile: UserProfile):
            if qr_dialog:
                qr_dialog.open = False
            header.update_account(profile.display_name, profile.username)
            asyncio.create_task(explorer_view.load_dialogs())
            page.snack_bar = ft.SnackBar(ft.Text(f"Logged in as {profile.display_name}!"), bgcolor=AppColors.SUCCESS)
            page.snack_bar.open = True
            page.update()

        def on_password_needed(_):
            if qr_dialog:
                qr_dialog.show_2fa_prompt()

        def on_error(err: str):
            page.snack_bar = ft.SnackBar(ft.Text(f"Login error: {err}"), bgcolor=AppColors.ERROR)
            page.snack_bar.open = True
            page.update()

        asyncio.create_task(
            auth_mgr.start_qr_login(
                on_qr_url=on_qr_url,
                on_success=on_success,
                on_password_needed=on_password_needed,
                on_error=on_error,
            )
        )

    def on_submit_2fa(password: str):
        async def _verify():
            ok, err = await auth_mgr.submit_2fa_password(password)
            if ok:
                if qr_dialog:
                    qr_dialog.open = False
                if auth_mgr.current_user:
                    header.update_account(auth_mgr.current_user.display_name, auth_mgr.current_user.username)
                asyncio.create_task(explorer_view.load_dialogs())
                page.snack_bar = ft.SnackBar(ft.Text("2FA Verification Successful!"), bgcolor=AppColors.SUCCESS)
                page.snack_bar.open = True
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"2FA Failed: {err}"), bgcolor=AppColors.ERROR)
                page.snack_bar.open = True
            page.update()

        asyncio.create_task(_verify())

    def on_download_task(task: DownloadTask):
        task.status = TaskStatus.QUEUED
        queue_mgr._cancel_flags[task.id] = False
        queue_view.refresh_tasks()

    def on_download_all():
        for t in queue_mgr.tasks:
            if t.status in (TaskStatus.QUEUED, TaskStatus.PAUSED):
                t.status = TaskStatus.QUEUED
                queue_mgr._cancel_flags[t.id] = False
        queue_view.refresh_tasks()

    def on_logout():
        async def _do_logout():
            await auth_mgr.logout()
            header.update_account(None, None)
            explorer_view.chat_list_column.controls = [
                ft.Text("Logged out. Link your account to view channels.", color=AppColors.TEXT_MUTED)
            ]
            explorer_view.media_list_column.controls.clear()
            page.snack_bar = ft.SnackBar(ft.Text("Unlinked account successfully."), bgcolor=AppColors.INFO)
            page.snack_bar.open = True
            page.update()

        asyncio.create_task(_do_logout())

    # Build Header
    header = AppHeader(
        on_account_click=lambda: asyncio.create_task(open_qr_dialog()),
        on_bot_click=lambda: switch_view(2),  # Navigate to Bot Center
        on_drive_click=lambda: switch_view(3),  # Navigate to Settings
    )

    # Build Views
    queue_view = QueueView(
        speed_hud=speed_hud,
        on_download_task=on_download_task,
        on_download_all=on_download_all,
    )
    explorer_view = ExplorerView(on_queue_updated=queue_view.refresh_tasks)
    bot_view = BotView(
        on_bot_state_changed=lambda: header.update_bot_status(
            bot_mgr.is_running, getattr(bot_mgr.bot_me, "username", None)
        )
    )
    settings_view = SettingsView(
        on_settings_saved=lambda: update_storage_hud(),
        on_logout=on_logout,
    )

    # Attach file picker to page overlay
    page.overlay.append(settings_view.folder_picker)

    # Dynamic Queue updates listener
    def on_queue_event(task: DownloadTask):
        speed_hud.update_task(download_engine._current_task)
        queue_view.refresh_tasks()

    queue_mgr.register_listener(on_queue_event)
    bot_mgr.set_callback(lambda _: queue_view.refresh_tasks())

    # Storage HUD refresher
    def update_storage_hud():
        try:
            target = config.download_dir
            usage = shutil.disk_usage(target)
            free_gb = usage.free / (1024 ** 3)
            header.update_storage(f"{free_gb:.1f} GB")
        except Exception:
            header.update_storage("N/A")

    update_storage_hud()

    # View switcher container
    content_area = ft.Container(content=queue_view, expand=True)

    def switch_view(index: int):
        rail.selected_index = index
        if index == 0:
            content_area.content = queue_view
            queue_view.refresh_tasks()
        elif index == 1:
            content_area.content = explorer_view
            if not explorer_view.dialogs:
                asyncio.create_task(explorer_view.load_dialogs())
        elif index == 2:
            content_area.content = bot_view
        elif index == 3:
            content_area.content = settings_view
            settings_view.refresh_drives()
        page.update()

    # Left Navigation Rail
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=80,
        min_extended_width=160,
        bgcolor=AppColors.SURFACE_DARK,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.DOWNLOAD_OUTLINED,
                selected_icon=ft.Icons.DOWNLOAD,
                label="Downloads",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.EXPLORE_OUTLINED,
                selected_icon=ft.Icons.EXPLORE,
                label="Explorer",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SMART_TOY_OUTLINED,
                selected_icon=ft.Icons.SMART_TOY,
                label="Bot Center",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label="Settings",
            ),
        ],
        on_change=lambda e: switch_view(e.control.selected_index),
    )

    # Master Layout
    page.add(
        ft.Column(
            [
                header,
                ft.Row(
                    [
                        rail,
                        ft.VerticalDivider(width=1, color=AppColors.BORDER_DARK),
                        content_area,
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )
    )

    # Auto-initialize session & bot if available
    async def auto_init():
        # Check active session
        if await auth_mgr.is_authorized():
            profile = auth_mgr.current_user
            if profile:
                header.update_account(profile.display_name, profile.username)
                await explorer_view.load_dialogs()

        # Check bot token
        if config.bot_token:
            started = await bot_mgr.start()
            if started:
                header.update_bot_status(True, getattr(bot_mgr.bot_me, "username", None))

        update_storage_hud()
        page.update()

    asyncio.create_task(auto_init())


if __name__ == "__main__":
    ft.app(target=main)
