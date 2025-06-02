"""
Main entry point for the PsychoChauffeur Telegram bot.
Handles message processing, command registration, and bot initialization.
"""
import asyncio
import hashlib
import ipaddress
# import logging # Removed - using custom loggers
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

from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler, ContextTypes, Application
)

# Import from your modules
from modules.keyboards import create_link_keyboard, button_callback
from modules.utils import (
    ScreenshotManager, MessageCounter, remove_links, screenshot_command, cat_command,
    extract_urls, init_directories
)
from modules.image_downloader import ImageDownloader
from modules.const import (
    TOKEN, OPENAI_API_KEY, KYIV_TZ, ALIEXPRESS_STICKER_ID,
    VideoPlatforms, LinkModification, Config # Ensure Config.ERROR_CHANNEL_ID is valid
)
from modules.gpt import (
    ask_gpt_command, analyze_command, answer_from_gpt, analyze_image,
    gpt_response  # Add gpt_response to imports
)
from modules.weather import WeatherCommandHandler
# Updated logger imports
from modules.logger import (
    TelegramErrorHandler,
    general_logger, chat_logger, error_logger,
    init_telegram_error_handler, shutdown_logging # Import new functions
)
from modules.user_management import restrict_user
from modules.video_downloader import setup_video_handlers
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity
from modules.geomagnetic import GeomagneticCommandHandler
from modules.reminders.reminders import ReminderManager
from modules.error_analytics import error_report_command, error_tracker
from config.config_manager import ConfigManager
from modules.safety import safety_manager

nest_asyncio.apply()

# URL shortener cache and rate limiter (keep as is)
_url_shortener_cache: Dict[str, str] = {}
_shortener_calls: deque = deque()
_SHORTENER_MAX_CALLS_PER_MINUTE: int = int(os.getenv('SHORTENER_MAX_CALLS_PER_MINUTE', '30'))

# Initialize global objects (keep as is)
message_counter = MessageCounter()
last_user_messages = {}
reminder_manager = ReminderManager()

# Initialize ConfigManager at module level
config_manager = ConfigManager()

# --- Removed Basic Logging Config ---
# logging.basicConfig(...) # REMOVED
# logger = logging.getLogger(__name__) # REMOVED - Use general_logger instead

# --- Keyboard mapping (keep as is) ---
keyboard_mapping = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г',
    'i': 'ш', 'o': 'щ', 'p': 'з', 'a': 'ф', 's': 'і', 'd': 'в', 'f': 'а',
    'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', 'z': 'я', 'x': 'ч',
    'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь'
}
keyboard_mapping.update({k.upper(): v.upper() for k, v in keyboard_mapping.items()})

# --- Command Handlers (keep structure, ensure they use correct loggers if needed) ---
@handle_errors(feedback_message="An error occurred in /start command.")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (start command logic - looks fine)
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
    general_logger.info(f"Handled /start command for user {update.effective_user.id}") # Example using general_logger


@handle_errors(feedback_message="An error occurred while translating the last message.")
async def translate_last_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (translate logic - looks fine)
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "User"
    previous_message = last_user_messages.get(user_id, {}).get('previous')
    if not previous_message:
        await update.message.reply_text("No previous message found to convert.")
        return
    converted_text = ''.join(keyboard_mapping.get(char, char) for char in previous_message)
    response_text = f"@{username} хотів сказати: {converted_text}"
    await update.message.reply_text(response_text)


def needs_gpt_response(update: Update, context: CallbackContext, message_text: str) -> tuple[bool, str]:
    """
    Determine if a message needs a GPT response and what type of response it needs.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        message_text: The message text to analyze
        
    Returns:
        tuple[bool, str]: (needs_response, response_type)
            - needs_response: Whether the message needs a GPT response
            - response_type: Type of response needed ('command', 'mention', 'private', 'random')
    """
    bot_username = context.bot.username
    is_private_chat = update.effective_chat.type == 'private'
    mentioned = f"@{bot_username}" in message_text
    contains_video_platform = any(platform in message_text.lower() for platform in VideoPlatforms.SUPPORTED_PLATFORMS)
    contains_modified_domain = any(domain in message_text for domain in LinkModification.DOMAINS)
    
    # Check if it's a command
    if message_text.startswith('/gpt'):
        return True, 'command'
    
    # Check if bot is mentioned
    if mentioned:
        return True, 'mention'
    
    # Check if it's a private chat message that needs private response
    if is_private_chat and not (contains_video_platform or contains_modified_domain):
        return True, 'private'
    
    return False, ''


