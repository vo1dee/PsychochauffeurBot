"""
Comprehensive type definitions for the PsychoChauffeur bot.

This module provides type hints, custom types, and generic types for better code quality
and IDE support throughout the application.
"""

from typing import (
    TypeVar, Generic, Protocol, Union, Optional, Dict, List, Any, 
    Callable, Awaitable, Tuple, Set, NamedTuple, TypedDict, Literal
)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import CallbackContext, Application
from typing import Any

# Generic type variables
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
ServiceType = TypeVar('ServiceType')
ConfigType = TypeVar('ConfigType')
HandlerType = TypeVar('HandlerType')

# Basic type aliases
UserId = int
ChatId = int
MessageId = int
FileId = str
Timestamp = datetime
JSONDict = Dict[str, Any]
ConfigDict = Dict[str, Any]

# Telegram-specific types
TelegramUpdate = Update
TelegramContext = CallbackContext[Any, Any, Any, Any]
TelegramMessage = Message
TelegramUser = User
TelegramChat = Chat
TelegramCallback = CallbackQuery
TelegramApplication = Application[Any, Any, Any, Any, Any, Any]

# Handler function types
MessageHandler = Callable[[Update, CallbackContext[Any, Any, Any, Any]], Awaitable[None]]
CommandHandler = Callable[[Update, CallbackContext[Any, Any, Any, Any]], Awaitable[None]]
CallbackHandler = Callable[[Update, CallbackContext[Any, Any, Any, Any]], Awaitable[None]]
ErrorHandler = Callable[[Exception, Update, CallbackContext[Any, Any, Any, Any]], Awaitable[None]]

# Service types
AsyncService = Callable[..., Awaitable[Any]]
SyncService = Callable[..., Any]

# Configuration types
class ConfigScope(Enum):
    """Configuration scope levels."""
    GLOBAL = "global"
    CHAT = "chat"
    USER = "user"
    MODULE = "module"

class ChatType(Enum):
    """Telegram chat types."""
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"

class MessageType(Enum):
    """Message content types."""
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"

# Error handling types
class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification."""
    GENERAL = "general"
    NETWORK = "network"
    API = "api"
    DATABASE = "database"
    PARSING = "parsing"
    INPUT = "input"
    PERMISSION = "permission"
    RESOURCE = "resource"

# Service registry types
class ServiceLifecycle(Enum):
    """Service lifecycle states."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

# Data model types
@dataclass
class UserInfo:
    """User information data class."""
    id: UserId
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    language_code: Optional[str]
    is_bot: bool = False

@dataclass
class ChatInfo:
    """Chat information data class."""
    id: ChatId
    type: ChatType
    title: Optional[str]
    username: Optional[str]
    description: Optional[str]

@dataclass
class MessageInfo:
    """Message information data class."""
    id: MessageId
    user: UserInfo
    chat: ChatInfo
    text: Optional[str]
    message_type: MessageType
    timestamp: Timestamp
    reply_to_message_id: Optional[MessageId] = None

# Configuration types
class ConfigValue(TypedDict, total=False):
    """Configuration value with metadata."""
    value: Any
    type: str
    description: Optional[str]
    default: Any
    required: bool

class ModuleConfig(TypedDict, total=False):
    """Module configuration structure."""
    enabled: bool
    settings: Dict[str, Any]
    dependencies: List[str]
    version: str

# Service interfaces
class Service(Protocol):
    """Base service protocol."""
    
    async def initialize(self) -> None:
        """Initialize the service."""
        ...
    
    async def start(self) -> None:
        """Start the service."""
        ...
    
    async def stop(self) -> None:
        """Stop the service."""
        ...
    
    async def health_check(self) -> bool:
        """Check service health."""
        ...

class ConfigurableService(Service, Protocol):
    """Service that can be configured."""
    
    def configure(self, config: ConfigDict) -> None:
        """Configure the service."""
        ...

