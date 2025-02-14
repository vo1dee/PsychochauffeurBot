import asyncio
import random
import os
import logging
import aiohttp
import re
import json
from typing import Optional, Tuple, List, Dict
from asyncio import Lock
from dataclasses import dataclass
from enum import Enum
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from const import VideoPlatforms
from utils import extract_urls
from modules.file_manager import error_logger
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
        self.yt_dlp_path = self._get_yt_dlp_path()
        
        # Service configuration - update to use environment variables
        self.service_url = os.getenv('YTDL_SERVICE_URL', 'http://192.168.88.27:8000')
        self.max_retries = int(os.getenv('YTDL_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('YTDL_RETRY_DELAY', '1'))
        
        # Load API key from environment or file
        self.api_key = self._load_api_key()
        
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
            async with aiohttp.ClientSession() as session:
                headers = {"X-API-Key": self.api_key}
                async with session.get(
                    f"{self.service_url}/health",
                    headers=headers,
                    timeout=2,  # Reduced timeout
                    ssl=False  # Disable SSL verification for local development
                ) as response:
                    return response.status == 200
        except Exception as e:
            error_logger.debug(f"Service health check failed: {str(e)}")
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
                                    
                                    # Transfer file
                                    async with session.get(
                                        f"{self.service_url}/files/{os.path.basename(service_file)}",
                                        headers=headers
                                    ) as file_response:
                                        if file_response.status == 200:
                                            with open(local_file, 'wb') as f:
                                                async for chunk in file_response.content.iter_chunked(8192):
                                                    f.write(chunk)
                                            return local_file, await self._get_video_title(url) or "Video"
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
            
            # Try service download only if explicitly configured
            if self.api_key and self.service_url:
                try:
                    service_available = await self._check_service_health()
                    if service_available:
                        # Try service download first
                        filename, title = await self._download_from_service(url)
                        if filename and os.path.exists(filename):
                            return filename, title
                except Exception as e:
                    error_logger.warning(f"Service download failed, using direct methods: {str(e)}")
            
            # Use direct download methods
            if platform == Platform.TIKTOK:
                return await self._download_tiktok_ytdlp(url)
            
            return await self._download_generic(url, platform)
            
        except Exception as e:
            error_logger.error(f"Download error: {str(e)}")
            return None, None

    async def _get_video_title(self, url: str) -> str:
        try:
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
                    await self._send_video(update, filename, title)
                else:
                    await self._handle_download_error(update, url)

        except Exception as e:
            await self._handle_processing_error(update, e, message_text)
        finally:
            await self._cleanup(processing_msg, filename, update)

    async def _send_video(self, update: Update, filename: str, title: str) -> None:
        try:
            file_size = os.path.getsize(filename)
            max_size = 50 * 1024 * 1024  # 50MB limit for Telegram
            
            if file_size > max_size:
                error_logger.warning(f"File too large: {file_size} bytes")
                await update.message.reply_text("❌ Video file too large to send.")
                return

            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"📹 {title}"
                )
        except Exception as e:
            error_logger.error(f"Video sending error: {str(e)}")
            await self.send_error_sticker(update)

    async def _handle_download_error(self, update: Update, url: str) -> None:
        """Handle download errors with detailed logging."""
        error_logger.error(
            f"⬇️ Download Error\n"
            f"URL: {url}\n"
            f"User ID: {update.effective_user.id}\n"
            f"Username: @{update.effective_user.username}\n"
            f"Platform: {next((p for p in self.supported_platforms if p in url), 'unknown')}"
        )
        await self.send_error_sticker(update)

    async def _handle_processing_error(self, update: Update, error: Exception, message_text: str) -> None:
        """Handle processing errors with detailed logging."""
        error_logger.error(
            f"⚠️ Processing Error\n"
            f"Error: {str(error)}\n"
            f"User ID: {update.effective_user.id}\n"
            f"Username: @{update.effective_user.username}\n"
            f"Message: {message_text}"
        )
        await self.send_error_sticker(update)

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
            output_template = os.path.join(self.download_path, '%(title)s.%(ext)s')
            
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
            output_template = os.path.join(self.download_path, '%(title)s.%(ext)s')
            
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