@handle_errors(feedback_message="An error occurred while analyzing the image.")
async def handle_photo(update: Update, context: CallbackContext) -> None:
    """Handle photos sent to the bot and log analysis without replying."""
    if not update.message or not update.message.photo:
        return
    
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"ID:{user_id}"
    chat_title = update.effective_chat.title or f"Private_{chat_id}"
    
    general_logger.info(
        f"Received photo from user {username}",
        extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username}
    )
    
    # Get the largest photo (highest quality)
    photo = update.message.photo[-1]
    
    try:
        # Download the photo
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Process the image with GPT-4o-mini (silently)
        await analyze_image(photo_bytes, update, context)
        
    except Exception as e:
        # Still log errors but don't send error message to chat
        error_context = {
            "user_id": user_id,
            "chat_id": chat_id,
            "file_id": photo.file_id
        }
        await ErrorHandler.handle_error(
            error=e,
            update=update, 
            context=context,
            context_data=error_context,
            feedback_message=None  # No feedback message to the user
        )

@handle_errors(feedback_message="An error occurred while processing your message.")
async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming text messages with standardized error handling."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    chat_id = str(update.message.chat_id)
    chat_type = "private" if update.effective_chat.type == "private" else "group"
    chat_name = update.effective_chat.title or f"{chat_type}_{chat_id}"
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    chat_title = update.effective_chat.title if update.effective_chat.title else "private"

    # Get chat configuration
    chat_config = await config_manager.get_config(
        chat_id=chat_id,
        chat_type=chat_type,
        chat_name=chat_name
    )

    # Check message safety
    if not await safety_manager.check_message_safety(update, context, message_text):
        return

    # Check for restriction triggers if restrictions are enabled
    if chat_type == "group" and chat_config.get("chat_settings", {}).get("restrictions_enabled", True):
        # Check for forbidden characters
        if any(char in message_text for char in "ЫыЪъЭэЁё"):
            chat_logger.warning(f"Restricting user {username} ({user_id}) in chat {chat_id} due to forbidden characters.",
                extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})
            await restrict_user(update, context)
            return

        # Check for restriction triggers
        restriction_triggers = chat_config.get("restriction_triggers", {})
        keywords = restriction_triggers.get("keywords", [])
        patterns = restriction_triggers.get("patterns", [])

        # Check keywords
        message_lower = message_text.lower()
        if any(keyword.lower() in message_lower for keyword in keywords):
            chat_logger.warning(f"Restricting user {username} ({user_id}) in chat {chat_id} due to restricted keyword.",
                extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})
            await restrict_user(update, context)
            return

        # Check regex patterns
        for pattern in patterns:
            try:
                if re.search(pattern, message_text, re.IGNORECASE):
                    chat_logger.warning(f"Restricting user {username} ({user_id}) in chat {chat_id} due to restricted pattern.",
                        extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})
                    await restrict_user(update, context)
                    return
            except re.error as e:
                error_logger.error(f"Invalid regex pattern '{pattern}': {e}")

    # Translate check
    if "бля!" in message_text:
        await translate_last_message(update, context)
        return

    # URL processing check
    urls = extract_urls(message_text)
    if urls:
        await process_urls(update, context, urls, message_text)
        return

    # Check if message needs GPT response
    needs_response, response_type = needs_gpt_response(update, context, message_text)
    if needs_response:
        await gpt_response(update, context, response_type=response_type, message_text_override=message_text)
        return

    # Handle random GPT responses
    await handle_random_gpt_response(update, context)