class AsyncRepository(Protocol, Generic[T]):
    """Generic async repository interface."""
    
    async def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by ID."""
        ...
    
    async def save(self, entity: T) -> T:
        """Save entity."""
        ...
    
    async def delete(self, id: Any) -> bool:
        """Delete entity by ID."""
        ...
    
    async def find_all(self) -> List[T]:
        """Find all entities."""
        ...
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """Find entities by criteria."""
        ...

# Command processing types
class CommandContext(NamedTuple):
    """Command execution context."""
    update: Update
    context: CallbackContext[Any, Any, Any, Any]
    command: str
    args: List[str]
    user: UserInfo
    chat: ChatInfo

class CommandResult(NamedTuple):
    """Command execution result."""
    success: bool
    message: Optional[str]
    data: Optional[Any] = None
    error: Optional[Exception] = None

# Event system types
class EventType(Enum):
    """System event types."""
    MESSAGE_RECEIVED = "message_received"
    COMMAND_EXECUTED = "command_executed"
    ERROR_OCCURRED = "error_occurred"
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    CONFIG_CHANGED = "config_changed"

@dataclass
class Event:
    """System event data class."""
    type: EventType
    timestamp: Timestamp
    source: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None

EventListener = Callable[[Event], Awaitable[None]]

# External service types
class APIResponse(TypedDict, total=False):
    """Standard API response structure."""
    success: bool
    data: Any
    error: Optional[str]
    status_code: int
    headers: Dict[str, str]

class DownloadResult(NamedTuple):
    """File download result."""
    success: bool
    file_path: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    error: Optional[str] = None

class WeatherData(TypedDict):
    """Weather information structure."""
    temperature: float
    feels_like: float
    humidity: int
    pressure: int
    description: str
    icon: str
    city: str
    country: str

# AI service types
class AIModel(Enum):
    """Available AI models."""
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_3_SONNET = "claude-3-sonnet"

class AIResponseType(Enum):
    """AI response types."""
    DIRECT = "direct"
    RANDOM = "random"
    CONTEXTUAL = "contextual"
    ANALYSIS = "analysis"

@dataclass
class AIContext:
    """AI request context."""
    chat_id: ChatId
    user_id: UserId
    message_history: List[MessageInfo]
    response_type: AIResponseType
    model: AIModel
    max_tokens: int = 1000
    temperature: float = 0.7

# Database types
class DatabaseOperation(Enum):
    """Database operation types."""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    TRANSACTION = "transaction"

@dataclass
class QueryResult:
    """Database query result."""
    success: bool
    rows_affected: int
    data: Optional[List[Dict[str, Any]]]
    error: Optional[str] = None

# Caching types
class CacheStrategy(Enum):
    """Cache strategies."""
    LRU = "lru"
    TTL = "ttl"
    FIFO = "fifo"
    NONE = "none"

@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: Timestamp
    expires_at: Optional[Timestamp]
    access_count: int = 0
    last_accessed: Optional[Timestamp] = None

# Validation types
ValidationRule = Callable[[Any], bool]
ValidationResult = Tuple[bool, Optional[str]]

class InputValidator(Protocol):
    """Input validation interface."""
    
    def validate(self, value: Any) -> ValidationResult:
        """Validate input value."""
        ...

# Monitoring types
@dataclass
class PerformanceMetric:
    """Performance metric data."""
    name: str
    value: float
    unit: str
    timestamp: Timestamp
    tags: Dict[str, str]

@dataclass
class HealthStatus:
    """Service health status."""
    service_name: str
    is_healthy: bool
    status_message: str
    last_check: Timestamp
    metrics: List[PerformanceMetric]

# Factory types
class Factory(Protocol, Generic[T]):
    """Generic factory interface."""
    
    def create(self, *args, **kwargs) -> T:
        """Create instance."""
        ...

class AsyncFactory(Protocol, Generic[T]):
    """Generic async factory interface."""
    
    async def create(self, *args, **kwargs) -> T:
        """Create instance asynchronously."""
        ...

# Strategy pattern types
class Strategy(Protocol, Generic[T]):
    """Generic strategy interface."""
    
    def execute(self, context: T) -> Any:
        """Execute strategy."""
        ...

class AsyncStrategy(Protocol, Generic[T]):
    """Generic async strategy interface."""
    
    async def execute(self, context: T) -> Any:
        """Execute strategy asynchronously."""
        ...

# Observer pattern types
class Observer(Protocol, Generic[T]):
    """Generic observer interface."""
    
    def update(self, subject: T, event: Event) -> None:
        """Handle update notification."""
        ...

class AsyncObserver(Protocol, Generic[T]):
    """Generic async observer interface."""
    
    async def update(self, subject: T, event: Event) -> None:
        """Handle update notification asynchronously."""
        ...

# Utility types for common patterns
Result = Union[T, Exception]
Maybe = Optional[T]
Either = Union[T, K]

# Type guards
def is_telegram_update(obj: Any) -> bool:
    """Type guard for Telegram Update objects."""
    return isinstance(obj, Update)

def is_callback_context(obj: Any) -> bool:
    """Type guard for CallbackContext objects."""
    return isinstance(obj, CallbackContext)

def is_message(obj: Any) -> bool:
    """Type guard for Message objects."""
    return isinstance(obj, Message)

# Literal types for specific values
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
HTTPMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
FileFormat = Literal["json", "yaml", "toml", "ini"]

# Union types for common combinations
ConfigSource = Union[str, Dict[str, Any], None]
HandlerFunction = Union[MessageHandler, CommandHandler, CallbackHandler]
ServiceInstance = Union[Service, ConfigurableService, Any]