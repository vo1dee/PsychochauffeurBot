import asyncio
import random
import os
import logging
import aiohttp
import re
import json
import base64
import html as html_lib
import uuid
import shutil
import subprocess
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from typing import Optional, Tuple, List, Dict, Any, Callable, TypedDict, cast
from asyncio import Semaphore
from dataclasses import dataclass
from enum import Enum
from telegram import (
    Update,
    InlineQueryResultCachedAudio,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters, InlineQueryHandler
from modules.const import (
    VideoPlatforms,
    InstagramConfig,
    MUSIC_DIR,
    SONG_CACHE_PATH,
    SONG_CACHE_CHAT_ID,
    SONG_CACHE_THREAD_ID,
)
from modules.song_cache import SongCache
from modules.utils import extract_urls
from modules.logger import (
    TelegramErrorHandler,
    general_logger,
    chat_logger,
    error_logger,
    init_telegram_error_handler,
    shutdown_logging,  # Import new functions
)
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
YTDL_SERVICE_API_KEY = os.getenv("YTDL_SERVICE_API_KEY")


class DownloadStrategy(TypedDict):
    name: str
    format: str
    args: List[str]


class Platform(Enum):
    TIKTOK = "tiktok.com"
    OTHER = "other"


@dataclass
class DownloadConfig:
    format: str
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    max_height: Optional[int] = None
    max_retries: int = 3
    extra_args: Optional[List[str]] = None


class VideoDownloader:
    ERROR_STICKERS = [
        "CAACAgQAAxkBAAExX39nn7xI2ENP9ev7Ib1-0GCV0TcFvwACNxUAAn_QmFB67ToFiTpdgTYE",
        "CAACAgQAAxkBAAExX31nn7xByvIhPZHPreVkPONIn82IKgACgxcAAuYrIFHS_QFCSfHYGTYE",
    ]

    @staticmethod
    def _compose_display_title(meta: dict) -> tuple:
        """Return (display_title, performer, webpage_url) from yt-dlp JSON metadata."""
        import re as _re

        def clean(s):
            return s.strip() if isinstance(s, str) else None

        def drop_artist_prefix(
            artist_name: Optional[str], track_name: Optional[str]
        ) -> Optional[str]:
            """Remove duplicated artist prefix from track title."""
            if not artist_name or not track_name:
                return track_name
            pattern = rf"^\s*{_re.escape(artist_name)}\s*[-–—:]\s*(.+)$"
            match = _re.match(pattern, track_name, flags=_re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return track_name

        def collapse_duplicate_title_artist_prefix(title_name: str) -> str:
            """Collapse titles like 'Artist - Artist - Song' to 'Artist - Song'."""
            parts = [p.strip() for p in title_name.split(" - ")]
            while (
                len(parts) >= 3
                and parts[0]
                and parts[1]
                and parts[0].casefold() == parts[1].casefold()
            ):
                parts = [parts[0]] + parts[2:]
            return " - ".join(parts)

        artist = clean(meta.get("artist"))
        track = clean(meta.get("track"))
        title = clean(meta.get("title")) or ""
        uploader = clean(meta.get("uploader")) or ""
        webpage_url = clean(meta.get("webpage_url")) or ""

        # Normalize unicode dashes in title
        title = _re.sub(r"[–—]", " - ", title)

        # Strip common trailing noise from title
        _noise = [
            r"\s*\(Official\s+(?:Music\s+)?Video\)",
            r"\s*\[Official\s+(?:Music\s+)?Video\]",
            r"\s*\(Official\s+Audio\)",
            r"\s*\[Official\s+Audio\]",
            r"\s*\(Lyric\s+Video\)",
            r"\s*\[Lyric\s+Video\]",
            r"\s*\(HD\)",
            r"\s*\[HD\]",
            r"\s*\(4K\)",
            r"\s*\[4K\]",
            r"\s*\(Remastered(?:\s+\d+)?\)",
            r"\s*\[Remastered(?:\s+\d+)?\]",
            r"\s*\(Explicit\)",
            r"\s*\[Explicit\]",
        ]
        for pattern in _noise:
            title = _re.sub(pattern, "", title, flags=_re.IGNORECASE).strip()
        title = collapse_duplicate_title_artist_prefix(title)

        # Strip ' - Topic' / 'VEVO' from uploader
        uploader_clean = _re.sub(
            r"\s*-\s*Topic\s*$", "", uploader, flags=_re.IGNORECASE
        ).strip()
        uploader_clean = (
            _re.sub(r"VEVO\s*$", "", uploader_clean, flags=_re.IGNORECASE).strip()
            or uploader_clean
        )

        # Priority 1: structured artist + track fields
        if artist and track:
            track = drop_artist_prefix(artist, track)
            display = f"{artist} - {track}"
            return display, artist, webpage_url

        # Priority 2: split on ' - ' in the cleaned title
        if " - " in title:
            left, right = title.rsplit(" - ", 1)
            left, right = left.strip(), right.strip()
            if left and right:
                display = f"{left} - {right}"
                return display, left, webpage_url

        # Priority 3: uploader + title
        if uploader_clean and title:
            title = drop_artist_prefix(uploader_clean, title) or title
            display = f"{uploader_clean} - {title}"
            return display, uploader_clean, webpage_url

        display = title or uploader_clean or "Audio"
        return display, None, webpage_url

    @staticmethod
    def _normalize_telegram_audio_metadata(
        title: Optional[str], performer: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """Ensure Telegram audio card doesn't duplicate performer in title."""
        normalized_title = (title or "Audio").strip() or "Audio"
        normalized_performer = (
            performer.strip() if isinstance(performer, str) else performer
        )
        if normalized_performer:
            pattern = rf"^\s*{re.escape(normalized_performer)}\s*[-–—:]\s*(.+)$"
            match = re.match(pattern, normalized_title, flags=re.IGNORECASE)
            if match:
                normalized_title = match.group(1).strip() or normalized_title
        return normalized_title, normalized_performer

    def __init__(
        self,
        download_path: str = "downloads",
        extract_urls_func: Optional[Callable[..., Any]] = None,
        config_manager: Optional[Any] = None,
    ) -> None:
        self.supported_platforms = VideoPlatforms.SUPPORTED_PLATFORMS
        self.download_path = os.path.abspath(download_path)
        self.extract_urls = extract_urls_func
        self.config_manager = config_manager

        # Check if extract_urls_func is callable
        if self.extract_urls is None or not callable(self.extract_urls):
            error_logger.error("extract_urls_func is not provided or not callable.")
            raise ValueError("extract_urls_func must be a callable function.")

        self.yt_dlp_path = self._get_yt_dlp_path()

        # Service configuration - use environment variables with fallback
        self.service_url = os.getenv("YTDL_SERVICE_URL", "https://ytdl.vo1dee.com")
        self.api_key = os.getenv("YTDL_SERVICE_API_KEY")
        self.max_retries = int(os.getenv("YTDL_MAX_RETRIES", "3"))
        self.retry_delay = int(os.getenv("YTDL_RETRY_DELAY", "1"))

        # Log service configuration
        error_logger.info(f"Service URL: {self.service_url}")
        error_logger.info(f"API Key present: {bool(self.api_key)}")

        self._init_download_path()
        self._verify_yt_dlp()
        self._download_semaphore = Semaphore(3)  # Allow up to 3 concurrent downloads
        self.last_download: Dict[str, Any] = {}

        # Song file_id cache (persists across restarts)
        self.song_cache = SongCache(SONG_CACHE_PATH)
        # Background caching state
        self._bg_tasks: set = set()
        self._inflight: Dict[str, Any] = {}  # video_id -> asyncio.Task
        self._bg_semaphore = Semaphore(2)

        # Platform-specific download configurations
        self.platform_configs = {
            Platform.TIKTOK: DownloadConfig(
                # Prioritize best video + best audio combination, fallback to best single file
                format="best[height<=1080][ext=mp4]/best",
                max_retries=3,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                },
                extra_args=[
                    "--merge-output-format",
                    "mp4",  # Ensure MP4 output
                    "--impersonate",
                    "chrome",  # Use browser impersonation to bypass bot detection
                    "--extractor-args",
                    "TikTok:api_hostname=vm.tiktok.com",
                    "--add-header",
                    "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "--add-header",
                    "Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "--add-header",
                    "Accept-Language:en-US,en;q=0.9",
                    "--add-header",
                    "Accept-Encoding:gzip, deflate, br",
                    "--add-header",
                    "DNT:1",
                    "--add-header",
                    "Connection:keep-alive",
                    "--add-header",
                    "Upgrade-Insecure-Requests:1",
                    "--add-header",
                    "Sec-Fetch-Dest:document",
                    "--add-header",
                    "Sec-Fetch-Mode:navigate",
                    "--add-header",
                    "Sec-Fetch-Site:none",
                    "--add-header",
                    "Sec-Fetch-User:?1",
                    "--add-header",
                    "Cache-Control:max-age=0",
                ],
            ),
            Platform.OTHER: DownloadConfig(
                format="best[ext=mp4][vcodec~='^avc1'][height<=1080]/best[ext=mp4][vcodec*=avc1][height<=1080]/22[height<=720]/18[height<=360]/best[ext=mp4][height<=1080]/best[ext=mp4]/best",  # H.264 + YouTube specific formats
                extra_args=[
                    "--merge-output-format",
                    "mp4",  # Ensure MP4 output
                ],
            ),
        }

        # Special configuration for YouTube Shorts - with bot detection avoidance
        self.youtube_shorts_config = DownloadConfig(
            format="18/best[ext=mp4]/best",  # Start with format 18 (360p MP4) which is almost always available
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            extra_args=[
                "--ignore-errors",  # Continue on errors
                "--ignore-config",  # Ignore system-wide config
                "--no-playlist",  # Don't download playlists
                "--geo-bypass",  # Try to bypass geo-restrictions
                "--socket-timeout",
                "30",  # Increased timeout for better reliability
                "--retries",
                "3",  # Reduced retries for faster response
                "--fragment-retries",
                "3",  # Reduced fragment retries
                "--merge-output-format",
                "mp4",  # Ensure MP4 output
                "--user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--referer",
                "https://www.youtube.com/",
                "--add-header",
                "Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "--add-header",
                "Accept-Language:en-US,en;q=0.9",
                "--extractor-args",
                "youtube:player_client=web",  # Use web client
            ],
        )

        # Configuration for YouTube clips - simplified for iOS compatibility
        self.youtube_clips_config = DownloadConfig(
            format="best[ext=mp4][vcodec~='^avc1'][height<=1080]/best[ext=mp4][vcodec*=avc1][height<=1080]/22/18/best[ext=mp4][height<=1080]/best[ext=mp4]/best",  # H.264 first
            extra_args=[
                "--ignore-errors",
                "--ignore-config",
                "--no-playlist",
                "--geo-bypass",
                "--socket-timeout",
                "10",
                "--merge-output-format",
                "mp4",  # Ensure MP4 output
            ],
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment variable or file."""
        # First try environment variable
        api_key = os.getenv("YTDL_SERVICE_API_KEY")
        if api_key:
            return api_key

        # If not in env, try local file
        try:
            api_key_path = "/opt/ytdl_service/api_key.txt"
            if os.path.exists(api_key_path):
                with open(api_key_path, "r") as f:
                    return f.read().strip()
        except Exception as e:
            error_logger.error(f"Failed to read API key file: {str(e)}")

        error_logger.warning("No API key found in environment or file")
        return None

    async def _check_service_health(self) -> bool:
        """Check if the download service is available."""
        if not self.service_url or not self.api_key:
            error_logger.error(
                "Service health check failed: URL or API key not configured."
            )
            error_logger.error(f"   YTDL_SERVICE_URL: {self.service_url}")
            error_logger.error(
                f"   YTDL_SERVICE_API_KEY: {'***' + self.api_key[-4:] if self.api_key and len(self.api_key) > 4 else 'Not set'}"
            )
            return False

        health_url = urljoin(self.service_url, "health")
        headers = {"X-API-Key": self.api_key}

        error_logger.info(f"Checking service health at: {health_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_url, headers=headers, timeout=5, ssl=False
                ) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            error_logger.info("✅ Service health check successful.")
                            error_logger.info(
                                f"   Service status: {data.get('status', 'unknown')}"
                            )
                            error_logger.info(
                                f"   yt-dlp version: {data.get('yt_dlp_version', 'unknown')}"
                            )
                            error_logger.info(
                                f"   FFmpeg available: {data.get('ffmpeg_available', 'unknown')}"
                            )
                            return True
                        except Exception as json_error:
                            error_logger.warning(
                                f"Service responded 200 but JSON parsing failed: {json_error}"
                            )
                            return True  # Still consider it healthy if it responds
                    else:
                        response_text = await response.text()
                        error_logger.warning(
                            f"❌ Service health check failed with status {response.status}"
                        )
                        error_logger.warning(f"   Response: {response_text[:200]}...")
                        return False
        except aiohttp.ClientConnectorError as e:
            error_logger.error(f"❌ Service health check - connection failed: {e}")
            error_logger.error(
                f"   This usually means the service is not running or not accessible"
            )
            return False
        except asyncio.TimeoutError:
            error_logger.error(f"❌ Service health check - timeout after 5 seconds")
            error_logger.error(f"   Service may be overloaded or network is slow")
            return False
        except Exception as e:
            error_logger.error(f"❌ Service health check - unexpected error: {e}")
            return False

    async def _download_from_service(
        self,
        url: str,
        format: str = "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best[ext=mp4]",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download video using the local service with enhanced retry logic."""
        if not self.service_url or not self.api_key:
            error_logger.warning(
                "Skipping service download: no service URL or API key configured."
            )
            return None, None

        headers = {"X-API-Key": self.api_key}
        download_url = urljoin(self.service_url, "download")

        error_logger.info(f"🔄 Attempting service download for: {url}")
        error_logger.info(f"   Service URL: {download_url}")
        error_logger.info(f"   Format: {format}")

        # Detect Instagram URLs for enhanced retry logic
        is_instagram = "instagram.com" in url.lower()
        max_attempts = InstagramConfig.MAX_RETRIES if is_instagram else self.max_retries

        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(max_attempts):
                    error_logger.info(f"   Attempt {attempt + 1}/{max_attempts}")

                    # Use different payload for Instagram on retries
                    if is_instagram and attempt > 0:
                        # Try different format strings for Instagram retries
                        retry_formats = [
                            format,  # Original format
                            "best[ext=mp4]/best",  # Simpler format
                            "bestvideo+bestaudio/best",  # More explicit
                            "best[ext=mp4][height<=720]/best[ext=mp4]/best",  # Lower quality fallback
                        ]
                        current_format = retry_formats[
                            min(attempt - 1, len(retry_formats) - 1)
                        ]
                        payload = {"url": url, "format": current_format}
                        error_logger.info(f"   Using retry format: {current_format}")
                    else:
                        payload = {"url": url, "format": format}

                    try:
                        async with session.post(
                            download_url,
                            json=payload,
                            headers=headers,
                            timeout=120,
                            ssl=False,
                        ) as response:
                            error_logger.info(f"   Response status: {response.status}")

                            if response.status == 200:
                                data = await response.json()
                                error_logger.info(
                                    f"   Service response: success={data.get('success')}, status={data.get('status')}"
                                )

                                if data.get("success"):
                                    if data.get("status") == "processing":
                                        error_logger.info(
                                            f"   Background processing started, download_id: {data.get('download_id')}"
                                        )
                                        return await self._poll_service_for_completion(
                                            session, data["download_id"], headers
                                        )
                                    else:
                                        error_logger.info(
                                            f"   Direct download completed: {data.get('title', 'Unknown title')}"
                                        )
                                        return await self._fetch_service_file(
                                            session, data, headers
                                        )
                                else:
                                    error_message = data.get("error", "Unknown error")
                                    error_logger.error(
                                        f"   Service reported failure: {error_message}"
                                    )

                                    # For Instagram, continue retrying on certain errors
                                    if is_instagram and any(
                                        keyword in error_message.lower()
                                        for keyword in InstagramConfig.RETRY_ERROR_PATTERNS
                                    ):
                                        error_logger.info(
                                            f"   Instagram-specific error detected, will retry: {error_message}"
                                        )
                                        if attempt < max_attempts - 1:
                                            await asyncio.sleep(
                                                self._calculate_retry_delay(
                                                    attempt, is_instagram
                                                )
                                            )
                                            continue
                                    return None, None
                            elif response.status in [502, 503, 504]:
                                error_logger.warning(
                                    f"   Service unavailable (HTTP {response.status}). Retrying in {self._calculate_retry_delay(attempt, is_instagram)}s..."
                                )
                                await asyncio.sleep(
                                    self._calculate_retry_delay(attempt, is_instagram)
                                )
                            elif response.status == 403:
                                error_logger.error(
                                    f"   Authentication failed (HTTP 403) - check API key"
                                )
                                return None, None
                            elif response.status == 429:  # Rate limiting
                                retry_delay = (
                                    self._calculate_retry_delay(attempt, is_instagram)
                                    * 2
                                )
                                error_logger.warning(
                                    f"   Rate limited (HTTP 429). Retrying in {retry_delay}s..."
                                )
                                await asyncio.sleep(retry_delay)
                            else:
                                response_text = await response.text()
                                error_logger.error(
                                    f"   Service download failed with status {response.status}"
                                )
                                error_logger.error(
                                    f"   Response: {response_text[:200]}..."
                                )

                                # For Instagram, retry on certain HTTP errors
                                if is_instagram and response.status in [400, 404, 500]:
                                    if attempt < max_attempts - 1:
                                        await asyncio.sleep(
                                            self._calculate_retry_delay(
                                                attempt, is_instagram
                                            )
                                        )
                                        continue
                                return None, None
                    except aiohttp.ClientConnectorError as e:
                        error_logger.error(
                            f"   Connection error on attempt {attempt + 1}: {e}"
                        )
                        if attempt < max_attempts - 1:
                            retry_delay = self._calculate_retry_delay(
                                attempt, is_instagram
                            )
                            error_logger.info(f"   Retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                    except asyncio.TimeoutError:
                        error_logger.error(
                            f"   Timeout on attempt {attempt + 1} (120s limit)"
                        )
                        if attempt < max_attempts - 1:
                            retry_delay = self._calculate_retry_delay(
                                attempt, is_instagram
                            )
                            error_logger.info(f"   Retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                    except Exception as e:
                        error_logger.error(
                            f"   Unexpected error on attempt {attempt + 1}: {e}"
                        )
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(
                                self._calculate_retry_delay(attempt, is_instagram)
                            )
        except Exception as e:
            error_logger.error(f"❌ Service session creation failed: {e}")
            return None, None

        error_logger.error(f"❌ All service download attempts failed for: {url}")
        return None, None

    def _calculate_retry_delay(self, attempt: int, is_instagram: bool = False) -> float:
        """Calculate retry delay with exponential backoff, longer for Instagram."""
        if is_instagram:
            base_delay = InstagramConfig.RETRY_DELAY_BASE
            multiplier = InstagramConfig.RETRY_BACKOFF_MULTIPLIER
            max_delay = InstagramConfig.MAX_RETRY_DELAY
        else:
            base_delay = self.retry_delay
            multiplier = 2.0  # Default backoff multiplier
            max_delay = 30  # Default max delay

        # Exponential backoff: base_delay * (multiplier ^ attempt)
        delay = base_delay * (multiplier**attempt)

        # Cap maximum delay
        return min(delay, max_delay)

    async def _poll_service_for_completion(
        self, session: aiohttp.ClientSession, download_id: str, headers: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Poll the service for download completion."""
        if not self.service_url:
            return None, None
        status_url = urljoin(self.service_url, f"status/{download_id}")
        for _ in range(60):  # Poll for up to 5 minutes
            await asyncio.sleep(5)
            try:
                async with session.get(status_url, headers=headers) as status_response:
                    if status_response.status == 200:
                        status_data = await status_response.json()
                        if status_data.get("status") == "completed":
                            return await self._fetch_service_file(
                                session, status_data, headers
                            )
                        elif status_data.get("status") == "failed":
                            error_logger.error(
                                f"Background download failed: {status_data.get('error')}"
                            )
                            return None, None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error_logger.error(f"Polling failed: {e}")
                return None, None
        error_logger.error("Background download timed out.")
        return None, None

    async def _fetch_service_file(
        self,
        session: aiohttp.ClientSession,
        data: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Fetch the downloaded file from the service."""
        service_file_path = data.get("file_path")
        if not service_file_path or not self.service_url:
            return None, None

        file_url = urljoin(
            self.service_url, f"files/{os.path.basename(service_file_path)}"
        )
        local_file = os.path.join(
            self.download_path, os.path.basename(service_file_path)
        )

        try:
            async with session.get(file_url, headers=headers) as file_response:
                if file_response.status == 200:
                    with open(local_file, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(8192):
                            f.write(chunk)
                    video_title = data.get("title", "Video")
                    return local_file, video_title
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error_logger.error(f"File fetch failed: {e}")
        return None, None

    async def download_video(
        self, url: str, chat_id: Optional[str] = None, chat_type: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        async with self._download_semaphore:
            try:
                url = url.strip().strip("\\")
                if self._is_story_url(url):
                    error_logger.info(f"Story URL detected and skipped: {url}")
                    return None, None

                # Get video config to determine download path
                video_config = await self._get_video_config(chat_id, chat_type)
                current_download_path = video_config.get(
                    "video_path", self.download_path
                )
                current_download_path = os.path.abspath(current_download_path)

                # Ensure the download directory exists
                os.makedirs(current_download_path, exist_ok=True)

                platform = self._get_platform(url)
                is_youtube_shorts = "youtube.com/shorts" in url.lower()
                is_youtube_clips = "youtube.com/clip" in url.lower()
                is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
                parsed_url = urlparse(url)
                host = parsed_url.hostname or ""
                is_instagram = host == "instagram.com" or host.endswith(
                    ".instagram.com"
                )

                # Prioritize service for YouTube, Instagram, and other problematic platforms
                if is_youtube or is_instagram:
                    error_logger.info(
                        f"🎬 Processing {'YouTube' if is_youtube else 'Instagram'} URL: {url}"
                    )
                    error_logger.info(
                        f"   URL type: {'Shorts' if is_youtube_shorts else 'Clips' if is_youtube_clips else 'Regular'}"
                    )

                    # Try service first
                    error_logger.info(f"🔧 Checking service availability...")
                    if await self._check_service_health():
                        result = await self._download_from_service(url)
                        if result and result[0]:
                            error_logger.info(
                                f"✅ Service download successful for: {url}"
                            )
                            return result
                        else:
                            error_logger.warning(
                                f"⚠️ Service download failed for: {url}, falling back to direct strategies"
                            )
                    else:
                        error_logger.warning(
                            f"⚠️ Service unavailable for: {url}, using direct strategies"
                        )

                # For TikTok, use direct download
                if platform == Platform.TIKTOK:
                    return await self._download_tiktok_ytdlp(url)

                # For YouTube, try multiple strategies
                if is_youtube:
                    return await self._download_youtube_with_strategies(
                        url, is_youtube_shorts, is_youtube_clips
                    )

                # For Instagram, try multiple strategies
                if is_instagram:
                    return await self._download_instagram_with_strategies(url)

                # For other platforms, use direct download
                config = self.platform_configs.get(platform)
                return await self._download_generic(
                    url, platform, config, current_download_path
                )

            except Exception as e:
                error_logger.error(f"Download error for {url}: {e}")
                return None, None

    async def _download_youtube_with_strategies(
        self, url: str, is_shorts: bool = False, is_clips: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download YouTube video using multiple fallback strategies."""
        error_logger.info(
            f"🎯 Starting YouTube download with multiple strategies for: {url}"
        )
        error_logger.info(
            f"   Type: {'Shorts' if is_shorts else 'Clips' if is_clips else 'Regular'}"
        )

        # Define strategies in order of preference (Android client works best based on testing)
        strategies = [
            {
                "name": "Android client with simple formats",
                "format": "18/22/best[ext=mp4]/best",
                "args": [
                    "--user-agent",
                    "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip",
                    "--extractor-args",
                    "youtube:player_client=android",
                    "--sleep-interval",
                    "1",
                    "--max-sleep-interval",
                    "3",
                ],
            },
            {
                "name": "iOS client with H.264",
                "format": "bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/18/22/best",
                "args": [
                    "--user-agent",
                    "com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)",
                    "--extractor-args",
                    "youtube:player_client=ios",
                ],
            },
            {
                "name": "Web client with headers",
                "format": "18/22/best[ext=mp4]/best",
                "args": [
                    "--user-agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "--referer",
                    "https://www.youtube.com/",
                    "--extractor-args",
                    "youtube:player_client=web",
                    "--sleep-interval",
                    "1",
                    "--max-sleep-interval",
                    "3",
                ],
            },
            {
                "name": "TV client fallback",
                "format": "best[ext=mp4]/best",
                "args": [
                    "--extractor-args",
                    "youtube:player_client=tv_embedded",
                ],
            },
            {
                "name": "Any format fallback",
                "format": "best",
                "args": [
                    "--user-agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ],
            },
            {
                "name": "HLS stream (m3u8) fallback",
                "format": "best[protocol=m3u8_native]/best[protocol=m3u8]",
                "args": [],
            },
        ]

        # Try each strategy
        for i, strategy in enumerate(strategies, 1):
            error_logger.info(f"📋 Strategy {i}/{len(strategies)}: {strategy['name']}")

            try:
                result = await self._try_youtube_strategy(url, strategy)
                if result and result[0]:
                    error_logger.info(f"✅ Strategy '{strategy['name']}' succeeded!")
                    return result
                else:
                    error_logger.warning(f"❌ Strategy '{strategy['name']}' failed")
            except Exception as e:
                error_logger.error(f"❌ Strategy '{strategy['name']}' error: {e}")

        error_logger.error(f"❌ All YouTube strategies failed for {url}")
        return None, None

    async def _download_instagram_with_strategies(
        self, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download Instagram video using multiple fallback strategies."""
        error_logger.info(
            f"📸 Starting Instagram download with multiple strategies for: {url}"
        )

        # Check for cookies file
        cookies_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies.txt"
        )
        has_cookies = os.path.exists(cookies_path)
        if has_cookies:
            error_logger.info(f"🍪 Using Instagram cookies from {cookies_path}")
        else:
            error_logger.warning(
                "⚠️ No cookies.txt found for Instagram. Some videos may require login."
            )

        # Define Instagram-specific strategies
        strategies = [
            {
                "name": "Instagram Mobile API with Cookies",
                "user_agent": InstagramConfig.USER_AGENTS[2],
                "format": "bestvideo+bestaudio/best",
                "args": [
                    "--user-agent",
                    InstagramConfig.USER_AGENTS[2],
                    "--add-header",
                    f"X-IG-App-ID:936619743392459",
                    "--add-header",
                    "X-IG-WWW-Claim:0",
                    "--add-header",
                    "X-Requested-With:XMLHttpRequest",
                    "--extractor-args",
                    "instagram:api_hostname=i.instagram.com;api_version=v1",
                ]
                + (["--cookies", cookies_path] if has_cookies else []),
            },
            {
                "name": "Instagram Web (embed) with Cookies",
                "user_agent": InstagramConfig.USER_AGENTS[0],
                "format": "bestvideo+bestaudio/best",
                "args": [
                    "--user-agent",
                    InstagramConfig.USER_AGENTS[0],
                    "--add-header",
                    "X-Requested-With:XMLHttpRequest",
                    "--extractor-args",
                    "instagram:api_hostname=www.instagram.com;api_version=v1",
                ]
                + (["--cookies", cookies_path] if has_cookies else []),
            },
            {
                "name": "Instagram Desktop with Cookies",
                "user_agent": InstagramConfig.USER_AGENTS[1],
                "format": "bestvideo+bestaudio/best",
                "args": [
                    "--user-agent",
                    InstagramConfig.USER_AGENTS[1],
                    "--add-header",
                    "Referer:https://www.instagram.com/",
                    "--extractor-args",
                    "instagram:api_hostname=www.instagram.com;api_version=v1",
                ]
                + (["--cookies", cookies_path] if has_cookies else []),
            },
            {
                "name": "Instagram Android with Cookies",
                "user_agent": InstagramConfig.USER_AGENTS[3],
                "format": "bestvideo+bestaudio/best",
                "args": [
                    "--user-agent",
                    InstagramConfig.USER_AGENTS[3],
                    "--extractor-args",
                    "instagram:api_hostname=i.instagram.com;api_version=v1",
                ]
                + (["--cookies", cookies_path] if has_cookies else []),
            },
            # Fallback strategies without cookies
            {
                "name": "Instagram Mobile API (no cookies)",
                "user_agent": InstagramConfig.USER_AGENTS[2],
                "format": "bestvideo+bestaudio/best",
                "args": [
                    "--user-agent",
                    InstagramConfig.USER_AGENTS[2],
                    "--add-header",
                    f"X-IG-App-ID:936619743392459",
                    "--add-header",
                    "X-IG-WWW-Claim:0",
                    "--add-header",
                    "X-Requested-With:XMLHttpRequest",
                    "--extractor-args",
                    "instagram:api_hostname=i.instagram.com;api_version=v1",
                ],
            },
            {
                "name": "Instagram Web (embed, no cookies)",
                "user_agent": InstagramConfig.USER_AGENTS[0],
                "format": "bestvideo+bestaudio/best",
                "args": [
                    "--user-agent",
                    InstagramConfig.USER_AGENTS[0],
                    "--add-header",
                    "X-Requested-With:XMLHttpRequest",
                    "--extractor-args",
                    "instagram:api_hostname=www.instagram.com;api_version=v1",
                ],
            },
        ]

        # Try each strategy
        for i, strategy in enumerate(strategies, 1):
            error_logger.info(
                f"📋 Trying Instagram strategy {i}/{len(strategies)}: {strategy['name']}"
            )

            try:
                result = await self._try_instagram_strategy(url, strategy)
                if result and result[0]:
                    error_logger.info(
                        f"✅ Instagram strategy '{strategy['name']}' succeeded!"
                    )
                    return result
                else:
                    error_logger.warning(
                        f"❌ Instagram strategy '{strategy['name']}' failed"
                    )
            except Exception as e:
                error_logger.error(
                    f"❌ Instagram strategy '{strategy['name']}' error: {e}"
                )

        error_logger.error(f"❌ All Instagram strategies failed for {url}")
        return None, None

    async def _try_instagram_strategy(
        self, url: str, strategy: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Try a single Instagram download strategy."""
        unique_filename = f"instagram_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(self.download_path, unique_filename)

        # Build command
        cmd = [
            self.yt_dlp_path,
            url,
            "-o",
            output_path,
            "--merge-output-format",
            "mp4",
            "--no-check-certificate",
            "--geo-bypass",
            "--ignore-errors",
            "--no-playlist",
            "--socket-timeout",
            "30",
            "--retries",
            "2",
            "--fragment-retries",
            "2",
            "-f",
            strategy["format"],
        ] + strategy["args"]

        error_logger.info(f"   Executing Instagram strategy: {strategy['name']}")

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

            if process.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                error_logger.info(f"   ✅ Downloaded {file_size} bytes")

                # Get title
                title = await self._get_video_title(url)
                return output_path, title
            else:
                stderr_text = stderr.decode()
                error_logger.warning(
                    f"   ❌ Process failed (code {process.returncode})"
                )
                error_logger.warning(f"   Error: {stderr_text[:200]}...")
                return None, None

        except asyncio.TimeoutError:
            error_logger.warning(f"   ⏰ Strategy timed out after 60 seconds")
            return None, None
        except Exception as e:
            error_logger.error(f"   ❌ Strategy execution error: {e}")
            return None, None
        finally:
            # Clean up any partial files
            if os.path.exists(output_path):
                try:
                    # Only remove if download failed
                    success = (
                        process is not None
                        and hasattr(process, "returncode")
                        and process.returncode == 0
                        and os.path.getsize(output_path) > 0
                    )
                    if not success:
                        os.remove(output_path)
                except Exception:
                    pass  # cleanup

    async def download_youtube_music(
        self, url: str
    ) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]
    ]:
        """Download audio from YouTube Music as MP3.

        Returns:
            (filename, display_title, performer, webpage_url, video_id) or (None, None, None, None, None)
        """
        error_logger.info(f"🎵 Starting YouTube Music download for: {url}")

        os.makedirs(MUSIC_DIR, exist_ok=True)

        output_template = os.path.join(MUSIC_DIR, "%(title)s.%(ext)s")

        # Environment with deno in PATH for JS challenge solving
        env = os.environ.copy()
        deno_path = os.path.expanduser("~/.deno/bin")
        if os.path.exists(deno_path):
            env["PATH"] = f"{deno_path}:{env.get('PATH', '')}"

        # Check for YouTube cookies file
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yt_cookies_path = os.path.join(project_root, "youtube_cookies.txt")
        has_yt_cookies = os.path.exists(yt_cookies_path)
        if has_yt_cookies:
            error_logger.info(f"🍪 Using YouTube cookies from {yt_cookies_path}")
        else:
            error_logger.info(
                "⚠️ No youtube_cookies.txt found. Some formats may be restricted."
            )

        cookies_args = ["--cookies", yt_cookies_path] if has_yt_cookies else []

        # Strategies ordered by reliability:
        # iOS/Android clients don't require PO tokens.
        # HLS is a fallback when HTTPS formats get 403.
        strategies = [
            {
                "name": "iOS client (bestaudio)",
                "format": "bestaudio/best",
                "args": ["--extractor-args", "youtube:player_client=ios"],
            },
            {
                "name": "Android client (bestaudio)",
                "format": "bestaudio/best",
                "args": ["--extractor-args", "youtube:player_client=android"],
            },
            {
                "name": "HLS stream (extract audio)",
                "format": "best[protocol=m3u8_native]/best[protocol=m3u8]",
                "args": [],
            },
            {
                "name": "Web Safari client",
                "format": "bestaudio/best",
                "args": ["--extractor-args", "youtube:player_client=web_safari"],
            },
            {
                "name": "Default (bestaudio)",
                "format": "bestaudio/best",
                "args": [],
            },
        ]

        for i, strategy in enumerate(strategies, 1):
            error_logger.info(f"📋 Strategy {i}/{len(strategies)}: {strategy['name']}")

            # Build yt-dlp command for audio extraction with metadata
            cmd = [
                self.yt_dlp_path,
                url,
                "-f",
                strategy["format"],
                "-x",  # Extract audio
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",  # Best quality
                "-o",
                output_template,
                "--embed-metadata",  # Preserve/embed metadata tags
                "--embed-thumbnail",  # Embed album art
                "--add-metadata",  # Add metadata to file
                "--no-check-certificate",
                "--geo-bypass",
                "--no-playlist",
                "--socket-timeout",
                "30",
                "--retries",
                "3",
                "--print",
                "after_move:%(.{id,artist,track,title,uploader,duration,webpage_url})j",
                "--print",
                "after_move:filepath",
            ]

            # Add cookies if available
            if cookies_args:
                cmd.extend(cookies_args)

            # Add strategy-specific args
            if strategy["args"]:
                cmd.extend(strategy["args"])

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=180.0
                )

                lines = (
                    [l for l in stdout.decode().strip().split("\n") if l.strip()]
                    if stdout
                    else []
                )
                output_path = lines[-1] if lines else None
                meta = {}
                for line in lines[:-1]:
                    try:
                        meta = json.loads(line)
                        break
                    except Exception:
                        pass

                if (
                    process.returncode == 0
                    and output_path
                    and os.path.exists(output_path)
                ):
                    file_size = os.path.getsize(output_path)
                    error_logger.info(
                        f"   ✅ Strategy '{strategy['name']}' succeeded! Downloaded {file_size} bytes"
                    )

                    display_title, performer, webpage_url = self._compose_display_title(
                        meta
                    )
                    video_id = meta.get("id") or ""
                    webpage_url = webpage_url or url
                    return output_path, display_title, performer, webpage_url, video_id
                else:
                    stderr_text = stderr.decode()
                    error_logger.warning(
                        f"   ❌ Strategy '{strategy['name']}' failed (code {process.returncode})"
                    )
                    if stderr_text:
                        error_logger.warning(f"   Error: {stderr_text[:200]}...")

            except asyncio.TimeoutError:
                error_logger.warning(f"   ⏰ Strategy '{strategy['name']}' timed out")
            except Exception as e:
                error_logger.error(f"   ❌ Strategy '{strategy['name']}' error: {e}")

        error_logger.error(f"❌ All YouTube Music strategies failed for {url}")
        return None, None, None, None, None

    async def resolve_streaming_url(
        self, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract track title and artist from a streaming platform URL.

        Uses platform-specific HTTP APIs (not yt-dlp, which refuses DRM-protected sites).

        Returns:
            (title, artist) tuple, or (None, None) on failure.
        """
        general_logger.info(f"Resolving streaming URL metadata: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                resolved_url = await self.normalize_music_platform_url(
                    url, session=session
                )
                url_lower = resolved_url.lower()
                if "deezer.com" in url_lower:
                    return await self._resolve_deezer(session, resolved_url)
                elif "spotify.com" in url_lower:
                    return await self._resolve_spotify(session, resolved_url)
                elif "music.apple.com" in url_lower:
                    return await self._resolve_apple_music(session, resolved_url)
        except Exception as e:
            error_logger.error(f"resolve_streaming_url error for {url}: {e}")

        return None, None

    def _is_music_platform_url(self, url: str) -> bool:
        """Check whether URL points to a supported music platform."""
        from modules.const import MusicPlatforms

        hostname = (urlparse(url).hostname or "").lower()
        if not hostname:
            return False

        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in MusicPlatforms.PLATFORM_DOMAINS
        )

    @staticmethod
    def _extract_meta_tag_content(
        html_text: str, attr: str, value: str
    ) -> Optional[str]:
        """Extract meta tag content by attribute/value pair."""
        patterns = [
            rf'<meta[^>]+{attr}=["\']{re.escape(value)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+{attr}=["\']{re.escape(value)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.IGNORECASE)
            if match:
                return html_lib.unescape(match.group(1)).strip()
        return None

    @staticmethod
    def _extract_spotify_artist_from_description(description: str) -> Optional[str]:
        """Extract artist from Spotify description style metadata."""
        normalized = html_lib.unescape(description).strip()
        if not normalized:
            return None

        # Example: "Listen to <track> on Spotify. Song · Artist · 2025"
        song_match = re.search(
            r"\bSong\s*[·•]\s*([^·•]+)", normalized, flags=re.IGNORECASE
        )
        if song_match:
            return song_match.group(1).strip()

        parts = [p.strip() for p in re.split(r"\s*[·•]\s*", normalized) if p.strip()]
        if len(parts) >= 2:
            # For "Track · Artist" or "... Song · Artist ..."
            if parts[0].lower() not in {"song", "album", "single", "ep", "playlist"}:
                return parts[1]
            if len(parts) >= 3:
                return parts[2]
        return None

    def _extract_artist_from_json_node(self, node: Any) -> Optional[str]:
        """Recursively extract artist name from JSON-LD node."""
        if isinstance(node, dict):
            for key in ("byArtist", "artist", "creator", "author"):
                artist_data = node.get(key)
                if isinstance(artist_data, dict):
                    name = artist_data.get("name")
                    if isinstance(name, str) and name.strip():
                        return name.strip()
                elif isinstance(artist_data, list):
                    for item in artist_data:
                        if isinstance(item, dict):
                            name = item.get("name")
                            if isinstance(name, str) and name.strip():
                                return name.strip()

            for value in node.values():
                candidate = self._extract_artist_from_json_node(value)
                if candidate:
                    return candidate
        elif isinstance(node, list):
            for item in node:
                candidate = self._extract_artist_from_json_node(item)
                if candidate:
                    return candidate
        return None

    def _extract_spotify_artist_from_json_ld(self, html_text: str) -> Optional[str]:
        """Extract artist name from Spotify JSON-LD blocks."""
        script_blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for block in script_blocks:
            payload_text = block.strip()
            if not payload_text:
                continue
            try:
                payload = json.loads(payload_text)
            except Exception:
                continue
            candidate = self._extract_artist_from_json_node(payload)
            if candidate:
                return candidate
        return None

    def _extract_music_url_from_text(self, value: str) -> Optional[str]:
        """Extract a supported music URL from plain or encoded text."""
        candidate = value.strip().strip('"').strip("'")
        if not candidate:
            return None

        for _ in range(3):
            parsed = urlparse(candidate)
            if (
                parsed.scheme in {"http", "https"}
                and parsed.netloc
                and self._is_music_platform_url(candidate)
            ):
                return candidate

            decoded = unquote(candidate)
            if decoded == candidate:
                break
            candidate = decoded

        url_match = re.search(r'https?://[^\s<>"\']+', candidate)
        if url_match:
            embedded_url = url_match.group(0).rstrip(").,;")
            if self._is_music_platform_url(embedded_url):
                return embedded_url
        return None

    def _extract_music_url_from_json_payload(self, payload: Any) -> Optional[str]:
        """Recursively extract a supported music URL from decoded JSON payload."""
        if isinstance(payload, str):
            return self._extract_music_url_from_text(payload)
        if isinstance(payload, dict):
            for value in payload.values():
                candidate = self._extract_music_url_from_json_payload(value)
                if candidate:
                    return candidate
        elif isinstance(payload, list):
            for item in payload:
                candidate = self._extract_music_url_from_json_payload(item)
                if candidate:
                    return candidate
        return None

    def _extract_music_url_from_cd_param(self, cd_value: str) -> Optional[str]:
        """Decode ffm.to style `cd` payload and extract destination music URL."""
        try:
            padded = cd_value + ("=" * (-len(cd_value) % 4))
            decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode(
                "utf-8", errors="ignore"
            )
        except Exception:
            return None

        candidate = self._extract_music_url_from_text(decoded)
        if candidate:
            return candidate

        try:
            payload = json.loads(decoded)
        except Exception:
            return None
        return self._extract_music_url_from_json_payload(payload)

    async def normalize_music_platform_url(
        self, url: str, session: Optional[aiohttp.ClientSession] = None
    ) -> str:
        """Resolve wrapped links to direct platform URLs (Spotify/Deezer/Apple/SoundCloud)."""
        candidate = url.strip()
        if self._is_music_platform_url(candidate):
            return candidate

        parsed = urlparse(candidate)
        query_params = parse_qs(parsed.query)

        # Most wrappers place destination URLs in one of these fields.
        direct_keys = (
            "url",
            "u",
            "dest",
            "desturl",
            "dest_url",
            "destination",
            "destination_url",
            "target",
            "target_url",
            "href",
            "link",
        )

        for key in direct_keys:
            for value in query_params.get(key, []):
                extracted = self._extract_music_url_from_text(value)
                if extracted:
                    general_logger.info(
                        f"Resolved wrapped music URL: {candidate} -> {extracted}"
                    )
                    return extracted

        for cd_value in query_params.get("cd", []):
            extracted = self._extract_music_url_from_cd_param(cd_value)
            if extracted:
                general_logger.info(
                    f"Resolved ffm wrapped music URL: {candidate} -> {extracted}"
                )
                return extracted

        for values in query_params.values():
            for value in values:
                extracted = self._extract_music_url_from_text(value)
                if extracted:
                    general_logger.info(
                        f"Resolved wrapped music URL: {candidate} -> {extracted}"
                    )
                    return extracted

        hostname = (parsed.hostname or "").lower()
        should_follow_redirects = bool(parsed.query) or hostname in {
            "ffm.to",
            "api.ffm.to",
            "smarturl.it",
            "lnk.to",
            "bit.ly",
            "t.co",
        }
        if parsed.scheme not in {"http", "https"} or not should_follow_redirects:
            return candidate

        owns_session = session is None
        http_session = session
        if owns_session:
            http_session = aiohttp.ClientSession()

        try:
            if not http_session:
                return candidate
            async with http_session.get(
                candidate,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=12),
            ) as response:
                final_url = str(response.url)
                if self._is_music_platform_url(final_url):
                    general_logger.info(
                        f"Resolved redirected music URL: {candidate} -> {final_url}"
                    )
                    return final_url
        except Exception as e:
            general_logger.warning(
                f"Failed to resolve wrapped music URL {candidate}: {e}"
            )
        finally:
            if owns_session and http_session:
                await http_session.close()

        return candidate

    async def _resolve_deezer(
        self, session: aiohttp.ClientSession, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve Deezer track metadata via Deezer public API."""
        try:
            async with session.get(
                url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                final_url = str(response.url)
        except Exception as e:
            general_logger.warning(f"Failed to follow Deezer redirect for {url}: {e}")
            final_url = url

        match = re.search(r"deezer\.com/(?:\w{2}/)?track/(\d+)", final_url)
        if not match:
            general_logger.warning(
                f"Could not extract Deezer track ID from {final_url}"
            )
            return None, None

        track_id = match.group(1)
        try:
            async with session.get(
                f"https://api.deezer.com/track/{track_id}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    title = data.get("title")
                    artist = data.get("artist", {}).get("name")
                    general_logger.info(f"Deezer resolved: '{artist} - {title}'")
                    return title, artist
                else:
                    general_logger.warning(
                        f"Deezer API returned {response.status} for track {track_id}"
                    )
        except Exception as e:
            general_logger.warning(f"Deezer API call failed for track {track_id}: {e}")

        return None, None

    async def _resolve_spotify(
        self, session: aiohttp.ClientSession, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve Spotify track metadata via oEmbed with robust HTML/JSON-LD fallback."""
        try:
            async with session.get(
                f"https://open.spotify.com/oembed?url={url}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    title = data.get("title")
                    artist = data.get("author_name")
                    if title:
                        if not artist:
                            _, artist = await self._scrape_spotify_metadata(
                                session, url
                            )
                        general_logger.info(
                            f"Spotify resolved via oEmbed: '{artist} - {title}'"
                        )
                        return title, artist
                else:
                    general_logger.warning(
                        f"Spotify oEmbed returned {response.status} for {url}"
                    )
        except Exception as e:
            general_logger.warning(f"Spotify oEmbed failed for {url}: {e}")

        title, artist = await self._scrape_spotify_metadata(session, url)
        if title:
            general_logger.info(
                f"Spotify resolved via HTML fallback: '{artist} - {title}'"
            )
            return title, artist
        return None, None

    async def _scrape_spotify_metadata(
        self, session: aiohttp.ClientSession, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Scrape Spotify title/artist from page metadata and JSON-LD."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with session.get(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    general_logger.warning(
                        f"Spotify page fetch returned {response.status} for {url}"
                    )
                    return None, None

                html_text = await response.text()
                title = self._extract_meta_tag_content(
                    html_text, "property", "og:title"
                )
                if not title:
                    title = self._extract_meta_tag_content(
                        html_text, "name", "twitter:title"
                    )

                description = self._extract_meta_tag_content(
                    html_text, "property", "og:description"
                )
                if not description:
                    description = self._extract_meta_tag_content(
                        html_text, "name", "description"
                    )

                artist = self._extract_spotify_artist_from_description(
                    description or ""
                )
                if not artist:
                    artist = self._extract_spotify_artist_from_json_ld(html_text)

                if not artist:
                    # Legacy fallback regex from older Spotify HTML layouts.
                    match = re.search(
                        r'<meta name="description" content="[^"]+\. Song · ([^·"]+)',
                        html_text,
                    )
                    if match:
                        artist = match.group(1).strip()
        except Exception as e:
            general_logger.warning(f"Could not scrape Spotify metadata for {url}: {e}")
            return None, None
        return title, artist

    async def _resolve_apple_music(
        self, session: aiohttp.ClientSession, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve Apple Music track metadata via oEmbed or og:title scraping."""
        try:
            async with session.get(
                f"https://music.apple.com/oembed?url={url}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    title = data.get("title")
                    if title:
                        general_logger.info(f"Apple Music resolved (oEmbed): '{title}'")
                        return title, None
        except Exception:
            pass

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
                    if m:
                        og_title = m.group(1).strip()
                        # Apple Music og:title is often "Song - Artist"
                        parts = og_title.rsplit(" - ", 1)
                        if len(parts) == 2:
                            general_logger.info(
                                f"Apple Music resolved (scraped): '{parts[1]} - {parts[0]}'"
                            )
                            return parts[0], parts[1]
                        general_logger.info(
                            f"Apple Music resolved (scraped title only): '{og_title}'"
                        )
                        return og_title, None
        except Exception as e:
            general_logger.warning(f"Apple Music scraping failed for {url}: {e}")

        return None, None

    async def search_and_download_track(
        self, query: str
    ) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]
    ]:
        """Search YouTube for a track and download it as MP3.

        Args:
            query: Search query, e.g. "Artist - Song Name"

        Returns:
            (filename, display_title, performer, webpage_url, video_id) or (None, None, None, None, None)
        """
        search_query = f"ytsearch1:{query} official audio"
        general_logger.info(f"Searching YouTube: {search_query}")

        os.makedirs(MUSIC_DIR, exist_ok=True)
        output_template = os.path.join(MUSIC_DIR, "%(title)s.%(ext)s")

        env = os.environ.copy()
        deno_path = os.path.expanduser("~/.deno/bin")
        if os.path.exists(deno_path):
            env["PATH"] = f"{deno_path}:{env.get('PATH', '')}"

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yt_cookies_path = os.path.join(project_root, "youtube_cookies.txt")
        cookies_args = (
            ["--cookies", yt_cookies_path] if os.path.exists(yt_cookies_path) else []
        )

        cmd = [
            self.yt_dlp_path,
            search_query,
            "-f",
            "bestaudio/best",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "-o",
            output_template,
            "--embed-metadata",
            "--embed-thumbnail",
            "--add-metadata",
            "--no-check-certificate",
            "--geo-bypass",
            "--no-playlist",
            "--socket-timeout",
            "30",
            "--retries",
            "3",
            "--print",
            "after_move:%(.{id,artist,track,title,uploader,duration,webpage_url})j",
            "--print",
            "after_move:filepath",
        ]
        if cookies_args:
            cmd.extend(cookies_args)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=180.0
            )

            lines = (
                [l for l in stdout.decode().strip().split("\n") if l.strip()]
                if stdout
                else []
            )
            output_path = lines[-1] if lines else None
            meta = {}
            for line in lines[:-1]:
                try:
                    meta = json.loads(line)
                    break
                except Exception:
                    pass

            if process.returncode == 0 and output_path and os.path.exists(output_path):
                display_title, performer, webpage_url = self._compose_display_title(
                    meta
                )
                video_id = meta.get("id") or ""
                general_logger.info(f"Track downloaded: {display_title}")
                return output_path, display_title, performer, webpage_url, video_id
            else:
                general_logger.warning(
                    f"Track search/download failed (code {process.returncode}): {stderr.decode()[:200]}"
                )
        except asyncio.TimeoutError:
            general_logger.warning(f"Track search timed out for query: {query}")
        except Exception as e:
            error_logger.error(f"search_and_download_track error: {e}")
        return None, None, None, None, None

    async def download_music_platform_url(
        self, url: str
    ) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]
    ]:
        """Download audio from a streaming platform URL.

        For SoundCloud: downloads directly via yt-dlp.
        For Spotify/Deezer/Apple Music: resolves metadata, then searches YouTube.

        Returns:
            (filename, display_title, performer, webpage_url, video_id) or 5-tuple of None
        """
        from modules.const import MusicPlatforms

        normalized_url = await self.normalize_music_platform_url(url)
        if normalized_url != url:
            general_logger.info(f"Using normalized music URL: {normalized_url}")
        url = normalized_url

        if MusicPlatforms.SOUNDCLOUD_DOMAIN in url.lower():
            general_logger.info(f"Direct SoundCloud download: {url}")
            os.makedirs(MUSIC_DIR, exist_ok=True)
            output_template = os.path.join(
                MUSIC_DIR, "%(uploader)s - %(title)s.%(ext)s"
            )

            cmd = [
                self.yt_dlp_path,
                url,
                "-f",
                "bestaudio/best",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
                "-o",
                output_template,
                "--embed-metadata",
                "--embed-thumbnail",
                "--add-metadata",
                "--no-check-certificate",
                "--no-playlist",
                "--socket-timeout",
                "30",
                "--retries",
                "3",
                "--print",
                "after_move:filepath",
            ]
            try:
                env = os.environ.copy()
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=180.0
                )
                output_path = (
                    stdout.decode().strip().split("\n")[-1] if stdout else None
                )
                if (
                    process.returncode == 0
                    and output_path
                    and os.path.exists(output_path)
                ):
                    title = os.path.splitext(os.path.basename(output_path))[0]
                    general_logger.info(f"SoundCloud downloaded: {title}")
                    # SoundCloud: uploader is the artist; no YouTube video_id
                    return output_path, title, None, url, ""
                else:
                    general_logger.warning(
                        f"SoundCloud download failed: {stderr.decode()[:200]}"
                    )
            except asyncio.TimeoutError:
                general_logger.warning(f"SoundCloud download timed out: {url}")
            except Exception as e:
                error_logger.error(f"SoundCloud download error: {e}")
            return None, None, None, None, None

        # Spotify / Deezer / Apple Music: resolve metadata then search YouTube
        title, artist = await self.resolve_streaming_url(url)
        if title:
            query = f"{artist} - {title}" if artist else title
        else:
            error_logger.error(f"❌ Could not resolve metadata for music URL: {url}")
            return None, None, None, None, None

        return await self.search_and_download_track(query)

    async def handle_music_platform_link(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Auto-handler: detect music platform URLs in messages and send audio."""
        from modules.const import MusicPlatforms

        if not update.message or not update.message.text:
            return

        # Check per-chat disable config
        if self.config_manager and update.effective_chat:
            try:
                config = await self.config_manager.get_config(module_name="music_auto")
                disabled_chats = config.get("disabled_chats", [])
                if update.effective_chat.id in disabled_chats:
                    return
            except Exception:
                pass

        urls = self.extract_urls(update.message.text)
        music_url = None
        for url in urls:
            normalized_url = await self.normalize_music_platform_url(url)
            if self._is_music_platform_url(normalized_url):
                music_url = normalized_url
                break

        if not music_url:
            return

        general_logger.info(f"Music platform link detected: {music_url}")
        processing_msg = await update.message.reply_text("⏳ Downloading track...")

        filename = None
        try:
            filename, title, performer, youtube_url, video_id = (
                await self.download_music_platform_url(music_url)
            )

            if not filename or not os.path.exists(filename):
                await processing_msg.edit_text("❌ Failed to download track.")
                return

            file_size = os.path.getsize(filename)
            if file_size > 50 * 1024 * 1024:
                await processing_msg.edit_text(
                    "❌ Audio file is too large to send (>50MB)."
                )
                return

            try:
                await processing_msg.delete()
            except Exception:
                pass

            await self._send_audio(
                update,
                context,
                filename,
                title,
                performer=performer,
                youtube_url=youtube_url,
                platform_url=music_url,
            )

            if update.effective_chat:
                from modules.event_tracker import record_bot_event

                user_id = update.effective_user.id if update.effective_user else None
                await record_bot_event("song_sent", update.effective_chat.id, user_id)

        except Exception as e:
            error_logger.error(f"handle_music_platform_link error: {e}", exc_info=True)
            try:
                await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")
            except Exception:
                pass
        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass

    async def _send_audio(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        filename: str,
        title: Optional[str],
        performer: Optional[str] = None,
        youtube_url: Optional[str] = None,
        platform_url: Optional[str] = None,
    ) -> None:
        """Send downloaded audio file to chat."""
        try:
            file_size = os.path.getsize(filename)
            max_size = 50 * 1024 * 1024

            if file_size > max_size:
                error_logger.warning(f"Audio file too large: {file_size} bytes")
                if update.message:
                    await update.message.reply_text("❌ Audio file too large to send.")
                return

            special_chars = [
                "_",
                "*",
                "[",
                "]",
                "(",
                ")",
                "~",
                "`",
                ">",
                "#",
                "+",
                "-",
                "=",
                "|",
                "{",
                "}",
                ".",
                "!",
            ]

            def esc(s: str) -> str:
                for c in special_chars:
                    s = s.replace(c, f"\\{c}")
                return s

            def platform_label_from_url(url: str) -> str:
                host = (urlparse(url).hostname or "").lower()
                if "spotify" in host:
                    return "Spotify"
                if "deezer" in host:
                    return "Deezer"
                if "apple" in host:
                    return "Apple Music"
                if "soundcloud" in host:
                    return "SoundCloud"
                return "Original"

            username = "Unknown"
            if update.effective_user:
                username = (
                    update.effective_user.username
                    or update.effective_user.first_name
                    or "Unknown"
                )

            tg_title, tg_performer = self._normalize_telegram_audio_metadata(
                title, performer
            )
            caption_title = f"{tg_performer} - {tg_title}" if tg_performer else tg_title
            caption = f"🎵 {esc(caption_title)}\n\n👤 Від: @{esc(username)}"

            if platform_url:
                source_label = platform_label_from_url(platform_url)
                caption += f"\n\n🔗 [{esc(source_label)}]({esc(platform_url)})"
            if youtube_url:
                caption += f"\n\n🔗 [YouTube]({esc(youtube_url)})"

            reply_markup = None
            buttons = []
            if youtube_url:
                buttons.append(InlineKeyboardButton("🔗 YouTube", url=youtube_url))
            if platform_url and platform_url != youtube_url:
                source_label = platform_label_from_url(platform_url)
                buttons.append(
                    InlineKeyboardButton(f"🎵 {source_label}", url=platform_url)
                )
            if buttons:
                reply_markup = InlineKeyboardMarkup([buttons])

            with open(filename, "rb") as audio_file:
                send_kwargs = dict(
                    audio=audio_file,
                    title=tg_title,
                    performer=tg_performer,
                    caption=caption,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup,
                )
                if update.message and update.message.reply_to_message:
                    await update.message.reply_to_message.reply_audio(**send_kwargs)
                elif update.effective_chat:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id, **send_kwargs
                    )

            try:
                if update.message:
                    await update.message.delete()
            except Exception as e:
                error_logger.error(f"Failed to delete original message: {str(e)}")

        except Exception as e:
            error_logger.error(f"Audio sending error: {str(e)}")
            await self.send_error_sticker(update)

    async def handle_inline_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline queries for YouTube Music, YouTube Shorts, TikTok, and cat photos."""
        query = update.inline_query
        if not query:
            return

        query_text = query.query.strip()
        error_logger.info(
            f"🔍 Inline query received: '{query_text}' from user {query.from_user.id}"
        )

        # Check for supported URLs first
        urls = extract_urls(query_text)

        if urls:
            url = urls[0]
            # Route to appropriate handler based on URL
            if "music.youtube.com" in url.lower():
                await self._handle_inline_youtube_music(query, context, url)
            elif "youtube.com/shorts" in url.lower():
                await self._handle_inline_youtube_shorts(query, context, url)
            elif "tiktok.com" in url.lower():
                await self._handle_inline_tiktok(query, context, url)
            else:
                # Unsupported URL - still show cat button
                await self._show_cat_with_hint(
                    query,
                    f"Unsupported link. Try music.youtube.com, youtube.com/shorts or tiktok.com",
                )
            return

        # Non-empty text without a URL: treat as song search
        if len(query_text) >= 3:
            await self._handle_inline_song_search(query, context, query_text)
            return

        # Empty/very short query - show cat photo button
        await self._handle_inline_cat(query, context)

    async def _handle_inline_cat(
        self, query: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline cat photo request."""
        error_logger.info("🐱 Fetching cat photo for inline...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.thecatapi.com/v1/images/search", timeout=5
                ) as response:
                    error_logger.info(f"🐱 Cat API response: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        cat_image_url = data[0]["url"]
                        error_logger.info(f"🐱 Cat image URL: {cat_image_url}")

                        from telegram import InlineQueryResultPhoto

                        results = [
                            InlineQueryResultPhoto(
                                id=f"cat_{uuid.uuid4().hex[:8]}",
                                photo_url=cat_image_url,
                                thumbnail_url=cat_image_url,
                                caption="🐱 Meow!",
                            )
                        ]
                        await query.answer(
                            results, cache_time=0
                        )  # No cache for random cats
                        error_logger.info("✅ Inline cat photo answered")
                    else:
                        error_logger.warning(f"🐱 Cat API returned {response.status}")
                        await query.answer([], cache_time=5)
        except Exception as e:
            error_logger.error(f"🐱 Inline cat error: {e}")
            await query.answer([], cache_time=5)

    async def fast_youtube_search(
        self, query: str, limit: int = 5, timeout: float = 8.0
    ) -> list:
        """Fast metadata-only YouTube search (no download).

        Returns list of metadata dicts with id, title, artist, track, uploader, duration, webpage_url.
        """
        search_query = f"ytsearch{limit}:{query}"
        env = os.environ.copy()
        deno_path = os.path.expanduser("~/.deno/bin")
        if os.path.exists(deno_path):
            env["PATH"] = f"{deno_path}:{env.get('PATH', '')}"

        cmd = [
            self.yt_dlp_path,
            search_query,
            "--skip-download",
            "--no-playlist",
            "--no-check-certificate",
            "--socket-timeout",
            "10",
            "--print",
            "%(.{id,title,artist,track,uploader,duration,webpage_url})j",
        ]

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yt_cookies_path = os.path.join(project_root, "youtube_cookies.txt")
        if os.path.exists(yt_cookies_path):
            cmd.extend(["--cookies", yt_cookies_path])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
            results = []
            for line in stdout.decode().strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except Exception:
                    pass
            return results
        except asyncio.TimeoutError:
            error_logger.warning(f"fast_youtube_search timed out for: {query}")
        except Exception as e:
            error_logger.error(f"fast_youtube_search error: {e}")
        return []

    def _schedule_background_cache(
        self, meta: dict, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Trigger a background download and cache for a single search hit."""
        video_id = meta.get("id", "")
        if not video_id or video_id in self._inflight or self.song_cache.get(video_id):
            return

        task = asyncio.create_task(self._run_background_cache(meta, context))
        self._inflight[video_id] = task
        self._bg_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._bg_tasks.discard(t)
            self._inflight.pop(video_id, None)

        task.add_done_callback(_done)

    async def _run_background_cache(
        self, meta: dict, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Download audio and upload to cache channel to obtain a Telegram file_id."""
        video_id = meta.get("id", "")
        webpage_url = meta.get("webpage_url", "")
        if not webpage_url:
            return

        error_logger.info(f"🔄 Background cache start: {video_id} ({webpage_url})")
        try:
            async with self._bg_semaphore:
                filename, display_title, performer, yt_url, vid = (
                    await self.download_youtube_music(webpage_url)
                )
                if not filename or not os.path.exists(filename):
                    error_logger.warning(
                        f"Background cache: download failed for {video_id}"
                    )
                    return

                try:
                    tg_title, tg_performer = self._normalize_telegram_audio_metadata(
                        display_title, performer
                    )
                    cache_display_title = (
                        f"{tg_performer} - {tg_title}" if tg_performer else tg_title
                    )
                    with open(filename, "rb") as audio_file:
                        msg = await context.bot.send_audio(
                            chat_id=SONG_CACHE_CHAT_ID,
                            message_thread_id=SONG_CACHE_THREAD_ID,
                            audio=audio_file,
                            title=tg_title,
                            performer=tg_performer,
                            caption=f"🔗 {yt_url or webpage_url}",
                            disable_notification=True,
                        )

                    if msg and msg.audio:
                        self.song_cache.set(
                            video_id=video_id,
                            file_id=msg.audio.file_id,
                            title=cache_display_title or "Audio",
                            performer=tg_performer,
                            webpage_url=yt_url or webpage_url,
                            duration=meta.get("duration"),
                        )
                        error_logger.info(
                            f"✅ Background cache done: {video_id} → {msg.audio.file_id}"
                        )
                finally:
                    try:
                        os.remove(filename)
                    except Exception:
                        pass
        except Exception as e:
            error_logger.exception(f"Background cache error for {video_id}: {e}")

    @staticmethod
    def _extract_video_id_from_url(url: str) -> str:
        """Extract YouTube video ID from a URL."""
        import re as _re

        m = _re.search(r"[?&v=]([a-zA-Z0-9_-]{11})", url)
        return m.group(1) if m else ""

    async def _handle_inline_youtube_music(
        self, query: Any, context: ContextTypes.DEFAULT_TYPE, url: str
    ) -> None:
        """Handle inline YouTube Music URL — check cache first, else article + background cache."""
        error_logger.info(f"🎵 Inline YouTube Music: {url}")

        video_id = self._extract_video_id_from_url(url)
        yt_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 YouTube", url=url)]]
        )

        # Cache hit: return instantly
        if video_id:
            cached = self.song_cache.get(video_id)
            if cached:
                try:
                    results = [
                        InlineQueryResultCachedAudio(
                            id=f"yt_{uuid.uuid4().hex[:8]}",
                            audio_file_id=cached["file_id"],
                            caption=f"🎵 {cached.get('title', 'Audio')}\n\n🔗 [YouTube]({url})",
                            parse_mode="MarkdownV2",
                            reply_markup=yt_button,
                        )
                    ]
                    await query.answer(results, cache_time=300)
                    error_logger.info(
                        f"✅ Inline YT Music (cached): {cached.get('title')}"
                    )
                    return
                except Exception as e:
                    err = str(e).lower()
                    if "file_id" in err or "invalid" in err:
                        self.song_cache.evict(video_id)
                    error_logger.warning(f"Inline YT Music cache hit failed: {e}")

        # Cache miss: return article with YouTube link, trigger background download
        meta = {
            "id": video_id,
            "webpage_url": url,
            "title": "",
            "artist": None,
            "track": None,
            "uploader": "",
            "duration": None,
        }
        # Try fast metadata lookup for a nicer display title
        hits = await self.fast_youtube_search(url, limit=1, timeout=5.0)
        if hits:
            meta = hits[0]

        display_title, _, _ = self._compose_display_title(meta)

        results = [
            InlineQueryResultArticle(
                id=f"yt_article_{uuid.uuid4().hex[:8]}",
                title=display_title,
                description="Audio will be cached for next search",
                input_message_content=InputTextMessageContent(
                    f"🎵 {display_title}\n🔗 {url}",
                ),
                reply_markup=yt_button,
            )
        ]
        try:
            await query.answer(results, cache_time=5, is_personal=True)
        except Exception as e:
            error_logger.error(f"Inline YT Music article answer error: {e}")

        self._schedule_background_cache(meta, context)

    async def _handle_inline_song_search(
        self, query: Any, context: ContextTypes.DEFAULT_TYPE, search_text: str
    ) -> None:
        """Handle inline song search — fast metadata search, serve cached audio or article fallback."""
        error_logger.info(f"🎵 Inline song search: '{search_text}'")

        hits = await self.fast_youtube_search(search_text, limit=5, timeout=7.0)
        if not hits:
            await self._send_inline_error(query, "No results found")
            return

        results = []
        uncached_hits = []

        for hit in hits:
            video_id = hit.get("id", "")
            display_title, performer, webpage_url = self._compose_display_title(hit)
            webpage_url = webpage_url or hit.get("webpage_url", "")

            yt_button = (
                InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 YouTube", url=webpage_url)]]
                )
                if webpage_url
                else None
            )

            cached = self.song_cache.get(video_id) if video_id else None
            if cached:
                try:
                    caption = f"🎵 {cached.get('title', display_title)}"
                    if webpage_url:
                        caption += f"\n\n🔗 [YouTube]({webpage_url})"
                    results.append(
                        InlineQueryResultCachedAudio(
                            id=f"song_{uuid.uuid4().hex[:8]}",
                            audio_file_id=cached["file_id"],
                            caption=caption,
                            parse_mode="MarkdownV2",
                            reply_markup=yt_button,
                        )
                    )
                    continue
                except Exception as e:
                    err = str(e).lower()
                    if "file_id" in err or "invalid" in err:
                        self.song_cache.evict(video_id)
                    error_logger.warning(f"Song cache hit failed for {video_id}: {e}")

            # Article fallback for uncached results
            results.append(
                InlineQueryResultArticle(
                    id=f"song_article_{uuid.uuid4().hex[:8]}",
                    title=display_title,
                    description="Tap to send YouTube link. Audio caching in background…",
                    input_message_content=InputTextMessageContent(
                        (
                            f"🎵 {display_title}\n🔗 {webpage_url}"
                            if webpage_url
                            else f"🎵 {display_title}"
                        ),
                    ),
                    reply_markup=yt_button,
                )
            )
            uncached_hits.append(hit)

        all_cached = len(uncached_hits) == 0
        try:
            await query.answer(
                results, cache_time=300 if all_cached else 5, is_personal=True
            )
            error_logger.info(
                f"✅ Inline song search answered: {len(results)} results ({len(uncached_hits)} uncached)"
            )
        except Exception as e:
            error_logger.error(f"Inline song search answer error: {e}")

        for hit in uncached_hits:
            self._schedule_background_cache(hit, context)

    async def _handle_inline_tiktok(
        self, query: Any, context: ContextTypes.DEFAULT_TYPE, url: str
    ) -> None:
        """Handle inline TikTok video download."""
        error_logger.info(f"🎬 Inline TikTok: {url}")

        try:
            # Download the video
            filename, title = await self._download_tiktok_ytdlp(url)

            if filename and os.path.exists(filename):
                file_size = os.path.getsize(filename)

                if file_size > 50 * 1024 * 1024:
                    error_logger.warning(f"Inline: Video file too large: {file_size}")
                    await self._send_inline_error(query, "Video file too large")
                    return

                # Send video to user privately to get file_id (will be deleted immediately)
                with open(filename, "rb") as video_file:
                    message = await context.bot.send_video(
                        chat_id=query.from_user.id,
                        video=video_file,
                        disable_notification=True,
                    )

                if message and message.video:
                    # Delete the temporary message from private chat
                    try:
                        await message.delete()
                    except Exception as e:
                        error_logger.warning(f"Could not delete temp message: {e}")

                    from telegram import InlineQueryResultCachedVideo

                    results = [
                        InlineQueryResultCachedVideo(
                            id=f"video_{uuid.uuid4().hex[:8]}",
                            video_file_id=message.video.file_id,
                            title=title or "TikTok Video",
                            caption=f"🎬 {title or 'TikTok'}\n\n🔗 {url}",
                        )
                    ]
                    await query.answer(results, cache_time=300)
                    error_logger.info(f"✅ Inline TikTok video ready: {title}")
                else:
                    await self._send_inline_error(query, "Failed to upload video")

                # Cleanup local file
                try:
                    os.remove(filename)
                except Exception:
                    pass  # cleanup
            else:
                await self._send_inline_error(query, "Download failed")

        except Exception as e:
            error_logger.error(f"Inline TikTok error: {e}")
            await self._send_inline_error(query, str(e))

    async def _handle_inline_youtube_shorts(
        self, query: Any, context: ContextTypes.DEFAULT_TYPE, url: str
    ) -> None:
        """Handle inline YouTube Shorts video download."""
        error_logger.info(f"🎬 Inline YouTube Shorts: {url}")

        try:
            # Try service first, then fall back to direct strategies
            filename, title = None, None
            if await self._check_service_health():
                result = await self._download_from_service(url)
                if result and result[0]:
                    filename, title = result
                    error_logger.info(
                        f"✅ Service download successful for Shorts: {url}"
                    )

            if not filename:
                filename, title = await self._download_youtube_with_strategies(
                    url, is_shorts=True
                )

            if filename and os.path.exists(filename):
                file_size = os.path.getsize(filename)

                if file_size > 50 * 1024 * 1024:
                    error_logger.warning(f"Inline: Video file too large: {file_size}")
                    await self._send_inline_error(query, "Video file too large")
                    return

                # Send video to user privately to get file_id
                with open(filename, "rb") as video_file:
                    message = await context.bot.send_video(
                        chat_id=query.from_user.id,
                        video=video_file,
                        caption=f"🎬 {title or 'YouTube Shorts'}\n\n🔗 {url}",
                        disable_notification=True,
                    )

                if message and message.video:
                    from telegram import InlineQueryResultCachedVideo

                    results = [
                        InlineQueryResultCachedVideo(
                            id=f"video_{uuid.uuid4().hex[:8]}",
                            video_file_id=message.video.file_id,
                            title=title or "YouTube Shorts",
                            caption=f"🎬 {title or 'YouTube Shorts'}\n\n🔗 {url}",
                        )
                    ]
                    try:
                        await query.answer(results, cache_time=300)
                        # Only delete the temp message if inline answer succeeded
                        try:
                            await message.delete()
                        except Exception as e:
                            error_logger.warning(f"Could not delete temp message: {e}")
                        error_logger.info(
                            f"✅ Inline YouTube Shorts video ready: {title}"
                        )
                    except BadRequest as e:
                        # Inline query expired - keep the video in private chat as fallback
                        error_logger.warning(
                            f"Inline query expired for Shorts, video kept in private chat: {e}"
                        )
                else:
                    await self._send_inline_error(query, "Failed to upload video")

                # Cleanup local file
                try:
                    os.remove(filename)
                except Exception:
                    pass  # cleanup
            else:
                await self._send_inline_error(query, "Download failed")

        except Exception as e:
            error_logger.error(f"Inline YouTube Shorts error: {e}")
            await self._send_inline_error(query, str(e))

    async def _send_inline_error(self, query: Any, error_msg: str) -> None:
        """Send error result for inline query."""
        results = [
            InlineQueryResultArticle(
                id="error",
                title="❌ Error",
                description=error_msg[:100],
                input_message_content=InputTextMessageContent(
                    message_text=f"❌ {error_msg}"
                ),
            )
        ]
        try:
            await query.answer(results, cache_time=10)
        except BadRequest as e:
            error_logger.warning(f"Inline error answer failed (query expired): {e}")

    async def _show_cat_with_hint(self, query: Any, hint: str) -> None:
        """Show cat photo with a hint message."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.thecatapi.com/v1/images/search"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        cat_image_url = data[0]["url"]

                        from telegram import InlineQueryResultPhoto

                        results = [
                            InlineQueryResultPhoto(
                                id=f"cat_{uuid.uuid4().hex[:8]}",
                                photo_url=cat_image_url,
                                thumbnail_url=cat_image_url,
                                caption="🐱 Meow!",
                            ),
                            InlineQueryResultArticle(
                                id="hint",
                                title="💡 Hint",
                                description=hint,
                                input_message_content=InputTextMessageContent(
                                    message_text=hint
                                ),
                            ),
                        ]
                        await query.answer(results, cache_time=0)
                    else:
                        await query.answer([], cache_time=5)
        except Exception as e:
            error_logger.error(f"Inline cat with hint error: {e}")
            await query.answer([], cache_time=5)

    async def _try_youtube_strategy(
        self, url: str, strategy: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Try a single YouTube download strategy."""
        unique_filename = f"yt_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(self.download_path, unique_filename)

        # Environment with deno in PATH for JS challenge solving
        env = os.environ.copy()
        deno_path = os.path.expanduser("~/.deno/bin")
        if os.path.exists(deno_path):
            env["PATH"] = f"{deno_path}:{env.get('PATH', '')}"

        # Build command
        cmd = [
            self.yt_dlp_path,
            url,
            "-o",
            output_path,
            "--merge-output-format",
            "mp4",
            "--no-check-certificate",
            "--geo-bypass",
            "--ignore-errors",
            "--no-playlist",
            "--socket-timeout",
            "30",
            "--retries",
            "2",
            "--fragment-retries",
            "2",
            "-f",
            strategy["format"],
        ] + strategy["args"]

        error_logger.info(f"   Command: {' '.join(cmd[:8])}... (truncated)")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90.0)

            if process.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                error_logger.info(f"   ✅ Downloaded {file_size} bytes")

                # Get title
                title = await self._get_video_title(url)
                return output_path, title
            else:
                stderr_text = stderr.decode()
                error_logger.warning(
                    f"   ❌ Process failed (code {process.returncode})"
                )
                error_logger.warning(f"   Error: {stderr_text[:200]}...")
                return None, None

        except asyncio.TimeoutError:
            error_logger.warning(f"   ⏰ Strategy timed out after 90 seconds")
            return None, None
        except Exception as e:
            error_logger.error(f"   ❌ Strategy execution error: {e}")
            return None, None
        finally:
            # Clean up any partial files
            if os.path.exists(output_path):
                try:
                    # Only remove if download failed
                    if not (
                        process.returncode == 0 and os.path.getsize(output_path) > 0
                    ):
                        os.remove(output_path)
                except Exception:
                    pass  # cleanup

    async def _get_video_title(self, url: str) -> str:
        try:
            # For YouTube Shorts, get both title and hashtags with better error handling
            if "youtube.com/shorts" in url.lower():
                error_logger.info(f"Getting title for YouTube Shorts: {url}")

                # Extract video ID for fallback
                video_id = (
                    url.split("/shorts/")[1].split("?")[0]
                    if "/shorts/" in url
                    else "unknown"
                )

                try:
                    # First try to get just the title (more likely to succeed)
                    title_process = await asyncio.create_subprocess_exec(
                        self.yt_dlp_path,
                        "--get-title",
                        "--no-warnings",
                        url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    # Get title with timeout
                    title_stdout, title_stderr = await asyncio.wait_for(
                        title_process.communicate(), timeout=15.0
                    )
                    title = title_stdout.decode().strip()

                    if not title:
                        error_logger.warning(f"Empty title for YouTube Shorts: {url}")
                        error_logger.warning(
                            f"Title stderr: {title_stderr.decode().strip()}"
                        )
                        title = f"YouTube Short {video_id}"

                    # Try to get tags if we have a title
                    hashtags = ""
                    try:
                        tags_process = await asyncio.create_subprocess_exec(
                            self.yt_dlp_path,
                            "--get-tags",
                            "--no-warnings",
                            url,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )

                        # Get tags with a shorter timeout
                        tags_stdout, _ = await asyncio.wait_for(
                            tags_process.communicate(), timeout=10.0
                        )
                        tags = tags_stdout.decode().strip()

                        # Add hashtags if available
                        if tags:
                            hashtags = " ".join(
                                [f"#{tag.strip()}" for tag in tags.split(",")]
                            )
                    except (asyncio.TimeoutError, Exception) as e:
                        error_logger.warning(
                            f"Failed to get tags for YouTube Shorts: {str(e)}"
                        )

                    # Combine title and hashtags if we have both
                    if hashtags:
                        return f"{title} {hashtags}"
                    return title

                except (asyncio.TimeoutError, Exception) as e:
                    error_logger.error(f"Error getting YouTube Shorts title: {str(e)}")
                    return f"YouTube Short {video_id}"
            else:
                # For other platforms, just get the title
                error_logger.info(f"Getting title for URL: {url}")
                process = await asyncio.create_subprocess_exec(
                    self.yt_dlp_path,
                    "--get-title",
                    "--no-warnings",
                    url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # Add timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=15.0
                )
                title = stdout.decode().strip()

                if not title:
                    error_logger.warning(f"Empty title for URL: {url}")
                    error_logger.warning(f"Stderr: {stderr.decode().strip()}")
                    # Try to extract some identifier from the URL
                    parts = url.split("/")
                    if len(parts) > 3:
                        return f"Video {parts[-1]}"
                return title or "Video"

        except asyncio.TimeoutError:
            error_logger.error(f"Title fetch timeout for URL: {url}")
            return "Video from " + url.split("/")[-1]
        except Exception as e:
            import traceback

            error_logger.error(f"Error getting title: {str(e)}")
            error_logger.error(f"Traceback: {traceback.format_exc()}")
            return "Video"

    async def send_error_sticker(self, update: Update) -> None:
        """Send error sticker with enhanced error logging."""
        try:
            chosen_sticker = random.choice(self.ERROR_STICKERS)
            if update.message:
                await update.message.reply_sticker(sticker=chosen_sticker)
        except Exception as e:
            user_id = update.effective_user.id if update.effective_user else "Unknown"
            username = (
                update.effective_user.username if update.effective_user else "Unknown"
            )
            error_logger.error(
                f"🚨 Sticker Error\n"
                f"Error: {str(e)}\n"
                f"User ID: {user_id}\n"
                f"Username: @{username}",
                extra={
                    "chat_id": (
                        update.effective_chat.id if update.effective_chat else "N/A"
                    ),
                    "username": (
                        update.effective_user.username
                        if update.effective_user
                        else "N/A"
                    ),
                    "chat_title": (
                        update.effective_chat.title if update.effective_chat else "N/A"
                    ),
                },
            )
            if update.message:
                await update.message.reply_text(
                    "❌ Error occurred. This has been reported to the developer."
                )

    async def handle_video_link(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle video link with improved error handling and resource cleanup."""
        processing_msg = None
        filename = None

        try:
            if not update.message or not update.message.text:
                return

            message_text = update.message.text.strip()
            if not self.extract_urls:
                error_logger.error("extract_urls function is not available")
                return

            error_logger.info(f"Video handler called with message: {message_text}")
            urls = self.extract_urls(message_text)
            error_logger.info(f"Extracted URLs: {urls}")

            if not urls:
                await self.send_error_sticker(update)
                return

            # Filter out story URLs
            urls = [url for url in urls if not self._is_story_url(url)]
            if not urls:
                if update.message:
                    await update.message.reply_text(
                        "❌ Stories are not supported for download."
                    )
                return

            # Get chat info for config BEFORE sending processing message
            chat_id = str(update.effective_chat.id) if update.effective_chat else None
            chat_type = (
                "private"
                if update.effective_chat and update.effective_chat.type == "private"
                else "group"
            )

            error_logger.info(f"DEBUG: chat_id={chat_id}, chat_type={chat_type}")

            # Send before video if configured BEFORE processing message
            error_logger.info("DEBUG: About to call _send_before_video_if_configured")
            await self._send_before_video_if_configured(
                update, context, chat_id, chat_type
            )
            error_logger.info(
                "DEBUG: Finished calling _send_before_video_if_configured"
            )

            # Now send processing message
            if update.message:
                processing_msg = await update.message.reply_text(
                    "⏳ Processing your request..."
                )

            for url in urls:
                # Check if this is a YouTube Music URL
                is_youtube_music = "music.youtube.com" in url.lower()

                if is_youtube_music:
                    # Handle YouTube Music - download as MP3
                    filename, title, performer, youtube_url, video_id = (
                        await self.download_youtube_music(url)
                    )
                    if filename and os.path.exists(filename):
                        await self._send_audio(
                            update,
                            context,
                            filename,
                            title,
                            performer=performer,
                            youtube_url=youtube_url or url,
                        )
                    else:
                        await self._handle_download_error(update, url)
                else:
                    # Handle regular video platforms
                    filename, title = await self.download_video(url, chat_id, chat_type)
                    if filename and os.path.exists(filename):
                        await self._send_video(
                            update, context, filename, title, source_url=url
                        )
                    else:
                        await self._handle_download_error(update, url)

        except Exception as e:
            await self._handle_processing_error(update, e, message_text)
        finally:
            await self._cleanup(processing_msg, filename, update)

    async def _send_before_video(
        self, chat_id: str, chat_type: str, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Send before video for the given chat."""
        try:
            video_config = await self._get_video_config(chat_id, chat_type)
            before_video_path = video_config.get("before_video_path")

            if before_video_path and os.path.exists(before_video_path):
                general_logger.info(
                    f"Sending before video for chat {chat_id}: {before_video_path}"
                )
                with open(before_video_path, "rb") as before_video_file:
                    await context.bot.send_video(
                        chat_id=chat_id, video=before_video_file
                    )
                general_logger.info("Before video sent successfully")
        except Exception as e:
            general_logger.error(f"Failed to send before video for chat {chat_id}: {e}")

    async def _send_before_video_if_configured(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: Optional[str],
        chat_type: Optional[str],
    ) -> None:
        """Send before video if configured for this chat."""
        if not chat_id or not chat_type:
            return

        await self._send_before_video(chat_id, chat_type, context)

    async def _send_video(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        filename: str,
        title: Optional[str],
        source_url: Optional[str] = None,
    ) -> None:
        try:
            # Get video config for this chat
            chat_id = str(update.effective_chat.id) if update.effective_chat else None
            chat_type = (
                "private"
                if update.effective_chat and update.effective_chat.type == "private"
                else "group"
            )

            video_config = await self._get_video_config(chat_id, chat_type)

            # Note: Before video is sent in _send_before_video_if_configured method
            # Videos are always sent now

            file_size = os.path.getsize(filename)
            max_size = 50 * 1024 * 1024  # 50MB limit for Telegram

            if file_size > max_size:
                error_logger.warning(f"File too large: {file_size} bytes")
                if update.message:
                    await update.message.reply_text("❌ Video file too large to send.")
                return

            # Build caption with manual entities to support expandable_blockquote
            # (HTML/MarkdownV2 parsers in older python-telegram-bot don't support it)
            from telegram import MessageEntity

            def utf16_len(s: str) -> int:
                return len(s.encode("utf-16-le")) // 2

            username = "Unknown"
            if update.effective_user:
                username = (
                    update.effective_user.username
                    or update.effective_user.first_name
                    or "Unknown"
                )

            caption = f"👤 Від: @{username}"
            caption_entities = []
            offset = utf16_len(caption)

            if source_url:
                link_prefix = "\n\n🔗 "
                link_label = "Посилання"
                offset += utf16_len(link_prefix)
                caption_entities.append(
                    MessageEntity(
                        type=MessageEntity.TEXT_LINK,
                        offset=offset,
                        length=utf16_len(link_label),
                        url=source_url,
                    )
                )
                caption += link_prefix + link_label
                offset += utf16_len(link_label)

            if title:
                title_prefix = "\n\n"
                # Truncate only if needed to stay within Telegram's 1024-char caption limit
                max_title_len = 1024 - len(caption) - len(title_prefix)
                truncated_title = (
                    title
                    if len(title) <= max_title_len
                    else title[: max_title_len - 3] + "..."
                )
                offset += utf16_len(title_prefix)
                caption_entities.append(
                    MessageEntity(
                        type="expandable_blockquote",
                        offset=offset,
                        length=utf16_len(truncated_title),
                    )
                )
                caption += title_prefix + truncated_title

            with open(filename, "rb") as video_file:
                send_kwargs = dict(caption=caption, caption_entities=caption_entities)
                # Check if the original message was a reply to another message
                if update.message and update.message.reply_to_message:
                    await update.message.reply_to_message.reply_video(
                        video=video_file, **send_kwargs
                    )
                else:
                    if update.effective_chat:
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=video_file,
                            **send_kwargs,
                        )

            # Track successful video download
            if update.effective_chat:
                from modules.event_tracker import record_bot_event

                _user_id = update.effective_user.id if update.effective_user else None
                asyncio.ensure_future(
                    record_bot_event(
                        "video_download", update.effective_chat.id, _user_id
                    )
                )

            # Delete the original message after successful video send
            try:
                if update.message:
                    await update.message.delete()
            except Exception as e:
                error_logger.error(f"Failed to delete original message: {str(e)}")

        except Exception as e:
            error_logger.error(f"Video sending error: {str(e)}")
            await self.send_error_sticker(update)

    async def _handle_download_error(self, update: Update, url: str) -> None:
        """Handle download errors with standardized handling."""
        from modules.error_handler import (
            ErrorHandler,
            ErrorCategory,
            ErrorSeverity,
            send_error_feedback,
        )

        # Determine platform for better error context
        platform = "unknown"
        if "music.youtube.com" in url:
            platform = "music.youtube.com"
        elif "youtube.com" in url or "youtu.be" in url:
            if "shorts" in url:
                platform = "youtube.com/shorts"
            elif "clip" in url:
                platform = "youtube.com/clips"
            else:
                platform = "youtube.com"
        elif "instagram.com" in url:
            platform = "instagram.com"
        elif "tiktok.com" in url:
            platform = "tiktok.com"
        else:
            platform = next(
                (p for p in self.supported_platforms if p in url), "unknown"
            )

        # Create context information
        context = {
            "url": url,
            "platform": platform,
            "user_id": (
                update.effective_user.id if update and update.effective_user else None
            ),
            "username": (
                update.effective_user.username
                if update and update.effective_user
                else None
            ),
        }

        # Create a standard error
        error = ErrorHandler.create_error(
            message=f"Failed to download video from {platform}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            context=context,
        )

        # Log error with our standard format
        error_message = ErrorHandler.format_error_message(error, update, prefix="⬇️")
        error_logger.error(error_message)

        # Send error feedback to user
        await send_error_feedback(update=update, stickers=self.ERROR_STICKERS)

    async def _handle_processing_error(
        self, update: Update, error: Exception, message_text: str
    ) -> None:
        """Handle processing errors with standardized handling."""
        from modules.error_handler import (
            ErrorHandler,
            ErrorCategory,
            ErrorSeverity,
            send_error_feedback,
        )

        # Create a standard error with the original exception
        std_error = ErrorHandler.create_error(
            message="Error processing video request",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.GENERAL,
            context={
                "message_text": message_text,
                "user_id": (
                    update.effective_user.id
                    if update and update.effective_user
                    else None
                ),
                "username": (
                    update.effective_user.username
                    if update and update.effective_user
                    else None
                ),
            },
            original_exception=error,
        )

        # Use our centralized error handler
        await ErrorHandler.handle_error(
            error=std_error,
            update=update,
            user_feedback_fn=lambda u, _: send_error_feedback(
                u, stickers=self.ERROR_STICKERS
            ),
        )

    async def _cleanup(
        self, processing_msg: Any, filename: Optional[str], update: Update
    ) -> None:
        """Clean up resources after processing."""
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception as e:
                user_id = (
                    update.effective_user.id if update.effective_user else "Unknown"
                )
                username = (
                    update.effective_user.username
                    if update.effective_user
                    else "Unknown"
                )
                error_logger.error(
                    f"🗑️ Cleanup Error\n"
                    f"Error: {str(e)}\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{username}"
                )

        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                user_id = (
                    update.effective_user.id if update.effective_user else "Unknown"
                )
                username = (
                    update.effective_user.username
                    if update.effective_user
                    else "Unknown"
                )
                error_logger.error(
                    f"🗑️ File Removal Error\n"
                    f"Error: {str(e)}\n"
                    f"File: {filename}\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{username}"
                )

    def _get_yt_dlp_path(self) -> str:
        """Get the path to yt-dlp executable."""
        path = shutil.which("yt-dlp")
        if path:
            return path

        common_paths = [
            "/usr/local/bin/yt-dlp",
            "/usr/bin/yt-dlp",
            os.path.expanduser("~/.local/bin/yt-dlp"),
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p

        return "yt-dlp"

    def _verify_yt_dlp(self) -> None:
        """Verify yt-dlp is installed and accessible."""
        try:
            subprocess.run(
                [self.yt_dlp_path, "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_logger.warning(
                f"yt-dlp verification failed: {e}. The application will rely on the service."
            )

    def _init_download_path(self) -> None:
        """Initialize the download directory."""
        try:
            os.makedirs(self.download_path, exist_ok=True)
            error_logger.info(f"Download directory initialized: {self.download_path}")
        except Exception as e:
            error_logger.error(f"Failed to create download directory: {str(e)}")
            raise RuntimeError(
                f"Could not create download directory: {self.download_path}"
            )

    def _get_platform(self, url: str) -> Platform:
        url = url.lower()
        # Use more precise URL matching to avoid substring attacks
        # Include all TikTok URL variants: www, vm (short links), m (mobile), vt (video short links)
        if url.startswith(
            (
                "https://tiktok.com/",
                "https://www.tiktok.com/",
                "https://vm.tiktok.com/",
                "https://m.tiktok.com/",
                "https://vt.tiktok.com/",
            )
        ):
            return Platform.TIKTOK
        else:
            return Platform.OTHER

    async def _get_tiktok_title_from_tikwm(self, url: str) -> Optional[str]:
        """Fetch the full TikTok title from tikwm API (yt-dlp --get-title truncates it)."""
        try:
            api_url = f"https://www.tikwm.com/api/?url={url}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
                    if data.get("code") != 0:
                        return None
                    return data.get("data", {}).get("title")
        except Exception as e:
            error_logger.warning(f"Failed to fetch TikTok title from tikwm: {e}")
            return None

    async def _download_tiktok_ytdlp(
        self, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using yt-dlp with tikwm fallback."""
        config = self.platform_configs[Platform.TIKTOK]

        # Try yt-dlp first
        result = await self._download_generic(
            url, Platform.TIKTOK, config, self.download_path
        )

        # If yt-dlp fails, try tikwm API as fallback
        if not result or not result[0]:
            error_logger.info(f"yt-dlp failed for TikTok, trying tikwm fallback: {url}")
            result = await self._download_tiktok_tikwm(url)
        elif result[0]:
            # yt-dlp succeeded but its --get-title truncates TikTok titles; get full title from tikwm
            full_title = await self._get_tiktok_title_from_tikwm(url)
            if full_title:
                result = (result[0], full_title)

        return result

    async def _download_tiktok_tikwm(
        self, url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using tikwm.com API as fallback."""
        try:
            api_url = f"https://www.tikwm.com/api/?url={url}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_logger.error(
                            f"tikwm API returned status {response.status}"
                        )
                        return None, None

                    data = await response.json()

                    if data.get("code") != 0:
                        error_logger.error(
                            f"tikwm API error: {data.get('msg', 'Unknown error')}"
                        )
                        return None, None

                    video_data = data.get("data", {})
                    video_url = video_data.get("play")  # No watermark URL
                    title = video_data.get("title", "TikTok Video")

                    if not video_url:
                        error_logger.error("tikwm API returned no video URL")
                        return None, None

                    # Download the video file
                    unique_filename = f"video_{uuid.uuid4()}.mp4"
                    output_path = os.path.join(self.download_path, unique_filename)

                    async with session.get(
                        video_url, timeout=aiohttp.ClientTimeout(total=120)
                    ) as video_response:
                        if video_response.status != 200:
                            error_logger.error(
                                f"Failed to download video from tikwm URL: {video_response.status}"
                            )
                            return None, None

                        with open(output_path, "wb") as f:
                            while True:
                                chunk = await video_response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)

                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        error_logger.info(f"✅ tikwm download successful: {title}")
                        return output_path, title
                    else:
                        error_logger.error("tikwm download resulted in empty file")
                        return None, None

        except asyncio.TimeoutError:
            error_logger.error("tikwm API request timed out")
            return None, None
        except Exception as e:
            error_logger.error(f"tikwm download error: {e}")
            return None, None

    async def _download_generic(
        self,
        url: str,
        platform: Platform,
        special_config: Optional[DownloadConfig] = None,
        download_path: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Generic video download using yt-dlp with bot detection avoidance."""
        config = special_config or self.platform_configs.get(platform)
        if not config:
            return None, None

        download_path = download_path or self.download_path
        unique_filename = f"video_{uuid.uuid4()}.mp4"
        output_template = os.path.join(download_path, unique_filename)

        # Base yt-dlp arguments with bot detection avoidance
        yt_dlp_args = [
            self.yt_dlp_path,
            url,
            "-o",
            output_template,
            "--merge-output-format",
            "mp4",
            "--no-check-certificate",  # Skip SSL certificate verification
            "--geo-bypass",  # Try to bypass geo-restrictions
        ]

        # Add format if specified
        if config.format:
            yt_dlp_args.extend(["-f", config.format])

        # Add extra arguments if specified
        if config.extra_args:
            yt_dlp_args.extend(config.extra_args)

        # Add headers if specified
        if config.headers:
            for key, value in config.headers.items():
                yt_dlp_args.extend(["--add-header", f"{key}:{value}"])

        # Special handling for YouTube URLs - add comprehensive bot detection avoidance
        is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
        if is_youtube:
            error_logger.info(f"Applying YouTube bot detection avoidance for: {url}")

            # Try multiple strategies for YouTube API extraction issues
            # Note: This is a fallback when the service is unavailable
            # Based on successful strategies from the service
            strategies: List[DownloadStrategy] = [
                # Strategy 1: Simple formats with Android client (most reliable)
                {
                    "name": "Android client with simple formats",
                    "format": "18/22/best[ext=mp4]/best",  # 360p, 720p, then best MP4
                    "args": [
                        "--user-agent",
                        "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip",
                        "--extractor-args",
                        "youtube:player_client=android",
                        "--sleep-interval",
                        "1",
                        "--max-sleep-interval",
                        "3",
                    ],
                },
                # Strategy 2: iOS client with H.264 preference
                {
                    "name": "iOS client with H.264",
                    "format": "bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/best",
                    "args": [
                        "--user-agent",
                        "com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)",
                        "--extractor-args",
                        "youtube:player_client=ios",
                    ],
                },
                # Strategy 3: Web client with browser headers
                {
                    "name": "Web client with headers",
                    "format": "18/22/best[ext=mp4]/best",
                    "args": [
                        "--user-agent",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "--referer",
                        "https://www.youtube.com/",
                        "--extractor-args",
                        "youtube:player_client=web",
                        "--sleep-interval",
                        "1",
                        "--max-sleep-interval",
                        "3",
                    ],
                },
                # Strategy 4: Fallback to any format
                {
                    "name": "Any format fallback",
                    "format": "best",
                    "args": [
                        "--user-agent",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "--extractor-args",
                        "youtube:player_client=web",
                    ],
                },
            ]

            # Try each strategy
            for i, strategy in enumerate(strategies):
                strategy_name = strategy["name"]
                strategy_format = strategy["format"]
                strategy_args = strategy["args"]

                error_logger.info(
                    f"Trying YouTube strategy {i+1}/{len(strategies)}: {strategy_name}"
                )

                # Create base args for this strategy
                strategy_yt_dlp_args = [
                    self.yt_dlp_path,
                    url,
                    "-o",
                    output_template,
                    "--merge-output-format",
                    "mp4",
                    "--no-check-certificate",
                    "--geo-bypass",
                    "--retries",
                    "2",
                    "--fragment-retries",
                    "3",
                    "-f",
                    strategy_format,
                ]

                # Add strategy-specific args
                strategy_yt_dlp_args.extend(strategy_args)

                try:
                    error_logger.info(
                        f"Executing: {' '.join(strategy_yt_dlp_args[:8])}... (truncated)"
                    )
                    process = await asyncio.create_subprocess_exec(
                        *strategy_yt_dlp_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=120.0
                    )

                    if process.returncode == 0 and os.path.exists(output_template):
                        error_logger.info(
                            f"✅ YouTube download successful with strategy: {strategy_name}"
                        )
                        return output_template, await self._get_video_title(url)
                    else:
                        stderr_text = stderr.decode()

                        # Check for specific errors
                        if (
                            "could not find" in stderr_text
                            and "cookies database" in stderr_text
                        ):
                            error_logger.warning(
                                f"❌ Strategy '{strategy_name}' failed: missing browser cookies"
                            )
                        elif "Sign in to confirm you're not a bot" in stderr_text:
                            error_logger.warning(
                                f"❌ Strategy '{strategy_name}' failed: bot detection"
                            )
                        elif (
                            "Failed to extract" in stderr_text
                            and "player response" in stderr_text
                        ):
                            error_logger.warning(
                                f"❌ Strategy '{strategy_name}' failed: YouTube API extraction error"
                            )
                        else:
                            error_logger.warning(
                                f"❌ Strategy '{strategy_name}' failed: {stderr_text[:150]}..."
                            )

                        # Clean up any partial files
                        if os.path.exists(output_template):
                            try:
                                os.remove(output_template)
                            except Exception:
                                pass  # cleanup

                        # If this is not the last strategy, continue to next
                        if i < len(strategies) - 1:
                            continue
                        else:
                            error_logger.error(
                                f"❌ All YouTube strategies failed for {url}"
                            )
                            return None, None

                except (asyncio.TimeoutError, Exception) as e:
                    error_logger.warning(f"❌ Strategy '{strategy_name}' error: {e}")
                    if "process" in locals() and process.returncode is None:
                        try:
                            process.kill()
                            await process.wait()
                        except Exception:
                            pass  # cleanup

                    # Clean up any partial files
                    if os.path.exists(output_template):
                        try:
                            os.remove(output_template)
                        except Exception:
                            pass  # cleanup

                    # If this is not the last strategy, continue to next
                    if i < len(strategies) - 1:
                        continue
                    else:
                        error_logger.error(
                            f"❌ All YouTube strategies failed with errors for {url}"
                        )
                        return None, None

            # This should not be reached, but just in case
            return None, None

        # For non-YouTube URLs, use the standard approach
        try:
            error_logger.info(
                f"Starting yt-dlp download with args: {' '.join(yt_dlp_args)}"
            )  # Log full command
            process = await asyncio.create_subprocess_exec(
                *yt_dlp_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=90.0
            )  # Increased timeout

            if process.returncode == 0:
                if os.path.exists(output_template):
                    error_logger.info(f"Download successful: {output_template}")
                    return output_template, await self._get_video_title(url)
                else:
                    error_logger.warning(
                        f"Download completed but file not found: {output_template}"
                    )
            else:
                stderr_text = stderr.decode()
                error_logger.error(f"Download failed for {url}: {stderr_text}")

        except (asyncio.TimeoutError, Exception) as e:
            error_logger.error(f"Generic download error for {url}: {e}")
            if "process" in locals() and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass  # cleanup

        return None, None

    def _is_story_url(self, url: str) -> bool:
        """Detect if the URL is a story (Instagram, Facebook, etc)."""
        # Add more patterns as needed for other platforms
        story_patterns = [
            r"instagram\.com/stories/",
            r"facebook\.com/stories/",
            r"snapchat\.com/add/",  # Snapchat stories
            r"tiktok\.com/@[\w\.-]+/story/",  # TikTok stories
            r"youtube\.com/stories/",
            r"youtu\.be/stories/",
        ]
        for pattern in story_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    async def _get_video_config(
        self, chat_id: Optional[str] = None, chat_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get video configuration for the current chat."""
        if not self.config_manager:
            # Return default config if no config manager is available
            return {"video_path": self.download_path, "before_video_path": ""}

        try:
            if chat_id and chat_type:
                # Get video_send module config directly
                module_config = await self.config_manager.get_config(
                    chat_id, chat_type, module_name="video_send"
                )
                if isinstance(module_config, dict) and "overrides" in module_config:
                    return cast(Dict[str, Any], module_config["overrides"])
                else:
                    return {"video_path": self.download_path, "before_video_path": ""}
            else:
                # Get global module config
                module_config = await self.config_manager.get_config(
                    module_name="video_send"
                )
                return cast(
                    Dict[str, Any],
                    module_config.get(
                        "overrides",
                        {"video_path": self.download_path, "before_video_path": ""},
                    ),
                )
        except Exception as e:
            general_logger.error(f"Failed to get video config: {e}")
            return {"video_path": self.download_path, "before_video_path": ""}


def setup_video_handlers(
    application: Any,
    extract_urls_func: Optional[Callable[..., Any]] = None,
    config_manager: Optional[Any] = None,
) -> None:
    """Set up video handlers with improved configuration."""
    # Check if handler is already registered to prevent duplicates
    if hasattr(application, "_video_handler_set"):
        general_logger.warning(
            "Video handler already registered, skipping duplicate registration"
        )
        return

    general_logger.info("Initializing video downloader...")
    video_downloader = VideoDownloader(
        download_path="downloads",
        extract_urls_func=extract_urls_func,
        config_manager=config_manager,
    )

    application.bot_data["video_downloader"] = video_downloader

    # Use the supported platforms from const.py
    video_pattern = "|".join(VideoPlatforms.SUPPORTED_PLATFORMS)
    general_logger.info(f"Setting up video handler with pattern: {video_pattern}")

    # Add the video handler with high priority
    def debug_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        message_text = update.message.text if update.message else "No message"
        general_logger.info(f"🎬 VIDEO HANDLER TRIGGERED for message: {message_text}")
        return video_downloader.handle_video_link(update, context)

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(video_pattern),
            debug_video_handler,
            block=True,  # Block other handlers to ensure video processing takes priority
        ),
        group=1,  # Higher priority group
    )

    # Add music platform auto-download handler
    from modules.const import MusicPlatforms

    music_pattern = "|".join(re.escape(d) for d in MusicPlatforms.PLATFORM_DOMAINS)
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(music_pattern),
            video_downloader.handle_music_platform_link,
            block=False,
        ),
        group=1,
    )
    general_logger.info(
        f"Music platform handler registered for: {', '.join(MusicPlatforms.PLATFORM_DOMAINS)}"
    )

    # Add inline query handler for YouTube Music, TikTok, cat photos, and song search
    application.add_handler(InlineQueryHandler(video_downloader.handle_inline_query))
    general_logger.info(
        "Inline query handler registered (music, youtube shorts, tiktok, cat, song search)"
    )

    # Mark as registered to prevent duplicates
    application._video_handler_set = True

    general_logger.info("Video handler setup complete")
