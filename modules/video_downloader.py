import yt_dlp
import browser_cookie3
import tempfile
import os
import logging
import telegram
from telegram import Update
from telegram.ext import ContextTypes
from modules.file_manager import general_logger, chat_logger, error_logger, init_error_handler

logger = logging.getLogger(__name__)

def extract_urls(text):
    # Dummy implementation, replace with actual URL extraction logic
    return [text] if text.startswith("http") else []

def download_video(url, output_path):
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def get_instagram_cookies():
    """Extract Instagram cookies from Chrome browser"""
    try:
        chrome_cookies = browser_cookie3.chrome(domain_name='.instagram.com')
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.writelines(f'.instagram.com\tTRUE\t/\tTRUE\t2597573456\t{cookie.name}\t{cookie.value}\n' for cookie in chrome_cookies)
            return f.name
    except Exception as e:
        logging.error(f"Failed to extract Instagram cookies: {e}")
        return None

async def download_video(url):
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/video.mp4',
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

        if 'instagram.com' in url:
            url = url.split('?')[0] + ('/' if not url.endswith('/') else '')

        try:
            filename = 'downloads/video.mp4'
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(filename):
                logging.info('Download complete, processing...')
            else:
                logging.error("File not found after download")
                return None, None
        except yt_dlp.utils.DownloadError as e:
            logging.error(f"yt-dlp download error: {str(e)}")
            return None, None
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return None, None
    except Exception as e:
        logging.error(f"Error in download_video function: {str(e)}")
        return None, None

def download_progress(d):
    pass

async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video download request"""
    processing_msg = None
    try:
        message_text = update.message.text.strip()
        urls = extract_urls(message_text)
        if not urls:
            return
        
        processing_msg = await update.message.reply_text("⏳ Processing your request...")
        
        for url in urls:
            if not "/shorts/" in url:
                await update.message.reply_text("#youtube", reply_to_message_id=update.message.message_id)
                return
                
            # ... rest of your download logic ...
            
    except Exception as e:
        error_msg = f"Error processing video request:\nUser: {update.effective_user.id}\nMessage: {message_text}\nError: {str(e)}"
        await error_logger(error_msg)
        
        # Send error sticker
        await update.message.reply_sticker(
            sticker="CAACAgIAAxkBAAEKqDFlUKAvtQr8WZeLfd8AAcOk85nqzWYAAioAA8GcYAwt9nwGwHb3ODQE"
        )
        
        # Clean up processing message
        if processing_msg:
            await processing_msg.delete()
            
        # Notify user
        await update.message.reply_text("❌ Something went wrong. Our team has been notified.")
        
        # Log to console as well
        logging.error(f"Video download error: {str(e)}")

async def handle_invalid_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle messages without supported video links
    """
    await update.message.reply_text("❌ Please send a valid video link from supported platforms.")