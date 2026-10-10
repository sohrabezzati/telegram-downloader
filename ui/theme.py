"""UI Theme and styling definitions for Telegram High-Speed Downloader."""

from __future__ import annotations

import flet as ft

# ---------------------------------------------------------------------------
# Flet 1.0+ Backwards-Compatibility Layer
# Normalizes padding, borders, alignments, and button APIs across Flet versions
# ---------------------------------------------------------------------------
if hasattr(ft, "Padding"):
    ft.padding.all = ft.Padding.all
    ft.padding.symmetric = ft.Padding.symmetric
    ft.padding.only = ft.Padding.only
if hasattr(ft, "Border"):
    ft.border.all = ft.Border.all
    ft.border.only = ft.Border.only
    ft.border.symmetric = ft.Border.symmetric
if hasattr(ft, "BorderRadius"):
    ft.border_radius.all = ft.BorderRadius.all
    ft.border_radius.only = ft.BorderRadius.only
if hasattr(ft, "Alignment"):
    ft.alignment.center = ft.Alignment.CENTER
    ft.alignment.top_left = ft.Alignment.TOP_LEFT
    ft.alignment.top_right = ft.Alignment.TOP_RIGHT
    ft.alignment.bottom_left = ft.Alignment.BOTTOM_LEFT
    ft.alignment.bottom_right = ft.Alignment.BOTTOM_RIGHT

# ImageFit -> BoxFit alias
if hasattr(ft, "BoxFit"):
    ft.ImageFit = ft.BoxFit

# Patch buttons to accept text=... as content and expose .text property
for _btn_cls in [ft.FilledButton, ft.OutlinedButton, ft.TextButton]:
    _orig_init = _btn_cls.__init__
    def _make_wrapped(orig):
        def _wrapped(self, *args, **kwargs):
            if "text" in kwargs:
                t = kwargs.pop("text")
                if "content" not in kwargs and not args:
                    kwargs["content"] = t
            orig(self, *args, **kwargs)
        return _wrapped
    _btn_cls.__init__ = _make_wrapped(_orig_init)
    _btn_cls.text = property(
        lambda self: self.content if isinstance(self.content, str) else None,
        lambda self, v: setattr(self, "content", v)
    )

# Patch Dropdown on_change -> on_select
_orig_dd_init = ft.Dropdown.__init__
def _wrapped_dd_init(self, *args, **kwargs):
    if "on_change" in kwargs and "on_select" not in kwargs:
        kwargs["on_select"] = kwargs.pop("on_change")
    _orig_dd_init(self, *args, **kwargs)
ft.Dropdown.__init__ = _wrapped_dd_init

# Patch DropdownOption positional arguments
_orig_opt_init = ft.DropdownOption.__init__
def _wrapped_opt_init(self, *args, **kwargs):
    if len(args) == 2:
        kwargs["key"] = args[0]
        kwargs["text"] = args[1]
        args = ()
    elif len(args) == 1:
        kwargs["key"] = args[0]
        args = ()
    _orig_opt_init(self, *args, **kwargs)
ft.DropdownOption.__init__ = _wrapped_opt_init

# Safe Control.update guard to prevent unmounted runtime errors
if hasattr(ft, "Control") and hasattr(ft.Control, "update"):
    _orig_control_update = ft.Control.update
    def _safe_control_update(self, *args, **kwargs):
        try:
            return _orig_control_update(self, *args, **kwargs)
        except RuntimeError as e:
            if "added to the page first" in str(e):
                return None
            raise
    ft.Control.update = _safe_control_update


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
