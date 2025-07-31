"""
Speech Recognition Service for voice and video note processing.

This service handles all speech recognition functionality including voice message
processing, language selection, callback handling, and configuration management.
It extracts the speech recognition logic from main.py into a dedicated, testable service.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from modules.service_registry import ServiceInterface
from modules.speechmatics import (
    transcribe_telegram_voice, 
    SpeechmaticsLanguageNotExpected, 
    SpeechmaticsNoSpeechDetected,
    SpeechmaticsRussianDetected
)
from modules.keyboards import get_language_keyboard
from config.config_manager import ConfigManager
from modules.logger import general_logger, error_logger


class SpeechRecognitionService(ServiceInterface):
    """Service for handling speech recognition functionality.
    
    This service manages all aspects of speech recognition including:
    - Voice and video note message handling
    - Speech configuration management per chat
    - Language selection and callback processing
    - File ID hash mapping for callback security
    - Integration with Speechmatics API
    
    The service follows the ServiceInterface pattern and can be registered
    with the ServiceRegistry for dependency injection.
    """
    
    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize the speech recognition service.
        
        Args:
            config_manager: Configuration manager for accessing chat settings
        """
        self.config_manager = config_manager
        self.file_id_hash_map: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> None:
        """Initialize the service."""
        self.logger.info("SpeechRecognitionService initialized")
        
    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        self.file_id_hash_map.clear()
        self.logger.info("SpeechRecognitionService shutdown")
        
    async def handle_voice_message(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle voice message by sending speech recognition button.
        
        Args:
            update: Telegram update containing the voice message
            context: Telegram callback context
        """
        if not await self._should_process_speech(update):
            return
            
        if not update.message or not update.message.voice:
            return
            
        file_id = update.message.voice.file_id
        await self._send_speech_recognition_button(update, context, file_id)
        
    async def handle_video_note(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle video note message by sending speech recognition button.
        
        Args:
            update: Telegram update containing the video note
            context: Telegram callback context
        """
        if not await self._should_process_speech(update):
            return
            
        if not update.message or not update.message.video_note:
            return
            
        file_id = update.message.video_note.file_id
        await self._send_speech_recognition_button(update, context, file_id)
        
    async def process_speech_recognition(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Process speech recognition callback from button press.
        
        Args:
            update: Telegram update containing the callback query
            context: Telegram callback context
        """
        query = update.callback_query
        if not query or not query.data:
            return
            
        await query.answer()
        
        # Validate callback data format
        if not query.data.startswith("speechrec_"):
            await query.edit_message_text(
                "❌ Invalid callback data format. Please try again with a new voice message. "
                "If the bot was restarted, old buttons will not work."
            )
            return
            
        file_hash = query.data[len("speechrec_"):]
        file_id = self.file_id_hash_map.get(file_hash)
        
        if not file_id:
            general_logger.debug(f"speechrec_callback: file_hash '{file_hash}' not found in file_id_hash_map.")
            await query.edit_message_text(
                "❌ This speech recognition button has expired or is invalid. "
                "Please send a new voice message and use the new button. "
                "If the bot was restarted, old buttons will not work."
            )
            return
            
        await query.edit_message_text("🔄 Recognizing speech, please wait...")
        
        try:
            transcript = await transcribe_telegram_voice(context.bot, file_id, language="auto")
            
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🗣️ Recognized speech:\n{transcript}"
                )
                
        except SpeechmaticsNoSpeechDetected:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ No speech was detected in the audio. Please try again with a clearer voice message."
                )
                
        except (SpeechmaticsLanguageNotExpected, SpeechmaticsRussianDetected):
            # Show language selection keyboard
            file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
            self.file_id_hash_map[file_hash] = file_id
            keyboard = get_language_keyboard(file_hash)
            
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Couldn't recognize the language. Please choose the correct language:",
                    reply_markup=keyboard
                )
                
        except Exception as e:
            error_logger.error(f"Speech recognition failed: {e}", exc_info=True)
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Speech recognition failed: {e}"
                )
                
    async def handle_language_selection(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle language selection callback for speech recognition.
        
        Args:
            update: Telegram update containing the callback query
            context: Telegram callback context
        """
        query = update.callback_query
        if not query or not query.data:
            return
            
        await query.answer()
        
        # Handle test callback for debugging
        if query.data == "test_callback":
            await query.edit_message_text("✅ Test callback received and handled!")
            return
            
        # Validate callback data format
        if '|' not in query.data:
            general_logger.debug(f"Invalid callback data received: {query.data}")
            await query.edit_message_text("❌ Invalid callback data. Please try again.")
            return
            
        lang_code, file_hash = query.data.split('|', 1)
        lang_code = lang_code.replace('lang_', '')
        file_id = self.file_id_hash_map.get(file_hash)
        
        general_logger.debug(f"Language selection callback: {lang_code}, hash: {file_hash} -> {file_id}")
        
        if not file_id:
            general_logger.debug(f"Hash {file_hash} not found in file_id_hash_map. Callback data: {query.data}")
            await query.edit_message_text("❌ This button has expired or is invalid. Please try again.")
            return
            
        # Show progress immediately
        await query.edit_message_text(f"🔄 Processing with {lang_code} language...", reply_markup=None)
        
        try:
            transcript = await transcribe_telegram_voice(context.bot, file_id, language=lang_code)
            await query.edit_message_text(f"🗣️ Recognized ({lang_code}):\n{transcript}")
            
        except (SpeechmaticsLanguageNotExpected, SpeechmaticsRussianDetected) as e:
            general_logger.debug(f"Speechmatics identified language not expected: {e}")
            file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
            self.file_id_hash_map[file_hash] = file_id
            keyboard = get_language_keyboard(file_hash)
            
            await query.edit_message_text(
                "❌ Couldn't recognize the language or it is not supported. Please choose another language:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            general_logger.debug(f"Error during manual language selection: {e}")
            await query.edit_message_text(f"❌ Speech recognition failed: {e}", reply_markup=None)
            
    async def get_speech_config(self, chat_id: str, chat_type: str) -> Optional[Dict[str, Any]]:
        """Get speech configuration for a chat.
        
        Args:
            chat_id: ID of the chat
            chat_type: Type of the chat (private, group, supergroup)
            
        Returns:
            Speech configuration dictionary or None if not found
        """
        config = await self.config_manager.get_config(
            chat_id=chat_id, 
            chat_type=chat_type, 
            module_name="speechmatics"
        )
        
        if config:
            result = config.get("config_modules", {}).get("speechmatics", {})
            return result  # type: ignore[no-any-return]
        return None
        
    async def is_speech_enabled(self, chat_id: str, chat_type: str) -> bool:
        """Check if speech recognition is enabled for a chat.
        
        Args:
            chat_id: ID of the chat
            chat_type: Type of the chat
            
        Returns:
            True if speech recognition is enabled, False otherwise
        """
        speech_config = await self.get_speech_config(chat_id, chat_type)
        return speech_config is not None and speech_config.get("enabled", False)
        
    async def toggle_speech_recognition(self, chat_id: str, chat_type: str, enabled: bool) -> None:
        """Toggle speech recognition for a chat.
        
        Args:
            chat_id: ID of the chat
            chat_type: Type of the chat
            enabled: Whether to enable or disable speech recognition
        """
        speech_config = await self.get_speech_config(chat_id, chat_type)
        
        if not speech_config:
            speech_config = {}
            
        if 'overrides' not in speech_config:
            speech_config['overrides'] = {}
            
        speech_config['enabled'] = enabled
        
        await self.config_manager.save_config(
            chat_id=chat_id,
            chat_type=chat_type,
            module_name="speechmatics",
            **speech_config
        )
        
    def validate_callback_data(self, callback_data: str) -> Tuple[bool, Optional[str]]:
        """Validate speech recognition callback data.
        
        Args:
            callback_data: The callback data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if callback_data.startswith("speechrec_"):
            file_hash = callback_data[len("speechrec_"):]
            if file_hash in self.file_id_hash_map:
                return True, None
            else:
                return False, "Speech recognition button has expired"
                
        elif callback_data.startswith("lang_") and '|' in callback_data:
            _, file_hash = callback_data.split('|', 1)
            if file_hash in self.file_id_hash_map:
                return True, None
            else:
                return False, "Language selection button has expired"
                
        return False, "Invalid callback data format"
        
    async def _should_process_speech(self, update: Update) -> bool:
        """Check if speech recognition should be processed for this update.
        
        Args:
            update: Telegram update to check
            
        Returns:
            True if speech should be processed, False otherwise
        """
        if not update.effective_chat:
            return False
            
        chat_id = str(update.effective_chat.id)
        chat_type = update.effective_chat.type
        
        return await self.is_speech_enabled(chat_id, chat_type)
        
    async def _send_speech_recognition_button(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any], 
        file_id: str
    ) -> None:
        """Send speech recognition button as reply to voice/video message.
        
        Args:
            update: Telegram update containing the message
            context: Telegram callback context
            file_id: File ID of the voice/video message
        """
        if not update.message:
            return
            
        # Create hash for callback data
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        self.file_id_hash_map[file_hash] = file_id
        
        general_logger.debug(f"Added file_id_hash_map entry: {file_hash} -> {file_id}")
        general_logger.debug(f"Current file_id_hash_map: {self.file_id_hash_map}")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎤 Recognize Speech", callback_data=f"speechrec_{file_hash}")]
        ])
        
        await update.message.reply_text(
            "Press the button to recognize speech in this voice or video message.\n\n"
            "⚠️ If the bot was recently restarted, old buttons will not work. "
            "Please send a new message if you see an error.",
            reply_markup=keyboard
        )