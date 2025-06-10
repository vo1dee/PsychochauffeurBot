import asyncio
import random
import os
import logging
import aiohttp
import re
import json
import uuid
from typing import Optional, Tuple, List, Dict
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

    def __init__(self, download_path: str = 'downloads', extract_urls_func=None):
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
        self.last_download = {}
        
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
            format="best[ext=mp4][vcodec~='^avc1'][height<=1080]/best[ext=mp4][vcodec*=avc1][height<=1080]/22/18/best[ext=mp4][height<=1080]/best[ext=mp4]/best",  # H.264 first, then YouTube specific formats
            extra_args=[
                "--ignore-errors",   # Continue on errors
                "--ignore-config",   # Ignore system-wide config
                "--no-playlist",     # Don't download playlists
                "--geo-bypass",      # Try to bypass geo-restrictions
                "--socket-timeout", "30",  # Increased timeout for better reliability
                "--concurrent-fragment-downloads", "1",  # Reduce concurrent downloads for better reliability
                "--retries", "10",  # More retries for better reliability
                "--fragment-retries", "10",  # More fragment retries
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
        # Make sure we have a URL and API key first
        if not self.service_url:
            error_logger.error("Service health check failed: YTDL_SERVICE_URL not configured")
            return False
            
        if not self.api_key:
            error_logger.error("Service health check failed: YTDL_SERVICE_API_KEY not configured")
            return False
            
        try:
            error_logger.info(f"Checking service health at: {self.service_url}/health")
            async with aiohttp.ClientSession() as session:
                headers = {"X-API-Key": self.api_key}
                error_logger.info(f"Request headers: {headers}")
                
                # Use a shorter timeout for the health check - 2 seconds
                async with session.get(
                    f"{self.service_url}/health",
                    headers=headers,
                    timeout=2,
                    ssl=False
                ) as response:
                    response_text = await response.text()
                    error_logger.info(f"Service health check response: {response.status} - {response_text}")
                    
                    if response.status == 200:
                        error_logger.info("Service health check successful")
                        return True
                    error_logger.warning(f"Service health check failed with status {response.status}")
                    return False
        except asyncio.TimeoutError:
            error_logger.error(f"Service health check timed out - connection to {self.service_url} timed out")
            error_logger.error("This could be due to firewall issues or the service being down")
            return False
        except aiohttp.ClientError as e:
            error_logger.error(f"Service health check failed - connection error: {str(e)}")
            error_logger.error(f"Make sure the service is running at {self.service_url} and is accessible from this machine")
            return False
        except Exception as e:
            import traceback
            error_logger.error(f"Service health check failed with exception: {str(e)}")
            error_logger.error(f"Exception type: {type(e)}")
            error_logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def _download_from_service(self, url: str, format: str = "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best[ext=mp4]") -> Tuple[Optional[str], Optional[str]]:
        """Download video using the local service."""
        if not self.service_url:
            error_logger.warning("Skipping service download - no service URL configured")
            return None, None
            
        if not self.api_key:
            error_logger.warning("Skipping service download - no API key available")
            return None, None
        
        try:
            headers = {"X-API-Key": self.api_key}
            payload = {"url": url, "format": format}
            error_logger.info(f"Sending download request to service for URL: {url}")
            
            # Check if it's a YouTube clip/short
            is_youtube_clip = any(x in url for x in ['youtube.com/clip', 'youtu.be/clip', 'youtube.com/shorts', 'youtu.be/shorts'])
            
            async with aiohttp.ClientSession() as session:
                for attempt in range(self.max_retries):
                    try:
                        async with session.post(
                            f"{self.service_url}/download",
                            json=payload,
                            headers=headers,
                            timeout=120,  # Increased from 30 to 120 seconds for YouTube clips
                            ssl=False  # Disable SSL verification for local development
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data["success"]:
                                    # Handle immediate response for YouTube clips
                                    if is_youtube_clip and data.get("status") == "processing":
                                        download_id = data["download_id"]
                                        error_logger.info(f"YouTube clip download started in background, ID: {download_id}")
                                        
                                        # Poll for completion
                                        for poll_attempt in range(60):  # Poll for up to 5 minutes (60 * 5 seconds)
                                            await asyncio.sleep(5)  # Wait 5 seconds between polls
                                            
                                            async with session.get(
                                                f"{self.service_url}/status/{download_id}",
                                                headers=headers
                                            ) as status_response:
                                                if status_response.status == 200:
                                                    status_data = await status_response.json()
                                                    error_logger.info(f"Download status: {status_data.get('status')} - Progress: {status_data.get('progress', 0)}%")
                                                    
                                                    if status_data["status"] == "completed":
                                                        # Download completed, get the file
                                                        service_file = status_data["file_path"]
                                                        local_file = os.path.join(
                                                            self.download_path,
                                                            os.path.basename(service_file)
                                                        )
                                                        
                                                        video_title = status_data.get("title", "Video")
                                                        
                                                        # Transfer file
                                                        async with session.get(
                                                            f"{self.service_url}/files/{os.path.basename(service_file)}",
                                                            headers=headers
                                                        ) as file_response:
                                                            if file_response.status == 200:
                                                                with open(local_file, 'wb') as f:
                                                                    async for chunk in file_response.content.iter_chunked(8192):
                                                                        f.write(chunk)
                                                                error_logger.info(f"YouTube clip download completed: {video_title}")
                                                                return local_file, video_title
                                                    elif status_data["status"] == "failed":
                                                        error_logger.error(f"Background download failed: {status_data.get('error')}")
                                                        return None, None
                                        
                                        error_logger.error("Background download timed out after 5 minutes")
                                        return None, None
                                    else:
                                        # Handle synchronous response for non-clips
                                        service_file = data["file_path"]
                                        local_file = os.path.join(
                                            self.download_path,
                                            os.path.basename(service_file)
                                        )
                                        
                                        # Get title from response or use fallback
                                        video_title = data.get("title") 
                                        if not video_title or video_title == "Video":
                                            # Try description first line as fallback
                                            description = data.get("description", "")
                                            if description:
                                                first_line = description.strip().split('\n')[0]
                                                if first_line and not first_line.startswith('#'):
                                                    video_title = first_line.strip()
                                            
                                            # If still no good title, try using hashtags
                                            if not video_title or video_title == "Video":
                                                hashtags = data.get("hashtags", [])
                                                if hashtags:
                                                    video_title = " ".join(hashtags[:3])  # Use first 3 hashtags
                                        
                                        # Still no title? Use generic with ID
                                        if not video_title or video_title == "Video":
                                            video_title = f"Video from {url.split('/')[-1]}"
                                        
                                        error_logger.info(f"Using video title: {video_title}")
                                        
                                        # Transfer file
                                        async with session.get(
                                            f"{self.service_url}/files/{os.path.basename(service_file)}",
                                            headers=headers
                                        ) as file_response:
                                            if file_response.status == 200:
                                                with open(local_file, 'wb') as f:
                                                    async for chunk in file_response.content.iter_chunked(8192):
                                                        f.write(chunk)
                                                return local_file, video_title
                            elif response.status == 403:
                                error_logger.error("API key authentication failed")
                                return None, None
                            elif response.status != 503:  # Don't retry on non-service errors
                                break
                    except aiohttp.ClientError as e:
                        error_logger.error(f"Service download attempt {attempt + 1} failed: {str(e)}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        break
            return None, None
        except Exception as e:
            error_logger.error(f"Service download error: {str(e)}")
            return None, None

    async def download_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            url = url.strip().strip('\\')
            platform = self._get_platform(url)
            error_logger.info(f"Starting video download for URL: {url}")
            error_logger.info(f"Detected platform: {platform}")
            is_youtube_shorts = "youtube.com/shorts" in url.lower()
            is_youtube_clips = "youtube.com/clip" in url.lower()
            if is_youtube_shorts or is_youtube_clips:
                error_logger.info(f"YouTube {'Shorts' if is_youtube_shorts else 'Clips'} URL detected: {url}")
                service_healthy = await self._check_service_health()
                error_logger.info(f"Service health check result: {service_healthy}")
                if service_healthy:
                    error_logger.info("Attempting service download")
                    result = await self._download_from_service(url)
                    if result[0]:
                        error_logger.info("Service download successful")
                        return result
                    error_logger.warning("Service download failed")
                else:
                    error_logger.warning("Service health check failed")
                config = self.youtube_clips_config if is_youtube_clips else self.youtube_shorts_config
                return await self._download_generic(url, platform, config)
            if platform == Platform.TIKTOK:
                error_logger.info(f"TikTok URL detected: {url}")
                return await self._download_tiktok_ytdlp(url)
            return await self._download_generic(url, platform)
        except Exception as e:
            error_logger.error(f"Download error: {str(e)}")
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
            await update.message.reply_sticker(sticker=chosen_sticker)
        except Exception as e:
            error_logger.error(
                f"🚨 Sticker Error\n"
                f"Error: {str(e)}\n"
                f"User ID: {update.effective_user.id}\n"
                f"Username: @{update.effective_user.username}"
            )
            await update.message.reply_text("❌ An error occurred.")

    async def handle_video_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle video link with improved error handling and resource cleanup."""
        processing_msg = None
        filename = None

        try:
            message_text = update.message.text.strip()
            urls = self.extract_urls(message_text)
            
            if not urls:
                await self.send_error_sticker(update)
                return

            processing_msg = await update.message.reply_text("⏳ Processing your request...")
            
            for url in urls:
                filename, title = await self.download_video(url)
                if filename and os.path.exists(filename):
                    await self._send_video(update, filename, title, source_url=url)
                else:
                    await self._handle_download_error(update, url)

        except Exception as e:
            await self._handle_processing_error(update, e, message_text)
        finally:
            await self._cleanup(processing_msg, filename, update)

    async def _send_video(self, update: Update, filename: str, title: str, source_url: str = None) -> None:
        try:
            file_size = os.path.getsize(filename)
            max_size = 50 * 1024 * 1024  # 50MB limit for Telegram
            
            if file_size > max_size:
                error_logger.warning(f"File too large: {file_size} bytes")
                await update.message.reply_text("❌ Video file too large to send.")
                return

            # Escape all special characters for Markdown V2
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            escaped_title = title
            for char in special_chars:
                escaped_title = escaped_title.replace(char, f'\\{char}')

            caption = f"📹 {escaped_title}"
            
            if source_url:
                # Escape special characters in URL
                escaped_url = source_url
                for char in special_chars:
                    escaped_url = escaped_url.replace(char, f'\\{char}')
                caption += f"\n\n🔗 [Посилання]({escaped_url})"

            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=caption,
                    parse_mode='MarkdownV2'  # Enable Markdown V2 formatting
                )
                
            # Delete the original message after successful video send
            try:
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

    async def _cleanup(self, processing_msg, filename: Optional[str], update: Update) -> None:
        """Clean up resources after processing."""
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception as e:
                error_logger.error(
                    f"🗑️ Cleanup Error\n"
                    f"Error: {str(e)}\n"
                    f"User ID: {update.effective_user.id}\n"
                    f"Username: @{update.effective_user.username}"
                )

        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                error_logger.error(
                    f"🗑️ File Removal Error\n"
                    f"Error: {str(e)}\n"
                    f"File: {filename}\n"
                    f"User ID: {update.effective_user.id}\n"
                    f"Username: @{update.effective_user.username}"
                )

    def _get_yt_dlp_path(self) -> str:
        """Get the path to yt-dlp executable."""
        try:
            # Try to find yt-dlp in PATH
            import shutil
            yt_dlp_path = shutil.which('yt-dlp')
            if yt_dlp_path:
                return yt_dlp_path
                
            # Check common installation locations
            common_paths = [
                '/usr/local/bin/yt-dlp',
                '/usr/bin/yt-dlp',
                'yt-dlp'  # fallback to expecting it in PATH
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return path
                    
            error_logger.warning("yt-dlp not found in common locations, using default 'yt-dlp'")
            return 'yt-dlp'
            
        except Exception as e:
            error_logger.error(f"Error finding yt-dlp path: {str(e)}")
            return 'yt-dlp'

    def _verify_yt_dlp(self) -> None:
        """Verify yt-dlp is installed and accessible."""
        try:
            import subprocess
            subprocess.run([self.yt_dlp_path, '--version'], 
                         check=True, 
                         capture_output=True)
        except Exception as e:
            error_logger.error(f"yt-dlp verification failed: {str(e)}")
            raise RuntimeError("yt-dlp is not properly installed or accessible")

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
        if "tiktok.com" in url or "vm.tiktok.com" in url:
            return Platform.TIKTOK
        else:
            return Platform.OTHER

    async def _download_tiktok_ytdlp(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using yt-dlp."""
        try:
            config = self.platform_configs[Platform.TIKTOK]
            # Force mp4 extension
            unique_filename = f"video_{uuid.uuid4()}.mp4"
            output_template = os.path.join(self.download_path, unique_filename) 

            # Clean up any old files first
            for old_file in os.listdir(self.download_path):
                if old_file.endswith(('.mp4', '.webm')):
                    try:
                        os.remove(os.path.join(self.download_path, old_file))
                    except Exception as e:
                        error_logger.error(f"Failed to remove old file {old_file}: {e}")
            
            process = await asyncio.create_subprocess_exec(
                self.yt_dlp_path,
                url,
                '-f', config.format,
                '-o', output_template,
                '--merge-output-format', 'mp4',
                '--no-warnings',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_template):
                return output_template, await self._get_video_title(url)
                        
            error_logger.error(f"TikTok download failed: {stderr.decode()}")
            return None, None
            
        except Exception as e:
            error_logger.error(f"TikTok download error: {str(e)}")
            return None, None

    async def _download_generic(self, url: str, platform: Platform, special_config: Optional[DownloadConfig] = None) -> Tuple[Optional[str], Optional[str]]:
        """Generic video download using yt-dlp."""
        try:
            # Use special_config if provided, otherwise use platform-specific config
            if special_config is not None:
                config = special_config
            else:
                config = self.platform_configs.get(platform, self.platform_configs[Platform.OTHER])
                
            error_logger.info(f"Using download config: {config}")
            
            # Force mp4 extension
            unique_filename = f"video_{uuid.uuid4()}.mp4"
            output_template = os.path.join(self.download_path, unique_filename) 
            
            # Add more verbose logging for YouTube content
            is_youtube_shorts = "youtube.com/shorts" in url.lower()
            is_youtube_clips = "youtube.com/clip" in url.lower()
            is_youtube_special = is_youtube_shorts or is_youtube_clips
            
            if is_youtube_special:
                content_type = "Shorts" if is_youtube_shorts else "Clips"
                error_logger.info(f"YouTube {content_type} direct download attempt: {url}")
                error_logger.info(f"Using yt-dlp path: {self.yt_dlp_path}")
                error_logger.info(f"Output template: {output_template}")
                error_logger.info(f"Format: {config.format}")
                
                # For clips, try to use a more reliable format option
                format_option = config.format
                if is_youtube_clips:
                    # Use a simpler format for clips to increase reliability
                    format_option = "best[ext=mp4]/best"
                    error_logger.info(f"Using simplified format for YouTube Clips: {format_option}")
                
                # Build args with potential extra options for clips
                yt_dlp_args = [
                    self.yt_dlp_path,
                    url,
                    '-f', format_option,
                    '-o', output_template,
                    '--merge-output-format', 'mp4',
                    '--verbose',  # Enable verbose output for debugging
                ]
                
                # Add specific args for clips if needed
                if is_youtube_clips:
                    # Add additional options that might help with clip downloads
                    yt_dlp_args.extend([
                        '--extractor-retries', '3',
                        '--fragment-retries', '10',
                        '--retry-sleep', '5',
                        '--no-check-certificate',
                        '--geo-bypass',
                    ])
                    error_logger.info("Added extra retry options for YouTube Clips")
            else:
                # Use standard args for other platforms
                yt_dlp_args = [
                    self.yt_dlp_path,
                    url,
                    '-f', config.format,
                    '-o', output_template,
                    '--merge-output-format', 'mp4',
                    '--verbose',  # Enable verbose output for debugging
                ]
                
                # Add platform-specific headers if available
                if config.headers:
                    for key, value in config.headers.items():
                        yt_dlp_args.extend(['--add-header', f'{key}:{value}'])
                        error_logger.info(f"Added header: {key}:{value}")
                
                # Add any extra args from the config
                if config.extra_args:
                    yt_dlp_args.extend(config.extra_args)
                    error_logger.info(f"Added extra args: {config.extra_args}")
            
            error_logger.info(f"Executing yt-dlp command: {' '.join(yt_dlp_args)}")
            process = await asyncio.create_subprocess_exec(
                *yt_dlp_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Log output for debugging
            if stdout:
                error_logger.info(f"Download stdout: {stdout.decode()}")
            if stderr:
                error_logger.info(f"Download stderr: {stderr.decode()}")
            
            if process.returncode == 0:
                # Find the downloaded file
                found_files = []
                for file in os.listdir(self.download_path):
                    if file.endswith(('.mp4', '.webm')):
                        filepath = os.path.join(self.download_path, file)
                        file_info = {"path": filepath, "size": os.path.getsize(filepath)}
                        found_files.append(file_info)
                        
                # If files were found, use the largest one
                if found_files:
                    found_files.sort(key=lambda x: x["size"], reverse=True)
                    largest_file = found_files[0]["path"]
                    error_logger.info(f"Found {len(found_files)} files, using largest: {largest_file} ({found_files[0]['size']} bytes)")
                    return largest_file, await self._get_video_title(url)
                else:
                    error_logger.error(f"No video files found in {self.download_path} after successful download")
                    
            # If direct download failed for clips, try using the service method as fallback
            if is_youtube_clips and process.returncode != 0:
                error_logger.info(f"YouTube Clips direct download failed, trying service method as fallback")
                if hasattr(self, '_download_from_service'):
                    # Use a specialized format string for clips via the service
                    clip_format = "best[ext=mp4]/best"
                    return await self._download_from_service(url, format=clip_format)
                
            if is_youtube_special:
                content_type = "Shorts" if is_youtube_shorts else "Clips"
                error_logger.error(f"YouTube {content_type} download failed (returncode: {process.returncode})")
            else:
                error_logger.error(f"Generic download failed: {stderr.decode()}")
            
            return None, None
            
        except Exception as e:
            import traceback
            error_logger.error(f"Generic download error: {str(e)}")
            error_logger.error(f"Traceback: {traceback.format_exc()}")
            return None, None

def setup_video_handlers(application, extract_urls_func=None):
    """Set up video handlers with improved configuration."""
    general_logger.info("Initializing video downloader...")
    video_downloader = VideoDownloader(
        download_path='downloads',
        extract_urls_func=extract_urls_func
    )
    
    application.bot_data['video_downloader'] = video_downloader

    # More specific filter for video platforms
    video_platforms = [
        'tiktok.com', 'vm.tiktok.com', 'youtube.com/shorts',
        'youtu.be/shorts', 'vimeo.com', 'reddit.com', 'twitch.tv', 'youtube.com/clip'
    ]
    
    video_pattern = '|'.join(video_platforms)
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
    return video_downloader