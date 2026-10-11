"""Storage and Drive Manager for Telegram High-Speed Downloader.

Detects internal and external USB drives, validates free disk space,
sanitizes filenames, and resolves directory organization templates.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class StorageDrive:
    name: str
    path: str
    total_bytes: int
    free_bytes: int
    used_bytes: int
    percent_used: float
    is_removable: bool

    @property
    def free_gb(self) -> float:
        return self.free_bytes / (1024 ** 3)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 ** 3)

    @property
    def free_formatted(self) -> str:
        if self.free_gb >= 1.0:
            return f"{self.free_gb:.1f} GB free"
        return f"{self.free_bytes / (1024 ** 2):.1f} MB free"


class StorageManager:
    """Manages drive detection, storage space validation, and path resolution."""

    @staticmethod
    def get_available_drives() -> List[StorageDrive]:
        """Detect all available system and external drives across macOS, Linux, and Windows."""
        drives: List[StorageDrive] = []
        os_name = platform.system()

        # Always include default Downloads directory
        home_downloads = Path.home() / "Downloads"
        if home_downloads.exists():
            try:
                usage = shutil.disk_usage(home_downloads)
                pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0
                drives.append(
                    StorageDrive(
                        name="Downloads (Default)",
                        path=str(home_downloads / "TelegramDownloader"),
                        total_bytes=usage.total,
                        free_bytes=usage.free,
                        used_bytes=usage.used,
                        percent_used=pct,
                        is_removable=False,
                    )
                )
            except Exception:
                pass

        if os_name == "Darwin":  # macOS
            volumes_dir = Path("/Volumes")
            if volumes_dir.exists():
                for vol in volumes_dir.iterdir():
                    if vol.is_dir() and not vol.name.startswith("."):
                        # Skip system root aliases
                        if vol.name in ("Macintosh HD", "Root", "Recovery"):
                            continue
                        try:
                            usage = shutil.disk_usage(vol)
                            pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0
                            drives.append(
                                StorageDrive(
                                    name=f"USB: {vol.name}",
                                    path=str(vol),
                                    total_bytes=usage.total,
                                    free_bytes=usage.free,
                                    used_bytes=usage.used,
                                    percent_used=pct,
                                    is_removable=True,
                                )
                            )
                        except Exception:
                            continue

        elif os_name == "Linux":
            media_dirs = [
                Path(f"/media/{os.getenv('USER', '')}"),
                Path("/run/media") / os.getenv("USER", ""),
                Path("/mnt"),
            ]
            for mdir in media_dirs:
                if mdir.exists() and mdir.is_dir():
                    for mount in mdir.iterdir():
                        if mount.is_dir() and not mount.name.startswith("."):
                            try:
                                usage = shutil.disk_usage(mount)
                                pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0
                                drives.append(
                                    StorageDrive(
                                        name=f"Drive: {mount.name}",
                                        path=str(mount),
                                        total_bytes=usage.total,
                                        free_bytes=usage.free,
                                        used_bytes=usage.used,
                                        percent_used=pct,
                                        is_removable=True,
                                    )
                                )
                            except Exception:
                                continue

        elif os_name == "Windows":
            import string
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    try:
                        usage = shutil.disk_usage(drive_path)
                        pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0
                        is_c = (letter == "C")
                        drives.append(
                            StorageDrive(
                                name=f"Drive ({letter}:)",
                                path=drive_path,
                                total_bytes=usage.total,
                                free_bytes=usage.free,
                                used_bytes=usage.used,
                                percent_used=pct,
                                is_removable=not is_c,
                            )
                        )
                    except Exception:
                        continue

        return drives

    @staticmethod
    def check_has_sufficient_space(target_path: Path | str, required_bytes: int) -> Tuple[bool, int, int]:
        """Check if destination folder has enough space for download.
        
        Returns:
            Tuple of (has_space: bool, free_bytes: int, shortfall_bytes: int)
        """
        target = Path(target_path).resolve()
        # Find existing parent if target doesn't exist yet
        check_dir = target
        while not check_dir.exists() and check_dir.parent != check_dir:
            check_dir = check_dir.parent

        try:
            usage = shutil.disk_usage(check_dir)
            # Reserve 100MB safety buffer
            safety_buffer = 100 * 1024 * 1024
            available = max(0, usage.free - safety_buffer)
            if available >= required_bytes:
                return True, usage.free, 0
            else:
                shortfall = required_bytes - available
                return False, usage.free, shortfall
        except Exception:
            return True, 0, 0

    @staticmethod
    def sanitize_filename(name: str, max_length: int = 240) -> str:
        """Sanitize filenames by stripping invalid characters and path traversals."""
        if not name:
            return "unnamed_file"
        # Strip directory separators and invalid OS characters
        sanitized = re.sub(r'[\\/*?:"<>|]', "_", name)
        # Strip leading dots or whitespace
        sanitized = sanitized.strip(" .")
        if not sanitized:
            sanitized = "unnamed_file"
        # Truncate if exceeds max length while preserving extension
        if len(sanitized) > max_length:
            stem, ext = os.path.splitext(sanitized)
            sanitized = stem[:max_length - len(ext)] + ext
        return sanitized

    @staticmethod
    def resolve_destination(
        base_dir: Path | str,
        template: str,
        filename: str,
        channel_title: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> Path:
        """Resolve full target file path using organizational template rules."""
        base = Path(base_dir).expanduser().resolve()
        safe_filename = StorageManager.sanitize_filename(filename)

        if template == "channel" and channel_title:
            safe_channel = StorageManager.sanitize_filename(channel_title)
            dest_dir = base / safe_channel
        elif template == "media_type" and media_type:
            safe_type = StorageManager.sanitize_filename(media_type.capitalize())
            dest_dir = base / safe_type
        else:
            dest_dir = base

        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir / safe_filename

    @staticmethod
    def inspect_file_status(file_path: Path, expected_size: int) -> str:
        """Inspect if file exists, is complete, incomplete, or pending.
        
        Returns:
            'DOWNLOADED', 'INCOMPLETE', or 'PENDING'
        """
        if not file_path.exists():
            return "PENDING"
        try:
            actual_size = file_path.stat().st_size
            if actual_size == 0 and expected_size > 0:
                return "INCOMPLETE"
            if actual_size == expected_size:
                return "DOWNLOADED"
            return "INCOMPLETE"
        except Exception:
            return "PENDING"


storage_mgr = StorageManager()
