"""Upload limits and file inputs that depend on which Bot API server the bot uses.

The bot talks to Telegram's cloud Bot API by default (50 MB uploads). When
``TELEGRAM_API_BASE_URL`` points at a local ``telegram-bot-api`` server running
with ``--local`` (see docs/LOCAL_BOT_API.md), uploads go up to 2000 MB.

Large files must be passed to python-telegram-bot as *paths*, not open file
handles: PTB reads a file handle fully into memory before sending, while in
local mode a path becomes a ``file://`` URI the server reads from disk itself.
"""

import os
from pathlib import Path
from typing import IO, Any, Dict, Union

from telegram import Bot

MB = 1024 * 1024
CLOUD_MAX_UPLOAD_BYTES = 50 * MB
LOCAL_MAX_UPLOAD_BYTES = 2000 * MB


def local_bot_api_url() -> str:
    """Base URL of the local Bot API server (e.g. ``http://telegram-bot-api:8081``), or ""."""
    return os.getenv("TELEGRAM_API_BASE_URL", "").strip().rstrip("/")


def local_bot_api_enabled() -> bool:
    return bool(local_bot_api_url())


def max_upload_bytes() -> int:
    return LOCAL_MAX_UPLOAD_BYTES if local_bot_api_enabled() else CLOUD_MAX_UPLOAD_BYTES


def max_upload_label() -> str:
    return f"{max_upload_bytes() // MB}MB"


def upload_timeouts(file_size: int, write: float = 120, read: float = 60) -> Dict[str, float]:
    """Per-request timeouts for sending a file of ``file_size`` bytes.

    In local mode the bot sends only a file path, then waits while the server
    uploads the file to Telegram, so the read timeout grows with the file
    (assuming at least ~1 MB/s), capped at one hour.
    """
    timeouts: Dict[str, float] = {"write_timeout": write, "read_timeout": read, "connect_timeout": 30}
    if local_bot_api_enabled():
        timeouts["read_timeout"] = min(3600.0, max(read, 60 + file_size / MB))
    return timeouts


def media_input(path: Union[str, Path], bot: Bot) -> Union[Path, IO[bytes]]:
    """File input for ``InputMedia*`` objects.

    PTB turns a path inside ``InputMedia`` into a ``file://`` URI regardless of
    mode, which the cloud API rejects, so only use paths in local mode. The
    caller must close the returned handle when it is a file object.
    """
    if getattr(bot, "local_mode", False):
        return Path(path)
    return open(path, "rb")


def close_media_input(handle: Any) -> None:
    close = getattr(handle, "close", None)
    if callable(close):
        close()
