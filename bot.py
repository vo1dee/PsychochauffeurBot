import asyncio
import hashlib
import logging
import nest_asyncio
import pytz
import random
import pyshorteners
from urllib.parse import urlparse, urlunparse
import re
import os
import telebot
import yt_dlp
import telegram


from modules.keyboards import create_link_keyboard, button_callback
from utils import remove_links, screenshot_command, schedule_task, cat_command, ScreenshotManager, game_state, game_command, end_game_command, clear_words_command, hint_command, load_game_state
from const import domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID
from modules.gpt import ask_gpt_command, analyze_command, answer_from_gpt
from modules.weather import weather
from modules.file_manager import general_logger, chat_logger
from modules.user_management import restrict_user
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
    ContextTypes
    )
from urllib.parse import urlparse, urlunparse

# Apply the patch to allow nested event loops
nest_asyncio.apply()
LOCAL_TZ = pytz.timezone('Europe/Kyiv')

message_counts = {}

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Supported platforms
SUPPORTED_PLATFORMS = [
    'tiktok.com', 'instagram.com', 'youtube.com', 
    'youtu.be', 'facebook.com', 'twitter.com', 
    'vimeo.com', 'reddit.com','x.com'
]

async def download_video(url):
    """
    Async video download using yt-dlp with Reddit authentication
    """
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',  # Combine best video and audio
        'merge_output_format': 'mp4',
        'postprocessors': [],  # Remove post-processing
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'restrictfilenames': True,  # Restrict file names to safe characters
        'max_filesize': 20 * 1024 * 1024,  # 20MB max file size
        'no_warnings': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'no_color': True,
        'nooverwrites': True,
        'no_part': True,
        'cookiefile': '.reddit_cookies.txt',
        'cookies_from_browser': 'firefox',    
        'retries': 3,
        'fragment_retries': 3,
        'extractor_args': {
            'reddit': {
                'comments': False,  # Disable downloading comments
            }
        },
        # Bypass age restrictions and bot checks
        'age_limit': 0,
        'nocheckcertificate': True,
        
        # Minimize user interaction
        'ignoreerrors': True,
        'quiet': True,
        
        # Retry options
        'retries': 3,
        'fragment_retries': 3,
        
        # Force download without login
        'force_generic_extractor': True,
    }
    try:    
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_title = info_dict.get('title', None)
            filename = ydl.prepare_filename(info_dict)
            
            # Attempt to handle multiple formats
            if isinstance(filename, list):
                filename = filename[0] if filename else None
            
            return filename, video_title
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None


def download_progress(d):
    """
    Log download progress
    """
    if d['status'] == 'finished':
        logger.info('Download complete, processing...')


async def handle_video_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video download request"""
    message_text = update.message.text.strip()
    
    # Extract URLs from the message
    urls = extract_urls(message_text)
    if not urls:
        return
        
    # Take the first URL found
    url = urls[0]
    
    # Check if it's a YouTube link but not a short
    if any(domain in url for domain in ["youtube.com", "youtu.be"]):
        if not "/shorts/" in url:
            await update.message.reply_text("#youtube", reply_to_message_id=update.message.message_id)
            return
    
    # Add debug logging
    logger.info(f"Attempting to download video from URL: {url}")
    
    # Send initial processing message
    processing_msg = await update.message.reply_text("🔄 Processing video...")
    
    try:
        # Download video
        filename, title = await download_video(url)
        
        if filename and os.path.exists(filename):
            # Check file size (50MB limit)
            file_size = os.path.getsize(filename) / (1024 * 1024)  # Convert to MB
            if file_size > 50:
                os.remove(filename)
                await processing_msg.delete()
                await update.message.reply_text("❌ Sorry, the video is too large (>50MB). Try a shorter video.")
                return
            
            # Log successful download
            logger.info(f"Successfully downloaded video: {filename}")
            
            # Send video file
            try:
                with open(filename, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file, 
                        caption=f"📹 {title or 'Downloaded Video'}"
                    )
            except telegram.error.BadRequest as e:
                if "Request Entity Too Large" in str(e):
                    await update.message.reply_text("❌ Sorry, the video is too large to send via Telegram (>50MB).")
                else:
                    raise e
            finally:
                # Clean up downloaded file
                os.remove(filename)
                await processing_msg.delete()
        else:
            logger.error(f"Download failed: filename={filename}, exists={os.path.exists(filename) if filename else False}")
            await update.message.reply_text("❌ Video download failed. Check the link and try again.")
    
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        if processing_msg:
            await processing_msg.delete()


async def handle_invalid_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle messages without supported video links
    """
    await update.message.reply_text("❌ Please send a valid video link from supported platforms.")



