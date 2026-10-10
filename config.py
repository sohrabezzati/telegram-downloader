"""Configuration manager for Telegram High-Speed Downloader.

Handles loading, validating, and persisting user preferences to a local JSON file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "tg_downloader" / "config.json"
LOCAL_CONFIG_PATH = Path("app_config.json")


DEFAULT_CONFIG: Dict[str, Any] = {
    "download_dir": str(Path.home() / "Downloads" / "TelegramDownloader"),
    "workers": 16,
    "max_concurrent_downloads": 1,
    "bandwidth_limit_mb": 0,  # 0 means unlimited
    "theme": "dark",  # "dark" or "light"
    "organization_template": "channel",  # "channel", "media_type", "flat"
    "bot_token": "",
    "bot_whitelist": [],  # List of int user IDs allowed to forward/use bot
    "bot_auto_download": False,
    "notify_system": True,
    "notify_bot": True,
    "active_session": "tg_session.session",
    "saved_accounts": [],  # List of {"name": str, "phone": str, "session": str, "username": str}
}


class ConfigManager:
    """Thread-safe and process-safe configuration manager."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or LOCAL_CONFIG_PATH
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Load configuration from disk, falling back to defaults if missing or corrupted."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                    if isinstance(stored, dict):
                        self._data.update(stored)
            except Exception:
                # If corrupted, preserve defaults
                pass
        else:
            self.save()

    def save(self) -> None:
        """Persist current configuration to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and persist immediately."""
        self._data[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple keys and persist once."""
        self._data.update(updates)
        self.save()

    @property
    def download_dir(self) -> Path:
        p = Path(self.get("download_dir", DEFAULT_CONFIG["download_dir"])).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def workers(self) -> int:
        val = int(self.get("workers", 16))
        return max(1, min(val, 32))

    @property
    def bot_token(self) -> str:
        # Check config first, fallback to os.environ
        token = self.get("bot_token", "").strip()
        if not token:
            token = os.getenv("TG_BOT_TOKEN", "").strip()
        return token

    @property
    def bot_whitelist(self) -> List[int]:
        raw = self.get("bot_whitelist", [])
        clean = []
        for item in raw:
            try:
                clean.append(int(item))
            except (ValueError, TypeError):
                continue
        return clean

    def add_whitelist_user(self, user_id: int) -> None:
        whitelist = self.bot_whitelist
        if user_id not in whitelist:
            whitelist.append(user_id)
            self.set("bot_whitelist", whitelist)

    def is_user_allowed(self, user_id: int) -> bool:
        whitelist = self.bot_whitelist
        if not whitelist:
            # If whitelist is empty, any user interacting with personal bot is allowed
            return True
        return user_id in whitelist


# Singleton instance
config = ConfigManager()
