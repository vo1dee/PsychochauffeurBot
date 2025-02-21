import asyncio
import hashlib
import logging
import nest_asyncio
import pytz
import random
import pyshorteners
import re
import os
from urllib.parse import urlparse, urlunparse

from modules.keyboards import create_link_keyboard, button_callback
from utils import (
    remove_links, screenshot_command, schedule_task, cat_command, ScreenshotManager,
    game_state, game_command, end_game_command, clear_words_command, hint_command,
    load_game_state, extract_urls, get_daily_log_path
)
from const import domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID, VideoPlatforms
from modules.gpt import ask_gpt_command, analyze_command, answer_from_gpt
from modules.weather import weather
from modules.file_manager import general_logger, chat_logger
from modules.user_management import restrict_user
from modules.video_downloader import VideoDownloader, setup_video_handlers
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler, ContextTypes
)

# Apply the patch to allow nested event loops
nest_asyncio.apply()

LOCAL_TZ = pytz.timezone('Europe/Kyiv')
SUPPORTED_PLATFORMS = VideoPlatforms.SUPPORTED_PLATFORMS


class MessageCounter:
    """Manages message counts per chat for random GPT responses."""
    def __init__(self):
        self.counts = {}

    def increment(self, chat_id):
        self.counts[chat_id] = self.counts.get(chat_id, 0) + 1
        return self.counts[chat_id]

    def reset(self, chat_id):
        self.counts[chat_id] = 0


