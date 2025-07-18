"""
Message handlers for different types of messages.

Contains handlers for text, photo, sticker, location, and voice messages.
"""

import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from modules.service_registry import service_registry
from modules.shared_constants import StickerIds, ConfigKeys
from modules.shared_utilities import (
    HashGenerator, TelegramHelpers, TextProcessor, ValidationMixin
)
from modules.types import (
    MessageHandler, UserId, ChatId, MessageId, ConfigDict
)
from modules.logger import general_logger, error_logger
from modules.const import Stickers
from modules.user_management import restrict_user, should_restrict_user
from modules.message_processor import (
    needs_gpt_response, update_message_history, get_previous_message,
    process_message_content
)
from modules.gpt import gpt_response, handle_photo_analysis as _handle_photo
from modules.keyboards import get_language_keyboard
from modules.speechmatics import (
    transcribe_telegram_voice, SpeechmaticsLanguageNotExpected,
    SpeechmaticsRussianDetected, SpeechmaticsNoSpeechDetected
)

logger = logging.getLogger(__name__)

# Global persistent mapping for file_id hashes
file_id_hash_map: Dict[str, str] = {}


async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming non-command text messages."""
    if not update.message or not update.message.text:
        return
        
    message_text: str = update.message.text.strip()
    user_id: UserId = update.message.from_user.id
    
    # Validate input
    if not ValidationMixin.validate_text_length(message_text)[0]:
        logger.warning(f"Message too long from user {user_id}")
        return
    
    # Update message history at the very start
    update_message_history(user_id, message_text)

    # Safeguard: Explicitly ignore commands to prevent interference with CommandHandlers
    if message_text.startswith('/'):
        return
    
    # --- БЛЯ! TRANSLATION COMMAND ---
    if message_text.lower() == "бля!":
        await _handle_translation_command(update, user_id)
        return
    # --- END БЛЯ! TRANSLATION COMMAND ---

    chat_id: ChatId = update.effective_chat.id
    
    # Update chat history for context using the global manager
    chat_history_manager = service_registry.get_service('chat_history_manager')
    chat_history_manager.add_message(chat_id, {
        'text': message_text,
        'is_user': True,
        'user_id': user_id,
        'timestamp': update.message.date
    })
    
    # Check for user restrictions
    if should_restrict_user(message_text):
        await restrict_user(update, context)
        return
    
    # Process message content and extract URLs
    cleaned_text, modified_links = process_message_content(message_text)
    
    # If all modified links are AliExpress, skip sending the "modified link" message
    if modified_links and all(urlparse(link).hostname and urlparse(link).hostname.endswith("aliexpress.com") for link in modified_links):
        return
    
    # Check for GPT response
    needs_response, response_type = needs_gpt_response(update, context, message_text)
    if needs_response:
        await gpt_response(update, context, response_type=response_type, message_text_override=cleaned_text)
        return

    # --- RANDOM GPT RESPONSE LOGIC ---
    # Only in group chats, not private
    if TelegramHelpers.is_group_chat(update):
        await handle_random_gpt_response(update, context, message_text, cleaned_text)

    # Handle modified links if any were found
    if modified_links:
        await process_urls(update, context, modified_links, cleaned_text)


async def _handle_translation_command(update: Update, user_id: UserId) -> None:
    """Handle the БЛЯ! translation command."""
    username: str = update.message.from_user.username or "User"
    previous_message: Optional[str] = get_previous_message(user_id)
    
    if not previous_message:
        await update.message.reply_text("Немає попереднього повідомлення для перекладу.")
        return
        
    from modules.keyboard_translator import auto_translate_text
    converted_text: str = auto_translate_text(previous_message)
    response_text: str = f"@{username} хотів сказати: {converted_text}"
    await update.message.reply_text(response_text)


async def handle_random_gpt_response(
    update: Update, 
    context: CallbackContext, 
    message_text: str, 
    cleaned_text: str
) -> None:
    """Handle random GPT responses in group chats."""
    # Block random GPT response if message contains any link
    from modules.url_processor import extract_urls
    if extract_urls(message_text):
        return

    chat_id: str = str(update.effective_chat.id)
    chat_type: str = update.effective_chat.type
    
    config_manager = service_registry.get_service('config_manager')
    message_counter = service_registry.get_service('message_counter')
    
    config: ConfigDict = await config_manager.get_config(
        chat_id=chat_id, chat_type=chat_type, module_name="chat_behavior"
    )
    
    # Check if chat_behavior module is enabled
    module_enabled: bool = config.get("enabled", False)
    overrides: Dict[str, Any] = config.get("overrides", {})
    random_settings: Dict[str, Any] = overrides.get("random_response_settings", {})
    random_enabled: bool = random_settings.get("enabled", False)
    
    # Both module and random settings must be enabled
    if module_enabled and random_enabled:
        min_words: int = random_settings.get("min_words", 5)
        message_threshold: int = random_settings.get("message_threshold", 50)
        probability: float = random_settings.get("probability", 0.02)
        
        # Only consider messages with enough words
        if len(message_text.split()) >= min_words:
            count: int = message_counter.increment(update.effective_chat.id)
            general_logger.info(
                f"Random response check: chat_id={chat_id}, "
                f"count={count}/{message_threshold}, probability={probability}"
            )
            
            if count >= message_threshold:
                import random
                if random.random() < probability:
                    message_counter.reset(update.effective_chat.id)
                    general_logger.info(f"Triggering random response in chat {chat_id}")
                    await gpt_response(
                        update, context, 
                        response_type="random", 
                        message_text_override=cleaned_text
                    )
                    return
    else:
        # Log why random responses are disabled
        if not module_enabled:
            general_logger.debug(
                f"Random responses disabled: chat_behavior module not enabled in chat {chat_id}"
            )
        elif not random_enabled:
            general_logger.debug(
                f"Random responses disabled: random_response_settings not enabled in chat {chat_id}"
            )


async def process_urls(
    update: Update, 
    context: CallbackContext, 
    urls: List[str], 
    message_text: str
) -> None:
    """Process URLs in the message."""
    chat_id: ChatId = update.effective_chat.id
    username: str = update.message.from_user.username or f"ID:{update.message.from_user.id}"
    
    if urls:
        await construct_and_send_message(chat_id, username, message_text, urls, update, context)


async def construct_and_send_message(
    chat_id: ChatId,
    username: str,
    cleaned_message_text: str,
    modified_links: List[str],
    update: Update,
    context: CallbackContext
) -> None:
    """Construct and send a message with modified links."""
    try:
        from modules.keyboards import create_link_keyboard
        from telegram.constants import ParseMode
        
        # Use shared utility for escaping markdown
        escaped_username: str = TextProcessor.escape_markdown(username)
        escaped_text: str = TextProcessor.escape_markdown(cleaned_message_text)
        escaped_links: List[str] = [TextProcessor.escape_markdown(url) for url in modified_links]
        
        message: str = f"@{escaped_username} хотів відправити:\n{escaped_text}"
        keyboard = create_link_keyboard(escaped_links, context)
        
        # Check if the original message was a reply to another message
        if update.message.reply_to_message:
            # If it was a reply, send the modified link message as a reply to the parent message
            await update.message.reply_to_message.reply_text(
                text=message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            # If it wasn't a reply, send the modified link message as a reply to the original message
            await update.message.reply_text(
                text=message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        error_logger.error(f"Failed to send message: {str(e)}", exc_info=True)
        raise


async def handle_photo_analysis(update: Update, context: CallbackContext) -> None:
    """Handle photo messages."""
    await _handle_photo(update, context)


async def handle_sticker(update: Update, context: CallbackContext) -> None:
    """Handle sticker messages."""
    if not update.message or not update.message.sticker:
        return
        
    sticker = update.message.sticker
    general_logger.info(f"Received sticker: {sticker.file_id} ({sticker.file_unique_id})")
    
    # Check if this is a restriction sticker
    if sticker.file_unique_id in [
        "AgAD9hQAAtMUCVM",
        "AgADrBgAAk_x0Es",
        "AgADJSsAArOEUEo",
        "AgAD32YAAvgziEo"
    ]:
        from modules.user_management import handle_restriction_sticker
        await handle_restriction_sticker(update, context)


async def handle_location(update: Update, context: CallbackContext) -> None:
    """Handle location messages by replying with a sticker."""
    if not update.message or not update.message.location:
        return
        
    location = update.message.location
    general_logger.info(f"Received location: lat={location.latitude}, lon={location.longitude}")
    
    try:
        # Reply with the location sticker
        await update.message.reply_sticker(sticker=Stickers.LOCATION)
        general_logger.info(f"Sent location sticker in response to location message")
    except Exception as e:
        error_logger.error(f"Failed to send location sticker: {e}")
        await update.message.reply_text("📍 Location received!")


async def handle_voice_or_video_note(update: Update, context: CallbackContext) -> None:
    """Handle voice and video note messages."""
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    
    config_manager = service_registry.get_service('config_manager')
    speech_config = await get_speech_config(chat_id, chat_type, config_manager)
    
    if not speech_config.get("enabled", False):
        return
    
    message = update.message
    user = message.from_user
    file_id = None
    
    if message.voice:
        file_id = message.voice.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    else:
        return
    
    # Send the speech recognition button
    await send_speech_recognition_button(update, context)


async def get_speech_config(chat_id: str, chat_type: str, config_manager):
    """Get speech configuration for a chat."""
    config = await config_manager.get_config(chat_id, chat_type)
    return config.get("config_modules", {}).get("speechmatics", {})


async def send_speech_recognition_button(update, context):
    """Send a speech recognition button as a reply to a voice message."""
    message = update.message
    if not message or (not message.voice and not message.video_note):
        return
    
    file_id = message.voice.file_id if message.voice else message.video_note.file_id
    file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
    
    # Store file_id for callback lookup
    file_id_hash_map[file_hash] = file_id
    logger.debug(f"Added file_id_hash_map entry: {file_hash} -> {file_id}")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎤 Recognize Speech", callback_data=f"speechrec_{file_hash}")]
    ])
    
    await message.reply_text(
        "Press the button to recognize speech in this voice or video message.\n\n⚠️ If the bot was recently restarted, old buttons will not work. Please send a new message if you see an error.",
        reply_markup=keyboard
    )