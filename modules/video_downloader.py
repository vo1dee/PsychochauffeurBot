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
from typing import Optional, Tuple, List, Dict, Any, Callable
from asyncio import Lock
from dataclasses import dataclass
from enum import Enum
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from modules.const import VideoPlatforms
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
        
        # Special configuration for YouTube Shorts - simplified for iOS compatibility
        self.youtube_shorts_config = DownloadConfig(
            format="18/best[ext=mp4]/best",  # Start with format 18 (360p MP4) which is almost always available
            extra_args=[
                "--ignore-errors",   # Continue on errors
                "--ignore-config",   # Ignore system-wide config
                "--no-playlist",     # Don't download playlists
                "--geo-bypass",      # Try to bypass geo-restrictions
                "--socket-timeout", "30",  # Increased timeout for better reliability
                "--retries", "5",  # Reduced retries for faster response
                "--fragment-retries", "5",  # Reduced fragment retries
                "--merge-output-format", "mp4",  # Ensure MP4 output
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
            return False
        
        health_url = urljoin(self.service_url, "health")
        headers = {"X-API-Key": self.api_key}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, headers=headers, timeout=2, ssl=False) as response:
                    if response.status == 200:
                        error_logger.info("Service health check successful.")
                        return True
                    error_logger.warning(f"Service health check failed with status {response.status}.")
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error_logger.error(f"Service health check failed: {e}")
            return False

    async def _download_from_service(self, url: str, format: str = "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best[ext=mp4]") -> Tuple[Optional[str], Optional[str]]:
        """Download video using the local service."""
        if not self.service_url or not self.api_key:
            error_logger.warning("Skipping service download: no service URL or API key configured.")
            return None, None

        headers = {"X-API-Key": self.api_key}
        payload = {"url": url, "format": format}
        download_url = urljoin(self.service_url, "download")

        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(self.max_retries):
                    try:
                        async with session.post(download_url, json=payload, headers=headers, timeout=120, ssl=False) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data.get("success"):
                                    if data.get("status") == "processing":
                                        return await self._poll_service_for_completion(session, data["download_id"], headers)
                                    else:
                                        return await self._fetch_service_file(session, data, headers)
                            elif response.status in [502, 503, 504]:
                                error_logger.warning(f"Service unavailable (HTTP {response.status}). Retrying...")
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                            else:
                                error_logger.error(f"Service download failed with status {response.status}.")
                                return None, None
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        error_logger.error(f"Service download attempt {attempt + 1} failed: {e}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error_logger.error(f"Service session creation failed: {e}")
            return None, None
        return None, None

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
                parsed_url = urlparse(url)
                host = parsed_url.hostname or ""
                is_instagram = host == "instagram.com" or host.endswith(".instagram.com")

                if is_instagram or is_youtube_shorts or is_youtube_clips:
                    if await self._check_service_health():
                        result = await self._download_from_service(url)
                        if result and result[0]:
                            return result
                
                if platform == Platform.TIKTOK:
                    return await self._download_tiktok_ytdlp(url)
                
                config = self.youtube_clips_config if is_youtube_clips else self.youtube_shorts_config if is_youtube_shorts else self.platform_configs.get(platform)
                return await self._download_generic(url, platform, config)

            except Exception as e:
                error_logger.error(f"Download error for {url}: {e}")
                return None, None

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
        
        # Create context information
        context = {
            "url": url,
            "platform": next((p for p in self.supported_platforms if p in url), 'unknown'),
            "user_id": update.effective_user.id if update and update.effective_user else None,
            "username": update.effective_user.username if update and update.effective_user else None,
        }
        
        # Create a standard error
        error = ErrorHandler.create_error(
            message=f"Failed to download video from {context['platform']}",
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
        """Generic video download using yt-dlp."""
        config = special_config or self.platform_configs.get(platform)
        if not config:
            return None, None

        unique_filename = f"video_{uuid.uuid4()}.mp4"
        output_template = os.path.join(self.download_path, unique_filename)
        
        yt_dlp_args = [self.yt_dlp_path, url, '-o', output_template, '--merge-output-format', 'mp4']
        if config.format:
            yt_dlp_args.extend(['-f', config.format])
        if config.extra_args:
            yt_dlp_args.extend(config.extra_args)
        if config.headers:
            for key, value in config.headers.items():
                yt_dlp_args.extend(['--add-header', f'{key}: {value}'])

        try:
            process = await asyncio.create_subprocess_exec(*yt_dlp_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

            if process.returncode == 0:
                if os.path.exists(output_template):
                    return output_template, await self._get_video_title(url)
            else:
                error_logger.error(f"Download failed for {url}: {stderr.decode()}")
        except (asyncio.TimeoutError, Exception) as e:
            error_logger.error(f"Generic download error for {url}: {e}")
            if 'process' in locals() and process.returncode is None:
                process.kill()

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
