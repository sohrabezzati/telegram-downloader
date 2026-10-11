"""FastAPI Backend Server for Telegram High-Speed Downloader.

Provides high-performance REST and WebSocket APIs to power the Flutter
native mobile, desktop, and web application.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from auth_manager import auth_mgr, UserProfile
from bot_manager import bot_mgr
from config import config
from download_engine import download_engine
from queue_manager import queue_mgr, DownloadTask, TaskStatus
from storage_manager import storage_mgr


# ---------------------------------------------------------------------------
# Global Auth State Tracking
# ---------------------------------------------------------------------------
class QRState:
    status: str = "idle"  # idle, loading, ready, needs_2fa, authorized, error
    url: Optional[str] = None
    qr_base64: Optional[str] = None
    error: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    _task: Optional[asyncio.Task] = None


qr_state = QRState()


def _format_user(user: Optional[UserProfile]) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "display_name": user.display_name,
        "phone": user.phone,
        "is_premium": user.is_premium,
    }


def _format_task(t: DownloadTask) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "total_bytes": t.total_bytes,
        "downloaded_bytes": t.downloaded_bytes,
        "progress_fraction": t.progress_fraction,
        "progress_percentage": t.progress_percentage,
        "speed_bps": t.speed_bps,
        "speed_mbps": round(t.speed_mbps, 2),
        "eta_seconds": round(t.eta_seconds, 1),
        "status": t.status.value,
        "error_message": t.error_message,
        "source": t.source,
        "channel_title": t.channel_title,
        "chat_id": t.chat_id,
        "message_id": t.message_id,
        "destination_path": t.destination_path,
        "worker_progress": t.worker_progress,
        "created_at": t.created_at,
        "completed_at": t.completed_at,
    }


# ---------------------------------------------------------------------------
# Lifespan Application Manager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[Server] Starting High-Speed Engine & Services...")
    download_engine.start()

    # Auto-start bot listener if configured
    if config.bot_token:
        asyncio.create_task(bot_mgr.start())

    # Pre-check active session in background
    async def _check_init_auth():
        try:
            if await auth_mgr.is_authorized():
                qr_state.status = "authorized"
                qr_state.user = _format_user(auth_mgr.current_user)
                print(f"[Server] Telegram user already authorized: {qr_state.user.get('display_name')}")
        except Exception as e:
            print(f"[Server] Session check notice: {e}")

    asyncio.create_task(_check_init_auth())

    yield

    # Shutdown
    print("[Server] Stopping engine & background listeners...")
    download_engine.stop()
    await bot_mgr.stop()


app = FastAPI(
    title="Telegram High-Speed Downloader API",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for Flutter apps (Web, Mobile, Desktop)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class PasswordRequest(BaseModel):
    password: str


class PhoneSendCodeRequest(BaseModel):
    phone: str


class PhoneVerifyCodeRequest(BaseModel):
    code: str


class AddQueueRequest(BaseModel):
    chat_id: int
    message_id: int
    title: str
    total_bytes: int
    channel_title: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    parallel_workers: Optional[int] = None
    download_dir: Optional[str] = None
    bot_token: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. System & Status Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def get_system_status():
    """Retrieve full system status, auth profile, storage metrics, and engine state."""
    auth_ok = await auth_mgr.is_authorized()
    current_u = _format_user(auth_mgr.current_user) if auth_ok else None

    # Disk space stats
    import shutil
    d_path = Path(config.download_dir).resolve()
    check_dir = d_path
    while not check_dir.exists() and check_dir.parent != check_dir:
        check_dir = check_dir.parent
    try:
        usage = shutil.disk_usage(check_dir)
        total_b = usage.total
        free_b = usage.free
        free_pct = (free_b / total_b) * 100 if total_b > 0 else 0
    except Exception:
        total_b = 1024 * 1024 * 1024 * 100
        free_b = 1024 * 1024 * 1024 * 50
        free_pct = 50.0

    # Queue counters
    tasks = queue_mgr.get_all_tasks()
    active_t = download_engine._current_task

    return {
        "online": True,
        "auth": {
            "is_authorized": auth_ok,
            "user": current_u,
        },
        "bot": {
            "is_running": bot_mgr.is_running,
            "username": bot_mgr.bot_me.username if bot_mgr.bot_me else None,
        },
        "storage": {
            "download_dir": str(config.download_dir),
            "free_bytes": free_b,
            "total_bytes": total_b,
            "free_gb": round(free_b / (1024 ** 3), 2),
            "total_gb": round(total_b / (1024 ** 3), 2),
            "free_percentage": round(free_pct, 1),
            "low_space": free_pct < 10.0,
        },
        "engine": {
            "parallel_workers": config.parallel_workers,
            "is_running": download_engine._is_running,
            "active_task": _format_task(active_t) if active_t else None,
            "total_queued": len(tasks),
            "completed_count": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
        },
    }


# ---------------------------------------------------------------------------
# 2. Authentication Flow (QR Code & Deep Link)
# ---------------------------------------------------------------------------
@app.get("/api/auth/qr")
async def start_qr_auth():
    """Initiate Telegram QR Code and 1-tap deep link device linking."""
    if await auth_mgr.is_authorized():
        return {
            "status": "authorized",
            "url": None,
            "qr_base64": None,
            "user": _format_user(auth_mgr.current_user),
        }

    # If already generating or ready, return existing state
    if qr_state.status in ("loading", "ready") and qr_state.url:
        return {
            "status": qr_state.status,
            "url": qr_state.url,
            "qr_base64": qr_state.qr_base64,
            "user": None,
        }

    # Reset state and kick off background task
    qr_state.status = "loading"
    qr_state.error = None
    qr_state.url = None
    qr_state.qr_base64 = None

    def on_qr_url(url: str, b64_img: str):
        qr_state.url = url
        qr_state.qr_base64 = b64_img
        qr_state.status = "ready"

    def on_success(profile: UserProfile):
        qr_state.status = "authorized"
        qr_state.user = _format_user(profile)

    def on_password_needed(_):
        qr_state.status = "needs_2fa"

    def on_error(err: str):
        qr_state.status = "error"
        qr_state.error = err

    if qr_state._task and not qr_state._task.done():
        qr_state._task.cancel()

    qr_state._task = asyncio.create_task(
        auth_mgr.start_qr_login(
            on_qr_url=on_qr_url,
            on_success=on_success,
            on_password_needed=on_password_needed,
            on_error=on_error,
        )
    )

    # Wait briefly for initial token to generate
    for _ in range(15):
        if qr_state.status in ("ready", "authorized", "needs_2fa", "error"):
            break
        await asyncio.sleep(0.2)

    return {
        "status": qr_state.status,
        "url": qr_state.url,
        "qr_base64": qr_state.qr_base64,
        "user": qr_state.user,
        "error": qr_state.error,
    }


@app.get("/api/auth/poll")
async def poll_auth_status():
    """Poll the status of the ongoing QR login session."""
    auth_ok = await auth_mgr.is_authorized()
    if auth_ok:
        qr_state.status = "authorized"
        qr_state.user = _format_user(auth_mgr.current_user)

    return {
        "status": qr_state.status,
        "user": qr_state.user,
        "url": qr_state.url,
        "qr_base64": qr_state.qr_base64,
        "error": qr_state.error,
    }


@app.post("/api/auth/phone/send-code")
async def send_phone_code(req: PhoneSendCodeRequest):
    """Send verification code directly to user's Telegram in-app sessions."""
    ok, err = await auth_mgr.send_phone_code(req.phone)
    if ok:
        return {"success": True, "phone": auth_mgr._phone}
    return {"success": False, "error": err}


