#!/usr/bin/env python3
"""
Telegram High-Speed Saved Messages Downloader
----------------------------------------------
Boosts download speeds by downloading chunks in parallel over multiple MTProto
connections directly to your flash card / USB drive or local disk.
"""

import argparse
import asyncio
import io
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv, set_key, unset_key
import qrcode
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.table import Table

from telethon import TelegramClient, errors
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
)

from parallel_downloader import download_media_fast

console = Console()
ENV_FILE = Path(__file__).parent / ".env"
SESSION_NAME = "tg_session"


def format_size(size_bytes: int) -> str:
    """Formats bytes into human readable string (KB, MB, GB)."""
    if not size_bytes or size_bytes < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0 or unit == "TB":
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def sanitize_filename(filename: str) -> str:
    """Removes unsafe characters for FAT32, exFAT, and macOS filesystems."""
    clean = re.sub(r'[\\/*?:"<>|]', "_", filename)
    clean = clean.strip(" .")
    return clean if clean else "downloaded_file"


def get_removable_drives() -> List[Dict[str, str]]:
    """Detects mounted USB flash drives and external disks on macOS / Linux."""
    drives = []
    # macOS mount point
    if os.path.exists("/Volumes"):
        for entry in os.scandir("/Volumes"):
            if entry.is_symlink():
                continue
            try:
                real_path = os.path.realpath(entry.path)
                if real_path == "/" or entry.name.lower() in ("macos", "macintosh hd"):
                    continue
                if entry.is_dir():
                    usage = shutil.disk_usage(entry.path)
                    drives.append({
                        "name": entry.name,
                        "path": entry.path,
                        "free_bytes": usage.free,
                        "total_bytes": usage.total,
                        "free_str": format_size(usage.free),
                        "total_str": format_size(usage.total),
                    })
            except Exception:
                pass
    return drives


def ensure_env_credentials() -> Tuple[int, str, Optional[str]]:
    """Loads or prompts for Telegram API credentials and saves them to .env."""
    load_dotenv(ENV_FILE)
    api_id_val = os.getenv("TG_API_ID")
    api_hash_val = os.getenv("TG_API_HASH")
    phone_val = os.getenv("TG_PHONE")

    if not api_id_val or not api_hash_val:
        console.print(
            Panel.fit(
                "[bold cyan]Telegram API Setup[/bold cyan]\n\n"
                "To download at maximum MTProto speeds, you need your personal Telegram API credentials:\n"
                "1. Go to: [bold underline yellow]https://my.telegram.org[/bold underline yellow]\n"
                "2. Log in with your Telegram phone number.\n"
                "3. Click on [bold green]'API development tools'[/bold green].\n"
                "4. Fill in any App title and Short name (e.g., 'downloader') and click 'Create application'.\n"
                "5. Copy your [bold]App api_id[/bold] and [bold]App api_hash[/bold].\n\n"
                "[dim]Credentials are saved locally in .env and never shared.[/dim]",
                title="[bold yellow]First-Time Setup[/bold yellow]",
            )
        )
        api_id_input = Prompt.ask("[bold green]Enter your API ID[/bold green]")
        api_hash_input = Prompt.ask("[bold green]Enter your API HASH[/bold green]").strip()
        phone_input = Prompt.ask(
            "[bold green]Enter your phone number (e.g. +1...)[/bold green] (optional)",
            default="",
        ).strip()

        # Save to .env
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), "TG_API_ID", api_id_input.strip())
        set_key(str(ENV_FILE), "TG_API_HASH", api_hash_input)
        if phone_input:
            set_key(str(ENV_FILE), "TG_PHONE", phone_input)

        api_id_val = api_id_input.strip()
        api_hash_val = api_hash_input
        phone_val = phone_input or None

    try:
        api_id = int(api_id_val)
    except ValueError:
        console.print("[bold red]Error: TG_API_ID must be a numeric integer.[/bold red]")
        sys.exit(1)

    return api_id, api_hash_val, phone_val