def contains_trigger_words(message_text):
    triggers = ["Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)

def sanitize_url(url: str, replace_domain: str = None) -> str:
    parsed_url = urlparse(url)
    netloc = replace_domain if replace_domain else parsed_url.netloc
    sanitized_url = urlunparse((parsed_url.scheme, netloc, parsed_url.path, '', '', ''))
    return sanitized_url

def extract_urls(text):
    """Extract URLs from text using regex pattern."""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /start command
    """
    welcome_text = (
        "🤖 Video Downloader Bot\n\n"
        "Send me a link from:\n"
        "• TikTok\n• Instagram\n• YouTube Shorts\n"
        "• Facebook\n• Twitter\n• Vimeo\n• Reddit\n\n"
        "I'll download and send the video directly!"
    )
    await update.message.reply_text(welcome_text)


async def handle_message(update: Update, context: CallbackContext):
    """Handle incoming messages."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    
    # Initialize modified_link before using it
    modified_link = message_text

    # Extract URLs if present
    urls = extract_urls(message_text)
    

    # Rest of the message handling...
    if urls:
        modified_link = urls[0]  # Take the first URL if multiple exist

    chat_id = update.message.chat_id
    username = update.message.from_user.username
    chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"

    # Log message with extra fields
    chat_logger.info(f"User message: {message_text}", extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})

    # Handle trigger words
    if contains_trigger_words(message_text):
        await restrict_user(update, context)
        return

    modified_links = []
    original_links = []

    # Process all links in a single pass
    urls = extract_urls(message_text)
    for link in urls:
        sanitized_link = sanitize_url(link)
        if re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', sanitized_link):
            if len(sanitized_link) > 60:
                modified_link = await shorten_url(sanitized_link)
                modified_link = await shorten_url(message_text)
            modified_link += " #aliexpress"
            modified_links.append(modified_link)
            # Send AliExpress sticker
            await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=ALIEXPRESS_STICKER_ID)
            continue

        # # Then check for domain modifications (x.com etc.)
        # for domain, modified_domain in domain_modifications.items():
        #     if domain in sanitized_link:
        #         modified_link = sanitized_link.replace(domain, modified_domain)
        #         modified_links.append(modified_link)
        #         break

    # # Send modified message if any links were processed
    # if modified_links:
    #     cleaned_message_text = remove_links(message_text).replace("\n", " ")
    #     await construct_and_send_message(chat_id, username, cleaned_message_text, modified_links, update, context)

    # Handle GPT queries
    if f"@{context.bot.username}" in message_text:
        # Process the message as a direct mention
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        await ask_gpt_command(cleaned_message, update, context)
        return  # Ensure to return after processing

    # Check if the chat is private and the message does not contain a link
    is_private_chat = update.effective_chat.type == 'private'
    contains_youtube_or_aliexpress = any(domain in message_text for domain in ["youtube.com", "youtu.be"]) or re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', message_text)
    contains_domain_modifications = any(domain in message_text for domain, modified_domain in domain_modifications.items())
    contain_download = any(domain in message_text for domain in SUPPORTED_PLATFORMS)

    if is_private_chat and not contains_youtube_or_aliexpress and not contains_domain_modifications and not contain_download:
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        await ask_gpt_command(cleaned_message, update, context)
        return  # Ensure to return after processing
    await random_gpt_response(update, context)


