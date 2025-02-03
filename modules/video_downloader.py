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
        self.download_path = download_path
        self.extract_urls = extract_urls_func
        os.makedirs(download_path, exist_ok=True)
        
        # Define error stickers
        self.ERROR_STICKERS = [
            "CAACAgQAAxkBAAExX39nn7xI2ENP9ev7Ib1-0GCV0TcFvwACNxUAAn_QmFB67ToFiTpdgTYE",
            "CAACAgQAAxkBAAExX31nn7xByvIhPZHPreVkPONIn82IKgACgxcAAuYrIFHS_QFCSfHYGTYE"
        ]

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
            
            if 'instagram.com' in url:
                # Instagram specific command
                command = [
                    'yt-dlp',
                    '-f', 'best',  # Use best format for Instagram
                    '--merge-output-format', 'mp4',
                    '-o', output_template,
                    '--no-check-certificates',
                    '--no-warnings',
                    '--add-header', 'User-Agent: Instagram 219.0.0.12.117 Android',
                    '--add-header', 'Cookie: ds_user_id=12345; sessionid=ABC123',
                    url
                ]
                
                # Try to get clean Instagram URL
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
                # First, list available formats
                list_command = [
                    'yt-dlp',
                    '-F',
                    url
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *list_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                formats = stdout.decode()
                
                # Parse formats to find the best video format
                format_id = None
                for line in formats.split('\n'):
                    if 'video only' in line.lower() or 'mp4' in line.lower():
                        format_id = line.split()[0]
                        break
                
                if not format_id:
                    format_id = 'best'  # Fallback to best if no specific format found
                
                command = [
                    'yt-dlp',
                    '-f', format_id,
                    '--merge-output-format', 'mp4',
                    '-o', output_template,
                    '--no-check-certificates',
                    '--no-warnings',
                    url
                ]
            else:
                command = [
                    'yt-dlp',
                    '-f', 'best[height<=720]',
                    '--merge-output-format', 'mp4',
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
                logger.error(f"yt-dlp error: {stderr.decode()}")
                
                # If Instagram download failed, try alternative method
                if 'instagram.com' in url:
                    logger.info("Trying alternative method for Instagram...")
                    alt_command = [
                        'yt-dlp',
                        '--format', 'dash-HD',  # Try specific Instagram format
                        '--merge-output-format', 'mp4',
                        '-o', output_template,
                        '--no-check-certificates',
                        '--no-warnings',
                        '--add-header', 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15',
                        url
                    ]
                    
                    process = await asyncio.create_subprocess_exec(
                        *alt_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    if process.returncode != 0:
                        return None, None

            # Use the fixed filename
            filename = os.path.join(self.download_path, 'video.mp4')
            if not os.path.exists(filename):
                return None, None

            # Get title based on platform
            if 'instagram.com' in url:
                try:
                    if '/reel/' in url:
                        reel_id = url.split('/reel/')[1].split('/?')[0]
                        title = f"Instagram Reel {reel_id}"
                    else:
                        post_id = url.split('/p/')[1].split('/?')[0]
                        title = f"Instagram Post {post_id}"
                except:
                    title = "Instagram Video"
            else:
                # Regular title extraction for other platforms
                title_command = [
                    'yt-dlp',
                    '--get-title',
                    url
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *title_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                title_stdout, _ = await process.communicate()
                title = title_stdout.decode().strip()

            return filename, title

        except Exception as e:
            logger.error(f"Error in download_video function: {str(e)}")
            return None, None


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



