"""Telegram Authentication and Session Manager.

Handles MTProto client lifecycle, seamless QR code device linking (auth.exportLoginToken),
2FA password authentication, and multi-account session profiles.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import qrcode
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhonePasswordFloodError,
    SessionPasswordNeededError,
)

from config import config

# Load .env variables
load_dotenv()

TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")


@dataclass
class UserProfile:
    id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    phone: Optional[str]
    is_premium: bool = False

    @property
    def display_name(self) -> str:
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)


class AuthManager:
    """Manages Telethon user client, session caching, and QR authentication."""

    def __init__(self, session_name: str = "tg_session"):
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None
        self.current_user: Optional[UserProfile] = None
        self._qr_login_task: Optional[asyncio.Task] = None
        self._active_qr = None
        self._is_connecting = False

    def get_client(self) -> TelegramClient:
        """Get or initialize the shared Telethon client."""
        if self.client is None:
            if not TG_API_ID or not TG_API_HASH:
                raise ValueError("TG_API_ID and TG_API_HASH must be set in .env or environment")
            self.client = TelegramClient(self.session_name, int(TG_API_ID), TG_API_HASH)
        return self.client

    async def ensure_connected(self) -> bool:
        """Connect the client to Telegram servers."""
        client = self.get_client()
        if not client.is_connected():
            await client.connect()
        return client.is_connected()

    async def is_authorized(self) -> bool:
        """Check if active session is already authenticated."""
        try:
            client = self.get_client()
            if not client.is_connected():
                await client.connect()
            auth = await client.is_user_authorized()
            if auth and self.current_user is None:
                await self.load_user_profile()
            return auth
        except Exception:
            return False

    async def load_user_profile(self) -> Optional[UserProfile]:
        """Fetch current user profile data."""
        client = self.get_client()
        try:
            me = await client.get_me()
            if me:
                self.current_user = UserProfile(
                    id=me.id,
                    first_name=me.first_name or "",
                    last_name=me.last_name,
                    username=me.username,
                    phone=me.phone,
                    is_premium=getattr(me, "premium", False),
                )
                return self.current_user
        except Exception as e:
            print(f"[AuthManager] Failed to load profile: {e}")
        return None

    def generate_qr_base64(self, url: str) -> str:
        """Render a Telegram login URL as a base64 encoded PNG data URI for Flet Image."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    async def start_qr_login(
        self,
        on_qr_url: Callable[[str, str], None],  # callback(raw_url, base64_image)
        on_success: Callable[[UserProfile], None],
        on_password_needed: Callable[[Any], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Initiate Telegram QR Code Device Linking flow."""
        client = self.get_client()
        if not client.is_connected():
            await client.connect()

        try:
            qr_login = await client.qr_login()
            self._active_qr = qr_login

            # Render initial QR
            b64 = self.generate_qr_base64(qr_login.url)
            on_qr_url(qr_login.url, b64)

            # Wait for user scan loop
            while True:
                try:
                    user = await qr_login.wait(timeout=15)
                    # Successful login
                    profile = await self.load_user_profile()
                    if profile:
                        on_success(profile)
                    return
                except asyncio.TimeoutError:
                    # Token expired, recreate/refresh
                    await qr_login.recreate()
                    b64 = self.generate_qr_base64(qr_login.url)
                    on_qr_url(qr_login.url, b64)
                except SessionPasswordNeededError:
                    on_password_needed(client)
                    return
                except FloodWaitError as e:
                    on_error(f"Telegram flood wait: please wait {e.seconds} seconds.")
                    return
        except Exception as e:
            on_error(str(e))

    async def submit_2fa_password(self, password: str) -> Tuple[bool, Optional[str]]:
        """Submit 2FA password after QR scan prompt."""
        client = self.get_client()
        try:
            await client.sign_in(password=password)
            profile = await self.load_user_profile()
            return True, None
        except PasswordHashInvalidError:
            return False, "Incorrect 2FA password. Please check and try again."
        except PhonePasswordFloodError:
            return False, "Too many password attempts. Telegram locked this account temporarily."
        except Exception as e:
            return False, str(e)

    async def logout(self) -> bool:
        """Cleanly log out of current Telegram user session."""
        try:
            client = self.get_client()
            if client.is_connected():
                await client.log_out()
            self.current_user = None
            # Remove session file
            session_file = Path(f"{self.session_name}.session")
            if session_file.exists():
                session_file.unlink()
            return True
        except Exception as e:
            print(f"[AuthManager] Logout error: {e}")
            return False


auth_mgr = AuthManager()
