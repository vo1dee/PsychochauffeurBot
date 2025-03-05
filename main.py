"""
Main entry point for the PsychoChauffeur Telegram bot.
Handles message processing, command registration, and bot initialization.
"""
import asyncio
import hashlib
import logging
import nest_asyncio
import re
import pyshorteners
import random
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, urlunparse
import pytz

# Define timezone constant
KYIV_TZ = pytz.timezone('Europe/Kyiv')

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler, ContextTypes
)

from modules.keyboards import create_link_keyboard, button_callback
from modules.utils import (
    remove_links, screenshot_command, cat_command, ScreenshotManager,
    extract_urls, ensure_directory, init_directories
)
from modules.const import (
    domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID, DATA_DIR,
    VideoPlatforms, LinkModification, Config
)
from modules.gpt import ask_gpt_command, analyze_command, answer_from_gpt
from modules.weather import WeatherCommandHandler
from modules.logger import general_logger, chat_logger, error_logger, get_daily_log_path,  init_error_handler
from modules.user_management import restrict_user
from modules.video_downloader import VideoDownloader, setup_video_handlers
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity


nest_asyncio.apply()

class MessageCounter:
    """Manages message counts per chat for random GPT responses."""
    def __init__(self):
        self.counts = {}

    def increment(self, chat_id: int) -> int:
        """Increment message count for a chat and return new count."""
        self.counts[chat_id] = self.counts.get(chat_id, 0) + 1
        return self.counts[chat_id]

    def reset(self, chat_id: int) -> None:
        """Reset message count for a chat."""
        self.counts[chat_id] = 0

# Initialize message counter
message_counter = MessageCounter()