@handle_errors(feedback_message="An error occurred while processing GPT response.")
async def handle_random_gpt_response(update: Update, context: CallbackContext) -> None:
    """Handle random GPT responses in chat."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    chat_id = str(update.message.chat_id)
    chat_type = "private" if update.effective_chat.type == "private" else "group"
    chat_name = update.effective_chat.title or f"{chat_type}_{chat_id}"
    
    # Get chat configuration (will create if missing)
    try:
        chat_config = await config_manager.get_config(
            chat_id=chat_id,
            chat_type=chat_type,
            chat_name=chat_name
        )
        
        # Get random response settings from config
        random_settings = chat_config.get("chat_settings", {}).get("random_response_settings", {})
        
        # Check if random responses are enabled
        if not random_settings.get("enabled", True):
            return
            
        # Check minimum word count
        min_words = random_settings.get("min_words", 5)
        if len(message_text.split()) < min_words:
            return

        # Get message count and check threshold
        current_count = message_counter.increment(chat_id)
        message_threshold = random_settings.get("message_threshold", 50)
        probability = random_settings.get("probability", 0.02)
        
        if current_count >= message_threshold and random.random() < probability:
            general_logger.info(
                f"Random GPT response triggered in chat {chat_id}: Message count: {current_count}",
                extra={
                    'chat_id': chat_id, 
                    'chattitle': chat_name,
                    'settings': {
                        'threshold': message_threshold,
                        'probability': probability,
                        'min_words': min_words
                    }
                }
            )
            await ask_gpt_command(message_text, update=update, context=context)
            message_counter.reset(chat_id)
            
    except Exception as e:
        error_logger.error(f"Error in handle_random_gpt_response: {e}", exc_info=True)
        # Continue with default behavior if config loading fails
        if len(message_text.split()) < 5:
            return

        current_count = message_counter.increment(chat_id)
        if current_count >= 50 and random.random() < 0.02:
            await ask_gpt_command(message_text, update=update, context=context)
            message_counter.reset(chat_id)

@handle_errors(feedback_message="An error occurred while processing your links.")
async def process_urls(update: Update, context: CallbackContext, urls: List[str], message_text: str) -> None:
    # ... (logic - uses ErrorHandler correctly, ensure video_downloader logs if needed)
    modified_links = []
    needs_video_download = any(platform in url.lower() for url in urls for platform in VideoPlatforms.SUPPORTED_PLATFORMS)

    if needs_video_download:
        video_downloader = context.bot_data.get('video_downloader')
        if video_downloader and hasattr(video_downloader, 'handle_video_link'):
            general_logger.info(f"Attempting video download for URLs: {urls}") # Use general_logger
            await video_downloader.handle_video_link(update, context)
        else:
            # Error handling for missing video downloader seems correct using ErrorHandler
            error = ErrorHandler.create_error(message="Video downloader not initialized properly", severity=ErrorSeverity.HIGH, category=ErrorCategory.RESOURCE, context={"urls": urls, "chat_id": update.effective_chat.id if update and update.effective_chat else None})
            await ErrorHandler.handle_error(error, update, context) # This likely logs via error_logger too
        return # Stop processing if it was a video link

    # Non-video URL processing
    for url in urls:
        sanitized_link = sanitize_url(url) # Sanitize first
        if not sanitized_link: continue # Skip if sanitization failed (e.g., IP address)

        processed = False
        # AliExpress check
        if re.search(r'(?:aliexpress|a\.aliexpress)\.(?:[a-z]{2,3})/(?:item/)?', sanitized_link):
            shortened_link = await shorten_url(sanitized_link) # Shorten sanitized link
            modified_links.append(f"{shortened_link} #aliexpress")
            try:
                await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=ALIEXPRESS_STICKER_ID)
            except Exception as sticker_err:
                 error_logger.warning(f"Failed to send AliExpress sticker: {sticker_err}", extra={'chat_id': update.effective_chat.id})
            processed = True
        # Other domain modification check
        else:
            for domain, modified_domain in LinkModification.DOMAINS.items():
                parsed_sanitized = urlparse(sanitized_link)
                hostname_sanitized = parsed_sanitized.hostname or ''
                
                # Use exact hostname matching or .domain.com matching
                if hostname_sanitized == domain or hostname_sanitized.endswith('.' + domain):
                    # If it's a subdomain, preserve the subdomain part
                    if hostname_sanitized.endswith('.' + domain):
                        subdomain_part = hostname_sanitized[:-len('.' + domain)]
                        modified_netloc = f"{subdomain_part}.{modified_domain}"
                    else:
                        modified_netloc = modified_domain
                        
                    port = f":{parsed_sanitized.port}" if parsed_sanitized.port else ''
                    modified_sanitized_link = urlunparse((parsed_sanitized.scheme, modified_netloc + port, parsed_sanitized.path, parsed_sanitized.params, parsed_sanitized.query, parsed_sanitized.fragment))
                    modified_links.append(await shorten_url(modified_sanitized_link))
                    processed = True
                    break

        # If not processed by specific rules and original URL is long, shorten the sanitized link
        if not processed and len(url) > 110: # Check original length
             modified_links.append(await shorten_url(sanitized_link)) # Shorten sanitized link

    if modified_links:
        cleaned_message_text = remove_links(message_text).strip()
        await construct_and_send_message(update.effective_chat.id, update.message.from_user.username, cleaned_message_text, modified_links, update, context)


# Import urlparse and urlunparse here if not imported globally
from urllib.parse import urlparse, urlunparse

def sanitize_url(url: str) -> str:
    """Sanitize a URL by keeping scheme, netloc, and path only."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ''

        # Reject IP addresses for safety
        try:
            ipaddress.ip_address(hostname)
            general_logger.warning(f"Rejected URL with IP address: {url}")
            return '' # Return empty string to indicate rejection
        except ValueError:
            pass # Not an IP address, continue

        # Disallow credentials
        if parsed.username or parsed.password:
            general_logger.warning(f"Rejected URL with credentials: {url}")
            return ''

        # Only allow reasonably safe hostnames (adjust regex if needed)
        if not hostname or not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
            general_logger.warning(f"Rejected URL with invalid hostname: {url}")
            return ''

        # Reconstruct netloc (hostname[:port])
        port = f":{parsed.port}" if parsed.port else ''
        netloc = hostname + port

        # Allow only http and https schemes
        if parsed.scheme not in ('http', 'https'):
             general_logger.warning(f"Rejected URL with invalid scheme: {url}")
             return ''

        # Reconstruct the sanitized URL - PRESERVE query and fragment parts
        return urlunparse((parsed.scheme, netloc, parsed.path, '', parsed.query, parsed.fragment))
    except Exception as e:
        # Log the error using the configured error logger
        error_logger.error(f"Failed to sanitize URL '{url}': {e}", exc_info=True)
        return url


