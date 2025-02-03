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
            error_logger.error("yt-dlp not found. Please install it using: sudo pip3 install --break-system-packages yt-dlp")
            raise RuntimeError("yt-dlp not found. Please install it manually using sudo.")
        
        # Define error stickers
        self.ERROR_STICKERS = [
            "CAACAgQAAxkBAAExX39nn7xI2ENP9ev7Ib1-0GCV0TcFvwACNxUAAn_QmFB67ToFiTpdgTYE",
            "CAACAgQAAxkBAAExX31nn7xByvIhPZHPreVkPONIn82IKgACgxcAAuYrIFHS_QFCSfHYGTYE"
        ]

    def _get_yt_dlp_path(self):
        """Find yt-dlp executable path."""
        try:
            import subprocess
            # Check common paths
            paths = [
                '/usr/local/bin/yt-dlp',
                '/usr/bin/yt-dlp',
                '/bin/yt-dlp',
                os.path.expanduser('~/.local/bin/yt-dlp')
            ]
            
            # Try which command first
            result = subprocess.run(['which', 'yt-dlp'], 
                                 capture_output=True, 
                                 text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Check common paths
            for path in paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    return path
                    
        except Exception as e:
            error_logger.error(f"Error finding yt-dlp: {str(e)}")
        return None

    async def send_error_sticker(self, update: Update):
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

    async def handle_video_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    try:
                        with open(filename, 'rb') as video_file:
                            await update.message.reply_video(
                                video=video_file,
                                caption=f"📹 {title}"
                            )
                    except Exception as e:
                        error_logger.error(
                            f"🎥 Video Sending Error\n"
                            f"Error: {str(e)}\n"
                            f"URL: {url}\n"
                            f"User ID: {update.effective_user.id}\n"
                            f"Username: @{update.effective_user.username}\n"
                            f"File Size: {os.path.getsize(filename) if os.path.exists(filename) else 'N/A'} bytes"
                        )
                        await self.send_error_sticker(update)
                else:
                    error_logger.error(
                        f"⬇️ Download Error\n"
                        f"URL: {url}\n"
                        f"User ID: {update.effective_user.id}\n"
                        f"Username: @{update.effective_user.username}\n"
                        f"Platform: {next((p for p in self.supported_platforms if p in url), 'unknown')}"
                    )
                    await self.send_error_sticker(update)

        except Exception as e:
            error_logger.error(
                f"⚠️ Processing Error\n"
                f"Error: {str(e)}\n"
                f"URL: {url if 'url' in locals() else 'N/A'}\n"
                f"User ID: {update.effective_user.id}\n"
                f"Username: @{update.effective_user.username}\n"
                f"Message: {message_text if 'message_text' in locals() else 'N/A'}"
            )
            await self.send_error_sticker(update)
        finally:
            # Clean up
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

    async def handle_invalid_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        error_logger.error(
            f"🔗 Invalid Link\n"
            f"Message: {update.message.text}\n"
            f"User ID: {update.effective_user.id}\n"
            f"Username: @{update.effective_user.username}"
        )
        await self.send_error_sticker(update)

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
                
            elif 'tiktok.com' in url:
                command = base_command + [
                    '-f', 'best',
                    '-o', output_template,
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