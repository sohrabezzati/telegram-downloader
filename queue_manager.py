"""Download Queue Manager for Telegram High-Speed Downloader.

Coordinates download lifecycles, states, concurrency limits, prioritization,
and telemetry callbacks for live UI rendering.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class DownloadTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = "Unnamed File"
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bps: float = 0.0
    eta_seconds: float = 0.0
    status: TaskStatus = TaskStatus.QUEUED
    error_message: Optional[str] = None
    source: str = "DIRECT"  # "BOT_FORWARD", "CHANNEL_EXPLORER", "DIRECT_LINK"
    channel_title: Optional[str] = None
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    media_obj: Any = None  # Reference to Telethon Message or Document
    destination_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    # Telemetry for chunk visualizer: worker_id -> chunk progress %
    worker_progress: Dict[int, float] = field(default_factory=dict)

    @property
    def progress_fraction(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(1.0, max(0.0, self.downloaded_bytes / self.total_bytes))

    @property
    def progress_percentage(self) -> int:
        return int(self.progress_fraction * 100)

    @property
    def speed_mbps(self) -> float:
        return self.speed_bps / (1024 * 1024)

    @property
    def formatted_size(self) -> str:
        if self.total_bytes >= 1024 ** 3:
            return f"{self.total_bytes / (1024 ** 3):.2f} GB"
        elif self.total_bytes >= 1024 ** 2:
            return f"{self.total_bytes / (1024 ** 2):.1f} MB"
        elif self.total_bytes >= 1024:
            return f"{self.total_bytes / 1024:.0f} KB"
        return f"{self.total_bytes} B"

    @property
    def formatted_downloaded(self) -> str:
        if self.total_bytes >= 1024 ** 3:
            return f"{self.downloaded_bytes / (1024 ** 3):.2f} GB"
        elif self.total_bytes >= 1024 ** 2:
            return f"{self.downloaded_bytes / (1024 ** 2):.1f} MB"
        return f"{self.downloaded_bytes / 1024:.0f} KB"

    @property
    def formatted_eta(self) -> str:
        if self.eta_seconds <= 0 or self.status != TaskStatus.DOWNLOADING:
            return "--:--"
        mins, secs = divmod(int(self.eta_seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"


class QueueManager:
    """Thread-safe queue manager for downloading tasks."""

    def __init__(self):
        self.tasks: List[DownloadTask] = []
        self._listeners: List[Callable[[DownloadTask], None]] = []
        self._lock = asyncio.Lock()
        self._is_processing = False
        self._cancel_flags: Dict[str, bool] = {}

    def register_listener(self, callback: Callable[[DownloadTask], None]) -> None:
        """Register a callback that fires whenever task progress updates."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[DownloadTask], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, task: DownloadTask) -> None:
        for cb in list(self._listeners):
            try:
                cb(task)
            except Exception:
                pass

    def add_task(self, task: DownloadTask) -> DownloadTask:
        """Add a new task to the queue."""
        # Avoid duplicate message_id from same chat
        if task.chat_id and task.message_id:
            for existing in self.tasks:
                if existing.chat_id == task.chat_id and existing.message_id == task.message_id:
                    if existing.status in (TaskStatus.COMPLETED, TaskStatus.DOWNLOADING, TaskStatus.QUEUED):
                        return existing

        self.tasks.append(task)
        self._notify(task)
        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def pause_task(self, task_id: str) -> None:
        t = self.get_task(task_id)
        if t and t.status in (TaskStatus.DOWNLOADING, TaskStatus.QUEUED):
            t.status = TaskStatus.PAUSED
            self._cancel_flags[task_id] = True
            self._notify(t)

    def resume_task(self, task_id: str) -> None:
        t = self.get_task(task_id)
        if t and t.status == TaskStatus.PAUSED:
            t.status = TaskStatus.QUEUED
            self._cancel_flags[task_id] = False
            self._notify(t)

    def cancel_task(self, task_id: str) -> None:
        t = self.get_task(task_id)
        if t:
            self._cancel_flags[task_id] = True
            t.status = TaskStatus.FAILED
            t.error_message = "Cancelled by user"
            self._notify(t)

    def remove_task(self, task_id: str) -> None:
        t = self.get_task(task_id)
        if t:
            self._cancel_flags[task_id] = True
            self.tasks = [task for task in self.tasks if task.id != task_id]
            self._notify(t)

    def clear_completed(self) -> None:
        self.tasks = [t for t in self.tasks if t.status not in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)]

    def is_cancelled(self, task_id: str) -> bool:
        return self._cancel_flags.get(task_id, False)

    def get_active_tasks(self) -> List[DownloadTask]:
        return [t for t in self.tasks if t.status == TaskStatus.DOWNLOADING]

    def get_queued_tasks(self) -> List[DownloadTask]:
        return [t for t in self.tasks if t.status == TaskStatus.QUEUED]

    def get_completed_tasks(self) -> List[DownloadTask]:
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]


queue_mgr = QueueManager()