async def shorten_url(url: str) -> str:
    # ... (logic looks fine, uses general_logger and error_logger correctly)
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
        general_logger.warning(f"URL shortener rate limit ({_SHORTENER_MAX_CALLS_PER_MINUTE}/min) reached; returning original URL: {url}")
        return url # Return original URL when rate limited

    try:
        # Using a timeout is generally a good idea for network requests
        shortener = pyshorteners.Shortener(timeout=5) # Add 5 second timeout
        shortened = shortener.tinyurl.short(url)

        # Cache and record call
        _url_shortener_cache[url] = shortened
        _shortener_calls.append(now)
        general_logger.info(f"Shortened URL: {url} -> {shortened}")
        return shortened
    except Exception as e:
         error_logger.error(f"TinyURL API error shortening {url}: {e}", exc_info=True)
         return url # Return original on API error
    except Exception as e: # Catch other potential errors like timeouts
         # Log error using error_logger
         error_logger.error(f"Failed to shorten URL {url}: {e}", exc_info=True)
         return url # Return original URL on failure


async def construct_and_send_message(chat_id: int, username: str, cleaned_message_text: str, modified_links: List[str], update: Update, context: CallbackContext) -> None:
    # ... (logic looks okay, uses general_logger, ErrorHandler handles errors which log to error_logger)
    try:
        modified_message = " ".join(modified_links)
        # Consider truncating cleaned_message_text if it's very long
        max_text_len = 3500 # Leave room for username, links, and formatting
        truncated_text = cleaned_message_text[:max_text_len] + ('...' if len(cleaned_message_text) > max_text_len else '')

        final_message = f"@{username}💬: {truncated_text}\nWants to share: {modified_message}"

        # Use first link for hash/keyboard, ensure list is not empty
        if not modified_links:
            error_logger.warning("construct_and_send_message called with empty modified_links list.")
            return

        first_link = modified_links[0]
        link_hash = hashlib.md5(first_link.encode()).hexdigest()[:8]
        context.bot_data[link_hash] = first_link # Store original shortened link for callback

        keyboard = create_link_keyboard(first_link)

        reply_to_id = None
        if update.message and update.message.reply_to_message:
            reply_to_id = update.message.reply_to_message.message_id

        await context.bot.send_message(
            chat_id=chat_id,
            text=final_message,
            reply_markup=keyboard,
            reply_to_message_id=reply_to_id
        )
        general_logger.info(f"Sent message with keyboard. Link hash: {link_hash}", extra={'chat_id': chat_id})

    except Exception as e:
        error_context = {"username": username, "cleaned_message": cleaned_message_text, "modified_links": modified_links, "chat_id": chat_id}
        # Let ErrorHandler manage logging and user feedback
        await ErrorHandler.handle_error(error=e, update=update, context=context, context_data=error_context, feedback_message="Sorry, an error occurred while processing your message.")