def select_destination_folder(cli_output: Optional[str] = None) -> Path:
    """Selects target download directory (Flash card / USB drive or custom path)."""
    if cli_output:
        dest = Path(cli_output).expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    drives = get_removable_drives()
    console.print("\n[bold cyan]Select Download Destination:[/bold cyan]")

    choices = {}
    idx = 1
    for drive in drives:
        choices[str(idx)] = Path(drive["path"])
        console.print(
            f" [bold green][{idx}][/bold green] [bold]{drive['name']}[/bold] "
            f"([dim]{drive['path']}[/dim]) — [cyan]{drive['free_str']} free[/cyan]"
        )
        idx += 1

    local_downloads = Path(__file__).parent / "downloads"
    choices[str(idx)] = local_downloads
    console.print(
        f" [bold green][{idx}][/bold green] Local folder: [dim]{local_downloads}[/dim]"
    )
    idx += 1

    choices[str(idx)] = "custom"
    console.print(f" [bold green][{idx}][/bold green] Enter custom folder path...")

    default_choice = "1" if drives else str(idx - 1)
    sel = Prompt.ask(
        "Choose destination",
        choices=[str(i) for i in range(1, idx + 1)],
        default=default_choice,
    )

    if choices[sel] == "custom":
        custom_path = Prompt.ask("Enter directory path").strip()
        target = Path(custom_path).expanduser().resolve()
    else:
        target = Path(choices[sel]).resolve()

    target.mkdir(parents=True, exist_ok=True)
    return target


