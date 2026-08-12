"""Persistent URL to Telegram media file_id cache."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Literal, Optional, TypedDict
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

_CAP = 1000
MediaKind = Literal["video", "photo"]
_HOST_ALIASES = {
    "twitter.com": "x.com",
    "fxtwitter.com": "x.com",
    "fixupx.com": "x.com",
    "d.fixupx.com": "x.com",
    "toinstagram.com": "instagram.com",
}


class VideoCacheEntry(TypedDict):
    file_id: str
    title: Optional[str]
    media_kind: MediaKind
    stored_at: str


def normalize_url(url: str) -> str:
    """Return the stable cache key for a downloaded media URL."""
    raw = url.strip().strip("\\")
    try:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        host = _HOST_ALIASES.get(host, host)
        path = parsed.path.rstrip("/")

        if host in {"youtube.com", "m.youtube.com"} and path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if video_id:
                return f"https://youtube.com/watch?v={video_id}"
            return f"https://youtube.com/watch?{parsed.query}"
        if host == "youtube.com" and path.startswith("/shorts/"):
            video_id = path.split("/", 3)[2]
            if video_id:
                return f"https://youtube.com/watch?v={video_id}"
        if host == "youtu.be":
            parts = [part for part in path.split("/") if part]
            video_id = (
                parts[1]
                if len(parts) > 1 and parts[0] == "shorts"
                else (parts[0] if parts else "")
            )
            if video_id:
                return f"https://youtube.com/watch?v={video_id}"
        return f"https://{host}{path}" if host else raw
    except Exception:
        return raw


class VideoCache:
    """Fail-safe persistent mapping of normalized URL to Telegram media."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._data: Dict[str, VideoCacheEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                self._data = data
            else:
                self._data = {}
        except Exception as error:
            logger.warning("VideoCache: load failed (%s), starting empty", error)
            self._data = {}

    def _save(self) -> None:
        tmp = str(self._path) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as file:
                json.dump(self._data, file, ensure_ascii=False)
            os.replace(tmp, self._path)
        except Exception as error:
            logger.warning("VideoCache: save failed: %s", error)

    def get(self, url: str) -> Optional[VideoCacheEntry]:
        try:
            entry = self._data.get(normalize_url(url))
            if not isinstance(entry, dict):
                return None
            if (
                not isinstance(entry.get("file_id"), str)
                or not entry["file_id"]
                or entry.get("media_kind") not in ("video", "photo")
                or not isinstance(entry.get("stored_at"), str)
                or (
                    entry.get("title") is not None
                    and not isinstance(entry["title"], str)
                )
            ):
                return None
            return entry
        except Exception as error:
            logger.warning("VideoCache: get failed: %s", error)
            return None

    def set(
        self, url: str, file_id: str, title: Optional[str], media_kind: MediaKind
    ) -> None:
        if (
            not isinstance(file_id, str)
            or not file_id
            or media_kind not in ("video", "photo")
        ):
            return
        try:
            self._data[normalize_url(url)] = {
                "file_id": file_id,
                "title": title,
                "media_kind": media_kind,
                "stored_at": datetime.utcnow().isoformat(),
            }
            if len(self._data) > _CAP:
                oldest = sorted(
                    self._data.items(), key=lambda item: item[1].get("stored_at", "")
                )
                for old_url, _ in oldest[: len(self._data) - _CAP]:
                    del self._data[old_url]
            self._save()
        except Exception as error:
            logger.warning("VideoCache: set failed: %s", error)

    def evict(self, url: str) -> None:
        try:
            key = normalize_url(url)
            if key in self._data:
                del self._data[key]
                self._save()
        except Exception as error:
            logger.warning("VideoCache: evict failed: %s", error)
