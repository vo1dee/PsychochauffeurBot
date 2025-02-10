import asyncio
import random
import os
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List, Dict
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from const import VideoPlatforms
from utils import extract_urls
from modules.file_manager import error_logger, init_error_handler

logger = logging.getLogger(__name__)

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
        self.yt_dlp_path = self._find_yt_dlp()
        
        self._init_download_path()
        self._verify_yt_dlp()
        
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
                extra_args=[
                    "--cookies-from-browser", "chrome",
                    "--force-generic-extractor",
                    "--allow-unplayable-formats",
                    "--ignore-config",
                    "--no-playlist"
                ]
            ),
            Platform.OTHER: DownloadConfig(
                format="best[height<=720]"
            )
        }

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

    async def download_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download video with platform-specific configurations and error handling."""
        try:
            url = url.strip().strip('\\')
            platform = self._get_platform(url)
            command = await self._build_download_command(url, platform)

            config = self.platform_configs[platform]
            max_retries = config.max_retries
            
            for attempt in range(max_retries):
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
                    
                    # If we get a specific error about no video formats, try alternative approach
                    if "No video formats found" in error_msg and platform == Platform.TIKTOK:
                        # Try alternative download method for TikTok
                        alt_command = command.copy()
                        alt_command.extend(['--format', 'download_addr-0'])
                        process = await asyncio.create_subprocess_exec(
                            *alt_command,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()
                        if process.returncode == 0:
                            filename = os.path.join(self.download_path, 'video.mp4')
                            if os.path.exists(filename):
                                title = await self._get_video_title(url)
                                return filename, title
                    
                except Exception as e:
                    error_logger.error(f"Download attempt {attempt + 1} error: {str(e)}")
                    if attempt == max_retries - 1:
                        raise

            return None, None

        except Exception as e:
            error_logger.error(f"Download error: {str(e)}")
            return None, None

    # ... [rest of the code remains exactly the same] ...

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