def find_existing_file(dest_dir: Path, filename: str, expected_size: int) -> Tuple[bool, Optional[Path], str]:
    """
    Checks if a file with the given name and size exists in dest_dir or common subfolders.
    Returns: (is_complete_match, found_path, reason)
      reason: 'match', 'empty', 'size_mismatch', or 'not_found'
    """
    candidates = [
        dest_dir / filename,
        dest_dir / "video_files" / filename,
        dest_dir / "downloads" / filename,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            try:
                actual_size = p.stat().st_size
                if expected_size and actual_size == expected_size and actual_size > 0:
                    return True, p, "match"
                elif actual_size == 0:
                    return False, p, "empty"
                else:
                    return False, p, "size_mismatch"
            except OSError:
                pass
    return False, None, "not_found"


def extract_media_info(msg) -> Optional[Dict]:
    """Extracts downloadable media metadata from a Telegram Message."""
    if not msg.media:
        return None

    filename = None
    media_type = "Document"
    size = msg.file.size if msg.file else 0

    if getattr(msg.media, "document", None):
        doc = msg.media.document
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name
            elif isinstance(attr, DocumentAttributeVideo):
                media_type = "Video"
            elif isinstance(attr, DocumentAttributeAudio):
                media_type = "Audio"

        if not filename:
            ext = msg.file.ext or ".bin"
            filename = f"telegram_{msg.id}{ext}"
    elif getattr(msg.media, "photo", None):
        media_type = "Photo"
        filename = f"photo_{msg.id}.jpg"
    else:
        return None

    filename = sanitize_filename(filename)
    return {
        "message": msg,
        "id": msg.id,
        "date": msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "N/A",
        "filename": filename,
        "size": size,
        "size_str": format_size(size),
        "type": media_type,
    }


def parse_indices(selection: str, max_count: int) -> List[int]:
    """Parses selection string like 'all', '1,3,5', or '1-4' into 1-based indices."""
    selection = selection.strip().lower()
    if not selection or selection in ("all", "a", "*"):
        return list(range(1, max_count + 1))

    selected = set()
    parts = selection.replace(";", ",").split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                start, end = int(start_str.strip()), int(end_str.strip())
                for i in range(start, end + 1):
                    if 1 <= i <= max_count:
                        selected.add(i)
            except ValueError:
                pass
        else:
            try:
                val = int(part)
                if 1 <= val <= max_count:
                    selected.add(val)
            except ValueError:
                pass

    return sorted(list(selected))


async def login_via_qr(client: TelegramClient):
    """Authenticates using Telegram QR code, bypassing phone flood locks."""
    console.print(
        Panel.fit(
            "[bold cyan]Telegram QR Code Login[/bold cyan]\n\n"
            "1. Open [bold]Telegram[/bold] on your phone or mobile device.\n"
            "   [bold yellow]👉 Tip: If you have multiple accounts, switch to the desired account first![/bold yellow]\n"
            "2. Go to: [bold yellow]Settings ➔ Devices ➔ Link Desktop Device[/bold yellow]\n"
            "3. Scan the QR code below with your camera.",
            title="[bold green]Scan to Log In[/bold green]",
        )
    )

    while True:
        try:
            qr_login = await client.qr_login()
        except Exception as e:
            console.print(f"[bold red]Failed to request QR login: {e}[/bold red]")
            sys.exit(1)

        qr = qrcode.QRCode(border=2)
        qr.add_data(qr_login.url)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        console.print(buf.getvalue())
        console.print(f"[dim]Direct Login Link: [link={qr_login.url}]{qr_login.url}[/link][/dim]\n")
        console.print("[cyan]Waiting for authorization in Telegram mobile app...[/cyan]")

        try:
            await qr_login.wait()
            break
        except asyncio.TimeoutError:
            console.print("[yellow]QR code expired. Refreshing...[/yellow]\n")
            continue
        except errors.SessionPasswordNeededError:
            console.print("\n[bold yellow]Two-Step Verification (2FA) is enabled on your account.[/bold yellow]")
            while True:
                pwd = Prompt.ask("[bold green]Enter your 2FA password[/bold green]", password=True)
                try:
                    await client.sign_in(password=pwd)
                    break
                except errors.PasswordHashInvalidError:
                    console.print("[bold red]Incorrect password! Please try again.[/bold red]")
                except errors.PhonePasswordFloodError:
                    console.print(
                        "[bold red]Telegram password flood lock is active. "
                        "Please wait before trying your password again.[/bold red]"
                    )
                    sys.exit(1)
            break


async def login_telegram(client: TelegramClient, phone: Optional[str] = None):
    """Connects and logs into Telegram via QR code or phone number."""
    await client.connect()
    if await client.is_user_authorized():
        return

    console.print(
        Panel.fit(
            "[bold cyan]Telegram Login Required[/bold cyan]\n\n"
            "Select how you want to log in:\n"
            " [bold green][1] QR Code Login (Recommended)[/bold green]\n"
            "     [dim]• Instant login via Telegram phone app[/dim]\n"
            "     [dim]• Bypasses SMS & PhonePasswordFlood rate limits[/dim]\n\n"
            " [bold green][2] Phone Number[/bold green]\n"
            "     [dim]• Sends SMS / Telegram confirmation code[/dim]",
            title="[bold yellow]Authentication[/bold yellow]",
        )
    )
    choice = Prompt.ask("Choose login method", choices=["1", "2"], default="1")

    if choice == "1":
        await login_via_qr(client)
    else:
        phone_input = Prompt.ask(
            "[bold green]Enter phone number (e.g. +1...)[/bold green]",
            default=phone or "",
        ).strip()
        if phone_input:
            set_key(str(ENV_FILE), "TG_PHONE", phone_input)
            phone = phone_input
        try:
            await client.start(phone=phone)
        except errors.PhonePasswordFloodError:
            console.print(
                "\n[bold red]Telegram Rate Limit Error (PhonePasswordFloodError):[/bold red]\n"
                "[yellow]Telegram has temporarily locked code requests for this phone number "
                "because of previous incorrect 2FA password attempts.[/yellow]\n"
            )
            if Confirm.ask("[bold cyan]Would you like to switch to QR Code login now?[/bold cyan]", default=True):
                await login_via_qr(client)
            else:
                sys.exit(1)


async def select_chat_or_channel(client: TelegramClient, cli_chat: Optional[str] = None) -> Tuple[Any, str]:
    """Selects target chat, channel, group, or Saved Messages."""
    if cli_chat:
        target = str(cli_chat).strip()
        if target.lower() in ("me", "saved", "saved messages"):
            return "me", "Saved Messages"

        # Check integer channel/chat ID (e.g. -1001234567890 or 1234567890)
        if target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
            try:
                entity = await client.get_entity(int(target))
                title = getattr(entity, "title", getattr(entity, "first_name", target))
                return entity, title
            except Exception as e:
                console.print(f"[bold red]Could not find channel/chat with ID {target}: {e}[/bold red]")
        else:
            # Check by username, t.me link, or title
            clean_target = target
            if "t.me/c/" in clean_target:
                # Private channel web link: https://t.me/c/1234567890/123
                parts = clean_target.split("t.me/c/")[1].split("/")
                clean_target = f"-100{parts[0]}"
                try:
                    entity = await client.get_entity(int(clean_target))
                    title = getattr(entity, "title", getattr(entity, "first_name", target))
                    return entity, title
                except Exception:
                    pass
            elif "t.me/" in clean_target:
                clean_target = clean_target.split("t.me/")[1].split("/")[0]

            try:
                entity = await client.get_entity(clean_target)
                title = getattr(entity, "title", getattr(entity, "first_name", target))
                return entity, title
            except Exception:
                # Search by dialog name / title across recent dialogs
                async for d in client.iter_dialogs(limit=100):
                    if d.name.lower() == target.lower():
                        return d.entity, d.name
                console.print(f"[bold red]Could not find channel/chat '{cli_chat}'[/bold red]")

        console.print("[dim]Falling back to interactive channel selection...[/dim]\n")

    console.print("\n[bold cyan]Select Download Source:[/bold cyan]")
    console.print(" [bold green][1][/bold green] 📌 Saved Messages [dim](My Cloud Storage)[/dim]")
    console.print(" [bold green][2][/bold green] 📢 Choose from my Channels & Groups")
    console.print(" [bold green][3][/bold green] 🔗 Enter Channel Username, Link, or ID")

    choice = Prompt.ask("Choose source", choices=["1", "2", "3"], default="1")

    if choice == "1":
        return "me", "Saved Messages"

    if choice == "2":
        with console.status("[cyan]Fetching your channels and groups...[/cyan]", spinner="dots"):
            dialogs = []
            async for d in client.iter_dialogs(limit=50):
                if d.is_channel or d.is_group:
                    dialogs.append(d)

        if not dialogs:
            console.print("[yellow]No channels or groups found on this account. Defaulting to Saved Messages.[/yellow]\n")
            return "me", "Saved Messages"

        console.print("\n[bold cyan]Your Channels & Groups:[/bold cyan]")
        for idx, d in enumerate(dialogs, 1):
            chat_type = "Channel" if d.is_channel else "Group"
            console.print(f" [bold green][{idx}][/bold green] [bold]{d.name}[/bold] [dim]({chat_type})[/dim]")

        d_choice = Prompt.ask(
            "Select channel/group",
            choices=[str(i) for i in range(1, len(dialogs) + 1)],
            default="1",
        )
        selected_dialog = dialogs[int(d_choice) - 1]
        return selected_dialog.entity, selected_dialog.name

    if choice == "3":
        while True:
            target = Prompt.ask("[bold green]Enter Channel username, link, or ID (or 'me')[/bold green]").strip()
            if not target:
                continue
            if target.lower() in ("me", "saved", "saved messages"):
                return "me", "Saved Messages"

            clean_target = target
            if "t.me/c/" in clean_target:
                parts = clean_target.split("t.me/c/")[1].split("/")
                clean_target = f"-100{parts[0]}"
            elif "t.me/" in clean_target:
                clean_target = clean_target.split("t.me/")[1].split("/")[0]

            try:
                if clean_target.isdigit() or (clean_target.startswith("-") and clean_target[1:].isdigit()):
                    entity = await client.get_entity(int(clean_target))
                else:
                    try:
                        entity = await client.get_entity(clean_target)
                    except Exception:
                        found = None
                        async for d in client.iter_dialogs(limit=100):
                            if d.name.lower() == clean_target.lower():
                                found = d
                                break
                        if found:
                            return found.entity, found.name
                        raise
                title = getattr(entity, "title", getattr(entity, "first_name", target))
                return entity, title
            except Exception as e:
                console.print(f"[bold red]Could not find '{target}': {e}. Please try again.[/bold red]")


async def main():
    parser = argparse.ArgumentParser(
        description="Download files from Telegram Channels, Groups, or Saved Messages at maximum speed."
    )
    parser.add_argument(
        "-c", "--channel", "--chat",
        dest="chat",
        help="Channel username, link, title, or ID to download from (default: interactive selection)",
        default=None,
    )
    parser.add_argument(
        "-o", "--output",
        help="Target download folder (e.g. '/Volumes/Hosainy USB')",
        default=None,
    )
    parser.add_argument(
        "-l", "--limit",
        help="Number of recent messages to check (default 50)",
        type=int,
        default=50,
    )
    parser.add_argument(
        "-w", "--workers",
        help="Number of parallel MTProto connections (default 16)",
        type=int,
        default=16,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all detected files without interactive prompt",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files if they already exist in destination",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Log out of the current Telegram session and remove credentials",
    )
    args = parser.parse_args()

    if args.logout:
        session_file = Path(__file__).parent / f"{SESSION_NAME}.session"
        if session_file.exists():
            session_file.unlink()
        for f in Path(__file__).parent.glob(f"{SESSION_NAME}*"):
            try:
                f.unlink()
            except OSError:
                pass

        if ENV_FILE.exists():
            try:
                unset_key(str(ENV_FILE), "TG_PHONE")
            except Exception:
                pass

        console.print(
            Panel.fit(
                "[bold green]✓ Logged out successfully.[/bold green]\n\n"
                "• Session files removed.\n"
                "• Saved phone number cleared.\n\n"
                "[bold yellow]Tip for switching accounts:[/bold yellow]\n"
                "• [bold cyan]QR Code Login:[/bold cyan] Make sure you switch to your desired account in the Telegram mobile app before scanning!\n"
                "• [bold cyan]Phone Number Login:[/bold cyan] Enter the phone number for your other account when prompted.",
                title="[bold]Logged Out[/bold]",
                border_style="green",
            )
        )
        return

    console.print(
        Panel.fit(
            "[bold green]⚡ Telegram High-Speed Terminal Downloader ⚡[/bold green]\n"
            "[dim]Parallel MTProto multi-stream engine + native cryptographic acceleration[/dim]",
            border_style="green",
        )
    )

    # 1. API Credentials
    api_id, api_hash, phone = ensure_env_credentials()

    # 2. Select Output Destination (Flash Card)
    dest_dir = select_destination_folder(args.output)
    console.print(f"[bold green]✓ Destination:[/bold green] [yellow]{dest_dir}[/yellow]")

    # Check available storage
    usage = shutil.disk_usage(str(dest_dir))
    console.print(f"[dim]Available free space on destination: {format_size(usage.free)}[/dim]\n")

    # 3. Connect to Telegram
    session_path = Path(__file__).parent / SESSION_NAME
    client = TelegramClient(str(session_path), api_id, api_hash)

    console.print("[cyan]Connecting to Telegram...[/cyan]")
    await login_telegram(client, phone=phone)
    me = await client.get_me()
    console.print(
        f"[bold green]✓ Logged in as:[/bold green] {me.first_name} "
        f"([dim]@{me.username or me.id}[/dim])\n"
    )

    # 4. Select Download Source (Channel, Group, or Saved Messages)
    target_entity, source_name = await select_chat_or_channel(client, cli_chat=args.chat)
    console.print(f"[bold green]✓ Source:[/bold green] [yellow]{source_name}[/yellow]\n")

    # 5. Fetch media from target entity
    with console.status(
        f"[bold cyan]Scanning last {args.limit} messages from '{source_name}'...[/bold cyan]",
        spinner="dots",
    ):
        messages = await client.get_messages(target_entity, limit=args.limit)
        items = []
        for msg in messages:
            info = extract_media_info(msg)
            if info:
                items.append(info)

    if not items:
        console.print(
            f"[bold yellow]No files or media found in the last {args.limit} messages of '{source_name}'.[/bold yellow]"
        )
        await client.disconnect()
        return

    # Check each file against destination drive for existing name & size
    for item in items:
        is_match, found_path, reason = find_existing_file(dest_dir, item["filename"], item["size"])
        item["is_existing"] = is_match
        item["existing_path"] = found_path
        item["reason"] = reason
        if is_match:
            item["status_str"] = "[bold green]✓ Downloaded[/bold green]"
        elif reason == "empty":
            item["status_str"] = "[dim red]⚠️ Empty (0B)[/dim red]"
        elif reason == "size_mismatch":
            item["status_str"] = "[yellow]⚠️ Incomplete[/yellow]"
        else:
            item["status_str"] = "[yellow]⏳ Pending[/yellow]"

    # 6. Display files table
    table = Table(
        title=f"Files Found in {source_name}",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("File Name", style="bold white", overflow="ellipsis")
    table.add_column("Type", style="cyan", width=8)
    table.add_column("Size", style="green", width=10, justify="right")
    table.add_column("Status", width=14)
    table.add_column("Date", style="dim", width=17)

    for idx, item in enumerate(items, 1):
        table.add_row(
            str(idx),
            item["filename"],
            item["type"],
            item["size_str"],
            item["status_str"],
            item["date"],
        )

    console.print(table)

    pending_items = [idx for idx, item in enumerate(items, 1) if not item["is_existing"]]
    existing_count = len(items) - len(pending_items)

    console.print(
        f"\nFound [bold]{len(items)}[/bold] total files "
        f"([green]{existing_count} already downloaded[/green], "
        f"[bold yellow]{len(pending_items)} pending[/bold yellow])"
    )

    # 7. Select files to download
    if args.all:
        selected_indices = list(range(1, len(items) + 1))
    else:
        default_choice = "new" if pending_items else "all"
        prompt_msg = (
            f"\nEnter files to download [bold]('new' for {len(pending_items)} pending, 'all', '1,3,5', '1-5')[/bold]"
            if pending_items
            else "\nEnter files to download [bold]('all', '1,3,5', '1-5')[/bold]"
        )
        selection_input = Prompt.ask(prompt_msg, default=default_choice).strip().lower()

        if selection_input in ("new", "n"):
            selected_indices = pending_items
            if not selected_indices:
                console.print("[bold green]✓ All files in this chat are already downloaded with matching size![/bold green]")
                await client.disconnect()
                return
        else:
            selected_indices = parse_indices(selection_input, len(items))

    if not selected_indices:
        console.print("[yellow]No files selected. Exiting.[/yellow]")
        await client.disconnect()
        return

    selected_items = [items[i - 1] for i in selected_indices]
    # Filter items that actually need downloading (unless --overwrite is set)
    items_to_download = [it for it in selected_items if args.overwrite or not it["is_existing"]]
    skipped_count = len(selected_items) - len(items_to_download)
    total_download_size = sum(item["size"] for item in items_to_download)

    if skipped_count > 0:
        console.print(
            f"[dim]ℹ Automatically skipping {skipped_count} file(s) that already exist with matching size.[/dim]"
        )

    if not items_to_download:
        console.print("[bold green]✓ All selected files are already downloaded with matching size![/bold green]")
        await client.disconnect()
        return

    console.print(
        f"\n[bold]Selected [cyan]{len(items_to_download)}[/cyan] files to download — "
        f"Total size: [green]{format_size(total_download_size)}[/green][/bold]"
    )

    if usage.free < total_download_size:
        console.print(
            f"[bold red]⚠️ Warning:[/bold red] Free space on destination ({format_size(usage.free)}) "
            f"is less than required download size ({format_size(total_download_size)})!"
        )
        if not Confirm.ask("Do you want to continue anyway?", default=False):
            await client.disconnect()
            return

    # 8. Start Downloads with Live Speed & Progress
    console.print(f"\n[bold green]Starting high-speed download ({args.workers} parallel workers)...[/bold green]\n")

    overall_start_time = time.time()
    total_downloaded_bytes = 0
    success_count = 0

    for i, item in enumerate(items_to_download, 1):
        target_path = dest_dir / item["filename"]

        # Check existing match on disk
        is_match, existing_path, reason = find_existing_file(dest_dir, item["filename"], item["size"])
        if is_match and not args.overwrite:
            rel_name = existing_path.name
            try:
                rel_name = str(existing_path.relative_to(dest_dir))
            except ValueError:
                pass
            console.print(
                f"[bold yellow]⏭ [{i}/{len(items_to_download)}] Skipping:[/bold yellow] "
                f"'{item['filename']}' already exists with matching size ({item['size_str']}) at [cyan]{rel_name}[/cyan]"
            )
            success_count += 1
            continue

        # If a 0-byte placeholder or corrupted file exists at target_path, clean it up
        if target_path.exists() and target_path.stat().st_size == 0:
            try:
                target_path.unlink()
            except OSError:
                pass

        console.print(
            f"[bold cyan][{i}/{len(items_to_download)}][/bold cyan] Downloading: "
            f"[bold white]{item['filename']}[/bold white] ({item['size_str']})"
        )

        file_size = item["size"] or 1
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Downloading", total=file_size)

            def update_progress(current, total):
                progress.update(task_id, completed=current, total=total)

            file_start = time.time()
            try:
                await download_media_fast(
                    client=client,
                    message=item["message"],
                    dest_path=str(target_path),
                    progress_callback=update_progress,
                    connections=args.workers,
                )
                elapsed = max(0.01, time.time() - file_start)
                speed = item["size"] / elapsed
                total_downloaded_bytes += item["size"]
                success_count += 1
                console.print(
                    f"[bold green]✓ Done:[/bold green] Saved to [dim]{target_path.name}[/dim] "
                    f"— [cyan]{format_size(speed)}/s[/cyan] in [cyan]{elapsed:.1f}s[/cyan]\n"
                )
            except errors.FloodWaitError as flood:
                wait_sec = flood.seconds
                wait_min = math.ceil(wait_sec / 60)
                if target_path.exists() and target_path.stat().st_size == 0:
                    try:
                        target_path.unlink()
                    except OSError:
                        pass
                console.print(
                    f"\n[bold red]⚠️ Telegram Rate Limit (FloodWait):[/bold red] Telegram servers require a wait of "
                    f"[bold yellow]{wait_sec} seconds (~{wait_min} minutes)[/bold yellow] "
                    f"for cross-datacenter authorization.\n"
                    f"[dim]Why this happens: Telegram temporarily throttles cross-datacenter connections "
                    f"when transferring multiple files quickly.[/dim]\n"
                )
                if wait_sec <= 60:
                    with console.status(f"[cyan]Waiting {wait_sec}s for rate limit to clear...[/cyan]", spinner="dots"):
                        await asyncio.sleep(wait_sec + 1)
                    # Retry this download
                    try:
                        await download_media_fast(
                            client=client,
                            message=item["message"],
                            dest_path=str(target_path),
                            progress_callback=update_progress,
                            connections=args.workers,
                        )
                        elapsed = max(0.01, time.time() - file_start)
                        speed = item["size"] / elapsed
                        total_downloaded_bytes += item["size"]
                        success_count += 1
                        console.print(
                            f"[bold green]✓ Done:[/bold green] Saved to [dim]{target_path.name}[/dim] "
                            f"— [cyan]{format_size(speed)}/s[/cyan] in [cyan]{elapsed:.1f}s[/cyan]\n"
                        )
                    except Exception as retry_err:
                        console.print(f"[bold red]✗ Failed to download on retry: {retry_err}[/bold red]\n")
                else:
                    console.print(
                        f"[yellow]💡 Tip:[/yellow] Re-run with fewer workers (e.g. [bold]-w 4[/bold]) or download in smaller batches.\n"
                        f"[dim]Download paused. You can re-run after {wait_min} minutes (completed files are skipped automatically).[/dim]\n"
                    )
                    break
            except Exception as exc:
                console.print(f"[bold red]✗ Failed to download {item['filename']}: {exc}[/bold red]\n")
                if target_path.exists() and target_path.stat().st_size == 0:
                    try:
                        target_path.unlink()
                    except OSError:
                        pass

    overall_elapsed = max(0.01, time.time() - overall_start_time)
    avg_speed = total_downloaded_bytes / overall_elapsed

    console.print(
        Panel.fit(
            f"[bold green]✨ All Downloads Completed! ✨[/bold green]\n\n"
            f"• Successfully Processed: [bold]{success_count}/{len(items_to_download)}[/bold] files\n"
            f"• Data Transferred: [bold green]{format_size(total_downloaded_bytes)}[/bold green]\n"
            f"• Total Time: [bold]{overall_elapsed:.1f} seconds[/bold]\n"
            f"• Average Transfer Speed: [bold cyan]{format_size(avg_speed)}/s[/bold cyan]\n"
            f"• Destination Folder: [bold yellow]{dest_dir}[/bold yellow]",
            title="[bold]Summary[/bold]",
            border_style="green",
        )
    )

    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Download cancelled by user.[/bold red]")
        sys.exit(0)
