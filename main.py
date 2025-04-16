"""
Main entry point for the PsychoChauffeur Telegram bot.
Handles message processing, command registration, and bot initialization.
"""
import asyncio
import hashlib
import ipaddress
import logging
import nest_asyncio
import re
import pyshorteners
import random
import sys
import telegram
import os
from datetime import datetime
from typing import List, Optional, Dict
import time
from collections import deque

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler, ContextTypes
)

from modules.keyboards import create_link_keyboard, button_callback
from modules.utils import (
    ScreenshotManager, MessageCounter, remove_links, screenshot_command, cat_command,
    extract_urls, init_directories
)
from modules.const import (
    TOKEN, OPENAI_API_KEY, KYIV_TZ, ALIEXPRESS_STICKER_ID,
    VideoPlatforms, LinkModification, Config
)
from modules.gpt import ask_gpt_command, analyze_command, answer_from_gpt
from modules.weather import WeatherCommandHandler
from modules.logger import general_logger, chat_logger, error_logger, init_error_handler
from modules.user_management import restrict_user
from modules.video_downloader import setup_video_handlers
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity
from modules.geomagnetic import GeomagneticCommandHandler
from modules.reminders.reminders import ReminderManager

nest_asyncio.apply()

# URL shortener cache and rate limiter
_url_shortener_cache: Dict[str, str] = {}
_shortener_calls: deque = deque()
_SHORTENER_MAX_CALLS_PER_MINUTE: int = int(os.getenv('SHORTENER_MAX_CALLS_PER_MINUTE', '30'))
# Initialize global objects
message_counter = MessageCounter()
last_user_messages = {}
reminder_manager = ReminderManager()  # Initialize ReminderManager

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Keyboard layout mapping for translation
keyboard_mapping = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г',
    'i': 'ш', 'o': 'щ', 'p': 'з', 'a': 'ф', 's': 'і', 'd': 'в', 'f': 'а',
    'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я', 'x': 'ч',
    'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь'
}
keyboard_mapping.update({k.upper(): v.upper() for k, v in keyboard_mapping.items()})

@handle_errors(feedback_message="An error occurred in /start command.")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        "🤖 PsychoChauffeur Bot\n\n"
        "🎥 Video Downloads from:\n"
        "• TikTok\n• Instagram\n• YouTube Shorts\n"
        "• Facebook\n• Twitter\n• Vimeo\n• Reddit\n• Twitch\n"
        "🔗 Link Processing:\n"
        "• AliExpress link optimization\n"
        "• Link modification for restricted domains\n\n"
        "🤖 Additional Features:\n"
        "• GPT responses\n"
        "• Weather updates -- /weather [city]\n"
        "• Solar flares screenshot -- /flares\n"
        "• Geomagnetic activity -- /gm\n"
        "• Random cat photos -- /cat \n\n"
        "• Reminders -- /remind\n\n"
        "❓ Questions or issues?\n"
        "Contact @vo1dee"
    )
    await update.message.reply_text(welcome_text)

@handle_errors(feedback_message="An error occurred while translating the last message.")
async def translate_last_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "User"
    previous_message = last_user_messages.get(user_id, {}).get('previous')
    if not previous_message:
        await update.message.reply_text("No previous message found to convert.")
        return
    converted_text = ''.join(keyboard_mapping.get(char, char) for char in previous_message)
    response_text = f"@{username} хотів сказати: {converted_text}"
    await update.message.reply_text(response_text)

def needs_gpt_response(update: Update, context: CallbackContext, message_text: str) -> bool:
    """Determine if a message needs a GPT response."""
    bot_username = context.bot.username
    is_private_chat = update.effective_chat.type == 'private'
    mentioned = f"@{bot_username}" in message_text
    contains_video_platform = any(platform in message_text.lower() for platform in VideoPlatforms.SUPPORTED_PLATFORMS)
    contains_modified_domain = any(domain in message_text for domain in LinkModification.DOMAINS)
    return (mentioned or (is_private_chat and not (contains_video_platform or contains_modified_domain)))

