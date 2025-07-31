"""
Callback Handler Service for centralized callback query processing.

This service handles all callback queries from inline keyboards including:
- Speech recognition callbacks
- Language selection callbacks  
- Link modification callbacks
- Video download callbacks
- Security validation and expiration handling

The service routes callbacks to appropriate handlers and provides centralized
validation, security checks, and error handling.
"""

import hashlib
import re
import time
from typing import Any, Dict, Optional, Set, Tuple, Callable, Awaitable
from telegram import Update
from telegram.ext import CallbackContext

from modules.service_registry import ServiceInterface
from modules.speech_recognition_service import SpeechRecognitionService
from modules.keyboards import BUTTONS_CONFIG, LANGUAGE_OPTIONS_CONFIG
from modules.logger import general_logger, error_logger


class CallbackHandlerService(ServiceInterface):
    """Service for handling all callback query processing.
    
    This service centralizes callback handling logic that was previously
    scattered across different modules. It provides:
    - Callback routing based on data patterns
    - Security validation and expiration handling
    - Integration with speech recognition service
    - Support for link modification callbacks
    - Comprehensive error handling and logging
    
    The service follows the ServiceInterface pattern and integrates with
    the existing ServiceRegistry for dependency injection.
    """
    
    def __init__(self, speech_service: Optional[SpeechRecognitionService] = None) -> None:
        """Initialize the callback handler service.
        
        Args:
            speech_service: Speech recognition service for handling speech callbacks
        """
        self.speech_service = speech_service
        self.callback_timestamps: Dict[str, float] = {}
        self.callback_expiry_seconds = 3600  # 1 hour expiry for callbacks
        
        # Define callback patterns and their handlers
        self._callback_handlers: Dict[str, Callable[[Update, CallbackContext[Any, Any, Any, Any]], Awaitable[None]]] = {
            r"^speechrec_": self._handle_speech_recognition_callback,
            r"^lang_": self._handle_language_selection_callback,
            r"^test_callback$": self._handle_test_callback,
            r"^[a-zA-Z_]+:[0-9a-f]+$": self._handle_link_modification_callback,
        }
        
    async def initialize(self) -> None:
        """Initialize the service."""
        general_logger.info("CallbackHandlerService initialized")
        
    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        self.callback_timestamps.clear()
        general_logger.info("CallbackHandlerService shutdown")
        
    async def handle_callback_query(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Main entry point for handling callback queries.
        
        Args:
            update: Telegram update containing the callback query
            context: Telegram callback context
        """
        query = update.callback_query
        if not query:
            general_logger.warning("Received update without callback_query")
            return
            
        await query.answer()
        
        callback_data = query.data
        if not callback_data:
            await self._send_error_response(query, "❌ Invalid callback data.")
            return
            
        general_logger.info(f"Processing callback: {callback_data}")
        
        try:
            # Clean up expired callbacks
            self._cleanup_expired_callbacks()
            
            # Route callback to appropriate handler
            await self._route_callback(callback_data, update, context)
            
        except Exception as e:
            error_logger.error(f"Error processing callback {callback_data}: {e}", exc_info=True)
            await self._send_error_response(query, f"❌ Error processing callback: {str(e)}")
            
    async def _route_callback(
        self, 
        callback_data: str, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any]
    ) -> None:
        """Route callback to appropriate handler based on data pattern.
        
        Args:
            callback_data: The callback data to route
            update: Telegram update
            context: Telegram callback context
        """
        for pattern, handler in self._callback_handlers.items():
            if re.match(pattern, callback_data):
                await handler(update, context)
                return
                
        # No handler found
        general_logger.warning(f"No handler found for callback data: {callback_data}")
        query = update.callback_query
        if query:
            await self._send_error_response(query, "❌ Unknown callback action.")
            
    async def _handle_speech_recognition_callback(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any]
    ) -> None:
        """Handle speech recognition callbacks.
        
        Args:
            update: Telegram update
            context: Telegram callback context
        """
        if not self.speech_service:
            query = update.callback_query
            if query:
                await self._send_error_response(query, "❌ Speech recognition service not available.")
            return
            
        await self.speech_service.process_speech_recognition(update, context)
        
    async def _handle_language_selection_callback(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any]
    ) -> None:
        """Handle language selection callbacks.
        
        Args:
            update: Telegram update
            context: Telegram callback context
        """
        if not self.speech_service:
            query = update.callback_query
            if query:
                await self._send_error_response(query, "❌ Speech recognition service not available.")
            return
            
        await self.speech_service.handle_language_selection(update, context)
        
    async def _handle_test_callback(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any]
    ) -> None:
        """Handle test callbacks for debugging.
        
        Args:
            update: Telegram update
            context: Telegram callback context
        """
        query = update.callback_query
        if query:
            await query.edit_message_text("✅ Test callback received and handled!")
            
    async def _handle_link_modification_callback(
        self, 
        update: Update, 
        context: CallbackContext[Any, Any, Any, Any]
    ) -> None:
        """Handle link modification callbacks (from keyboards.py).
        
        Args:
            update: Telegram update
            context: Telegram callback context
        """
        query = update.callback_query
        if not query or not query.data:
            return
            
        callback_data = query.data
        
        # Validate format: action:hash
        if ':' not in callback_data:
            await self._send_error_response(query, "Invalid callback data.")
            return
            
        action, link_hash = callback_data.split(':', 1)
        
        # Validate action
        valid_actions = {btn['action'] for btn in BUTTONS_CONFIG + LANGUAGE_OPTIONS_CONFIG}
        valid_actions.update({'download_video', 'download_instagram_service'})
        
        if action not in valid_actions:
            await self._send_error_response(query, "Unknown action.")
            return
            
        # Validate hash: 8 hex chars
        if not re.fullmatch(r"[0-9a-f]{8}", link_hash):
            await self._send_error_response(query, "Invalid callback identifier.")
            return
            
        general_logger.info(f"Link modification callback - Action: {action}, Hash: {link_hash}")
        
        if not query.message or not hasattr(query.message, 'chat_id'):
            return
            
        # Get original link from bot_data
        original_link = context.bot_data.get(link_hash)
        
        if not original_link:
            await self._send_error_response(
                query, 
                "Sorry, this button has expired. Please generate a new link."
            )
            return
            
        # Import and delegate to existing button_callback logic
        # This maintains compatibility with existing keyboard functionality
        from modules.keyboards import button_callback
        await button_callback(update, context)
        
    def validate_callback_data(self, callback_data: str) -> Tuple[bool, Optional[str]]:
        """Validate callback data format and security.
        
        Args:
            callback_data: The callback data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not callback_data:
            return False, "Empty callback data"
            
        # Check for expired callbacks
        if self._is_callback_expired(callback_data):
            return False, "Callback has expired"
            
        # Validate speech recognition callbacks
        if callback_data.startswith("speechrec_"):
            if self.speech_service:
                return self.speech_service.validate_callback_data(callback_data)
            return False, "Speech service not available"
            
        # Validate language selection callbacks
        elif callback_data.startswith("lang_") and '|' in callback_data:
            if self.speech_service:
                return self.speech_service.validate_callback_data(callback_data)
            return False, "Speech service not available"
            
        # Validate link modification callbacks
        elif ':' in callback_data:
            action, link_hash = callback_data.split(':', 1)
            
            # Check action validity
            valid_actions = {btn['action'] for btn in BUTTONS_CONFIG + LANGUAGE_OPTIONS_CONFIG}
            valid_actions.update({'download_video', 'download_instagram_service'})
            
            if action not in valid_actions:
                return False, f"Invalid action: {action}"
                
            # Check hash format (8 hex chars for link hashes)
            if not re.fullmatch(r"[0-9a-f]{8}", link_hash):
                return False, "Invalid hash format"
                
            return True, None
            
        # Test callback
        elif callback_data == "test_callback":
            return True, None
            
        return False, "Unknown callback format"
        
    def register_callback_timestamp(self, callback_data: str) -> None:
        """Register timestamp for callback expiration tracking.
        
        Args:
            callback_data: The callback data to track
        """
        self.callback_timestamps[callback_data] = time.time()
        
    def _is_callback_expired(self, callback_data: str) -> bool:
        """Check if a callback has expired.
        
        Args:
            callback_data: The callback data to check
            
        Returns:
            True if expired, False otherwise
        """
        timestamp = self.callback_timestamps.get(callback_data)
        if not timestamp:
            return False
            
        return (time.time() - timestamp) > self.callback_expiry_seconds
        
    def _cleanup_expired_callbacks(self) -> None:
        """Clean up expired callback timestamps."""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.callback_timestamps.items()
            if (current_time - timestamp) > self.callback_expiry_seconds
        ]
        
        for key in expired_keys:
            del self.callback_timestamps[key]
            
        if expired_keys:
            general_logger.debug(f"Cleaned up {len(expired_keys)} expired callbacks")
            
    async def _send_error_response(self, query: Any, message: str) -> None:
        """Send error response to callback query.
        
        Args:
            query: Telegram callback query
            message: Error message to send
        """
        try:
            if hasattr(query, 'edit_message_text'):
                await query.edit_message_text(message)
            elif hasattr(query, 'message') and hasattr(query.message, 'edit_text'):
                await query.message.edit_text(message)
        except Exception as e:
            error_logger.error(f"Failed to send error response: {e}")
            
    def get_supported_callback_patterns(self) -> Set[str]:
        """Get set of supported callback patterns.
        
        Returns:
            Set of regex patterns for supported callbacks
        """
        return set(self._callback_handlers.keys())
        
    def set_speech_service(self, speech_service: SpeechRecognitionService) -> None:
        """Set the speech recognition service.
        
        Args:
            speech_service: Speech recognition service instance
        """
        self.speech_service = speech_service
        general_logger.info("Speech service set for CallbackHandlerService")