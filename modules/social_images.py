"""Photo-post support for TikTok slideshows and X/Twitter image tweets.

yt-dlp only understands video, so photo posts (TikTok "photo mode" carousels,
X tweets with only pictures) fail in the regular video pipeline. This module
looks them up through public JSON mirrors instead:

* TikTok: tikwm.com returns ``data.images`` for photo posts, plus the
  background sound under ``data.music`` / ``data.music_info``.
* X/Twitter: api.fxtwitter.com (with api.vxtwitter.com as a fallback) returns
  the tweet's media list.

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

# Telegram allows at most 10 items per media group.
MEDIA_GROUP_LIMIT = 10
# Telegram rejects photo uploads above 10 MB.
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
class ImagePost:
    """A photo-only post resolved to direct image URLs."""

    platform: str  # "tiktok" or "x"
    image_urls: List[str]
    title: Optional[str] = None
    audio: Optional[PostAudio] = None
    paths: List[str] = field(default_factory=list)


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
        image_urls=images,
        title=(payload.get("title") or "").strip() or None,
        audio=audio,
    )


def parse_fxtwitter(data: Dict[str, Any]) -> Optional[ImagePost]:
    """Build an ImagePost from an api.fxtwitter.com response.

    Returns None when the tweet has no photos or contains video/GIF media —
    those stay on the yt-dlp video path.
    """
    if not isinstance(data, dict):
        return None
    tweet = data.get("tweet") or {}
    media = tweet.get("media") or {}
    if media.get("videos"):
        return None
    photos = media.get("photos") or [
        m for m in (media.get("all") or []) if m.get("type") == "photo"
    ]
    urls = [_x_large_image(p["url"]) for p in photos if p.get("url")]
    if not urls:
        return None
    return ImagePost(
        platform="x",
        image_urls=urls,
        title=(tweet.get("text") or "").strip() or None,
    )


def parse_vxtwitter(data: Dict[str, Any]) -> Optional[ImagePost]:
    """Build an ImagePost from an api.vxtwitter.com response."""
    if not isinstance(data, dict):
        return None
    media = data.get("media_extended") or []
    if any(m.get("type") in ("video", "gif") for m in media):
        return None
    urls = [
        _x_large_image(m["url"])
        for m in media
        if m.get("type") == "image" and m.get("url")
    ]
    if not urls:
        return None
    return ImagePost(
        platform="x",
        image_urls=urls,
        title=(data.get("text") or "").strip() or None,
    )


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


def _normalize_image(raw: bytes) -> tuple:
    """Return (bytes, ext); converts formats Telegram photos dislike to JPEG."""
    if raw[:3] == b"\xff\xd8\xff":
        return raw, "jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw, "png"
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            out = io.BytesIO()
            img.convert("RGB").save(out, format="JPEG", quality=92)
            return out.getvalue(), "jpg"
    except Exception as e:  # unknown format: let Telegram decide
        error_logger.warning(f"Image conversion failed, sending as-is: {e!r}")
        return raw, "jpg"


async def download_images(
    image_urls: List[str], download_dir: str, prefix: str, referer: Optional[str] = None
) -> List[str]:
    """Download images concurrently, preserving order. Failed items are skipped."""
    os.makedirs(download_dir, exist_ok=True)
    headers = {"User-Agent": _BROWSER_UA}
    if referer:
        headers["Referer"] = referer
    semaphore = asyncio.Semaphore(4)

    async def fetch_one(session: aiohttp.ClientSession, index: int, src: str) -> Optional[str]:
        async with semaphore:
            try:
                async with session.get(
                    src, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_logger.warning(
                            f"Image {index} download returned HTTP {response.status}"
                        )
                        return None
                    raw = await response.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error_logger.warning(f"Image {index} download failed: {e!r}")
                return None
        if not raw:
            return None
        data, ext = await asyncio.to_thread(_normalize_image, raw)
        path = os.path.join(download_dir, f"{prefix}_{uuid.uuid4().hex[:8]}_{index:02d}.{ext}")
        with open(path, "wb") as f:
            f.write(data)
        return path

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *(fetch_one(session, i, u) for i, u in enumerate(image_urls))
        )
    return [p for p in results if p]


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
