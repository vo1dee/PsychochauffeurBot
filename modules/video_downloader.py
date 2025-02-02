import yt_dlp
import browser_cookie3
import tempfile
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from const import VideoPlatforms


logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = VideoPlatforms.SUPPORTED_PLATFORMS

class VideoDownloader:
    def __init__(self, download_path='downloads'):  # Change the parameter to download_path
        self.supported_platforms = SUPPORTED_PLATFORMS  # Use the constant directly
        self.download_path = download_path
        os.makedirs(download_path, exist_ok=True)
        self.base_opts = {
            'format': 'best',
            'max_filesize': 50 * 1024 * 1024,
            'nooverwrites': True,
            'no_part': True,
            'retries': 5,
            'fragment_retries': 5,
            'ignoreerrors': False,
            'quiet': True,
            'no_check_certificate': True,
            'extractor_args': {
                'instagram': {
                    'download_thumbnails': False,
                    'extract_flat': False,
                }
            },
            'http_headers': {
                'User-Agent': 'Instagram 219.0.0.12.117 Android',
                'Cookie': ''
            }
        }
        
        # Create downloads directory if it doesn't exist
        os.makedirs(download_path, exist_ok=True)

    def extract_urls(self, text):
        return [text] if text.startswith("http") else []

    async def get_instagram_cookies(self):
        try:
            chrome_cookies = browser_cookie3.chrome(domain_name='.instagram.com')
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.writelines(f'.instagram.com\tTRUE\t/\tTRUE\t2597573456\t{cookie.name}\t{cookie.value}\n' 
                           for cookie in chrome_cookies)
                return f.name
        except Exception as e:
            logger.error(f"Failed to extract Instagram cookies: {e}")
            return None

    async def download_video(self, url):
        try:
            filename = os.path.join(self.download_path, 'video.mp4')
            ydl_opts = self.base_opts.copy()
            ydl_opts['outtmpl'] = filename

            if 'instagram.com' in url:
                url = url.split('?')[0] + ('/' if not url.endswith('/') else '')

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Downloaded Video')
                ydl.download([url])

            if os.path.exists(filename):
                logger.info('Download complete, processing...')
                return filename, title
            else:
                logger.error("File not found after download")
                return None, None

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            return None, None
        except Exception as e:
            logger.error(f"Error in download_video function: {str(e)}")
            return None, None

    async def handle_video_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        processing_msg = None
        try:
            message_text = update.message.text.strip()
            urls = self.extract_urls(message_text)
            if not urls:
                return

            processing_msg = await update.message.reply_text("⏳ Processing your request...")
            
            for url in urls:
                filename, title = await self.download_video(url)
                if filename:
                    with open(filename, 'rb') as video_file:
                        await update.message.reply_video(
                            video=video_file,
                            caption=f"📹 {title}"
                        )
                    os.remove(filename)
                    await processing_msg.delete()
                else:
                    await update.message.reply_text("❌ Video download failed")

        except Exception as e:
            error_msg = f"Error processing video request:\nUser: {update.effective_user.id}\nMessage: {message_text}\nError: {str(e)}"
            logger.error(error_msg)
            
            if processing_msg:
                await processing_msg.delete()
                
            await update.message.reply_sticker(
                sticker="CAACAgIAAxkBAAEKqDFlUKAvtQr8WZeLfd8AAcOk85nqzWYAAioAA8GcYAwt9nwGwHb3ODQE"
            )
            await update.message.reply_text("❌ Something went wrong. Our team has been notified.")

    async def handle_invalid_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Please send a valid video link from supported platforms.")


def setup_video_handlers(application):
    # Initialize video downloader with download path
    video_downloader = VideoDownloader(download_path='downloads')  # Specify the download path
    application.bot_data['video_downloader'] = video_downloader

    # Add video download handlers
    application.add_handler(MessageHandler(
        filters.TEXT & 
        filters.Regex('|'.join(SUPPORTED_PLATFORMS)), 
        video_downloader.handle_video_link
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.Regex('|'.join(SUPPORTED_PLATFORMS)), 
        video_downloader.handle_invalid_link
    ))

    return video_downloader