@handle_errors(feedback_message="An error occurred handling sticker.")
async def handle_sticker(update: Update, context: CallbackContext) -> None:
    # ... (logic looks fine, uses general_logger)
    sticker_id = update.message.sticker.file_unique_id
    file_id = update.message.sticker.file_id # Log file_id too, might be useful
    username = update.message.from_user.username or f"ID:{update.message.from_user.id}"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or f"Private_{chat_id}"

    general_logger.info(f"Received sticker: unique_id={sticker_id}, file_id={file_id}",
        extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username}
    )

    # Example specific sticker ID check
    if sticker_id == "AgAD6BQAAh-z-FM": # Make this configurable?
        general_logger.warning(f"Matched specific sticker from {username}, restricting user.",
             extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})
        await restrict_user(update, context)


@handle_errors(feedback_message="An error occurred in /wordle command.")
async def wordle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /wordle command by sending the Wordle game link."""
    wordle_link = "https://www.nytimes.com/games/wordle/index.html"
    await update.message.reply_text(f"🎮 Play Wordle here: {wordle_link}")
    general_logger.info(f"Handled /wordle command for user {update.effective_user.id}")


@handle_errors(feedback_message="An error occurred while updating chat configuration.")
async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /config command to manage chat configuration."""
    if not update.message:
        return

    chat_id = str(update.effective_chat.id)
    chat_type = 'private' if update.effective_chat.type == 'private' else 'group'
    
    # Check if user has permission (only admins in groups)
    if chat_type == 'group':
        user = await update.effective_chat.get_member(update.effective_user.id)
        if not user.status in ['creator', 'administrator']:
            await update.message.reply_text("❌ Only administrators can modify chat configuration.")
            return

    # Get current config
    current_config = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type)
    current_state = current_config.get("chat_metadata", {}).get("custom_config_enabled", False)

    # Parse command arguments
    args = context.args
    if not args:
        await update.message.reply_text(
            f"Current configuration status: {'enabled' if current_state else 'disabled'}\n\n"
            "Usage:\n"
            "/config enable - Enable custom configuration\n"
            "/config disable - Disable custom configuration (use global settings)\n"
            "/config backup - Create a backup of current configuration"
        )
        return

    command = args[0].lower()

    if command == 'enable':
        # Enable custom configuration for the chat
        success = await config_manager.enable_custom_config(chat_id, chat_type)
        if success:
            await update.message.reply_text("✅ Custom configuration has been enabled for this chat.")
        else:
            await update.message.reply_text("❌ Failed to enable custom configuration. Please try again later.")
        return

    elif command == 'disable':
        # Disable custom configuration for the chat
        success = await config_manager.disable_custom_config(chat_id, chat_type)
        if success:
            await update.message.reply_text("✅ Custom configuration has been disabled for this chat.")
        else:
            await update.message.reply_text("❌ Failed to disable custom configuration. Please try again later.")
        return

    elif command == 'backup':
        success = await config_manager.backup_config(chat_id, chat_type)
        if success:
            await update.message.reply_text("✅ Configuration backup created successfully.")
        else:
            await update.message.reply_text("❌ Failed to create backup. Please try again later.")
        return

    else:
        await update.message.reply_text(
            "Invalid command. Use /config to see available commands."
        )
        return


