import asyncio
import hashlib
import logging
import pytz
import random
import pyshorteners
import re
import os
import telebot
import yt_dlp
import telegram
import browser_cookie3
import tempfile
import json
import nest_asyncio
from modules.file_manager import init_error_handler


from modules.keyboards import create_link_keyboard, button_callback
from utils import remove_links, screenshot_command, schedule_task, cat_command, ScreenshotManager, game_state, game_command, end_game_command, clear_words_command, hint_command, load_game_state
from const import domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID
from modules.gpt import ask_gpt_command, analyze_command, answer_from_gpt
from modules.weather import weather
from modules.file_manager import general_logger, chat_logger, error_logger, init_error_handler
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
from modules.video_downloader import get_instagram_cookies, download_video, handle_video_link, handle_invalid_link
from utils.url_utils import extract_urls


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
    'tiktok.com',
    'instagram.com',
    'youtube.com',
    'youtu.be',
    'facebook.com',
    'twitter.com',
    'vimeo.com',
    'reddit.com',
    'x.com',
    'threads.net'
]

# Apply the patch to allow nested event loops
nest_asyncio.apply()


def contains_trigger_words(message_text):
    triggers = ["Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)

def sanitize_url(url: str, replace_domain: str = None) -> str:
    parsed_url = urlparse(url)
    netloc = replace_domain if replace_domain else parsed_url.netloc
    sanitized_url = urlunparse((parsed_url.scheme, netloc, parsed_url.path, '', '', ''))
    return sanitized_url

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and route to appropriate handlers."""
    try:
        if not update.message or not update.message.text:
            return

        message_text = update.message.text.strip()
        urls = extract_urls(message_text)
        
        if urls and any(platform in url.lower() for url in urls for platform in SUPPORTED_PLATFORMS):
            await handle_video_link(update, context)
        else:
            await handle_invalid_link(update, context)
            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await error_logger(f"Handle message error: {str(e)}")
        await update.message.reply_text("❌ An error occurred while processing your request.")

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
    try:
        if not update.message or not update.message.text:
            return
            
        message_text = update.message.text.strip()
        chat_id = update.message.chat_id
        username = update.message.from_user.username
        chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"
        
        # Log message with extra fields
        chat_logger.info(f"User message: {message_text}", 
                        extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})

        # Extract URLs first for multiple checks
        urls = extract_urls(message_text)

        # Check for supported video platforms first
        if urls and any(platform in url.lower() for url in urls for platform in SUPPORTED_PLATFORMS):
            await handle_video_link(update, context)
            return

        # Handle trigger words
        if contains_trigger_words(message_text):
            await restrict_user(update, context)
            return

        # Check for bot mention for GPT processing
        if f"@{context.bot.username}" in message_text:
            cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
            await ask_gpt_command(cleaned_message, update, context)
            return

        # Handle YouTube links
        if any(domain in message_text for domain in ["youtube.com", "youtu.be"]):
            for link in urls:
                sanitized_link = sanitize_url(link)
                if len(sanitized_link) > 60:
                    modified_link = await shorten_url(sanitized_link)
                await update.message.reply_text("#youtube", reply_to_message_id=update.message.message_id)
                return

        # Process other links
        modified_links = []
        for link in urls:
            sanitized_link = sanitize_url(link)
            
            # Handle AliExpress links
            if re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', sanitized_link):
                if len(sanitized_link) > 60:
                    modified_link = await shorten_url(sanitized_link)
                modified_link += " #aliexpress"
                modified_links.append(modified_link)
                await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=ALIEXPRESS_STICKER_ID)
                continue

            # Handle domain modifications
            for domain, modified_domain in domain_modifications.items():
                if domain in sanitized_link:
                    modified_link = sanitized_link.replace(domain, modified_domain)
                    modified_links.append(modified_link)
                    break

        # Send modified message if any links were processed
        if modified_links:
            cleaned_message_text = remove_links(message_text).replace("\n", " ")
            await construct_and_send_message(chat_id, username, cleaned_message_text, modified_links, update, context)
            return

        # Handle private chat messages
        is_private_chat = update.effective_chat.type == 'private'
        contains_youtube_or_aliexpress = any(domain in message_text for domain in ["youtube.com", "youtu.be"]) or \
                                    re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', message_text)
        contains_domain_modifications = any(domain in message_text for domain, modified_domain in domain_modifications.items())
        contain_download = any(domain in message_text for domain in SUPPORTED_PLATFORMS)

        if is_private_chat and not (contains_youtube_or_aliexpress or contains_domain_modifications or contain_download):
            cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
            await ask_gpt_command(cleaned_message, update, context)
            return

        # Handle invalid links
        if urls:
            await handle_invalid_link(update, context)
            return

        await random_gpt_response(update, context)

    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await error_logger(f"Handle message error: {str(e)}")
        await update.message.reply_text("❌ An error occurred while processing your request.")


async def construct_and_send_message(chat_id, username, cleaned_message_text, modified_links, update, context):
    """Construct and send modified message with links."""
    try:
        general_logger.info(f"Constructing and sending message for chat_id: {chat_id}, username: {username}")
        general_logger.info(f"Cleaned message text: {cleaned_message_text}")
        general_logger.info(f"Modified links: {modified_links}")

        modified_message = " ".join(modified_links)
        final_message = f"@{username}💬: {cleaned_message_text}\nWants to share: {modified_message}"
        
        general_logger.info(f"Final message: {final_message}")
        
        # Store link and create keyboard
        link_hash = hashlib.md5(modified_links[0].encode()).hexdigest()[:8]
        context.bot_data[link_hash] = modified_links[0]
        reply_markup = create_link_keyboard(modified_links[0])

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


async def random_gpt_response(update: Update, context: CallbackContext):
    """Randomly responds to a message with a 2% chance using GPT, only if the message has 5 or more words."""
    chat_id = update.message.chat_id
    message_counts[chat_id] = message_counts.get(chat_id, 0) + 1

    message_text = update.message.text

    if not message_text:
        general_logger.info("Message text is empty or None.")
        return

    word_count = len(message_text.split())  # Count the number of words

    if word_count < 5:  # Check if the message has less than 5 words
        return  # Skip processing if not enough words

    random_value = random.random()
    current_message_count = message_counts[chat_id]

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

async def test_error_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test command to trigger error logging"""
    try:
        # Deliberately cause different types of errors
        
        # 1. Division by zero error
        result = 1 / 0
        
    except Exception as e:
        error_logger.error(f"Test error triggered: {str(e)}", exc_info=True)
        await update.message.reply_text("Test error has been logged to the channel!")

async def main():
    """Main function"""
    # Load game state at startup
    load_game_state()

    # Ensure downloads directory exists
    ensure_downloads_dir()

    # Initialize application
    application = ApplicationBuilder().token(TOKEN).build()

    # Initialize error handler with bot instance
    init_error_handler(application.bot)

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
        'hint': hint_command,
        'testerror': test_error_command
    }

    for command, handler in commands.items():
        application.add_handler(CommandHandler(command, handler))

    # Add handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex('|'.join(SUPPORTED_PLATFORMS)), 
            handle_video_link
        ),
        group=1
    )
    
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_message
        ),
        group=2
    )
    
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the screenshot scheduler
    screenshot_manager = ScreenshotManager()
    asyncio.create_task(screenshot_manager.schedule_task())

    # Start bot
    logger.info("Bot is running...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_bot():
    """Run the bot with proper event loop handling"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    run_bot()