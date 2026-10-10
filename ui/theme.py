"""UI Theme and styling definitions for Telegram High-Speed Downloader."""

from __future__ import annotations

import flet as ft


class AppColors:
    # Primary Telegram Blue accents
    PRIMARY = "#2AABEE"
    PRIMARY_LIGHT = "#5BC0F8"
    PRIMARY_DARK = "#229ED9"

    # Status accents
    SUCCESS = "#00C853"      # Emerald Green for Downloaded
    WARNING = "#FFB300"      # Amber for Pending
    ERROR = "#FF5252"        # Coral Red for Failed
    INFO = "#00B0FF"         # Bright Blue for Active

    # Dark Theme Backgrounds & Surfaces (Pitch/OLED & Deep Slate)
    BG_DARK = "#0E1621"       # Telegram Desktop dark background
    SURFACE_DARK = "#17212B"  # Telegram Desktop dark surface
    CARD_DARK = "#242F3D"     # Telegram card container
    BORDER_DARK = "#2B394A"

    # Light Theme Backgrounds & Surfaces
    BG_LIGHT = "#F4F6F8"
    SURFACE_LIGHT = "#FFFFFF"
    CARD_LIGHT = "#FFFFFF"
    BORDER_LIGHT = "#E0E0E0"

    # Text Colors
    TEXT_MUTED = "#8E9AA8"
    TEXT_WHITE = "#FFFFFF"


def get_theme(mode: str = "dark") -> ft.Theme:
    """Generate consistent Flet Theme."""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=AppColors.PRIMARY,
            secondary=AppColors.SUCCESS,
            surface=AppColors.SURFACE_DARK if mode == "dark" else AppColors.SURFACE_LIGHT,
        ),
    )
