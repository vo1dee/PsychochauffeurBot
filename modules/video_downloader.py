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
from modules.file_manager import error_logger, init_error_handler
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')

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
    max_retries: int = 1
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
        self.yt_dlp_path = self._get_yt_dlp_path()  # Fixed method name here
        
        self._init_download_path()
        self._verify_yt_dlp()

        self.lock = Lock()
        self.last_download = {}
        
        # Platform-specific download configurations
        self.platform_configs = {
            Platform.INSTAGRAM: DownloadConfig(
                format="best",
                headers={
                    "User-Agent": "Instagram 219.0.0.12.117 Android",
                    "Cookie": "ds_user_id=12345; sessionid=ABC123"
                }
            ),
            Platform.TIKTOK: DownloadConfig(
                format="best",
                max_retries=3,
                headers={
                    "User-Agent": "TikTok/26.2.0 (iPhone; iOS 14.4.2; Scale/3.00)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5"
                },
                extra_args=[
                    "--no-check-certificates",
                    "--no-warnings",
                    "--quiet",
                    "--referer", "https://www.tiktok.com/"
                ]
            ),
            Platform.OTHER: DownloadConfig(
                format="best[height<=720]"
            )
        }



    def _init_download_path(self) -> None:
        """Initialize download directory."""
        os.makedirs(self.download_path, exist_ok=True)

    def _verify_yt_dlp(self) -> None:
        """Verify yt-dlp installation."""
        if not self.yt_dlp_path:
            error_msg = "yt-dlp not found. Please install it using: sudo pip3 install --break-system-packages yt-dlp"
            error_logger.error(error_msg)
            raise RuntimeError(error_msg)


    def _get_platform(self, url: str) -> Platform:
        """Determine the platform from the URL."""
        url = url.lower()
        if "tiktok.com" in url:
            return Platform.TIKTOK
        elif "instagram.com" in url:
            return Platform.INSTAGRAM
        else:
            return Platform.OTHER



    @staticmethod
    def _get_yt_dlp_path() -> Optional[str]:  # Changed from _find_yt_dlp to _get_yt_dlp_path
        """Find yt-dlp executable path."""
        try:
            import subprocess
            common_paths = [
                '/usr/local/bin/yt-dlp',
                '/usr/bin/yt-dlp',
                '/bin/yt-dlp',
                os.path.expanduser('~/.local/bin/yt-dlp')
            ]
            
            # Try 'which' command first
            result = subprocess.run(['which', 'yt-dlp'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Check common paths
            return next((path for path in common_paths 
                       if os.path.exists(path) and os.access(path, os.X_OK)), None)
                    
        except Exception as e:
            error_logger.error(f"Error finding yt-dlp: {str(e)}")
            return None


    async def _build_download_command(self, url: str, platform: Platform) -> List[str]:
        """Build platform-specific download command."""
        config = self.platform_configs[platform]
        output_template = os.path.join(self.download_path, 'video.%(ext)s')
        
        command = [
            self.yt_dlp_path,
            '--no-check-certificates',
            '--no-warnings',
            '--merge-output-format', 'mp4',
            '-f', config.format,
            '-o', output_template
        ]

        # Add headers if configured
        if config.headers:
            for key, value in config.headers.items():
                command.extend(['--add-header', f'{key}: {value}'])

        # Add extra arguments if configured
        if config.extra_args:
            command.extend(config.extra_args)

        command.append(url)
        return command

    async def _extract_tiktok_video_id(self, url: str) -> Optional[str]:
        """Extract TikTok video ID from URL."""
        patterns = [
            r'video/(\d+)',
            r'/v/(\d+)',
            r'tiktok.com/.*?/video/(\d+)',
            r'vm.tiktok.com/(\w+)',
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.group(1)
        return None

    async def _get_tiktok_download_url(self, url: str) -> Optional[str]:
        """Get direct download URL for TikTok video."""
        try:
            # First, resolve any short URL
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5"
                }
                
                async with session.get(url, headers=headers, allow_redirects=True) as response:
                    if response.status != 200:
                        error_logger.error(f"Failed to fetch TikTok URL: Status {response.status}")
                        return None
                        
                    final_url = str(response.url)
                    video_id = None
                    
                    if match := re.search(r'/video/(\d+)', final_url):
                        video_id = match.group(1)
                    
                    if not video_id:
                        text = await response.text()
                        if match := re.search(r'"id":"(\d+)"', text):
                            video_id = match.group(1)

                    if not video_id:
                        error_logger.error(f"Could not extract video ID from URL: {url}")
                        return None

                    if not RAPIDAPI_KEY:
                        error_logger.error("RAPIDAPI_KEY not found in environment variables")
                        return None

                    # Use rapid API endpoint
                    api_url = "https://tiktok-download-without-watermark.p.rapidapi.com/analysis"
                    headers = {
                        "X-RapidAPI-Key": RAPIDAPI_KEY,
                        "X-RapidAPI-Host": "tiktok-download-without-watermark.p.rapidapi.com"
                    }
                    params = {"url": final_url}

                    try:
                        async with session.get(api_url, headers=headers, params=params) as api_response:
                            if api_response.status == 200:
                                data = await api_response.json()
                                if data and isinstance(data, dict):
                                    play_url = data.get("data", {}).get("play")
                                    if play_url:
                                        return play_url
                                    error_logger.error(f"No play URL found in RapidAPI response: {data}")
                            else:
                                error_logger.error(f"RapidAPI request failed with status: {api_response.status}")
                    except aiohttp.ClientError as e:
                        error_logger.error(f"RapidAPI request failed: {str(e)}")

                    # Fallback to alternative API if RapidAPI fails
                    fallback_api = f"https://api.tiktokv.com/aweme/v1/feed/?aweme_id={video_id}"
                    headers = {
                        "User-Agent": "TikTok 26.2.0 rv:262018 (iPhone; iOS 14.4.2; en_US) Cronet",
                        "Accept": "application/json"
                    }
                    
                    async with session.get(fallback_api, headers=headers) as fallback_response:
                        if fallback_response.status == 200:
                            data = await fallback_response.json()
                            if data and isinstance(data, dict):
                                try:
                                    aweme_list = data.get('aweme_list', [])
                                    if aweme_list and len(aweme_list) > 0:
                                        video_data = aweme_list[0].get('video', {})
                                        play_addr = video_data.get('play_addr', {})
                                        url_list = play_addr.get('url_list', [])
                                        if url_list and len(url_list) > 0:
                                            return url_list[0]
                                        error_logger.error("No URL found in url_list")
                                    else:
                                        error_logger.error("No videos found in aweme_list")
                                except Exception as e:
                                    error_logger.error(f"Error parsing fallback API response: {str(e)}")
                        else:
                            error_logger.error(f"Fallback API request failed with status: {fallback_response.status}")

            error_logger.error("All download methods failed")
            return None
            
        except aiohttp.ClientError as e:
            error_logger.error(f"Network error during download: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            error_logger.error(f"Invalid JSON response: {str(e)}")
            return None
        except Exception as e:
            error_logger.error(f"Unexpected error: {str(e)}")
            return None

    async def _download_tiktok_api(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using API method."""
        try:
            video_id = await self._extract_tiktok_video_id(url)
            if not video_id:
                error_logger.error(f"Could not extract video ID from URL: {url}")
                return None, None

            api_url = f"https://api16-normal-c-useast1a.tiktokv.com/aweme/v1/feed/?aweme_id={video_id}"
            headers = {
                "User-Agent": "TikTok 26.2.0 rv:262018 (iPhone; iOS 14.4.2; en_US) Cronet"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and isinstance(data, dict):
                            try:
                                aweme_list = data.get('aweme_list', [])
                                if aweme_list and len(aweme_list) > 0:
                                    video_data = aweme_list[0].get('video', {})
                                    play_addr = video_data.get('play_addr', {})
                                    url_list = play_addr.get('url_list', [])
                                    if url_list and len(url_list) > 0:
                                        video_url = url_list[0]
                                        filename = os.path.join(self.download_path, 'video.mp4')
                                        
                                        async with session.get(video_url) as video_response:
                                            if video_response.status == 200:
                                                with open(filename, 'wb') as f:
                                                    async for chunk in video_response.content.iter_chunked(8192):
                                                        f.write(chunk)
                                                return filename, "TikTok Video"
                                            else:
                                                error_logger.error(f"Video download failed with status: {video_response.status}")
                                    else:
                                        error_logger.error("No URL found in url_list")
                                else:
                                    error_logger.error("No videos found in aweme_list")
                            except Exception as e:
                                error_logger.error(f"Error parsing API response: {str(e)}")
                    else:
                        error_logger.error(f"API request failed with status: {response.status}")
            return None, None
        except Exception as e:
            error_logger.error(f"TikTok API download failed: {str(e)}")
            return None, None

    async def _download_tiktok_ytdlp(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video using yt-dlp method."""
        try:
            command = [
                self.yt_dlp_path,
                '--no-warnings',
                '--format', 'best',
                '-o', os.path.join(self.download_path, 'video.%(ext)s'),
                '--add-header', 'User-Agent: TikTok 26.2.0 rv:262018 (iPhone; iOS 14.4.2; en_US) Cronet',
                '--add-header', 'Accept: application/json',
                url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                filename = os.path.join(self.download_path, 'video.mp4')
                if os.path.exists(filename):
                    return filename, "TikTok Video"
            return None, None
        except Exception as e:
            error_logger.error(f"yt-dlp TikTok download failed: {str(e)}")
            return None, None

    async def _download_generic(self, url: str, platform: Platform) -> Tuple[Optional[str], Optional[str]]:
        """Generic download method for non-TikTok platforms."""
        try:
            command = await self._build_download_command(url, platform)
            config = self.platform_configs[platform]
            
            for attempt in range(config.max_retries):
                try:
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        filename = os.path.join(self.download_path, 'video.mp4')
                        if os.path.exists(filename):
                            title = await self._get_video_title(url)
                            return filename, title
                    
                    error_msg = stderr.decode()
                    error_logger.error(f"Download attempt {attempt + 1} failed: {error_msg}")
                    
                except Exception as e:
                    error_logger.error(f"Download attempt {attempt + 1} error: {str(e)}")
                    if attempt == config.max_retries - 1:
                        raise

            return None, None
        except Exception as e:
            error_logger.error(f"Generic download error: {str(e)}")
            return None, None

    async def download_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download video with improved error handling and multiple fallback methods."""
        try:
            url = url.strip().strip('\\')
            platform = self._get_platform(url)
            
            if platform == Platform.TIKTOK:
                # Try multiple methods for TikTok downloads
                methods = [
                    self._download_tiktok_direct,
                    self._download_tiktok_api,
                    self._download_tiktok_ytdlp
                ]
                
                for method in methods:
                    try:
                        result = await method(url)
                        if result and result[0] and os.path.exists(result[0]):
                            return result
                    except Exception as e:
                        error_logger.error(f"TikTok download method failed: {str(e)}")
                        continue
                
                # If all methods fail, try one last time with a simple configuration
                return await self._download_tiktok_simple(url)
            
            # For other platforms, use the original method
            return await self._download_generic(url, platform)
        
        except Exception as e:
            error_logger.error(f"Download error: {str(e)}")
            return None, None

    async def _download_tiktok_direct(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download TikTok video directly using API."""
        try:
            video_url = await self._get_tiktok_download_url(url)
            if not video_url:
                return None, None
            
            filename = os.path.join(self.download_path, 'video.mp4')
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as response:
                    if response.status == 200:
                        with open(filename, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        return filename, "TikTok Video"
            return None, None
        except Exception as e:
            error_logger.error(f"Direct TikTok download failed: {str(e)}")
            return None, None

    async def _download_tiktok_simple(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Simple fallback method for TikTok downloads."""
        try:
            command = [
                self.yt_dlp_path,
                '--no-warnings',
                '--format', 'best',
                '-o', os.path.join(self.download_path, 'video.%(ext)s'),
                '--user-agent', 'TikTok/26.2.0 (iPhone; iOS 14.4.2; Scale/3.00)',
                '--referer', 'https://www.tiktok.com/',
                url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                filename = os.path.join(self.download_path, 'video.mp4')
                if os.path.exists(filename):
                    return filename, "TikTok Video"
            return None, None
        except Exception as e:
            error_logger.error(f"Simple TikTok download failed: {str(e)}")
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