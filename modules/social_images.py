"""Photo-post support for TikTok slideshows and X/Twitter photo/mixed tweets.

yt-dlp only understands video, so photo posts (TikTok "photo mode" carousels,
X tweets with only pictures) fail in the regular video pipeline. This module
looks them up through public JSON mirrors instead:

* TikTok: tikwm.com returns ``data.images`` for photo posts, plus the
  background sound under ``data.music`` / ``data.music_info``.
* X/Twitter: api.fxtwitter.com (with api.vxtwitter.com as a fallback) returns
  the tweet's media list. Tweets with photos (alone or mixed with videos/GIFs)
  are sent as one album; video-only tweets stay on the yt-dlp path.

The parse_* functions are pure so they can be unit-tested without network.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

from modules.logger import error_logger
from modules.telegram_files import max_upload_bytes

# Telegram allows at most 10 items per media group.
MEDIA_GROUP_LIMIT = 10
# Telegram rejects photo uploads above 10 MB; the video limit depends on the Bot API
# server (50 MB cloud, 2000 MB local), see modules/telegram_files.py.
MAX_PHOTO_BYTES = 10 * 1024 * 1024

_X_HOSTS = (
    "x.com",
    "twitter.com",
    "fixupx.com",
    "fxtwitter.com",
    "vxtwitter.com",
    "fixvx.com",
    "nitter.net",
)
_TIKTOK_HOSTS = ("tiktok.com",)
_STATUS_ID_RE = re.compile(r"/status(?:es)?/(\d+)")

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class PostAudio:
    """Background sound attached to a photo post."""

    url: str
    title: Optional[str] = None
    performer: Optional[str] = None


@dataclass
class MediaItem:
    """One photo or video of a post; ``path`` is set once downloaded."""

    kind: str  # "photo" or "video"
    url: str
    path: Optional[str] = None


@dataclass
class ImagePost:
    """A post with photos (optionally mixed with videos) resolved to direct URLs."""

    platform: str  # "tiktok" or "x"
    media: List[MediaItem]
    title: Optional[str] = None
    audio: Optional[PostAudio] = None

    @property
    def image_urls(self) -> List[str]:
        return [m.url for m in self.media if m.kind == "photo"]

    @property
    def downloaded(self) -> List[MediaItem]:
        return [m for m in self.media if m.path]

    @property
    def paths(self) -> List[str]:
        return [m.path for m in self.media if m.path]


def _host_matches(url: str, hosts: tuple) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in hosts)


def is_x_url(url: str) -> bool:
    return _host_matches(url, _X_HOSTS) and bool(_STATUS_ID_RE.search(url))


def is_tiktok_url(url: str) -> bool:
    return _host_matches(url, _TIKTOK_HOSTS)


def extract_x_status_id(url: str) -> Optional[str]:
    match = _STATUS_ID_RE.search(urlparse(url).path)
    return match.group(1) if match else None


def _x_large_image(url: str) -> str:
    """Request the 'large' rendition (≤2048px) of a pbs.twimg.com image.

    'orig' can exceed Telegram's photo size/dimension limits; the default
    (no name param) is a downscaled 'medium'.
    """
    if "pbs.twimg.com/media/" not in url:
        return url
    base = url.split("?", 1)[0]
    return f"{base}?name=large"


def parse_tikwm_images(data: Dict[str, Any]) -> Optional[ImagePost]:
    """Build an ImagePost from a tikwm ``/api/`` response, or None for videos."""
    if not isinstance(data, dict) or data.get("code") != 0:
        return None
    payload = data.get("data") or {}
    images = [u for u in (payload.get("images") or []) if isinstance(u, str) and u]
    if not images:
        return None

    audio: Optional[PostAudio] = None
    music_info = payload.get("music_info") or {}
    audio_url = payload.get("music") or music_info.get("play")
    if isinstance(audio_url, str) and audio_url:
        audio = PostAudio(
            url=audio_url,
            title=music_info.get("title") or None,
            performer=music_info.get("author") or None,
        )

    return ImagePost(
        platform="tiktok",
        media=[MediaItem("photo", u) for u in images],
        title=(payload.get("title") or "").strip() or None,
        audio=audio,
    )


def _x_post(items: List[MediaItem], text: Any) -> Optional[ImagePost]:
    """Photo tweets (alone or mixed) become a post; video-only/no media → None."""
    if not any(m.kind == "photo" for m in items):
        return None
    return ImagePost(
        platform="x",
        media=items,
        title=(text or "").strip() or None,
    )


def parse_fxtwitter(data: Dict[str, Any]) -> Optional[ImagePost]:
    """Build a post from an api.fxtwitter.com response.

    Returns None when the tweet has no photos — video-only tweets stay on the
    yt-dlp video path. Mixed tweets keep every item in tweet order.
    """
    if not isinstance(data, dict):
        return None
    tweet = data.get("tweet") or {}
    media = tweet.get("media") or {}
    entries = media.get("all") or (
        (media.get("photos") or []) + (media.get("videos") or [])
    )
    items: List[MediaItem] = []
    for entry in entries:
        url = entry.get("url")
        if not url:
            continue
        if entry.get("type") == "photo":
            items.append(MediaItem("photo", _x_large_image(url)))
        elif entry.get("type") in ("video", "gif"):
            items.append(MediaItem("video", url))
    return _x_post(items, tweet.get("text"))


def parse_vxtwitter(data: Dict[str, Any]) -> Optional[ImagePost]:
    """Build a post from an api.vxtwitter.com response."""
    if not isinstance(data, dict):
        return None
    items: List[MediaItem] = []
    for entry in data.get("media_extended") or []:
        url = entry.get("url")
        if not url:
            continue
        if entry.get("type") == "image":
            items.append(MediaItem("photo", _x_large_image(url)))
        elif entry.get("type") in ("video", "gif"):
            items.append(MediaItem("video", url))
    return _x_post(items, data.get("text"))


async def _get_json(url: str, timeout: float = 15) -> Optional[Dict[str, Any]]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"User-Agent": _BROWSER_UA, "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status != 200:
                    error_logger.warning(f"{url} returned HTTP {response.status}")
                    return None
                return await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        error_logger.warning(f"JSON fetch failed for {url}: {e!r}")
        return None


async def fetch_x_image_post(url: str) -> Optional[ImagePost]:
    """Resolve an X/Twitter status URL to its photos (None if not a photo tweet)."""
    status_id = extract_x_status_id(url)
    if not status_id:
        return None
    data = await _get_json(f"https://api.fxtwitter.com/status/{status_id}")
    if data is not None and data.get("code") == 200:
        # fxtwitter answered authoritatively; don't second-guess a video tweet.
        return parse_fxtwitter(data)
    data = await _get_json(f"https://api.vxtwitter.com/Twitter/status/{status_id}")
    return parse_vxtwitter(data) if data else None


# Photos above this size/side are re-encoded before upload: Telegram downscales
# photos to 2560px anyway, and smaller uploads avoid Bot API timeouts.
_PHOTO_MAX_SIDE = 2560
_PHOTO_REENCODE_BYTES = 2 * 1024 * 1024


def _normalize_image(raw: bytes) -> tuple:
    """Return (bytes, ext) ready for sendPhoto.

    JPEG/PNG under the size and dimension caps pass through untouched; anything
    else (WebP/HEIC, oversized, huge dimensions) is re-encoded as a JPEG of at
    most 2560px on the long side.
    """
    is_jpeg = raw[:3] == b"\xff\xd8\xff"
    is_png = raw[:8] == b"\x89PNG\r\n\x1a\n"
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            small_enough = (
                max(img.size) <= _PHOTO_MAX_SIDE and len(raw) <= _PHOTO_REENCODE_BYTES
            )
            if (is_jpeg or is_png) and small_enough:
                return raw, "jpg" if is_jpeg else "png"
            img = img.convert("RGB")
            img.thumbnail((_PHOTO_MAX_SIDE, _PHOTO_MAX_SIDE))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=88, optimize=True)
            return out.getvalue(), "jpg"
    except Exception as e:  # unknown format / no Pillow: let Telegram decide
        error_logger.warning(f"Image conversion failed, sending as-is: {e!r}")
        return raw, "png" if is_png else "jpg"


async def download_media(
    items: List[MediaItem], download_dir: str, prefix: str, referer: Optional[str] = None
) -> None:
    """Download items concurrently, setting ``item.path``; failures stay None."""
    os.makedirs(download_dir, exist_ok=True)
    headers = {"User-Agent": _BROWSER_UA}
    if referer:
        headers["Referer"] = referer
    semaphore = asyncio.Semaphore(4)

    async def fetch_one(session: aiohttp.ClientSession, index: int, item: MediaItem) -> None:
        limit = max_upload_bytes() if item.kind == "video" else MAX_PHOTO_BYTES
        async with semaphore:
            try:
                async with session.get(
                    item.url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120 if item.kind == "video" else 30),
                ) as response:
                    if response.status != 200:
                        error_logger.warning(
                            f"Media {index} download returned HTTP {response.status}"
                        )
                        return
                    if (response.content_length or 0) > limit:
                        error_logger.warning(f"Media {index} too large for Telegram, skipped")
                        return
                    raw = await response.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error_logger.warning(f"Media {index} download failed: {e!r}")
                return
        if not raw:
            return
        if item.kind == "photo":
            raw, ext = await asyncio.to_thread(_normalize_image, raw)
        else:
            ext = "mp4"
        if len(raw) > limit:
            error_logger.warning(f"Media {index} too large for Telegram, skipped")
            return
        path = os.path.join(download_dir, f"{prefix}_{uuid.uuid4().hex[:8]}_{index:02d}.{ext}")
        with open(path, "wb") as f:
            f.write(raw)
        item.path = path

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*(fetch_one(session, i, m) for i, m in enumerate(items)))


async def download_file(url: str, path: str, timeout: float = 60) -> bool:
    """Stream a URL to disk. Returns True when a non-empty file was written."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"User-Agent": _BROWSER_UA},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status != 200:
                    error_logger.warning(f"Download {url[:80]} returned HTTP {response.status}")
                    return False
                with open(path, "wb") as f:
                    async for chunk in response.content.iter_chunked(65536):
                        f.write(chunk)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        error_logger.warning(f"Download {url[:80]} failed: {e!r}")
        return False
    return os.path.exists(path) and os.path.getsize(path) > 0