@handle_errors(feedback_message="An error occurred while processing your message.")
async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming text messages with standardized error handling."""
    if not update.message or not update.message.text:
        return
    message_text = update.message.text
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    user_id = update.message.from_user.id
    last_user_messages.setdefault(user_id, {'current': None, 'previous': None})
    last_user_messages[user_id]['previous'] = last_user_messages[user_id]['current']
    last_user_messages[user_id]['current'] = message_text
    chat_title = update.effective_chat.title or "Private Chat"
    chat_logger.info(f"User message: {message_text}", extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})
    if any(char in message_text for char in "ЫыЪъЭэЁё"):
        await restrict_user(update, context)
        return
    if "бля!" in message_text:
        await translate_last_message(update, context)
        return
    urls = extract_urls(message_text)
    if urls:
        logger.info(f"Processing URLs: {urls}")
        await process_urls(update, context, urls, message_text)
        return
    if needs_gpt_response(update, context, message_text):
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        logger.info(f"GPT response triggered for: {cleaned_message}")
        await ask_gpt_command(cleaned_message, update, context)
        return
    await handle_random_gpt_response(update, context)

@handle_errors(feedback_message="An error occurred while processing GPT response.")
async def handle_random_gpt_response(update: Update, context: CallbackContext) -> None:
    """Handle random GPT responses based on message count with error handling."""
    message_text = update.message.text
    chat_id = update.message.chat_id
    if not message_text or len(message_text.split()) < 5:
        return
    current_count = message_counter.increment(chat_id)
    if current_count > 50 and random.random() < 0.02:
        general_logger.info(
            f"Random GPT response triggered in chat {chat_id}: "
            f"Message count: {current_count}"
        )
        await answer_from_gpt(message_text, update, context)
        message_counter.reset(chat_id)

@handle_errors(feedback_message="An error occurred while processing your links.")
async def process_urls(update: Update, context: CallbackContext, urls: List[str], message_text: str) -> None:
    """Process URLs for modification or video downloading with standardized error handling."""
    modified_links = []
    needs_video_download = any(platform in url.lower() for url in urls for platform in VideoPlatforms.SUPPORTED_PLATFORMS)
    if needs_video_download:
        video_downloader = context.bot_data.get('video_downloader')
        if video_downloader and hasattr(video_downloader, 'handle_video_link'):
            logger.info(f"Attempting video download for URLs: {urls}")
            await video_downloader.handle_video_link(update, context)
        else:
            error = ErrorHandler.create_error(message="Video downloader not initialized properly", severity=ErrorSeverity.HIGH, category=ErrorCategory.RESOURCE, context={"urls": urls, "chat_id": update.effective_chat.id if update and update.effective_chat else None})
            await ErrorHandler.handle_error(error, update, context)
        return
    for url in urls:
        sanitized_link = sanitize_url(url)
        if re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', sanitized_link):
            modified_link = await shorten_url(sanitized_link)
            modified_links.append(f"{modified_link} #aliexpress")
            await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=ALIEXPRESS_STICKER_ID)
        else:
            processed = False
            for domain, modified_domain in LinkModification.DOMAINS.items():
                if domain in sanitized_link and modified_domain not in sanitized_link:
                    modified_link = sanitized_link.replace(domain, modified_domain)
                    modified_links.append(await shorten_url(modified_link))
                    processed = True
                    break
                elif modified_domain in sanitized_link:
                    modified_links.append(await shorten_url(sanitized_link))
                    processed = True
                    break
            # If original URL is very long, shorten the sanitized link
            if not processed and len(url) > 110:
                modified_links.append(await shorten_url(sanitized_link))
    if modified_links:
        cleaned_message_text = remove_links(message_text).strip()
        await construct_and_send_message(update.effective_chat.id, update.message.from_user.username, cleaned_message_text, modified_links, update, context)

def sanitize_url(url: str, replace_domain: Optional[str] = None) -> str:
    """Sanitize a URL by keeping scheme, netloc, and path only."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        # Reject IP addresses for safety
        try:
            ipaddress.ip_address(hostname)
            return ''
        except ValueError:
            pass
        # Disallow credentials or weird hostnames
        if parsed.username or parsed.password:
            return ''
        # Only allow hostnames with letters, digits, hyphens or dots
        if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
            return ''
        # Reconstruct netloc (hostname[:port])
        port = f":{parsed.port}" if parsed.port else ''
        netloc = replace_domain if replace_domain else hostname + port
        return urlunparse((parsed.scheme, netloc, parsed.path, '', '', ''))
    except Exception as e:
        error = ErrorHandler.create_error(
            message="Failed to sanitize URL", severity=ErrorSeverity.LOW,
            category=ErrorCategory.PARSING, context={"url": url}, original_exception=e
        )
        error_message = ErrorHandler.format_error_message(error)
        error_logger.error(error_message)
        return url

