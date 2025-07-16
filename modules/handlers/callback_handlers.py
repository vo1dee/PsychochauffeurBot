"""
Callback query handlers for inline keyboard interactions.

Contains handlers for button callbacks, speech recognition, and language selection.
"""

import hashlib
import logging
from typing import Dict, Optional

from telegram import Update
from telegram.ext import CallbackContext

from modules.shared_utilities import HashGenerator, ValidationMixin
from modules.types import CallbackHandler, UserId, ChatId
from modules.keyboards import button_callback as _button_callback, get_language_keyboard
from modules.speechmatics import (
    transcribe_telegram_voice, SpeechmaticsLanguageNotExpected,
    SpeechmaticsRussianDetected, SpeechmaticsNoSpeechDetected
)

logger = logging.getLogger(__name__)

# Import the global file_id_hash_map from message_handlers
from modules.handlers.message_handlers import file_id_hash_map


async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle general button callbacks."""
    await _button_callback(update, context)


async def speechrec_callback(update: Update, context: CallbackContext) -> None:
    """Handle speech recognition callback."""
    query = update.callback_query
    await query.answer()
    data: str = query.data
    
    # Debug log for callback data
    logger.debug(f"speechrec_callback received data: {data}")
    logger.debug(f"file_id_hash_map keys: {list(file_id_hash_map.keys())}")
    
    if not data.startswith("speechrec_"):
        await query.edit_message_text(
            "❌ Invalid callback data format. Please try again with a new voice message. "
            "If the bot was restarted, old buttons will not work."
        )
        return
    
    file_hash: str = data[len("speechrec_"):]
    file_id: Optional[str] = file_id_hash_map.get(file_hash)
    
    if not file_id:
        logger.debug(f"speechrec_callback: file_hash '{file_hash}' not found in file_id_hash_map.")
        await query.edit_message_text(
            "❌ This speech recognition button has expired or is invalid. "
            "Please send a new voice message and use the new button. "
            "If the bot was restarted, old buttons will not work."
        )
        return
    
    logger.debug(f"speechrec_callback: found file_id for hash {file_hash}")
    await query.edit_message_text("🔄 Recognizing speech, please wait...")
    
    try:
        transcript: str = await transcribe_telegram_voice(context.bot, file_id, language="auto")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🗣️ Recognized speech:\n{transcript}"
        )
    except SpeechmaticsNoSpeechDetected:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No speech was detected in the audio. Please try again with a clearer voice message."
        )
    except SpeechmaticsLanguageNotExpected:
        # Use shared utility for hash generation
        file_hash = HashGenerator.file_id_hash(file_id)
        file_id_hash_map[file_hash] = file_id
        keyboard = get_language_keyboard(file_hash)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Couldn't recognize the language. Please choose the correct language:",
            reply_markup=keyboard
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Speech recognition failed: {e}"
        )


async def language_selection_callback(update: Update, context: CallbackContext) -> None:
    """Handle language selection callback."""
    logger.debug("Callback handler entered (any callback)")
    logger.debug(f"Full update: {update}")
    
    query = update.callback_query
    await query.answer()
    data: str = query.data
    
    logger.debug(f"Language selection callback triggered. Data: {data}")
    
    if data == "test_callback":
        await query.edit_message_text("✅ Test callback received and handled!")
        return
    
    if '|' not in data:
        logger.debug(f"Invalid callback data received: {data}")
        await query.edit_message_text("❌ Invalid callback data. Please try again.")
        return
    
    lang_code: str
    file_hash: str
    lang_code, file_hash = data.split('|', 1)
    lang_code = lang_code.replace('lang_', '')
    file_id: Optional[str] = file_id_hash_map.get(file_hash)
    
    logger.debug(f"(callback) Callback data hash lookup: {file_hash} -> {file_id}")
    
    if not file_id:
        logger.debug(f"(callback) Hash {file_hash} not found in file_id_hash_map. Callback data: {data}")
        await query.edit_message_text("❌ This button has expired or is invalid. Please try again.")
        return
    
    # Show progress immediately
    await query.edit_message_text(f"🔄 Processing with {lang_code} language...", reply_markup=None)
    
    try:
        # Use shared utility for hash generation
        file_hash = HashGenerator.file_id_hash(file_id)
        file_id_hash_map[file_hash] = file_id
        keyboard = get_language_keyboard(file_hash)
        transcript: str = await transcribe_telegram_voice(context.bot, file_id, language=lang_code)
        await query.edit_message_text(f"🗣️ Recognized ({lang_code}):\n{transcript}")
    except SpeechmaticsLanguageNotExpected as e:
        logger.debug(f"Speechmatics identified language not expected: {e}")
        file_hash = HashGenerator.file_id_hash(file_id)
        file_id_hash_map[file_hash] = file_id
        keyboard = get_language_keyboard(file_hash)
        await query.edit_message_text(
            "❌ Couldn't recognize the language or it is not supported. Please choose another language:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.debug(f"Error during manual language selection: {e}")
        await query.edit_message_text(f"❌ Speech recognition failed: {e}", reply_markup=None)