async def random_gpt_response(update: Update, context: CallbackContext):
    """Randomly responds to a message with a 2% chance using GPT, only if the message has 5 or more words."""
    chat_id = update.message.chat_id
    message_counts[chat_id] = message_counts.get(chat_id, 0) + 1

    message_text = update.message.text

    if not message_text:
        general_logger.info("Message text is empty or None.")
        return

    word_count = len(message_text.split())  # Count the number of words
    # general_logger.info(f"Message text: '{message_text}' | Word count: {word_count}")

    if word_count < 5:  # Check if the message has less than 5 words
        # general_logger.info("Message has less than 5 words, skipping processing.")
        return  # Skip processing if not enough words

    random_value = random.random()
    current_message_count = message_counts[chat_id]
    # general_logger.info(f"Random value: {random_value} | Current message count: {current_message_count}")

    if random_value < 0.02 and current_message_count > 50:
        general_logger.info(
            f"Random GPT response triggered in chat {chat_id}: "
            f"Message: '{message_text}' | Random value: {random_value:.4f} | "
            f"Current message count: {current_message_count}"
        )


        # Call the GPT function
        await answer_from_gpt(message_text, update, context)

        # Reset message count for the chat
        message_counts[chat_id] = 0

async def handle_sticker(update: Update, context: CallbackContext):
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username

    general_logger.info(f"Received sticker with file_unique_id: {sticker_id}")

    if sticker_id == "AgAD6BQAAh-z-FM":
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)

async def shorten_url(url):
    # Create a Shortener object
    s = pyshorteners.Shortener()

    try:
        # Use a specific shortening service (e.g., TinyURL)
        short_url = s.tinyurl.short(url)
        return short_url
    except Exception as e:
        logging.error(f"Error shortening URL {url}: {str(e)}")
        return url  # Return the original URL if there's an error

async def construct_and_send_message(chat_id, username, cleaned_message_text, modified_links, update, context):
    try:
        # Log the function call for debugging
        general_logger.info(f"Constructing and sending message for chat_id: {chat_id}, username: {username}")

        # Log the cleaned message text and modified links
        general_logger.info(f"Cleaned message text: {cleaned_message_text}")
        general_logger.info(f"Modified links: {modified_links}")

        # Create the message
        modified_message = " ".join(modified_links)  # Use space to join links
        final_message = f"@{username}💬: {cleaned_message_text}\nWants to share: {modified_message}"

        # Log the final message
        general_logger.info(f"Final message: {final_message}")

        # Store the link and create keyboard
        link_hash = hashlib.md5(modified_links[0].encode()).hexdigest()[:8]
        context.bot_data[link_hash] = modified_links[0]
        reply_markup = create_link_keyboard(modified_links[0])
        # Send modified message and delete original
        await context.bot.send_message(
            chat_id=chat_id,
            text=final_message,
            reply_to_message_id=update.message.reply_to_message.message_id if update.message.reply_to_message else None,
            reply_markup=reply_markup
        )
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

    except Exception as e:
        general_logger.error(f"Error modifying links: {str(e)}")
        await update.message.reply_text("Sorry, an error occurred. Please try again.")

def ensure_downloads_dir():
    """Ensure downloads directory exists and is empty"""
    downloads_dir = 'downloads'
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    else:
        # Clean any leftover files
        for file in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error cleaning downloads directory: {e}")

async def main():
    # Load game state at startup
    load_game_state()

    # Ensure downloads directory exists
    ensure_downloads_dir()

    application = ApplicationBuilder().token(TOKEN).build()

    # Add command handlers
    commands = {
        'start': start,
        'cat': cat_command,
        'gpt': ask_gpt_command,
        'analyze': analyze_command,
        'flares': screenshot_command,
        'weather': weather,
        'game': game_command,
        'endgame': end_game_command,
        'clearwords': clear_words_command,
        'hint': hint_command
    }

    for command, handler in commands.items():
        application.add_handler(CommandHandler(command, handler))

    # Add video download handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex('|'.join(SUPPORTED_PLATFORMS)), 
            handle_video_link
        ),
        group=1  # Move group parameter here
    )
    
    # General message handler
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_message
        ),
        group=2  # Move group parameter here
    )
    
    # Other handlers...
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the screenshot scheduler
    screenshot_manager = ScreenshotManager()
    asyncio.create_task(screenshot_manager.schedule_task())

    # Start bot
    logger.info("Bot is running...")
    await application.run_polling()

if __name__ == '__main__':
    # Apply the patch to allow nested event loops
    nest_asyncio.apply()
    
    # Create a new event loop
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(main())