@app.post("/api/auth/phone/verify-code")
async def verify_phone_code(req: PhoneVerifyCodeRequest):
    """Verify in-app 5-digit code sent by Telegram."""
    ok, needs_2fa, err = await auth_mgr.sign_in_code(req.code)
    if ok:
        qr_state.status = "authorized"
        qr_state.user = _format_user(auth_mgr.current_user)
        return {"success": True, "needs_2fa": False, "user": qr_state.user}
    elif needs_2fa:
        qr_state.status = "needs_2fa"
        return {"success": False, "needs_2fa": True, "error": None}
    else:
        return {"success": False, "needs_2fa": False, "error": err}


@app.post("/api/auth/2fa")
async def submit_2fa(req: PasswordRequest):
    """Submit Two-Step Verification Cloud Password."""
    ok, err = await auth_mgr.submit_2fa_password(req.password)
    if ok:
        qr_state.status = "authorized"
        qr_state.user = _format_user(auth_mgr.current_user)
        return {"success": True, "user": qr_state.user}
    return {"success": False, "error": err}


@app.post("/api/auth/logout")
async def logout():
    """Disconnect and clear user session."""
    ok = await auth_mgr.logout()
    qr_state.status = "idle"
    qr_state.user = None
    qr_state.url = None
    qr_state.qr_base64 = None
    return {"success": ok}