@handle_errors(feedback_message="An error occurred while processing your file.")
async def handle_file(update: Update, context: CallbackContext) -> None:
    """Handle incoming files with safety checks."""
    if not update.message or not update.message.document:
        return

    file = update.message.document
    chat_id = str(update.message.chat_id)
    chat_type = "private" if update.effective_chat.type == "private" else "group"
    chat_name = update.effective_chat.title or f"{chat_type}_{chat_id}"
    
    # Check file safety
    if not await safety_manager.check_file_safety(update, context, file.mime_type):
        await update.message.reply_text("⚠️ This file type is not allowed in this chat.")
        return
        
    # Process the file based on its type
    if file.mime_type.startswith('image/'):
        # Handle image files
        pass
    elif file.mime_type.startswith('video/'):
        # Handle video files
        pass
    elif file.mime_type.startswith('audio/'):
        # Handle audio files
        pass
    else:
        # Handle other file types
        pass


@handle_errors(feedback_message="An error occurred while processing GPT command.")
async def gpt_command_handler(update: Update, context: CallbackContext) -> None:
    """Wrapper for the /gpt command to properly handle the command format."""
    if not update.message:
        return
        
    # Extract the prompt from the command
    command_parts = update.message.text.split(' ', 1)
    prompt = command_parts[1] if len(command_parts) > 1 else None
    
    # Call ask_gpt_command with the prompt
    await ask_gpt_command(prompt, update=update, context=context)


def register_handlers(application: Application, bot: Bot, config_manager: ConfigManager) -> None:
    """Register all command and message handlers."""
    # Command handlers
    commands = {
        'start': start,
        'cat': cat_command,
        'gpt': gpt_command_handler,  # Use the wrapper instead
        'analyze': analyze_command,
        'flares': screenshot_command,
        'weather': WeatherCommandHandler(),
        'errors': error_report_command,
        'gm': GeomagneticCommandHandler(),
        'ping': lambda update, context: update.message.reply_text("🏓 Bot is online!"),
        'remind': reminder_manager.remind,
        'config': config_command,
        'wordle': wordle  # Add wordle command
    }
    
    for command, handler in commands.items():
        application.add_handler(CommandHandler(command, handler))
    general_logger.info(f"Registered {len(commands)} commands.")
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Video downloader setup
    video_downloader = setup_video_handlers(application, extract_urls_func=extract_urls)
    application.bot_data['video_downloader'] = video_downloader
    
    # Add file handler
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    general_logger.info("All handlers registered successfully")


async def main() -> None:
    """Main entry point for the bot."""
    try:
        # Initialize directories and permissions
        init_directories()
        general_logger.info("Directories initialized with proper permissions")
        
        # Initialize config manager
        await config_manager.initialize()
        general_logger.info("Configuration manager initialized")
        
        # Initialize error tracking
        await error_tracker.initialize()
        general_logger.info("Error tracking initialized")
        
        # Initialize reminder manager
        await reminder_manager.initialize()
        general_logger.info("Reminder manager initialized")
        
        # Initialize safety manager
        await safety_manager.initialize()
        general_logger.info("Safety manager initialized")
        
        # Create the Application
        application = ApplicationBuilder().token(TOKEN).build()
        
        # Get the bot instance
        bot = application.bot
        
        # Register all handlers
        register_handlers(application, bot, config_manager)
        
        # Start the bot
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        error_logger.error(f"Error in main: {e}")
        raise
    finally:
        try:
            # Cleanup
            await error_tracker.stop()
            await reminder_manager.stop()
            await safety_manager.stop()
            await shutdown_logging()
        except Exception as e:
            error_logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        general_logger.info("Bot stopped by user")
    except Exception as e:
        error_logger.error(f"Fatal error: {e}")
        sys.exit(1)