# Dictionary to store the last message for each user
last_user_messages = {}

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Keyboard layout mapping for translation feature
keyboard_mapping = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г',
    'i': 'ш', 'o': 'щ', 'p': 'з', 'a': 'ф', 's': 'і', 'd': 'в', 'f': 'а',
    'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я', 'x': 'ч',
    'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь'
}
keyboard_mapping.update({k.upper(): v.upper() for k, v in keyboard_mapping.items()})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for /start command.

    Parameters:
    update (Update): Incoming update object containing message details.
    context (ContextTypes.DEFAULT_TYPE): Context object containing bot and update data.

    Returns:
    None
    """
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
        "• Solar flares screenshot --  /flares\n"
        "• Random cat photos -- /cat \n\n"
        "❓ Questions or issues?\n"
        "Contact @vo1dee"
    )
    await update.message.reply_text(welcome_text)

async def translate_last_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert the last message from English keyboard layout to Ukrainian."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "User"
    
    last_message = last_user_messages.get(user_id)
    if not last_message:
        await update.message.reply_text("No previous message found to convert.")
        return

    converted_text = ''.join(keyboard_mapping.get(char, char) for char in last_message)
    response_text = f"@{username} хотів сказати: {converted_text}"
    await update.message.reply_text(response_text)

def needs_gpt_response(update: Update, context: CallbackContext, message_text: str) -> bool:
    """Determine if a message needs a GPT response."""
    bot_username = context.bot.username
    is_private_chat = update.effective_chat.type == 'private'
    mentioned = f"@{bot_username}" in message_text
    contains_video_platform = any(platform in message_text.lower() 
                                for platform in VideoPlatforms.SUPPORTED_PLATFORMS)
    contains_modified_domain = any(domain in message_text 
                                 for domain in LinkModification.DOMAINS)
    
    return (mentioned or (is_private_chat and 
            not (contains_video_platform or contains_modified_domain)))

@handle_errors(feedback_message="An error occurred while processing your message.")
async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming text messages with standardized error handling."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    chat_id = update.message.chat_id
    username = update.message.from_user.username

    # Store last message for translation feature
    last_user_messages[update.message.from_user.id] = message_text

    # Log message
    chat_title = update.effective_chat.title or "Private Chat"
    log_path = get_daily_log_path(chat_id, chat_title=chat_title)
    chat_logger.info(f"User message: {message_text}", extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})

    # Handle trigger words
    if any(char in message_text for char in "ЫыЪъЭэЁё"):
        await restrict_user(update, context)
        return

    # Process URLs if present
    urls = extract_urls(message_text)
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
async def process_urls(
    update: Update,
    context: CallbackContext,
    urls: List[str],
    message_text: str
) -> None:
    """Process URLs for modification or video downloading with standardized error handling."""
    modified_links = []
    needs_video_download = any(
        platform in url.lower() 
        for url in urls 
        for platform in VideoPlatforms.SUPPORTED_PLATFORMS
    )

    for url in urls:
        sanitized_link = sanitize_url(url)
        if re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', sanitized_link):
            modified_link = await shorten_url(sanitized_link) if len(sanitized_link) > 60 else sanitized_link
            modified_links.append(f"{modified_link} #aliexpress")
            await context.bot.send_sticker(
                chat_id=update.effective_chat.id,
                sticker=ALIEXPRESS_STICKER_ID
            )
        else:
            for domain, modified_domain in LinkModification.DOMAINS.items():
                if domain in sanitized_link and modified_domain not in sanitized_link:
                    modified_links.append(sanitized_link.replace(domain, modified_domain))
                    break
                elif modified_domain in sanitized_link:
                    modified_links.append(sanitized_link)
                    break

    if modified_links:
        cleaned_message_text = remove_links(message_text).strip()
        await construct_and_send_message(
            update.effective_chat.id,
            update.message.from_user.username,
            cleaned_message_text,
            modified_links,
            update,
            context
        )

    if needs_video_download:
        video_downloader = context.bot_data.get('video_downloader')
        if video_downloader and hasattr(video_downloader, 'handle_video_link'):
            logger.info(f"Attempting video download for URLs: {urls}")
            await video_downloader.handle_video_link(update, context)
        else:
            # Use standardized error handler
            error = ErrorHandler.create_error(
                message="Video downloader not initialized properly",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.RESOURCE,
                context={
                    "urls": urls,
                    "chat_id": update.effective_chat.id if update and update.effective_chat else None
                }
            )
            await ErrorHandler.handle_error(error, update, context)

def sanitize_url(url: str, replace_domain: Optional[str] = None) -> str:
    """Sanitize a URL by keeping scheme, netloc, and path only."""
    try:
        parsed_url = urlparse(url)
        netloc = replace_domain if replace_domain else parsed_url.netloc
        return urlunparse((parsed_url.scheme, netloc, parsed_url.path, '', '', ''))
    except Exception as e:
        # Create standardized error
        error = ErrorHandler.create_error(
            message=f"Failed to sanitize URL",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.PARSING,
            context={"url": url},
            original_exception=e
        )
        # Log error with structured format
        error_message = ErrorHandler.format_error_message(error)
        error_logger.error(error_message)
        return url

async def shorten_url(url: str) -> str:
    """Shorten a URL using TinyURL service."""
    try:
        return pyshorteners.Shortener().tinyurl.short(url)
    except Exception as e:
        # Create standardized error
        error = ErrorHandler.create_error(
            message="Failed to shorten URL",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.NETWORK,
            context={"url": url},
            original_exception=e
        )
        # Log error with structured format
        error_message = ErrorHandler.format_error_message(error)
        error_logger.error(error_message)
        return url

def remove_links(text: str) -> str:
    """Remove URLs from text."""
    return re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

async def construct_and_send_message(
    chat_id: int,
    username: str,
    cleaned_message_text: str,
    modified_links: List[str],
    update: Update,
    context: CallbackContext
) -> None:
    """Construct and send a message with modified links."""
    from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
    
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
        # Create error context
        error_context = {
            "username": username,
            "cleaned_message": cleaned_message_text,
            "modified_links": modified_links,
            "chat_id": chat_id
        }
        
        # Use standardized error handling
        await ErrorHandler.handle_error(
            error=e,
            update=update,
            context=context,
            feedback_message="Sorry, an error occurred while processing your message."
        )

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
    from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
    
    try:
        # Initialize required directories and state
        init_directories()

        # Build application
        application = ApplicationBuilder().token(TOKEN).build()

        # Import error analytics report command
        from modules.error_analytics import error_report_command
        
        # Register command handlers
        commands = {
            'start': start,
            'cat': cat_command,
            'gpt': ask_gpt_command,
            'analyze': analyze_command,
            'flares': screenshot_command,
            'weather': WeatherCommandHandler(),
            'blya': translate_last_message,
            'errors': error_report_command  # New command for error analytics
        }
        
        for command, handler in commands.items():
            application.add_handler(CommandHandler(command, handler))

        # Register message handlers
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ))
        application.add_handler(MessageHandler(
            filters.Sticker.ALL,
            handle_sticker
        ))
        application.add_handler(CallbackQueryHandler(button_callback))

        # Initialize video downloader
        video_downloader = setup_video_handlers(
            application,
            extract_urls_func=extract_urls
        )
        application.bot_data['video_downloader'] = video_downloader
        
        # Initialize error handler with await
        await init_error_handler(application, Config.ERROR_CHANNEL_ID)
        
        # Test error logger
        error_logger.error("Test error message - If you see this in the Telegram channel, error logging is working!")
        
        # Start screenshot scheduler
        screenshot_manager = ScreenshotManager()
        asyncio.create_task(screenshot_manager.schedule_task())

        # Start polling
        logger.info("Bot is starting...")
        await application.run_polling()

    except Exception as e:
        # Create a critical error for bot startup failure
        standard_error = ErrorHandler.create_error(
            message="Bot failed to start",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.GENERAL,
            context={
                "system_info": {
                    "python_version": sys.version,
                    "event_loop": str(asyncio.get_event_loop()),
                },
                "time": datetime.now(KYIV_TZ).isoformat()
            },
            original_exception=e
        )
        
        # Log with detailed context
        error_message = ErrorHandler.format_error_message(standard_error, prefix="💥")
        error_logger.critical(error_message)
        
        # Still raise to prevent silent failures
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Cannot close a running event loop" in str(e):
            error_logger.error("Event loop is already running. Please check your environment.")
        else:
            raise