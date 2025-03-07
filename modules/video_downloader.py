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
from modules.logger import init_error_handler, error_logger
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
YTDL_SERVICE_API_KEY = os.getenv('YTDL_SERVICE_API_KEY')

class Platform(Enum):
    INSTAGRAM = "instagram.com"
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
        
        # Service configuration - update to use environment variables
        self.service_url = os.getenv('YTDL_SERVICE_URL')  # Add default value
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
            Platform.INSTAGRAM: DownloadConfig(
                format="best",
                headers={
                    "User-Agent": "Instagram 219.0.0.12.117 Android"
                }
            ),
            Platform.TIKTOK: DownloadConfig(
                format="best",
                max_retries=3,
                headers={
                    "User-Agent": "TikTok/26.2.0 (iPhone; iOS 14.4.2; Scale/3.00)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5"
                }
            ),
            Platform.OTHER: DownloadConfig(
                format="best[height<=720]"
            )
        }

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
        try:
            error_logger.info(f"Checking service health at: {self.service_url}/health")
            async with aiohttp.ClientSession() as session:
                headers = {"X-API-Key": self.api_key} if self.api_key else {}
                error_logger.info(f"Request headers: {headers}")
                
                async with session.get(
                    f"{self.service_url}/health",
                    headers=headers,
                    timeout=5,
                    ssl=False
                ) as response:
                    response_text = await response.text()
                    error_logger.info(f"Service health check response: {response.status} - {response_text}")
                    
                    if response.status == 200:
                        error_logger.info("Service health check successful")
                        return True
                    error_logger.warning(f"Service health check failed with status {response.status}")
                    return False
        except Exception as e:
            error_logger.error(f"Service health check failed with exception: {str(e)}")
            return False

        async def _download_from_service(self, url: str, format: str = "best") -> Tuple[Optional[str], Optional[str]]:
         """Download video using the local service."""
        if not self.api_key:
            error_logger.warning("Skipping service download - no API key available")
            return None, None
        
        try:
            headers = {"X-API-Key": self.api_key}
            payload = {"url": url, "format": format}
            
            async with aiohttp.ClientSession() as session:
                for attempt in range(self.max_retries):
                    try:
                        async with session.post(
                            f"{self.service_url}/download",
                            json=payload,
                            headers=headers,
                            timeout=30,
                            ssl=False  # Disable SSL verification for local development
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data["success"]:
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
        """Download video with service-first approach and fallback."""
        try:
            url = url.strip().strip('\\')
            platform = self._get_platform(url)
            
            # Check if it's a YouTube Shorts URL
            if "youtube.com/shorts" in url.lower():
                error_logger.info(f"YouTube Shorts URL detected: {url}")
                # Try service first for YouTube Shorts
                service_healthy = await self._check_service_health()
                error_logger.info(f"Service health check result: {service_healthy}")
                
                if service_healthy:
                    error_logger.info("Attempting service download")
                    result = await self._download_from_service(url)
                    if result[0]:  # If service download successful
                        error_logger.info("Service download successful")
                        return result
                    error_logger.warning("Service download failed")
                else:
                    error_logger.warning("Service health check failed")
                
                # Fallback to direct download if service fails
                error_logger.warning("Falling back to direct download")
            
            # For all other platforms or if service failed, use direct methods
            return await self._download_generic(url, platform)
            
        except Exception as e:
            error_logger.error(f"Download error: {str(e)}")
            return None, None

    async def _get_video_title(self, url: str) -> str:
        try:
            # For YouTube Shorts, get both title and hashtags
            if "youtube.com/shorts" in url.lower():
                title_process = await asyncio.create_subprocess_exec(
                    self.yt_dlp_path,
                    '--get-title',
                    url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                tags_process = await asyncio.create_subprocess_exec(
                    self.yt_dlp_path,
                    '--get-tags',
                    url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Get results with timeout
                title_stdout, _ = await asyncio.wait_for(title_process.communicate(), timeout=30.0)
                tags_stdout, _ = await asyncio.wait_for(tags_process.communicate(), timeout=30.0)
                
                title = title_stdout.decode().strip() or "Video"
                tags = tags_stdout.decode().strip()
                
                # Add hashtags if available
                if tags:
                    hashtags = " ".join([f"#{tag.strip()}" for tag in tags.split(',')])
                    return f"{title} {hashtags}"
                return title
            else:
                # For other platforms, just get the title
                process = await asyncio.create_subprocess_exec(
                    self.yt_dlp_path,
                    '--get-title',
                    url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Add timeout
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)
                return stdout.decode().strip() or "Video"
        except asyncio.TimeoutError:
            error_logger.error(f"Title fetch timeout for URL: {url}")
            return "Video"
        except Exception as e:
            error_logger.error(f"Error getting title: {str(e)}")
            return "Video"

    @staticmethod
    def _get_instagram_title(url: str) -> str:
        """Extract Instagram content title."""
        try:
            if '/reel/' in url:
                reel_id = url.split('/reel/')[1].split('/?')[0]
                return f"Instagram Reel {reel_id}"
            elif '/p/' in url:
                post_id = url.split('/p/')[1].split('/?')[0]
                return f"Instagram Post {post_id}"
            return "Instagram Video"
        except Exception:
            return "Instagram Video"

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
                caption += f"\n\n🔗 [Source]({escaped_url})"

            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=caption,
                    parse_mode='MarkdownV2'  # Enable Markdown V2 formatting
                )
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
        """Determine the platform from the URL."""
        url = url.lower()
        
        if "instagram.com" in url:
            return Platform.INSTAGRAM
        elif "tiktok.com" in url:
            return Platform.TIKTOK
        else:
            return Platform.OTHER

    async def _download_tiktok_ytdlp(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using yt-dlp."""
        try:
            config = self.platform_configs[Platform.TIKTOK]
            unique_filename = f"video_{uuid.uuid4()}.%(ext)s"
            output_template = os.path.join(self.download_path, unique_filename) 

            
            process = await asyncio.create_subprocess_exec(
                self.yt_dlp_path,
                url,
                '-f', config.format,
                '-o', output_template,
                '--no-warnings',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Find the downloaded file
                for file in os.listdir(self.download_path):
                    if file.endswith(('.mp4', '.webm')):
                        filepath = os.path.join(self.download_path, file)
                        return filepath, await self._get_video_title(url)
                        
            error_logger.error(f"TikTok download failed: {stderr.decode()}")
            return None, None
            
        except Exception as e:
            error_logger.error(f"TikTok download error: {str(e)}")
            return None, None

    async def _download_generic(self, url: str, platform: Platform) -> Tuple[Optional[str], Optional[str]]:
        """Generic video download using yt-dlp."""
        try:
            config = self.platform_configs.get(platform, self.platform_configs[Platform.OTHER])
            unique_filename = f"video_{uuid.uuid4()}.%(ext)s"
            output_template = os.path.join(self.download_path, unique_filename) 

            
            process = await asyncio.create_subprocess_exec(
                self.yt_dlp_path,
                url,
                '-f', config.format,
                '-o', output_template,
                '--no-warnings',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Find the downloaded file
                for file in os.listdir(self.download_path):
                    if file.endswith(('.mp4', '.webm')):
                        filepath = os.path.join(self.download_path, file)
                        return filepath, await self._get_video_title(url)
                        
            error_logger.error(f"Generic download failed: {stderr.decode()}")
            return None, None
            
        except Exception as e:
            error_logger.error(f"Generic download error: {str(e)}")
            return None, None

def setup_video_handlers(application, extract_urls_func=None):
    """Set up video handlers with improved configuration."""
    video_downloader = VideoDownloader(
        download_path='downloads',
        extract_urls_func=extract_urls_func
    )
    
    application.bot_data['video_downloader'] = video_downloader

    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex('|'.join(VideoPlatforms.SUPPORTED_PLATFORMS)), 
        video_downloader.handle_video_link
    ))

    return video_downloader