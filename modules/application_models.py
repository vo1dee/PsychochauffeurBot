"""
Data models for the application refactoring.

This module contains the enhanced data models used throughout the refactored
application architecture, including service configuration, message context,
and handler metadata.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from telegram import Update
from telegram.ext import CallbackContext


@dataclass
class ServiceConfiguration:
    """Configuration for service initialization.
    
    This class holds all the essential configuration parameters needed
    to initialize and configure the bot services.
    
    Attributes:
        telegram_token: The Telegram bot token for API access
        error_channel_id: Optional channel ID for error reporting and notifications
        database_url: Optional database connection URL
        redis_url: Optional Redis connection URL for caching
        debug_mode: Whether to enable debug mode features
    """
    telegram_token: str
    error_channel_id: Optional[str] = None
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    debug_mode: bool = False
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.telegram_token:
            raise ValueError("telegram_token is required")


@dataclass
class MessageContext:
    """Enhanced context for message processing.
    
    This class provides a comprehensive context object that contains
    all the information needed for processing messages throughout
    the application.
    
    Attributes:
        update: The Telegram update object
        context: The Telegram callback context
        user_id: ID of the user who sent the message
        chat_id: ID of the chat where the message was sent
        chat_type: Type of chat (private, group, supergroup, channel)
        message_text: Text content of the message (if any)
        urls: List of URLs extracted from the message
        is_command: Whether the message is a command
        requires_gpt_response: Whether the message should trigger a GPT response
    """
    update: Update
    context: CallbackContext[Any, Any, Any, Any]
    user_id: int
    chat_id: int
    chat_type: str
    message_text: Optional[str] = None
    urls: List[str] = field(default_factory=list)
    is_command: bool = False
    requires_gpt_response: bool = False
    
    @classmethod
    def from_update(cls, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> 'MessageContext':
        """Create MessageContext from Telegram update and context.
        
        Args:
            update: The Telegram update object
            context: The Telegram callback context
            
        Returns:
            MessageContext: A new MessageContext instance
            
        Raises:
            ValueError: If required information is missing from the update
        """
        if not update.effective_user:
            raise ValueError("Update must have an effective user")
        if not update.effective_chat:
            raise ValueError("Update must have an effective chat")
            
        message_text = None
        is_command = False
        
        if update.message and update.message.text:
            message_text = update.message.text.strip()
            is_command = message_text.startswith('/')
        
        return cls(
            update=update,
            context=context,
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            chat_type=update.effective_chat.type,
            message_text=message_text,
            is_command=is_command
        )


@dataclass
class HandlerMetadata:
    """Metadata for message handlers.
    
    This class contains metadata information about message handlers,
    including their capabilities, priority, and configuration.
    
    Attributes:
        name: Unique name of the handler
        description: Human-readable description of what the handler does
        message_types: List of message types this handler can process
        priority: Priority level for handler execution (higher = earlier)
        enabled: Whether the handler is currently enabled
        dependencies: List of service names this handler depends on
    """
    name: str
    description: str
    message_types: List[str]
    priority: int = 0
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        if not self.name:
            raise ValueError("Handler name is required")
        if not self.description:
            raise ValueError("Handler description is required")
        if not self.message_types:
            raise ValueError("At least one message type must be specified")


@dataclass
class CommandMetadata:
    """Metadata for bot commands.
    
    This class contains metadata information about bot commands,
    including their configuration, permissions, and categorization.
    
    Attributes:
        name: Command name (without the / prefix)
        description: Human-readable description of the command
        category: Category this command belongs to (basic, gpt, utility, speech)
        admin_only: Whether this command requires admin privileges
        enabled: Whether the command is currently enabled
        aliases: Alternative names for this command
        usage: Usage example or syntax help
    """
    name: str
    description: str
    category: str = "basic"
    admin_only: bool = False
    enabled: bool = True
    aliases: List[str] = field(default_factory=list)
    usage: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate command metadata after initialization."""
        if not self.name:
            raise ValueError("Command name is required")
        if not self.description:
            raise ValueError("Command description is required")
        if self.category not in ["basic", "gpt", "utility", "speech", "admin"]:
            raise ValueError(f"Invalid command category: {self.category}")


@dataclass
class ServiceHealth:
    """Health status information for a service.
    
    This class represents the health status of a service,
    including whether it's running, any error information,
    and performance metrics.
    
    Attributes:
        service_name: Name of the service
        is_healthy: Whether the service is currently healthy
        status: Current status description
        last_check: Timestamp of the last health check
        error_message: Error message if the service is unhealthy
        metrics: Optional performance metrics
    """
    service_name: str
    is_healthy: bool
    status: str
    last_check: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)