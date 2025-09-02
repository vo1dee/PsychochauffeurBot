import asyncio
import random
import os
import logging
import aiohttp
import re
import json
import uuid
import shutil
import subprocess
from urllib.parse import urljoin, urlparse
from typing import Optional, Tuple, List, Dict, Any, Callable, TypedDict
from asyncio import Lock
from dataclasses import dataclass
from enum import Enum
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from modules.const import VideoPlatforms, InstagramConfig
from modules.utils import extract_urls
from modules.logger import (
    TelegramErrorHandler,
    general_logger, chat_logger, error_logger,
    init_telegram_error_handler, shutdown_logging # Import new functions
)
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
YTDL_SERVICE_API_KEY = os.getenv('YTDL_SERVICE_API_KEY')

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
        "CAACAgQAAxkBAAExX31nn7xByvIhPZHPreVkPONIn82IKgACgxcAAuYrIFHS_QFCSfHYGTYE"
    ]

    def __init__(self, download_path: str = 'downloads', extract_urls_func: Optional[Callable[..., Any]] = None) -> None:
        self.supported_platforms = VideoPlatforms.SUPPORTED_PLATFORMS
        self.download_path = os.path.abspath(download_path)
        self.extract_urls = extract_urls_func
        
        # Check if extract_urls_func is callable
        if self.extract_urls is None or not callable(self.extract_urls):
            error_logger.error("extract_urls_func is not provided or not callable.")
            raise ValueError("extract_urls_func must be a callable function.")
        
        self.yt_dlp_path = self._get_yt_dlp_path()
        
        # Service configuration - use environment variables
        self.service_url = os.getenv('YTDL_SERVICE_URL')
        self.api_key = os.getenv('YTDL_SERVICE_API_KEY')
        self.max_retries = int(os.getenv('YTDL_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('YTDL_RETRY_DELAY', '1'))
        
        # Log service configuration
        error_logger.info(f"Service URL: {self.service_url}")
        error_logger.info(f"API Key present: {bool(self.api_key)}")
        
        self._init_download_path()
        self._verify_yt_dlp()
        self.lock = Lock()
        self.last_download: Dict[str, Any] = {}
        
        # Platform-specific download configurations
        self.platform_configs = {
            Platform.TIKTOK: DownloadConfig(
                format="best[ext=mp4][vcodec~='^avc1']/best[ext=mp4][vcodec*=avc1]/best[ext=mp4]/best",  # Aggressive H.264 first
                max_retries=3,
                headers={
                    "User-Agent": "TikTok/26.2.0 (iPhone; iOS 14.4.2; Scale/3.00)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5"
                }
            ),
            Platform.OTHER: DownloadConfig(
                format="best[ext=mp4][vcodec~='^avc1'][height<=1080]/best[ext=mp4][vcodec*=avc1][height<=1080]/22[height<=720]/18[height<=360]/best[ext=mp4][height<=1080]/best[ext=mp4]/best",  # H.264 + YouTube specific formats
                extra_args=[
                    "--merge-output-format", "mp4",  # Ensure MP4 output
                ]
            )
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
                "--ignore-errors",   # Continue on errors
                "--ignore-config",   # Ignore system-wide config
                "--no-playlist",     # Don't download playlists
                "--geo-bypass",      # Try to bypass geo-restrictions
                "--socket-timeout", "30",  # Increased timeout for better reliability
                "--retries", "3",  # Reduced retries for faster response
                "--fragment-retries", "3",  # Reduced fragment retries
                "--merge-output-format", "mp4",  # Ensure MP4 output
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--referer", "https://www.youtube.com/",
                "--add-header", "Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "--add-header", "Accept-Language:en-US,en;q=0.9",
                "--extractor-args", "youtube:player_client=web",  # Use web client
            ]
        )
        
        # Configuration for YouTube clips - simplified for iOS compatibility
        self.youtube_clips_config = DownloadConfig(
            format="best[ext=mp4][vcodec~='^avc1'][height<=1080]/best[ext=mp4][vcodec*=avc1][height<=1080]/22/18/best[ext=mp4][height<=1080]/best[ext=mp4]/best",  # H.264 first
            extra_args=[
                "--ignore-errors",
                "--ignore-config",
                "--no-playlist",
                "--geo-bypass",
                "--socket-timeout", "10",
                "--merge-output-format", "mp4",  # Ensure MP4 output
            ]
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment variable or file."""
        # First try environment variable
        api_key = os.getenv('YTDL_SERVICE_API_KEY')
        if api_key:
            return api_key
            
        # If not in env, try local file
        try:
            api_key_path = '/opt/ytdl_service/api_key.txt'
            if os.path.exists(api_key_path):
                with open(api_key_path, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            error_logger.error(f"Failed to read API key file: {str(e)}")
        
        error_logger.warning("No API key found in environment or file")
        return None

    async def _check_service_health(self) -> bool:
        """Check if the download service is available."""
        if not self.service_url or not self.api_key:
            error_logger.error("Service health check failed: URL or API key not configured.")
            error_logger.error(f"   YTDL_SERVICE_URL: {self.service_url}")
            error_logger.error(f"   YTDL_SERVICE_API_KEY: {'***' + self.api_key[-4:] if self.api_key and len(self.api_key) > 4 else 'Not set'}")
            return False
        
        health_url = urljoin(self.service_url, "health")
        headers = {"X-API-Key": self.api_key}
        
        error_logger.info(f"Checking service health at: {health_url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, headers=headers, timeout=5, ssl=False) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            error_logger.info("✅ Service health check successful.")
                            error_logger.info(f"   Service status: {data.get('status', 'unknown')}")
                            error_logger.info(f"   yt-dlp version: {data.get('yt_dlp_version', 'unknown')}")
                            error_logger.info(f"   FFmpeg available: {data.get('ffmpeg_available', 'unknown')}")
                            return True
                        except Exception as json_error:
                            error_logger.warning(f"Service responded 200 but JSON parsing failed: {json_error}")
                            return True  # Still consider it healthy if it responds
                    else:
                        response_text = await response.text()
                        error_logger.warning(f"❌ Service health check failed with status {response.status}")
                        error_logger.warning(f"   Response: {response_text[:200]}...")
                        return False
        except aiohttp.ClientConnectorError as e:
            error_logger.error(f"❌ Service health check - connection failed: {e}")
            error_logger.error(f"   This usually means the service is not running or not accessible")
            return False
        except asyncio.TimeoutError:
            error_logger.error(f"❌ Service health check - timeout after 5 seconds")
            error_logger.error(f"   Service may be overloaded or network is slow")
            return False
        except Exception as e:
            error_logger.error(f"❌ Service health check - unexpected error: {e}")
            return False

    async def _download_from_service(self, url: str, format: str = "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best[ext=mp4]") -> Tuple[Optional[str], Optional[str]]:
        """Download video using the local service with enhanced retry logic."""
        if not self.service_url or not self.api_key:
            error_logger.warning("Skipping service download: no service URL or API key configured.")
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
                            "best[ext=mp4][height<=720]/best[ext=mp4]/best"  # Lower quality fallback
                        ]
                        current_format = retry_formats[min(attempt - 1, len(retry_formats) - 1)]
                        payload = {"url": url, "format": current_format}
                        error_logger.info(f"   Using retry format: {current_format}")
                    else:
                        payload = {"url": url, "format": format}

                    try:
                        async with session.post(download_url, json=payload, headers=headers, timeout=120, ssl=False) as response:
                            error_logger.info(f"   Response status: {response.status}")

                            if response.status == 200:
                                data = await response.json()
                                error_logger.info(f"   Service response: success={data.get('success')}, status={data.get('status')}")

                                if data.get("success"):
                                    if data.get("status") == "processing":
                                        error_logger.info(f"   Background processing started, download_id: {data.get('download_id')}")
                                        return await self._poll_service_for_completion(session, data["download_id"], headers)
                                    else:
                                        error_logger.info(f"   Direct download completed: {data.get('title', 'Unknown title')}")
                                        return await self._fetch_service_file(session, data, headers)
                                else:
                                    error_message = data.get('error', 'Unknown error')
                                    error_logger.error(f"   Service reported failure: {error_message}")

                                    # For Instagram, continue retrying on certain errors
                                    if is_instagram and any(keyword in error_message.lower() for keyword in InstagramConfig.RETRY_ERROR_PATTERNS):
                                        error_logger.info(f"   Instagram-specific error detected, will retry: {error_message}")
                                        if attempt < max_attempts - 1:
                                            await asyncio.sleep(self._calculate_retry_delay(attempt, is_instagram))
                                            continue
                                    return None, None
                            elif response.status in [502, 503, 504]:
                                error_logger.warning(f"   Service unavailable (HTTP {response.status}). Retrying in {self._calculate_retry_delay(attempt, is_instagram)}s...")
                                await asyncio.sleep(self._calculate_retry_delay(attempt, is_instagram))
                            elif response.status == 403:
                                error_logger.error(f"   Authentication failed (HTTP 403) - check API key")
                                return None, None
                            elif response.status == 429:  # Rate limiting
                                retry_delay = self._calculate_retry_delay(attempt, is_instagram) * 2
                                error_logger.warning(f"   Rate limited (HTTP 429). Retrying in {retry_delay}s...")
                                await asyncio.sleep(retry_delay)
                            else:
                                response_text = await response.text()
                                error_logger.error(f"   Service download failed with status {response.status}")
                                error_logger.error(f"   Response: {response_text[:200]}...")

                                # For Instagram, retry on certain HTTP errors
                                if is_instagram and response.status in [400, 404, 500]:
                                    if attempt < max_attempts - 1:
                                        await asyncio.sleep(self._calculate_retry_delay(attempt, is_instagram))
                                        continue
                                return None, None
                    except aiohttp.ClientConnectorError as e:
                        error_logger.error(f"   Connection error on attempt {attempt + 1}: {e}")
                        if attempt < max_attempts - 1:
                            retry_delay = self._calculate_retry_delay(attempt, is_instagram)
                            error_logger.info(f"   Retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                    except asyncio.TimeoutError:
                        error_logger.error(f"   Timeout on attempt {attempt + 1} (120s limit)")
                        if attempt < max_attempts - 1:
                            retry_delay = self._calculate_retry_delay(attempt, is_instagram)
                            error_logger.info(f"   Retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                    except Exception as e:
                        error_logger.error(f"   Unexpected error on attempt {attempt + 1}: {e}")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(self._calculate_retry_delay(attempt, is_instagram))
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
            max_delay = 30.0  # Default max delay

        # Exponential backoff: base_delay * (multiplier ^ attempt)
        delay = base_delay * (multiplier ** attempt)

        # Cap maximum delay
        return min(delay, max_delay)

    async def _poll_service_for_completion(self, session: aiohttp.ClientSession, download_id: str, headers: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
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
                            return await self._fetch_service_file(session, status_data, headers)
                        elif status_data.get("status") == "failed":
                            error_logger.error(f"Background download failed: {status_data.get('error')}")
                            return None, None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error_logger.error(f"Polling failed: {e}")
                return None, None
        error_logger.error("Background download timed out.")
        return None, None

    async def _fetch_service_file(self, session: aiohttp.ClientSession, data: Dict[str, Any], headers: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """Fetch the downloaded file from the service."""
        service_file_path = data.get("file_path")
        if not service_file_path or not self.service_url:
            return None, None
        
        file_url = urljoin(self.service_url, f"files/{os.path.basename(service_file_path)}")
        local_file = os.path.join(self.download_path, os.path.basename(service_file_path))
        
        try:
            async with session.get(file_url, headers=headers) as file_response:
                if file_response.status == 200:
                    with open(local_file, 'wb') as f:
                        async for chunk in file_response.content.iter_chunked(8192):
                            f.write(chunk)
                    video_title = data.get("title", "Video")
                    return local_file, video_title
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error_logger.error(f"File fetch failed: {e}")
        return None, None

    async def download_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        async with self.lock:
            try:
                url = url.strip().strip('\\')
                if self._is_story_url(url):
                    error_logger.info(f"Story URL detected and skipped: {url}")
                    return None, None

                platform = self._get_platform(url)
                is_youtube_shorts = "youtube.com/shorts" in url.lower()
                is_youtube_clips = "youtube.com/clip" in url.lower()
                is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
                parsed_url = urlparse(url)
                host = parsed_url.hostname or ""
                is_instagram = host == "instagram.com" or host.endswith(".instagram.com")

                # Prioritize service for YouTube, Instagram, and other problematic platforms
                if is_youtube or is_instagram:
                    error_logger.info(f"🎬 Processing {'YouTube' if is_youtube else 'Instagram'} URL: {url}")
                    error_logger.info(f"   URL type: {'Shorts' if is_youtube_shorts else 'Clips' if is_youtube_clips else 'Regular'}")
                    
                    # Try service first
                    error_logger.info(f"🔧 Checking service availability...")
                    if await self._check_service_health():
                        result = await self._download_from_service(url)
                        if result and result[0]:
                            error_logger.info(f"✅ Service download successful for: {url}")
                            return result
                        else:
                            error_logger.warning(f"⚠️ Service download failed for: {url}, falling back to direct strategies")
                    else:
                        error_logger.warning(f"⚠️ Service unavailable for: {url}, using direct strategies")
                
                # For TikTok, use direct download
                if platform == Platform.TIKTOK:
                    return await self._download_tiktok_ytdlp(url)
                
                # For YouTube, try multiple strategies
                if is_youtube:
                    return await self._download_youtube_with_strategies(url, is_youtube_shorts, is_youtube_clips)
                
                # For other platforms, use direct download
                config = self.platform_configs.get(platform)
                return await self._download_generic(url, platform, config)

            except Exception as e:
                error_logger.error(f"Download error for {url}: {e}")
                return None, None

    async def _download_youtube_with_strategies(self, url: str, is_shorts: bool = False, is_clips: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """Download YouTube video using multiple fallback strategies."""
        error_logger.info(f"🎯 Starting YouTube download with multiple strategies for: {url}")
        error_logger.info(f"   Type: {'Shorts' if is_shorts else 'Clips' if is_clips else 'Regular'}")
        
        # Define strategies in order of preference (Android client works best based on testing)
        strategies = [
            {
                'name': 'Android client with simple formats',
                'format': '18/22/best[ext=mp4]/best',
                'args': [
                    '--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                    '--extractor-args', 'youtube:player_client=android',
                    '--sleep-interval', '1',
                    '--max-sleep-interval', '3',
                ]
            },
            {
                'name': 'iOS client with H.264',
                'format': 'bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/18/22/best',
                'args': [
                    '--user-agent', 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
                    '--extractor-args', 'youtube:player_client=ios',
                ]
            },
            {
                'name': 'Web client with headers',
                'format': '18/22/best[ext=mp4]/best',
                'args': [
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    '--referer', 'https://www.youtube.com/',
                    '--extractor-args', 'youtube:player_client=web',
                    '--sleep-interval', '1',
                    '--max-sleep-interval', '3',
                ]
            },
            {
                'name': 'TV client fallback',
                'format': 'best[ext=mp4]/best',
                'args': [
                    '--extractor-args', 'youtube:player_client=tv_embedded',
                ]
            },
            {
                'name': 'Any format fallback',
                'format': 'best',
                'args': [
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ]
            }
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

    async def _try_youtube_strategy(self, url: str, strategy: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Try a single YouTube download strategy."""
        unique_filename = f"yt_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(self.download_path, unique_filename)
        
        # Build command
        cmd = [
            self.yt_dlp_path, url,
            '-o', output_path,
            '--merge-output-format', 'mp4',
            '--no-check-certificate',
            '--geo-bypass',
            '--ignore-errors',
            '--no-playlist',
            '--socket-timeout', '30',
            '--retries', '2',
            '--fragment-retries', '2',
            '-f', strategy['format']
        ] + strategy['args']
        
        error_logger.info(f"   Command: {' '.join(cmd[:8])}... (truncated)")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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
                error_logger.warning(f"   ❌ Process failed (code {process.returncode})")
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
                    if not (process.returncode == 0 and os.path.getsize(output_path) > 0):
                        os.remove(output_path)
                except:
                    pass

    async def _get_video_title(self, url: str) -> str:
        try:
            # For YouTube Shorts, get both title and hashtags with better error handling
            if "youtube.com/shorts" in url.lower():
                error_logger.info(f"Getting title for YouTube Shorts: {url}")
                
                # Extract video ID for fallback
                video_id = url.split("/shorts/")[1].split("?")[0] if "/shorts/" in url else "unknown"
                
                try:
                    # First try to get just the title (more likely to succeed)
                    title_process = await asyncio.create_subprocess_exec(
                        self.yt_dlp_path,
                        '--get-title',
                        '--no-warnings',
                        url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    # Get title with timeout
                    title_stdout, title_stderr = await asyncio.wait_for(title_process.communicate(), timeout=15.0)
                    title = title_stdout.decode().strip()
                    
                    if not title:
                        error_logger.warning(f"Empty title for YouTube Shorts: {url}")
                        error_logger.warning(f"Title stderr: {title_stderr.decode().strip()}")
                        title = f"YouTube Short {video_id}"
                    
                    # Try to get tags if we have a title
                    hashtags = ""
                    try:
                        tags_process = await asyncio.create_subprocess_exec(
                            self.yt_dlp_path,
                            '--get-tags',
                            '--no-warnings',
                            url,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        # Get tags with a shorter timeout
                        tags_stdout, _ = await asyncio.wait_for(tags_process.communicate(), timeout=10.0)
                        tags = tags_stdout.decode().strip()
                        
                        # Add hashtags if available
                        if tags:
                            hashtags = " ".join([f"#{tag.strip()}" for tag in tags.split(',')])
                    except (asyncio.TimeoutError, Exception) as e:
                        error_logger.warning(f"Failed to get tags for YouTube Shorts: {str(e)}")
                    
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
                    '--get-title',
                    '--no-warnings',
                    url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Add timeout
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
                title = stdout.decode().strip()
                
                if not title:
                    error_logger.warning(f"Empty title for URL: {url}")
                    error_logger.warning(f"Stderr: {stderr.decode().strip()}")
                    # Try to extract some identifier from the URL
                    parts = url.split('/')
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
            username = update.effective_user.username if update.effective_user else "Unknown"
            error_logger.error(
                f"🚨 Sticker Error\n"
                f"Error: {str(e)}\n"
                f"User ID: {user_id}\n"
                f"Username: @{username}"
            )
            if update.message:
                await update.message.reply_text("❌ An error occurred.")

    async def handle_video_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle video link with improved error handling and resource cleanup."""
        processing_msg = None
        filename = None

        try:
            if not update.message or not update.message.text:
                return
                
            message_text = update.message.text.strip()
            if not self.extract_urls:
                return
            urls = self.extract_urls(message_text)
            
            if not urls:
                await self.send_error_sticker(update)
                return

            # Filter out story URLs
            urls = [url for url in urls if not self._is_story_url(url)]
            if not urls:
                if update.message:
                    await update.message.reply_text("❌ Stories are not supported for download.")
                return

            if update.message:
                processing_msg = await update.message.reply_text("⏳ Processing your request...")
            
            for url in urls:
                filename, title = await self.download_video(url)
                if filename and os.path.exists(filename):
                    await self._send_video(update, context, filename, title, source_url=url)
                else:
                    await self._handle_download_error(update, url)

        except Exception as e:
            await self._handle_processing_error(update, e, message_text)
        finally:
            await self._cleanup(processing_msg, filename, update)

    async def _send_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, filename: str, title: Optional[str], source_url: Optional[str] = None) -> None:
        try:
            file_size = os.path.getsize(filename)
            max_size = 50 * 1024 * 1024  # 50MB limit for Telegram
            
            if file_size > max_size:
                error_logger.warning(f"File too large: {file_size} bytes")
                if update.message:
                    await update.message.reply_text("❌ Video file too large to send.")
                return

            # Escape all special characters for Markdown V2
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            escaped_title = title or "Video"
            for char in special_chars:
                escaped_title = escaped_title.replace(char, f'\\{char}')

            # Get username and escape it
            username = "Unknown"
            if update.effective_user:
                username = update.effective_user.username or update.effective_user.first_name or "Unknown"
            escaped_username = username
            for char in special_chars:
                escaped_username = escaped_username.replace(char, f'\\{char}')

            caption = f"📹 {escaped_title}\n\n👤 Від: @{escaped_username}"
            
            if source_url:
                # Escape special characters in URL
                escaped_url = source_url
                for char in special_chars:
                    escaped_url = escaped_url.replace(char, f'\\{char}')
                caption += f"\n\n🔗 [Посилання]({escaped_url})"

            with open(filename, 'rb') as video_file:
                # Check if the original message was a reply to another message
                if update.message and update.message.reply_to_message:
                    # If it was a reply, send the video as a reply to the parent message
                    await update.message.reply_to_message.reply_video(
                        video=video_file,
                        caption=caption,
                        parse_mode='MarkdownV2'  # Enable Markdown V2 formatting
                    )
                else:
                    # If it wasn't a reply, send the video as a new message (not as a reply)
                    if update.effective_chat:
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=video_file,
                            caption=caption,
                            parse_mode='MarkdownV2'  # Enable Markdown V2 formatting
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
        from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity, send_error_feedback
        
        # Determine platform for better error context
        platform = "unknown"
        if "youtube.com" in url or "youtu.be" in url:
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
            platform = next((p for p in self.supported_platforms if p in url), 'unknown')
        
        # Create context information
        context = {
            "url": url,
            "platform": platform,
            "user_id": update.effective_user.id if update and update.effective_user else None,
            "username": update.effective_user.username if update and update.effective_user else None,
        }
        
        # Create a standard error
        error = ErrorHandler.create_error(
            message=f"Failed to download video from {platform}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            context=context
        )
        
        # Log error with our standard format
        error_message = ErrorHandler.format_error_message(error, update, prefix="⬇️")
        error_logger.error(error_message)
        
        # Send error feedback to user
        await send_error_feedback(
            update=update,
            stickers=self.ERROR_STICKERS
        )

    async def _handle_processing_error(self, update: Update, error: Exception, message_text: str) -> None:
        """Handle processing errors with standardized handling."""
        from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity, send_error_feedback
        
        # Create a standard error with the original exception
        std_error = ErrorHandler.create_error(
            message="Error processing video request",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.GENERAL,
            context={
                "message_text": message_text,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "username": update.effective_user.username if update and update.effective_user else None,
            },
            original_exception=error
        )
        
        # Use our centralized error handler
        await ErrorHandler.handle_error(
            error=std_error,
            update=update,
            user_feedback_fn=lambda u, _: send_error_feedback(u, stickers=self.ERROR_STICKERS)
        )

    async def _cleanup(self, processing_msg: Any, filename: Optional[str], update: Update) -> None:
        """Clean up resources after processing."""
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception as e:
                user_id = update.effective_user.id if update.effective_user else "Unknown"
                username = update.effective_user.username if update.effective_user else "Unknown"
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
                user_id = update.effective_user.id if update.effective_user else "Unknown"
                username = update.effective_user.username if update.effective_user else "Unknown"
                error_logger.error(
                    f"🗑️ File Removal Error\n"
                    f"Error: {str(e)}\n"
                    f"File: {filename}\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{username}"
                )

    def _get_yt_dlp_path(self) -> str:
        """Get the path to yt-dlp executable."""
        path = shutil.which('yt-dlp')
        if path:
            return path
        
        common_paths = ['/usr/local/bin/yt-dlp', '/usr/bin/yt-dlp', os.path.expanduser('~/.local/bin/yt-dlp')]
        for p in common_paths:
            if os.path.exists(p):
                return p
        
        return 'yt-dlp'

    def _verify_yt_dlp(self) -> None:
        """Verify yt-dlp is installed and accessible."""
        try:
            subprocess.run([self.yt_dlp_path, '--version'], check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_logger.warning(f"yt-dlp verification failed: {e}. The application will rely on the service.")

    def _init_download_path(self) -> None:
        """Initialize the download directory."""
        try:
            os.makedirs(self.download_path, exist_ok=True)
            error_logger.info(f"Download directory initialized: {self.download_path}")
        except Exception as e:
            error_logger.error(f"Failed to create download directory: {str(e)}")
            raise RuntimeError(f"Could not create download directory: {self.download_path}")

    def _get_platform(self, url: str) -> Platform:
        url = url.lower()
        # Use more precise URL matching to avoid substring attacks
        if url.startswith(('https://tiktok.com/', 'https://www.tiktok.com/', 'https://vm.tiktok.com/', 'https://m.tiktok.com/')):
            return Platform.TIKTOK
        else:
            return Platform.OTHER

    async def _download_tiktok_ytdlp(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using yt-dlp."""
        config = self.platform_configs[Platform.TIKTOK]
        return await self._download_generic(url, Platform.TIKTOK, config)

    async def _download_generic(self, url: str, platform: Platform, special_config: Optional[DownloadConfig] = None) -> Tuple[Optional[str], Optional[str]]:
        """Generic video download using yt-dlp with bot detection avoidance."""
        config = special_config or self.platform_configs.get(platform)
        if not config:
            return None, None

        unique_filename = f"video_{uuid.uuid4()}.mp4"
        output_template = os.path.join(self.download_path, unique_filename)
        
        # Base yt-dlp arguments with bot detection avoidance
        yt_dlp_args = [
            self.yt_dlp_path, url, 
            '-o', output_template, 
            '--merge-output-format', 'mp4',
            '--no-check-certificate',  # Skip SSL certificate verification
            '--geo-bypass',  # Try to bypass geo-restrictions
        ]
        
        # Add format if specified
        if config.format:
            yt_dlp_args.extend(['-f', config.format])
            
        # Add extra arguments if specified
        if config.extra_args:
            yt_dlp_args.extend(config.extra_args)
            
        # Add headers if specified
        if config.headers:
            for key, value in config.headers.items():
                yt_dlp_args.extend(['--add-header', f'{key}:{value}'])

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
                    'name': 'Android client with simple formats',
                    'format': '18/22/best[ext=mp4]/best',  # 360p, 720p, then best MP4
                    'args': [
                        '--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                        '--extractor-args', 'youtube:player_client=android',
                        '--sleep-interval', '1',
                        '--max-sleep-interval', '3',
                    ]
                },
                # Strategy 2: iOS client with H.264 preference
                {
                    'name': 'iOS client with H.264',
                    'format': 'bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/best',
                    'args': [
                        '--user-agent', 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
                        '--extractor-args', 'youtube:player_client=ios',
                    ]
                },
                # Strategy 3: Web client with browser headers
                {
                    'name': 'Web client with headers',
                    'format': '18/22/best[ext=mp4]/best',
                    'args': [
                        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        '--referer', 'https://www.youtube.com/',
                        '--extractor-args', 'youtube:player_client=web',
                        '--sleep-interval', '1',
                        '--max-sleep-interval', '3',
                    ]
                },
                # Strategy 4: Fallback to any format
                {
                    'name': 'Any format fallback',
                    'format': 'best',
                    'args': [
                        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        '--extractor-args', 'youtube:player_client=web',
                    ]
                }
            ]
            
            # Try each strategy
            for i, strategy in enumerate(strategies):
                strategy_name = strategy['name']
                strategy_format = strategy['format']
                strategy_args = strategy['args']
                
                error_logger.info(f"Trying YouTube strategy {i+1}/{len(strategies)}: {strategy_name}")
                
                # Create base args for this strategy
                strategy_yt_dlp_args = [
                    self.yt_dlp_path, url, 
                    '-o', output_template, 
                    '--merge-output-format', 'mp4',
                    '--no-check-certificate',
                    '--geo-bypass',
                    '--retries', '2',
                    '--fragment-retries', '3',
                    '-f', strategy_format
                ]
                
                # Add strategy-specific args
                strategy_yt_dlp_args.extend(strategy_args)
                
                try:
                    error_logger.info(f"Executing: {' '.join(strategy_yt_dlp_args[:8])}... (truncated)")
                    process = await asyncio.create_subprocess_exec(
                        *strategy_yt_dlp_args, 
                        stdout=asyncio.subprocess.PIPE, 
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)

                    if process.returncode == 0 and os.path.exists(output_template):
                        error_logger.info(f"✅ YouTube download successful with strategy: {strategy_name}")
                        return output_template, await self._get_video_title(url)
                    else:
                        stderr_text = stderr.decode()
                        
                        # Check for specific errors
                        if "could not find" in stderr_text and "cookies database" in stderr_text:
                            error_logger.warning(f"❌ Strategy '{strategy_name}' failed: missing browser cookies")
                        elif "Sign in to confirm you're not a bot" in stderr_text:
                            error_logger.warning(f"❌ Strategy '{strategy_name}' failed: bot detection")
                        elif "Failed to extract" in stderr_text and "player response" in stderr_text:
                            error_logger.warning(f"❌ Strategy '{strategy_name}' failed: YouTube API extraction error")
                        else:
                            error_logger.warning(f"❌ Strategy '{strategy_name}' failed: {stderr_text[:150]}...")
                        
                        # Clean up any partial files
                        if os.path.exists(output_template):
                            try:
                                os.remove(output_template)
                            except:
                                pass
                        
                        # If this is not the last strategy, continue to next
                        if i < len(strategies) - 1:
                            continue
                        else:
                            error_logger.error(f"❌ All YouTube strategies failed for {url}")
                            return None, None
                            
                except (asyncio.TimeoutError, Exception) as e:
                    error_logger.warning(f"❌ Strategy '{strategy_name}' error: {e}")
                    if 'process' in locals() and process.returncode is None:
                        try:
                            process.kill()
                            await process.wait()
                        except:
                            pass
                    
                    # Clean up any partial files
                    if os.path.exists(output_template):
                        try:
                            os.remove(output_template)
                        except:
                            pass
                    
                    # If this is not the last strategy, continue to next
                    if i < len(strategies) - 1:
                        continue
                    else:
                        error_logger.error(f"❌ All YouTube strategies failed with errors for {url}")
                        return None, None
            
            # This should not be reached, but just in case
            return None, None

        # For non-YouTube URLs, use the standard approach
        try:
            error_logger.info(f"Starting yt-dlp download with args: {' '.join(yt_dlp_args[:5])}...")  # Log first 5 args only
            process = await asyncio.create_subprocess_exec(
                *yt_dlp_args, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90.0)  # Increased timeout

            if process.returncode == 0:
                if os.path.exists(output_template):
                    error_logger.info(f"Download successful: {output_template}")
                    return output_template, await self._get_video_title(url)
                else:
                    error_logger.warning(f"Download completed but file not found: {output_template}")
            else:
                stderr_text = stderr.decode()
                error_logger.error(f"Download failed for {url}: {stderr_text}")
                
        except (asyncio.TimeoutError, Exception) as e:
            error_logger.error(f"Generic download error for {url}: {e}")
            if 'process' in locals() and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass

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
            r"youtu\.be/stories/"
        ]
        for pattern in story_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

def setup_video_handlers(application: Any, extract_urls_func: Optional[Callable[..., Any]] = None) -> None:
    """Set up video handlers with improved configuration."""
    general_logger.info("Initializing video downloader...")
    video_downloader = VideoDownloader(
        download_path='downloads',
        extract_urls_func=extract_urls_func
    )
    
    application.bot_data['video_downloader'] = video_downloader

    # Use the supported platforms from const.py
    video_pattern = '|'.join(VideoPlatforms.SUPPORTED_PLATFORMS)
    general_logger.info(f"Setting up video handler with pattern: {video_pattern}")
    
    # Add the video handler with high priority
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(video_pattern),
            video_downloader.handle_video_link,
            block=True  # Block other handlers to ensure video processing takes priority
        ),
        group=1  # Higher priority group
    )
    
    general_logger.info("Video handler setup complete")
