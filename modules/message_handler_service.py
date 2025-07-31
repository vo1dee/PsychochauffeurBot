"""
Message Handler Service

Centralized message processing service that handles all incoming messages
and routes them to appropriate specialized handlers.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from config.config_manager import ConfigManager
from modules.application_models import MessageContext, HandlerMetadata
from modules.const import Stickers
from modules.error_handler import handle_errors
from modules.gpt import gpt_response
from modules.keyboards import create_link_keyboard
from modules.logger import general_logger, error_logger
from modules.message_processor import (
    needs_gpt_response, update_message_history, get_previous_message,
    process_message_content, should_restrict_user
)
from modules.service_registry import ServiceInterface
from modules.url_processor import extract_urls
from modules.user_management import restrict_user, handle_restriction_sticker
from modules.utils import MessageCounter, chat_history_manager

logger = logging.getLogger(__name__)


class BaseMessageHandler(ABC):
    """Base class for all message handlers."""
    
    def __init__(self, name: str, description: str, message_types: List[str], priority: int = 0) -> None:
        self.metadata = HandlerMetadata(
            name=name,
            description=description,
            message_types=message_types,
            priority=priority
        )
    
    @abstractmethod
    async def can_handle(self, message_context: MessageContext) -> bool:
        """Check if this handler can process the given message context."""
        pass
    
    @abstractmethod
    async def handle(self, message_context: MessageContext) -> None:
        """Process the message using this handler."""
        pass


class TextMessageHandler(BaseMessageHandler):
    """Handler for text messages including URL processing and GPT integration."""
    
    def __init__(self, config_manager: ConfigManager, message_counter: MessageCounter) -> None:
        super().__init__(
            name="text_message_handler",
            description="Handles text messages, URL processing, and GPT responses",
            message_types=["text"],
            priority=10
        )
        self.config_manager = config_manager
        self.message_counter = message_counter
    
    async def can_handle(self, message_context: MessageContext) -> bool:
        """Check if this is a text message that needs processing."""
        return (
            message_context.message_text is not None and
            not message_context.is_command and
            message_context.update.message is not None
        )
    
    @handle_errors(feedback_message="An error occurred while processing your message.")
    async def handle(self, message_context: MessageContext) -> None:
        """Process text message with URL handling and GPT integration."""
        if not message_context.message_text or not message_context.update.message:
            return
        
        message_text = message_context.message_text
        user_id = message_context.user_id
        update = message_context.update
        context = message_context.context
        
        # Update message history at the very start
        update_message_history(user_id, message_text)
        
        # Handle БЛЯ! translation command
        if message_text.lower() == "бля!":
            await self._handle_translation_command(update, user_id)
            return
        
        # Update chat history for context
        if update.effective_chat:
            chat_history_manager.add_message(update.effective_chat.id, {
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
        if modified_links and all(
            link.lower().startswith((
                'https://aliexpress.com/', 
                'https://www.aliexpress.com/', 
                'https://m.aliexpress.com/'
            )) for link in modified_links
        ):
            return
        
        # Check for GPT response
        needs_response, response_type = needs_gpt_response(update, context, message_text)
        if needs_response:
            await gpt_response(update, context, response_type=response_type, message_text_override=cleaned_text)
            return
        
        # Handle random GPT response logic in group chats
        if await self._should_trigger_random_gpt(update, message_text, cleaned_text):
            return
        
        # Handle modified links if any were found
        if modified_links:
            await self._process_urls(update, context, modified_links, cleaned_text)
    
    async def _handle_translation_command(self, update: Update, user_id: int) -> None:
        """Handle the БЛЯ! translation command."""
        if not update.message or not update.message.from_user:
            return
        
        username = update.message.from_user.username or "User"
        previous_message = get_previous_message(user_id)
        
        if not previous_message:
            await update.message.reply_text("Немає попереднього повідомлення для перекладу.")
            return
        
        from modules.keyboard_translator import auto_translate_text
        converted_text = auto_translate_text(previous_message)
        response_text = f"@{username} хотів сказати: {converted_text}"
        await update.message.reply_text(response_text)
    
    async def _should_trigger_random_gpt(self, update: Update, message_text: str, cleaned_text: str) -> bool:
        """Check if random GPT response should be triggered."""
        # Only in group chats, not private
        if not update.effective_chat or update.effective_chat.type not in {"group", "supergroup"}:
            return False
        
        # Block random GPT response if message contains any link
        if extract_urls(message_text):
            return False
        
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        config = await self.config_manager.get_config(
            chat_id=str(chat_id), 
            chat_type=chat_type, 
            module_name="chat_behavior"
        )
        
        # Check if chat_behavior module is enabled
        module_enabled = config.get("enabled", False)
        overrides = config.get("overrides", {})
        random_settings = overrides.get("random_response_settings", {})
        random_enabled = random_settings.get("enabled", False)
        
        # Both module and random settings must be enabled
        if not (module_enabled and random_enabled):
            if not module_enabled:
                general_logger.debug(f"Random responses disabled: chat_behavior module not enabled in chat {chat_id}")
            elif not random_enabled:
                general_logger.debug(f"Random responses disabled: random_response_settings not enabled in chat {chat_id}")
            return False
        
        min_words = random_settings.get("min_words", 5)
        message_threshold = random_settings.get("message_threshold", 50)
        probability = random_settings.get("probability", 0.02)
        
        # Only consider messages with enough words
        if len(message_text.split()) < min_words:
            return False
        
        count = self.message_counter.increment(update.effective_chat.id)
        general_logger.info(f"Random response check: chat_id={chat_id}, count={count}/{message_threshold}, probability={probability}")
        
        if count >= message_threshold:
            import random
            if random.random() < probability:
                self.message_counter.reset(update.effective_chat.id)
                general_logger.info(f"Triggering random response in chat {chat_id}")
                await gpt_response(update, message_context.context, response_type="random", message_text_override=cleaned_text)
                return True
        
        return False
    
    @handle_errors(feedback_message="An error occurred while processing your links.")
    async def _process_urls(self, update: Update, context: CallbackContext[Any, Any, Any, Any], urls: List[str], message_text: str) -> None:
        """Process URLs in the message."""
        if not update.message or not update.message.from_user or not update.effective_chat:
            return
        
        username = update.message.from_user.username or f"ID:{update.message.from_user.id}"
        await self._construct_and_send_message(update.effective_chat.id, username, message_text, urls, update, context)
    
    @handle_errors(feedback_message="An error occurred while constructing the message.")
    async def _construct_and_send_message(
        self,
        chat_id: int,
        username: str,
        cleaned_message_text: str,
        modified_links: List[str],
        update: Update,
        context: CallbackContext[Any, Any, Any, Any]
    ) -> None:
        """Construct and send a message with modified links."""
        try:
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            escaped_username = username
            for char in special_chars:
                escaped_username = escaped_username.replace(char, f'\\{char}')
            
            escaped_text = cleaned_message_text
            for char in special_chars:
                escaped_text = escaped_text.replace(char, f'\\{char}')
            
            escaped_links = []
            for url in modified_links:
                escaped_url = url
                for char in special_chars:
                    escaped_url = escaped_url.replace(char, f'\\{char}')
                escaped_links.append(escaped_url)
            
            message = f"@{escaped_username} хотів відправити:\n{escaped_text}"
            keyboard = create_link_keyboard(escaped_links, context)
            
            # Check if the original message was a reply to another message
            if update.message and update.message.reply_to_message:
                # If it was a reply, send the modified link message as a reply to the parent message
                await update.message.reply_to_message.reply_text(
                    text=message,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                # If it wasn't a reply, send the modified link message as a reply to the original message
                if update.message:
                    await update.message.reply_text(
                        text=message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
        except Exception as e:
            error_logger.error(f"Failed to send message: {str(e)}", exc_info=True)
            raise


class StickerHandler(BaseMessageHandler):
    """Handler for sticker messages."""
    
    def __init__(self) -> None:
        super().__init__(
            name="sticker_handler",
            description="Handles sticker messages and restriction logic",
            message_types=["sticker"],
            priority=5
        )
    
    async def can_handle(self, message_context: MessageContext) -> bool:
        """Check if this is a sticker message."""
        return (
            message_context.update.message is not None and
            message_context.update.message.sticker is not None
        )
    
    @handle_errors(feedback_message="An error occurred while handling sticker.")
    async def handle(self, message_context: MessageContext) -> None:
        """Handle sticker messages."""
        update = message_context.update
        context = message_context.context
        
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
            await handle_restriction_sticker(update, context)


class LocationHandler(BaseMessageHandler):
    """Handler for location messages."""
    
    def __init__(self) -> None:
        super().__init__(
            name="location_handler",
            description="Handles location messages by replying with a sticker",
            message_types=["location"],
            priority=5
        )
    
    async def can_handle(self, message_context: MessageContext) -> bool:
        """Check if this is a location message."""
        return (
            message_context.update.message is not None and
            message_context.update.message.location is not None
        )
    
    @handle_errors(feedback_message="An error occurred while handling location.")
    async def handle(self, message_context: MessageContext) -> None:
        """Handle location messages by replying with a sticker."""
        update = message_context.update
        
        if not update.message or not update.message.location:
            return
        
        location = update.message.location
        general_logger.info(f"Received location: lat={location.latitude}, lon={location.longitude}")
        
        try:
            # Reply with the location sticker
            await update.message.reply_sticker(sticker=Stickers.LOCATION)
            general_logger.info("Sent location sticker in response to location message")
        except Exception as e:
            error_logger.error(f"Failed to send location sticker: {e}")
            await update.message.reply_text("📍 Location received!")


class MessageHandlerService(ServiceInterface):
    """Centralized message processing service."""
    
    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.message_counter = MessageCounter()
        self.handlers: List[BaseMessageHandler] = []
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the message handler service."""
        if self._initialized:
            return
        
        # Initialize specialized handlers
        self.handlers = [
            TextMessageHandler(self.config_manager, self.message_counter),
            StickerHandler(),
            LocationHandler(),
        ]
        
        # Sort handlers by priority (higher priority first)
        self.handlers.sort(key=lambda h: h.metadata.priority, reverse=True)
        
        self._initialized = True
        logger.info("Message Handler Service initialized with %d handlers", len(self.handlers))
    
    async def shutdown(self) -> None:
        """Shutdown the message handler service."""
        self.handlers.clear()
        self._initialized = False
        logger.info("Message Handler Service shutdown")
    
    async def handle_text_message(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle incoming text messages."""
        if not self._initialized:
            await self.initialize()
        
        try:
            message_context = MessageContext.from_update(update, context)
            
            # Extract URLs from message if it's a text message
            if message_context.message_text:
                message_context.urls = extract_urls(message_context.message_text)
            
            # Find and execute the appropriate handler
            for handler in self.handlers:
                if await handler.can_handle(message_context):
                    await handler.handle(message_context)
                    break
            else:
                logger.debug("No handler found for message type: %s", type(update.message).__name__ if update.message else "unknown")
        
        except Exception as e:
            error_logger.error(f"Error in message handling: {str(e)}", exc_info=True)
    
    async def handle_sticker_message(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle incoming sticker messages."""
        if not self._initialized:
            await self.initialize()
        
        try:
            message_context = MessageContext.from_update(update, context)
            
            # Find the sticker handler
            for handler in self.handlers:
                if handler.metadata.name == "sticker_handler" and await handler.can_handle(message_context):
                    await handler.handle(message_context)
                    break
        
        except Exception as e:
            error_logger.error(f"Error in sticker handling: {str(e)}", exc_info=True)
    
    async def handle_location_message(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle incoming location messages."""
        if not self._initialized:
            await self.initialize()
        
        try:
            message_context = MessageContext.from_update(update, context)
            
            # Find the location handler
            for handler in self.handlers:
                if handler.metadata.name == "location_handler" and await handler.can_handle(message_context):
                    await handler.handle(message_context)
                    break
        
        except Exception as e:
            error_logger.error(f"Error in location handling: {str(e)}", exc_info=True)
    
    async def process_urls(self, update: Update, context: CallbackContext[Any, Any, Any, Any], urls: List[str]) -> None:
        """Process URLs in the message."""
        if not update.message or not update.message.from_user:
            return
        
        username = update.message.from_user.username or f"ID:{update.message.from_user.id}"
        message_text = update.message.text or ""
        
        if urls and update.effective_chat:
            text_handler = next((h for h in self.handlers if h.metadata.name == "text_message_handler"), None)
            if isinstance(text_handler, TextMessageHandler):
                await text_handler._construct_and_send_message(
                    update.effective_chat.id, username, message_text, urls, update, context
                )
    
    async def check_random_gpt_response(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> bool:
        """Check if a random GPT response should be triggered."""
        if not update.message or not update.message.text:
            return False
        
        text_handler = next((h for h in self.handlers if h.metadata.name == "text_message_handler"), None)
        if isinstance(text_handler, TextMessageHandler):
            return await text_handler._should_trigger_random_gpt(update, update.message.text, update.message.text)
        
        return False
    
    def get_handler_metadata(self) -> List[HandlerMetadata]:
        """Get metadata for all registered handlers."""
        return [handler.metadata for handler in self.handlers]