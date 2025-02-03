import asyncio
import random
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from const import VideoPlatforms
from utils import extract_urls
from modules.file_manager import error_logger,init_error_handler

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = VideoPlatforms.SUPPORTED_PLATFORMS


class VideoDownloader:
    def __init__(self, download_path='downloads', extract_urls_func=None):
        self.supported_platforms = SUPPORTED_PLATFORMS
        self.download_path = os.path.abspath(download_path)
        self.extract_urls = extract_urls_func
        self.yt_dlp_path = self._get_yt_dlp_path()
        
        # Create downloads directory
        os.makedirs(download_path, exist_ok=True)
        
        # Verify yt-dlp installation
        if not self.yt_dlp_path:
            error_logger.error("yt-dlp not found. Installing...")
            self._install_yt_dlp()
            self.yt_dlp_path = self._get_yt_dlp_path()
            if not self.yt_dlp_path:
                raise RuntimeError("Could not install or find yt-dlp")
        
        # Define error stickers
        self.ERROR_STICKERS = [
            "CAACAgQAAxkBAAExX39nn7xI2ENP9ev7Ib1-0GCV0TcFvwACNxUAAn_QmFB67ToFiTpdgTYE",
            "CAACAgQAAxkBAAExX31nn7xByvIhPZHPreVkPONIn82IKgACgxcAAuYrIFHS_QFCSfHYGTYE"
        ]

    def _get_yt_dlp_path(self):
        """Find yt-dlp executable path."""
        try:
            import subprocess
            result = subprocess.run(['which', 'yt-dlp'], 
                                 capture_output=True, 
                                 text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Check common paths
            paths = [
                '/usr/local/bin/yt-dlp',
                '/usr/bin/yt-dlp',
                '/bin/yt-dlp',
                os.path.expanduser('~/.local/bin/yt-dlp')
            ]
            
            for path in paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    return path
                    
        except Exception as e:
            error_logger.error(f"Error finding yt-dlp: {str(e)}")
        return None

    def _install_yt_dlp(self):
        """Install yt-dlp using pip."""
        try:
            import subprocess
            subprocess.run(['pip3', 'install', '--user', '--upgrade', 'yt-dlp'], 
                         check=True)
            subprocess.run(['chmod', '+x', 
                          os.path.expanduser('~/.local/bin/yt-dlp')], 
                         check=True)
        except Exception as e:
            error_logger.error(f"Error installing yt-dlp: {str(e)}")

    async def download_video(self, url):
        try:
            # Clean the URL
            url = url.strip().strip('\\')
            
            # Use a simple filename
            output_template = os.path.join(self.download_path, 'video.%(ext)s')
            
            base_command = [
                self.yt_dlp_path,
                '--no-check-certificates',
                '--no-warnings',
                '--merge-output-format', 'mp4'
            ]
            
            if 'instagram.com' in url:
                command = base_command + [
                    '-f', 'best',
                    '-o', output_template,
                    '--add-header', 'User-Agent: Instagram 219.0.0.12.117 Android',
                    '--add-header', 'Cookie: ds_user_id=12345; sessionid=ABC123',
                    url
                ]
                
                # Clean Instagram URL
                try:
                    if '/reel/' in url:
                        reel_id = url.split('/reel/')[1].split('/?')[0]
                        url = f'https://www.instagram.com/reel/{reel_id}/'
                    elif '/p/' in url:
                        post_id = url.split('/p/')[1].split('/?')[0]
                        url = f'https://www.instagram.com/p/{post_id}/'
                except:
                    pass

            elif 'tiktok.com' in url:
                command = base_command + [
                    '-f', 'best',
                    '-o', output_template,
                    '--add-header', 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15',
                    url
                ]
            else:
                command = base_command + [
                    '-f', 'best[height<=720]',
                    '-o', output_template,
                    url
                ]

            # Execute download command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_logger.error(f"Download error: {stderr.decode()}")
                return None, None

            # Check for downloaded file
            filename = os.path.join(self.download_path, 'video.mp4')
            if not os.path.exists(filename):
                return None, None

            # Get title
            title = await self._get_video_title(url)
            return filename, title

        except Exception as e:
            error_logger.error(f"Download error: {str(e)}")
            return None, None

    async def _get_video_title(self, url):
        """Get video title based on platform."""
        try:
            if 'instagram.com' in url:
                if '/reel/' in url:
                    reel_id = url.split('/reel/')[1].split('/?')[0]
                    return f"Instagram Reel {reel_id}"
                else:
                    post_id = url.split('/p/')[1].split('/?')[0]
                    return f"Instagram Post {post_id}"
            
            # Get title using yt-dlp
            process = await asyncio.create_subprocess_exec(
                self.yt_dlp_path,
                '--get-title',
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            title = stdout.decode().strip()
            return title if title else "Video"

        except Exception as e:
            error_logger.error(f"Error getting title: {str(e)}")
            return "Video"


def setup_video_handlers(application, extract_urls_func=None):
    video_downloader = VideoDownloader(
        download_path='downloads',
        extract_urls_func=extract_urls_func
    )
    application.bot_data['video_downloader'] = video_downloader

    # Add handlers
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex('|'.join(SUPPORTED_PLATFORMS)), 
        video_downloader.handle_video_link
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.Regex('|'.join(SUPPORTED_PLATFORMS)), 
        video_downloader.handle_invalid_link
    ))

    return video_downloader