message_counter = MessageCounter()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def contains_trigger_words(message_text: str) -> bool:
    """Check if message contains trigger words for user restriction."""
    triggers = ["Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)


def sanitize_url(url: str, replace_domain: str = None) -> str:
    """Sanitize a URL by keeping scheme, netloc, and path only."""
    try:
        parsed_url = urlparse(url)
        netloc = replace_domain if replace_domain else parsed_url.netloc
        return urlunparse((parsed_url.scheme, netloc, parsed_url.path, '', '', ''))
    except Exception as e:
        logger.error(f"Failed to sanitize URL {url}: {e}")
        return url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    welcome_text = (
        "🤖 Video Downloader Bot\n\n"
        "Send me a link from:\n"
        "• TikTok\n• Instagram\n• YouTube Shorts\n"
        "• Facebook\n• Twitter\n• Vimeo\n• Reddit\n\n"
        "I'll download and send the video directly!"
    )
    await update.message.reply_text(welcome_text)


def needs_gpt_response(update: Update, context: CallbackContext, message_text: str) -> bool:
    """Determine if a GPT response is needed based on message context."""
    bot_username = context.bot.username
    is_private_chat = update.effective_chat.type == 'private'
    mentioned = f"@{bot_username}" in message_text
    contains_youtube_or_aliexpress = any(domain in message_text for domain in ["youtube.com", "youtu.be"]) or \
                                     re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', message_text)
    contains_domain_modifications = any(domain in message_text for domain in domain_modifications)
    return (mentioned or (is_private_chat and not (contains_youtube_or_aliexpress or contains_domain_modifications)))


async def handle_message(update: Update, context: CallbackContext):
    """Handle incoming text messages."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    urls = extract_urls(message_text)
    chat_id = update.message.chat_id
    username = update.message.from_user.username

    # Log message
    chat_title = update.message.chat.title or "Private Chat"
    chat_logger.info(f"User message: {message_text}", extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})

    # Handle trigger words
    if contains_trigger_words(message_text):
        await restrict_user(update, context)
        return

    # Process URLs if present
    if urls:
        logger.info(f"Processing URLs: {urls}")
        await process_urls(update, context, urls, message_text)
        return

    # Handle GPT responses
    if needs_gpt_response(update, context, message_text):
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        logger.info(f"GPT response triggered for: {cleaned_message}")
        await ask_gpt_command(cleaned_message, update, context)
        return

    # Random GPT response
    await random_gpt_response(update, context)


async def process_urls(update: Update, context: CallbackContext, urls: list, message_text: str):
    """Process URLs for modification or video downloading."""
    modified_links = []
    needs_video_download = any(platform in url.lower() for url in urls for platform in SUPPORTED_PLATFORMS)

    for url in urls:
        sanitized_link = sanitize_url(url)
        if re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', sanitized_link):
            modified_link = await shorten_url(sanitized_link) if len(sanitized_link) > 60 else sanitized_link
            modified_links.append(f"{modified_link} #aliexpress")
            await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=ALIEXPRESS_STICKER_ID)
        else:
            for domain, modified_domain in domain_modifications.items():
                if domain in sanitized_link and modified_domain not in sanitized_link:
                    modified_links.append(sanitized_link.replace(domain, modified_domain))
                    break
                elif modified_domain in sanitized_link:
                    modified_links.append(sanitized_link)
                    break

    if modified_links:
        cleaned_message_text = remove_links(message_text).replace("\n", " ")
        await construct_and_send_message(update.effective_chat.id, update.message.from_user.username,
                                        cleaned_message_text, modified_links, update, context)

    if needs_video_download:
        video_downloader = context.bot_data.get('video_downloader')
        if video_downloader:
            logger.info(f"Attempting video download for URLs: {urls}")
            await video_downloader.handle_video_link(update, context)


async def random_gpt_response(update: Update, context: CallbackContext):
    """Randomly respond with GPT if message meets criteria."""
    chat_id = update.message.chat_id
    message_text = update.message.text

    if not message_text:
        general_logger.info("Message text is empty or None.")
        return

    word_count = len(message_text.split())
    if word_count < 5:
        return

    current_count = message_counter.increment(chat_id)
    if random.random() < 0.02 and current_count > 50:
        general_logger.info(
            f"Random GPT response triggered in chat {chat_id}: "
            f"Message: '{message_text}' | Random value: {random.random():.4f} | "
            f"Current message count: {current_count}"
        )
        await answer_from_gpt(message_text, update, context)
        message_counter.reset(chat_id)


async def handle_sticker(update: Update, context: CallbackContext):
    """Handle incoming stickers."""
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username

    general_logger.info(f"Received sticker with file_unique_id: {sticker_id}")
    if sticker_id == "AgAD6BQAAh-z-FM":
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)


async def shorten_url(url: str) -> str:
    """Shorten a URL using TinyURL."""
    s = pyshorteners.Shortener()
    try:
        return s.tinyurl.short(url)
    except Exception as e:
        logging.error(f"Error shortening URL {url}: {str(e)}")
        return url


async def construct_and_send_message(chat_id: int, username: str, cleaned_message_text: str,
                                    modified_links: list, update: Update, context: CallbackContext):
    """Construct and send a message with modified links."""
    try:
        modified_message = " ".join(modified_links)
        final_message = f"@{username}💬: {cleaned_message_text}\nWants to share: {modified_message}"

        link_hash = hashlib.md5(modified_links[0].encode()).hexdigest()[:8]
        context.bot_data[link_hash] = modified_links[0]

        keyboard = create_link_keyboard(modified_links[0])
        await context.bot.send_message(
            chat_id=chat_id,
            text=final_message,
            reply_markup=keyboard,
            reply_to_message_id=update.message.reply_to_message.message_id if update.message.reply_to_message else None
        )
        general_logger.info(f"Sent message with keyboard. Link hash: {link_hash}")
    except Exception as e:
        general_logger.error(f"Error in construct_and_send_message: {str(e)}")
        await update.message.reply_text("Sorry, an error occurred.")


async def main():
    """Main function to initialize and run the bot."""
    try:
        load_game_state()
        os.makedirs('downloads', exist_ok=True)
        application = ApplicationBuilder().token(TOKEN).build()

        # Command handlers
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

        # Message and callback handlers
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
        application.add_handler(CallbackQueryHandler(button_callback))

        # Initialize video downloader
        video_downloader = setup_video_handlers(application, extract_urls_func=extract_urls)
        application.bot_data['video_downloader'] = VideoDownloader(download_path='downloads')

        # Start screenshot scheduler
        screenshot_manager = ScreenshotManager()
        asyncio.create_task(screenshot_manager.schedule_task())

        # Start bot
        logger.info("Bot is running...")
        await application.run_polling()
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())