async def shorten_url(url: str) -> str:
    """Shorten a URL if it exceeds 110 characters using TinyURL service with caching and rate limiting."""
    # Quick return for short URLs
    if len(url) <= 110:
        return url
    now = time.time()
    # Purge old timestamps older than 60 sec
    while _shortener_calls and now - _shortener_calls[0] > 60:
        _shortener_calls.popleft()
    # Return cached result if exists
    if url in _url_shortener_cache:
        return _url_shortener_cache[url]
    # Enforce rate limit
    if len(_shortener_calls) >= _SHORTENER_MAX_CALLS_PER_MINUTE:
        general_logger.warning(f"URL shortener rate limit reached; skipping shorten for {url}")
        return url
    try:
        shortened = pyshorteners.Shortener().tinyurl.short(url)
        # Cache and record call
        _url_shortener_cache[url] = shortened
        _shortener_calls.append(now)
        general_logger.info(f"Shortened URL: {url} -> {shortened}")
        return shortened
    except Exception as e:
        error = ErrorHandler.create_error(
            message="Failed to shorten URL",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.NETWORK,
            context={"url": url},
            original_exception=e
        )
        error_message = ErrorHandler.format_error_message(error)
        error_logger.error(error_message)
        return url

async def construct_and_send_message(chat_id: int, username: str, cleaned_message_text: str, modified_links: List[str], update: Update, context: CallbackContext) -> None:
    """Construct and send a message with modified links."""
    try:
        modified_message = " ".join(modified_links)
        final_message = f"@{username}💬: {cleaned_message_text}\nWants to share: {modified_message}"
        link_hash = hashlib.md5(modified_links[0].encode()).hexdigest()[:8]
        context.bot_data[link_hash] = modified_links[0]
        keyboard = create_link_keyboard(modified_links[0])
        await context.bot.send_message(chat_id=chat_id, text=final_message, reply_markup=keyboard, reply_to_message_id=(update.message.reply_to_message.message_id if update.message.reply_to_message else None))
        general_logger.info(f"Sent message with keyboard. Link hash: {link_hash}")
    except Exception as e:
        error_context = {"username": username, "cleaned_message": cleaned_message_text, "modified_links": modified_links, "chat_id": chat_id}
        await ErrorHandler.handle_error(error=e, update=update, context=context, context_data=error_context, feedback_message="Sorry, an error occurred while processing your message.")

@handle_errors(feedback_message="An error occurred handling sticker.")
async def handle_sticker(update: Update, context: CallbackContext) -> None:
    """Handle incoming stickers."""
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username
    general_logger.info(f"Received sticker with file_unique_id: {sticker_id}")
    if sticker_id == "AgAD6BQAAh-z-FM":
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)

async def main() -> None:
    """Initialize and run the bot."""
    # Validate required environment variables
    if not TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set. Exiting.")
        sys.exit(1)
    if not OPENAI_API_KEY:
        logger.critical("OPENAI_API_KEY is not set. Exiting.")
        sys.exit(1)
    try:
        init_directories()
        application = ApplicationBuilder().token(TOKEN).build()
        from modules.error_analytics import error_report_command
        commands = {
            'start': start,
            'cat': cat_command,
            'gpt': ask_gpt_command,
            'analyze': analyze_command,
            'flares': screenshot_command,
            'weather': WeatherCommandHandler(),
            'errors': error_report_command,
            'gm': GeomagneticCommandHandler(),
            'ping': lambda update, context: update.message.reply_text("🏓 Bot is online!"),
            'remind': reminder_manager.remind
        }
        for command, handler in commands.items():
            application.add_handler(CommandHandler(command, handler))

        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
        application.add_handler(CallbackQueryHandler(button_callback))
        video_downloader = setup_video_handlers(application, extract_urls_func=extract_urls)
        application.bot_data['video_downloader'] = video_downloader
        await init_error_handler(application, Config.ERROR_CHANNEL_ID)
        error_logger.error("Test notification message - If you see this in the Telegram channel, error logging is working!")
        screenshot_manager = ScreenshotManager()
        asyncio.create_task(screenshot_manager.schedule_task())
        reminder_manager.schedule_startup(application.job_queue)
        logger.info("Bot is starting...")
        await application.run_polling()
    except Exception as e:
        standard_error = ErrorHandler.create_error(message="Bot failed to start", severity=ErrorSeverity.CRITICAL, category=ErrorCategory.GENERAL, context={"system_info": {"python_version": sys.version, "event_loop": str(asyncio.get_event_loop())}, "time": datetime.now(KYIV_TZ).isoformat()}, original_exception=e)
        error_message = ErrorHandler.format_error_message(standard_error, prefix="💥")
        error_logger.critical(error_message)
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Cannot close a running event loop" in str(e):
            error_logger.error("Event loop is already running. Please check your environment.")
        else:
            raise