# ---------------------------------------------------------------------------
# 3. Channels, Chats & Saved Messages Explorer
# ---------------------------------------------------------------------------
@app.get("/api/dialogs")
async def get_dialogs():
    """Fetch joined channels, groups, and Saved Messages."""
    if not await auth_mgr.is_authorized():
        raise HTTPException(status_code=401, detail="Telegram account not authorized")

    client = auth_mgr.get_client()
    try:
        dialogs = await client.get_dialogs(limit=50)
        result = []
        for d in dialogs:
            is_self = d.is_user and getattr(d.entity, "is_self", False)
            title = "Saved Messages" if is_self else (d.name or "Unnamed Chat")
            result.append(
                {
                    "id": d.id,
                    "title": title,
                    "is_channel": d.is_channel,
                    "is_group": d.is_group,
                    "is_user": d.is_user,
                    "is_self": is_self,
                    "unread_count": d.unread_count,
                }
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dialogs/{chat_id}/media")
async def get_dialog_media(chat_id: int, limit: int = 50, offset_id: int = 0):
    """Retrieve downloadable media messages from a channel, chat, or Saved Messages."""
    if not await auth_mgr.is_authorized():
        raise HTTPException(status_code=401, detail="Telegram account not authorized")

    client = auth_mgr.get_client()
    try:
        entity = await client.get_entity(chat_id)
        messages = await client.get_messages(entity, limit=limit, offset_id=offset_id)

        items = []
        queued_map = {f"{t.chat_id}_{t.message_id}": t.status.value for t in queue_mgr.get_all_tasks()}

        for m in messages:
            if not m.media:
                continue

            file_name = "media_file"
            file_size = 0
            mime = "application/octet-stream"

            if isinstance(m.media, MessageMediaDocument) and m.media.document:
                doc = m.media.document
                file_size = doc.size
                mime = doc.mime_type or mime
                for attr in doc.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        file_name = attr.file_name
                    elif isinstance(attr, DocumentAttributeVideo):
                        mime = "video/mp4"
                        if not file_name or file_name == "media_file":
                            file_name = f"video_{m.id}.mp4"
                    elif isinstance(attr, DocumentAttributeAudio):
                        mime = "audio/mpeg"
                        if not file_name or file_name == "media_file":
                            file_name = f"audio_{m.id}.mp3"
            elif isinstance(m.media, MessageMediaPhoto):
                file_name = f"photo_{m.id}.jpg"
                mime = "image/jpeg"
                file_size = 1024 * 500  # Estimate
            else:
                continue

            key = f"{chat_id}_{m.id}"
            items.append(
                {
                    "chat_id": chat_id,
                    "message_id": m.id,
                    "title": file_name,
                    "total_bytes": file_size,
                    "date": m.date.isoformat() if m.date else "",
                    "mime_type": mime,
                    "queue_status": queued_map.get(key),
                }
            )

        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 4. Download Queue & Management Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/queue")
async def get_download_queue():
    """Retrieve full list of download tasks."""
    tasks = queue_mgr.get_all_tasks()
    return [_format_task(t) for t in tasks]


@app.post("/api/queue/add")
async def add_to_queue(req: AddQueueRequest):
    """Add a file to the high-speed download queue."""
    client = auth_mgr.get_client()
    try:
        entity = await client.get_entity(req.chat_id)
        msg = await client.get_messages(entity, ids=req.message_id)
        if not msg or not msg.media:
            raise HTTPException(status_code=404, detail="Media message not found")

        task = DownloadTask(
            title=req.title,
            total_bytes=req.total_bytes,
            source="CHANNEL_EXPLORER",
            channel_title=req.channel_title,
            chat_id=req.chat_id,
            message_id=req.message_id,
            media_obj=msg,
        )
        queue_mgr.add_task(task)
        return {"success": True, "task": _format_task(task)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/queue/{task_id}/pause")
async def pause_task(task_id: str):
    queue_mgr.pause_task(task_id)
    return {"success": True}


@app.post("/api/queue/{task_id}/resume")
async def resume_task(task_id: str):
    queue_mgr.resume_task(task_id)
    return {"success": True}


@app.post("/api/queue/{task_id}/cancel")
async def cancel_task(task_id: str):
    queue_mgr.cancel_task(task_id)
    return {"success": True}


@app.post("/api/queue/clear")
async def clear_completed_tasks():
    queue_mgr.clear_completed()
    return {"success": True}


# ---------------------------------------------------------------------------
# 5. Bot Forwarding Inbox Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/bot/files")
async def get_bot_forwarded_files():
    """Fetch files forwarded by users to the Telegram bot."""
    tasks = [t for t in queue_mgr.get_all_tasks() if t.source == "BOT_FORWARD"]
    return [_format_task(t) for t in tasks]


# ---------------------------------------------------------------------------
# 6. Settings Configuration
# ---------------------------------------------------------------------------
@app.get("/api/settings")
async def get_settings():
    return {
        "parallel_workers": config.parallel_workers,
        "download_dir": str(config.download_dir),
        "bot_token": config.bot_token,
    }


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    if req.parallel_workers is not None:
        config.parallel_workers = max(1, min(16, req.parallel_workers))
    if req.download_dir is not None:
        config.download_dir = req.download_dir
    if req.bot_token is not None:
        config.bot_token = req.bot_token
        # Restart bot listener with new token
        asyncio.create_task(bot_mgr.start())

    config.save()
    return {"success": True, "settings": await get_settings()}


# ---------------------------------------------------------------------------
# 7. Real-Time Telemetry WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """Stream live MB/s speed, chunk worker lights, and task progress."""
    await websocket.accept()
    try:
        while True:
            active_t = download_engine._current_task
            tasks = queue_mgr.get_all_tasks()

            payload = {
                "active_task": _format_task(active_t) if active_t else None,
                "overall_speed_mbps": round(active_t.speed_mbps, 2) if active_t else 0.0,
                "queue_count": len([t for t in tasks if t.status == TaskStatus.QUEUED]),
                "completed_count": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                "active_count": 1 if active_t else 0,
            }

            await websocket.send_json(payload)
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
# ---------------------------------------------------------------------------
# 8. Serve Flutter Web Frontend (if compiled)
# ---------------------------------------------------------------------------
web_dir = Path(__file__).parent / "frontend" / "build" / "web"
if web_dir.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="flutter_web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
