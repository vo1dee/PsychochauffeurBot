"""
Command Processor

This module provides standardized command processing and handler management
for the PsychoChauffeur bot.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters
from typing import Any

from modules.service_registry import ServiceInterface
from modules.error_handler import handle_errors

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands supported by the processor."""
    TEXT_COMMAND = "text_command"
    CALLBACK_QUERY = "callback_query"
    MESSAGE_HANDLER = "message_handler"
    PHOTO_HANDLER = "photo_handler"
    VOICE_HANDLER = "voice_handler"
    STICKER_HANDLER = "sticker_handler"
    LOCATION_HANDLER = "location_handler"


@dataclass
class CommandMetadata:
    """Metadata for command handlers."""
    name: str
    description: str
    command_type: CommandType
    permissions: Optional[List[str]] = None
    rate_limit: Optional[int] = None
    admin_only: bool = False
    group_only: bool = False
    private_only: bool = False
    
    def __post_init__(self) -> None:
        if self.permissions is None:
            self.permissions = []


class BaseCommandHandler(ABC):
    """Base class for all command handlers."""
    
    def __init__(self, metadata: CommandMetadata):
        self.metadata = metadata
    
    @abstractmethod
    async def handle(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle the command."""
        pass
    
    async def can_execute(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> bool:
        """Check if the command can be executed in the current context."""
        # Check chat type restrictions
        if self.metadata.private_only and update.effective_chat and update.effective_chat.type != 'private':
            return False
        
        if self.metadata.group_only and update.effective_chat and update.effective_chat.type == 'private':
            return False
        
        # Check admin permissions
        if self.metadata.admin_only:
            return await self._is_admin(update, context)
        
        return True
    
    async def _is_admin(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> bool:
        """Check if user is admin."""
        chat = update.effective_chat
        user = update.effective_user
        
        if chat and chat.type == 'private':
            return True
            
        try:
            if chat and user:
                member = await context.bot.get_chat_member(chat.id, user.id)
                return member.status in {"administrator", "creator"}
        except Exception:
            pass
        return False


class TextCommandHandler(BaseCommandHandler):
    """Handler for text-based commands."""
    
    def __init__(self, metadata: CommandMetadata, handler_func: Callable[..., Any]):
        super().__init__(metadata)
        self.handler_func = handler_func
    
    @handle_errors(feedback_message="An error occurred while processing the command.")
    async def handle(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle the text command."""
        if not await self.can_execute(update, context):
            if update.message:
                await update.message.reply_text("❌ Error occurred. This has been reported to the developer.")
            return
        
        await self.handler_func(update, context)


class CallbackQueryHandler(BaseCommandHandler):
    """Handler for callback queries."""
    
    def __init__(self, metadata: CommandMetadata, handler_func: Callable[..., Any], pattern: Optional[str] = None):
        super().__init__(metadata)
        self.handler_func = handler_func
        self.pattern = pattern
    
    @handle_errors(feedback_message="An error occurred while processing the callback.")
    async def handle(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle the callback query."""
        if not await self.can_execute(update, context):
            if update.callback_query:
                await update.callback_query.answer("❌ You don't have permission to use this feature.")
            return
        
        await self.handler_func(update, context)


class MessageFilterHandler(BaseCommandHandler):
    """Handler for filtered messages."""
    
    def __init__(self, metadata: CommandMetadata, handler_func: Callable[..., Any], message_filter: Any):
        super().__init__(metadata)
        self.handler_func = handler_func
        self.message_filter = message_filter
    
    @handle_errors(feedback_message="An error occurred while processing the message.")
    async def handle(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle the filtered message."""
        if not await self.can_execute(update, context):
            return  # Silently ignore for message handlers
        
        await self.handler_func(update, context)


class CommandProcessor(ServiceInterface):
    """
    Centralized command processor for standardized command handling.
    
    Manages command registration, routing, and execution with
    consistent error handling and permission checking.
    """
    
    def __init__(self) -> None:
        self._handlers: Dict[str, BaseCommandHandler] = {}
        self._telegram_handlers: List[Any] = []
        self._rate_limiter: Dict[str, Dict[int, float]] = {}
    
    async def initialize(self) -> None:
        """Initialize the command processor."""
        logger.info("Command Processor initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the command processor."""
        self._handlers.clear()
        self._telegram_handlers.clear()
        self._rate_limiter.clear()
        logger.info("Command Processor shutdown")
    
    def register_text_command(
        self,
        command: str,
        handler_func: Callable[..., Any],
        description: str = "",
        admin_only: bool = False,
        group_only: bool = False,
        private_only: bool = False,
        rate_limit: Optional[int] = None
    ) -> 'CommandProcessor':
        """Register a text command handler."""
        metadata = CommandMetadata(
            name=command,
            description=description,
            command_type=CommandType.TEXT_COMMAND,
            admin_only=admin_only,
            group_only=group_only,
            private_only=private_only,
            rate_limit=rate_limit
        )
        
        handler = TextCommandHandler(metadata, handler_func)
        self._handlers[command] = handler
        
        # Create Telegram handler
        telegram_handler = CommandHandler(command, handler.handle)
        self._telegram_handlers.append(telegram_handler)
        
        logger.info(f"Registered text command: /{command}")
        return self
    
    def register_callback_handler(
        self,
        name: str,
        handler_func: Callable[..., Any],
        pattern: Optional[str] = None,
        description: str = "",
        admin_only: bool = False
    ) -> 'CommandProcessor':
        """Register a callback query handler."""
        metadata = CommandMetadata(
            name=name,
            description=description,
            command_type=CommandType.CALLBACK_QUERY,
            admin_only=admin_only
        )
        
        handler = CallbackQueryHandler(metadata, handler_func, pattern)
        self._handlers[name] = handler
        
        # Create Telegram handler
        from telegram.ext import CallbackQueryHandler as TelegramCallbackHandler
        if pattern:
            telegram_handler = TelegramCallbackHandler(handler.handle, pattern=pattern)
        else:
            telegram_handler = TelegramCallbackHandler(handler.handle)
        self._telegram_handlers.append(telegram_handler)
        
        logger.info(f"Registered callback handler: {name}")
        return self
    
    def register_message_handler(
        self,
        name: str,
        handler_func: Callable[..., Any],
        message_filter: Any,
        description: str = "",
        admin_only: bool = False,
        group_only: bool = False,
        private_only: bool = False
    ) -> 'CommandProcessor':
        """Register a message handler with filter."""
        metadata = CommandMetadata(
            name=name,
            description=description,
            command_type=CommandType.MESSAGE_HANDLER,
            admin_only=admin_only,
            group_only=group_only,
            private_only=private_only
        )
        
        handler = MessageFilterHandler(metadata, handler_func, message_filter)
        self._handlers[name] = handler
        
        # Create Telegram handler
        telegram_handler = MessageHandler(message_filter, handler.handle)
        self._telegram_handlers.append(telegram_handler)
        
        logger.info(f"Registered message handler: {name}")
        return self
    
    def get_telegram_handlers(self) -> List[Any]:
        """Get all Telegram handlers for registration."""
        return self._telegram_handlers.copy()
    
    def get_registered_commands(self) -> List[str]:
        """Get list of all registered command names."""
        return list(self._handlers.keys())
    
    def get_command_info(self, command: str) -> Optional[CommandMetadata]:
        """Get metadata for a specific command."""
        handler = self._handlers.get(command)
        return handler.metadata if handler else None
    
    def get_commands_by_type(self, command_type: CommandType) -> List[str]:
        """Get all commands of a specific type."""
        return [
            name for name, handler in self._handlers.items()
            if handler.metadata.command_type == command_type
        ]