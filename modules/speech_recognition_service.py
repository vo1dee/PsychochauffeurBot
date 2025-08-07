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
from modules.service_error_boundary import ServiceErrorBoundary, with_error_boundary
from modules.speechmatics import (
    transcribe_telegram_voice, 
    SpeechmaticsLanguageNotExpected, 
    SpeechmaticsNoSpeechDetected,
    SpeechmaticsRussianDetected
)
from modules.keyboards import get_language_keyboard
from config.config_manager import ConfigManager
from modules.logger import general_logger, error_logger

# Create component-specific logger with clear service identification
service_logger = logging.getLogger('speech_recognition_service')
service_logger.setLevel(logging.INFO)


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
        """Initialize the speech recognition service with configuration integration.
        
        Args:
            config_manager: Configuration manager for accessing chat settings
        """
        self.config_manager = config_manager
        self.file_id_hash_map: Dict[str, str] = {}
        self.error_boundary = ServiceErrorBoundary("speech_recognition_service")
        
        # Configuration integration
        self._service_config: Dict[str, Any] = {}
        self._config_change_callbacks: List[Any] = []
        
        # Enhanced logging with service identification
        self.logger = logging.getLogger('speech_recognition_service')
        self.logger.info("SpeechRecognitionService instance created with configuration integration")
        
    async def initialize(self) -> None:
        """Initialize the service with configuration integration."""
        self.logger.info("Initializing SpeechRecognitionService with configuration integration...")
        
        try:
            # Load service configuration
            await self._load_service_configuration()
            
            # Setup configuration change notifications
            await self._setup_configuration_notifications()
            
            self.logger.info("SpeechRecognitionService initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize SpeechRecognitionService: {e}", exc_info=True)
            raise
        
    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources with proper configuration cleanup."""
        self.logger.info("Shutting down SpeechRecognitionService...")
        
        try:
            # Clear configuration change callbacks
            self._config_change_callbacks.clear()
            
            # Clear file ID hash map
            self.file_id_hash_map.clear()
            
            # Clear service configuration
            self._service_config.clear()
            
            self.logger.info("SpeechRecognitionService shutdown completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during SpeechRecognitionService shutdown: {e}", exc_info=True)
        
    async def handle_voice_message(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle voice message by sending speech recognition button.
        
        Args:
            update: Telegram update containing the voice message
            context: Telegram callback context
        """
        async def _handle_voice_operation() -> None:
            if not await self._should_process_speech(update):
                return
                
            if not update.message or not update.message.voice:
                return
                
            file_id = update.message.voice.file_id
            await self._send_speech_recognition_button(update, context, file_id)
        
        await self.error_boundary.execute_with_boundary(
            operation=_handle_voice_operation,
            operation_name="handle_voice_message",
            timeout=30.0,  # Speech processing timeout
            context={
                "update_id": update.update_id if update else None,
                "chat_id": update.effective_chat.id if update and update.effective_chat else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "file_id": update.message.voice.file_id if update and update.message and update.message.voice else None
            }
        )
        
    async def handle_video_note(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle video note message by sending speech recognition button.
        
        Args:
            update: Telegram update containing the video note
            context: Telegram callback context
        """
        async def _handle_video_note_operation() -> None:
            if not await self._should_process_speech(update):
                return
                
            if not update.message or not update.message.video_note:
                return
                
            file_id = update.message.video_note.file_id
            await self._send_speech_recognition_button(update, context, file_id)
        
        await self.error_boundary.execute_with_boundary(
            operation=_handle_video_note_operation,
            operation_name="handle_video_note",
            timeout=30.0,  # Speech processing timeout
            context={
                "update_id": update.update_id if update else None,
                "chat_id": update.effective_chat.id if update and update.effective_chat else None,
                "user_id": update.effective_user.id if update and update.effective_user else None,
                "file_id": update.message.video_note.file_id if update and update.message and update.message.video_note else None
            }
        )
        
    async def process_speech_recognition(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Process speech recognition callback from button press.
        
        Args:
            update: Telegram update containing the callback query
            context: Telegram callback context
        """
        async def _process_speech_operation() -> None:
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
        
        await self.error_boundary.execute_with_boundary(
            operation=_process_speech_operation,
            operation_name="process_speech_recognition",
            timeout=60.0,  # Longer timeout for speech processing
            context={
                "update_id": update.update_id if update else None,
                "callback_data": update.callback_query.data if update and update.callback_query else None,
                "chat_id": update.effective_chat.id if update and update.effective_chat else None,
                "user_id": update.effective_user.id if update and update.effective_user else None
            }
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
        
        if not config:
            return None
            
        # If config has config_modules structure, extract speechmatics config
        if isinstance(config, dict) and "config_modules" in config:
            speechmatics_config = config.get("config_modules", {}).get("speechmatics")
            return speechmatics_config if isinstance(speechmatics_config, dict) else None
        
        # Otherwise assume config is already the speechmatics config
        return config
        
    async def is_speech_enabled(self, chat_id: str, chat_type: str) -> bool:
        """Check if speech recognition is enabled for a chat.
        
        Args:
            chat_id: ID of the chat
            chat_type: Type of the chat
            
        Returns:
            True if speech recognition is enabled, False otherwise
        """
        speech_config = await self.get_speech_config(chat_id, chat_type)
        if not speech_config:
            return False
            
        # Check nested overrides first (due to config manager structure)
        overrides = speech_config.get("overrides", {})
        if isinstance(overrides, dict):
            # Handle double-nested overrides structure
            nested_overrides = overrides.get("overrides", {})
            if isinstance(nested_overrides, dict) and "enabled" in nested_overrides:
                return bool(nested_overrides["enabled"])
            # Handle single-level overrides
            if "enabled" in overrides:
                return bool(overrides["enabled"])
            
        # Fall back to root level enabled setting
        return bool(speech_config.get("enabled", False))
        
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
            config_data=speech_config,
            chat_id=chat_id,
            chat_type=chat_type,
            module_name="speechmatics"
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
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the speech recognition service."""
        metrics = self.error_boundary.get_health_status()
        return {
            "service_name": "speech_recognition_service",
            "status": metrics.status.value,
            "error_rate": metrics.error_rate,
            "success_rate": metrics.success_rate,
            "total_requests": metrics.total_requests,
            "consecutive_failures": metrics.consecutive_failures,
            "circuit_breaker_state": self.error_boundary.circuit_breaker.state.value,
            "file_id_hash_map_size": len(self.file_id_hash_map)
        }
    
    def register_fallback_handler(self, operation_name: str, fallback_handler: Any) -> None:
        """Register a fallback handler for specific operations."""
        self.error_boundary.register_fallback(operation_name, fallback_handler)
        self.logger.info(f"Registered fallback handler for {operation_name}")
    
    async def perform_health_check(self) -> bool:
        """Perform a health check on the speech recognition service."""
        async def health_check() -> bool:
            # Check if service can access configuration
            try:
                test_config = await self.get_speech_config("test", "private")
                return True  # Service is responsive
            except Exception:
                return False
        
        return await self.error_boundary.perform_health_check(health_check)
    
    async def handle_speech_command(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle the /speech command for toggling speech recognition."""
        if not update.effective_chat or not update.effective_user:
            return

        chat_id = str(update.effective_chat.id)
        chat_type = update.effective_chat.type
        user_id = update.effective_user.id

        # Check if user is admin
        if not await self._is_admin(update, context):
            if update.message:
                await update.message.reply_text("❌ Only admins can use this command.")
            return

        if not context.args:
            if update.message:
                await update.message.reply_text("Usage: /speech on|off")
            return

        enabled = context.args[0].lower() == "on"
        await self.toggle_speech_recognition(chat_id, chat_type, enabled)

        if update.message:
            await update.message.reply_text(f"Speech recognition {'enabled' if enabled else 'disabled'}.")
    
    async def _is_admin(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> bool:
        """Check if the user is an admin in the chat."""
        chat = update.effective_chat
        user = update.effective_user

        if not chat or not user:
            return False

        if chat.type == 'private':
            return True

        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ['creator', 'administrator']
    
    async def _load_service_configuration(self) -> None:
        """Load service-specific configuration from ConfigManager."""
        try:
            # Load global speech recognition configuration
            config = await self.config_manager.get_config(module_name="speechmatics")
            self._service_config = config.get("overrides", {}) if config else {}
            
            self.logger.info(f"Loaded service configuration: {len(self._service_config)} settings")
            self.logger.debug(f"Configuration keys: {list(self._service_config.keys())}")
            
        except Exception as e:
            self.logger.warning(f"Failed to load service configuration, using defaults: {e}")
            self._service_config = {}
    
    async def _setup_configuration_notifications(self) -> None:
        """Setup configuration change notification handling."""
        try:
            # Register for configuration change notifications if ConfigManager supports it
            if hasattr(self.config_manager, 'register_change_callback'):
                callback = self._handle_configuration_change
                self.config_manager.register_change_callback("speechmatics", callback)
                self._config_change_callbacks.append(callback)
                self.logger.info("Registered for configuration change notifications")
            else:
                self.logger.debug("ConfigManager does not support change notifications")
                
        except Exception as e:
            self.logger.warning(f"Failed to setup configuration notifications: {e}")
    
    async def _handle_configuration_change(self, module_name: str, new_config: Dict[str, Any]) -> None:
        """Handle configuration changes for the speech recognition service.
        
        Args:
            module_name: Name of the configuration module that changed
            new_config: New configuration data
        """
        if module_name != "speechmatics":
            return
            
        self.logger.info(f"Configuration change detected for {module_name}")
        
        try:
            # Update service configuration
            old_config = self._service_config.copy()
            self._service_config = new_config.get("overrides", {})
            
            # Log configuration changes
            added_keys = set(self._service_config.keys()) - set(old_config.keys())
            removed_keys = set(old_config.keys()) - set(self._service_config.keys())
            modified_keys = {
                key for key in self._service_config.keys() & old_config.keys()
                if self._service_config[key] != old_config[key]
            }
            
            if added_keys:
                self.logger.info(f"Configuration added: {added_keys}")
            if removed_keys:
                self.logger.info(f"Configuration removed: {removed_keys}")
            if modified_keys:
                self.logger.info(f"Configuration modified: {modified_keys}")
            
            # Apply configuration changes
            await self._apply_configuration_changes()
            
        except Exception as e:
            self.logger.error(f"Error handling configuration change: {e}", exc_info=True)
    
    async def _apply_configuration_changes(self) -> None:
        """Apply configuration changes to speech recognition service."""
        try:
            # Update internal settings based on new configuration
            # For example, update timeout settings, language preferences, etc.
            
            self.logger.debug("Applied configuration changes to speech recognition service")
            
        except Exception as e:
            self.logger.error(f"Error applying configuration changes: {e}", exc_info=True)
    
    def get_service_configuration(self) -> Dict[str, Any]:
        """Get current service configuration.
        
        Returns:
            Current service configuration dictionary
        """
        return self._service_config.copy()
    
    async def update_service_configuration(self, new_config: Dict[str, Any]) -> None:
        """Update service configuration.
        
        Args:
            new_config: New configuration to apply
        """
        self.logger.info("Updating service configuration")
        
        try:
            # Save configuration through ConfigManager
            await self.config_manager.save_config(
                config_data={"enabled": True, "overrides": new_config},
                module_name="speechmatics"
            )
            
            # Update local configuration
            self._service_config = new_config.copy()
            
            # Apply changes
            await self._apply_configuration_changes()
            
            self.logger.info("Service configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update service configuration: {e}", exc_info=True)
            raise