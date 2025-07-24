"""
Shared utilities and common functionality to reduce code duplication.

This module contains reusable components, base classes, and utility functions
that are used across multiple modules in the application.
"""

import asyncio
import hashlib
import logging
import re
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import wraps
from typing import (
    Any, Dict, List, Optional, Callable, Awaitable, TypeVar, Generic,
    Union, Tuple, Set, AsyncGenerator
)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from modules.types import (
    UserId, ChatId, MessageId, Timestamp, JSONDict, ConfigDict,
    ErrorSeverity, ErrorCategory, MessageHandler, CommandHandler,
    PerformanceMetric, CacheEntry, ValidationResult
)

# Type variables
T = TypeVar('T')
R = TypeVar('R')

logger = logging.getLogger(__name__)


class SingletonMeta(type):
    """Metaclass for implementing singleton pattern."""
    _instances: Dict[type, Any] = {}
    
    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class BaseService(ABC):
    """Base class for all services with common functionality."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._initialized = False
        self._running = False
        self._start_time: Optional[datetime] = None
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the service."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the service."""
        pass
    
    async def health_check(self) -> bool:
        """Check service health."""
        return self._initialized and self._running
    
    def get_uptime(self) -> Optional[timedelta]:
        """Get service uptime."""
        if self._start_time:
            return datetime.now() - self._start_time
        return None
    
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
    
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running


class AsyncContextManager(Generic[T]):
    """Base class for async context managers."""
    
    async def __aenter__(self) -> 'AsyncContextManager[T]':
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Any) -> None:
        await self.cleanup()
    
    @abstractmethod
    async def setup(self) -> None:
        """Setup resources."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources."""
        pass


class RateLimiter:
    """Rate limiter for controlling request frequency."""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for the given key."""
        now = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the time window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < self.time_window
        ]
        
        # Check if under the limit
        if len(self.requests[key]) < self.max_requests:
            self.requests[key].append(now)
            return True
        
        return False
    
    def get_reset_time(self, key: str) -> Optional[float]:
        """Get time until rate limit resets for the key."""
        if key not in self.requests or not self.requests[key]:
            return None
        
        oldest_request = min(self.requests[key])
        return oldest_request + self.time_window - time.time()


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
    
    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker is open")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful execution."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self) -> None:
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class RetryManager:
    """Manages retry logic with exponential backoff."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any
    ) -> T:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
        
        if last_exception is None:
            raise RuntimeError("Retry failed but no exception was captured")
        raise last_exception


class CacheManager(Generic[T]):
    """Generic cache manager with TTL support."""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if entry.expires_at and datetime.now() > entry.expires_at:
            del self._cache[key]
            return None
        
        # Update access info
        entry.access_count += 1
        entry.last_accessed = datetime.now()
        
        # Type annotation to ensure proper return type
        value: T = entry.value
        return value
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
        
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            expires_at=expires_at
        )
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.expires_at and now > entry.expires_at
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)


class ValidationMixin:
    """Mixin class providing common validation methods."""
    
    @staticmethod
    def validate_user_id(user_id: Any) -> ValidationResult:
        """Validate user ID."""
        if not isinstance(user_id, int) or user_id <= 0:
            return False, "Invalid user ID"
        return True, None
    
    @staticmethod
    def validate_chat_id(chat_id: Any) -> ValidationResult:
        """Validate chat ID."""
        if not isinstance(chat_id, int):
            return False, "Invalid chat ID"
        return True, None
    
    @staticmethod
    def validate_text_length(text: Any, max_length: int = 4096) -> ValidationResult:
        """Validate text length."""
        # Change parameter type to Any to avoid mypy confusion
        if not isinstance(text, str):
            return (False, "Text must be a string")
        
        if len(text) > max_length:
            return (False, f"Text too long (max {max_length} characters)")
        return (True, None)
    
    @staticmethod
    def validate_url(url: str) -> ValidationResult:
        """Validate URL format."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            return False, "Invalid URL format"
        return True, None


class TextProcessor:
    """Utility class for text processing operations."""
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text."""
        url_pattern = r'http[s]?://(?:[a-zA-Z0-9]|[\$\-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    @staticmethod
    def remove_urls(text: str) -> str:
        """Remove URLs from text."""
        url_pattern = r'http[s]?://\S+'
        return re.sub(url_pattern, '', text).strip()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe file system usage."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_length] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to specified length with suffix."""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape markdown special characters."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        escaped_text = text
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        return escaped_text


class HashGenerator:
    """Utility class for generating various types of hashes."""
    
    @staticmethod
    def md5_hash(data: str) -> str:
        """Generate MD5 hash."""
        return hashlib.md5(data.encode()).hexdigest()
    
    @staticmethod
    def sha256_hash(data: str) -> str:
        """Generate SHA256 hash."""
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def short_hash(data: str, length: int = 8) -> str:
        """Generate short hash for IDs."""
        return hashlib.md5(data.encode()).hexdigest()[:length]
    
    @staticmethod
    def file_id_hash(file_id: str, length: int = 16) -> str:
        """Generate hash for file IDs."""
        return hashlib.md5(file_id.encode()).hexdigest()[:length]


class TelegramHelpers:
    """Helper functions for Telegram-specific operations."""
    
    @staticmethod
    def create_inline_keyboard(
        buttons: List[List[Tuple[str, str]]]
    ) -> InlineKeyboardMarkup:
        """Create inline keyboard from button data."""
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for text, callback_data in row:
                keyboard_row.append(InlineKeyboardButton(text, callback_data=callback_data))
            keyboard.append(keyboard_row)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def extract_user_info(update: Update) -> Optional[Dict[str, Any]]:
        """Extract user information from update."""
        if not update.effective_user:
            return None
        
        user = update.effective_user
        return {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'language_code': user.language_code,
            'is_bot': user.is_bot
        }
    
    @staticmethod
    def extract_chat_info(update: Update) -> Optional[Dict[str, Any]]:
        """Extract chat information from update."""
        if not update.effective_chat:
            return None
        
        chat = update.effective_chat
        return {
            'id': chat.id,
            'type': chat.type,
            'title': chat.title,
            'username': chat.username,
            'description': getattr(chat, 'description', None)
        }
    
    @staticmethod
    def is_private_chat(update: Update) -> bool:
        """Check if update is from private chat."""
        return bool(update.effective_chat and update.effective_chat.type == "private")
    
    @staticmethod
    def is_group_chat(update: Update) -> bool:
        """Check if update is from group chat."""
        return bool(update.effective_chat and 
                update.effective_chat.type in ["group", "supergroup"])


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self) -> None:
        self.metrics: List[PerformanceMetric] = []
    
    @asynccontextmanager
    async def measure_time(self, operation_name: str) -> AsyncGenerator[None, None]:
        """Context manager to measure execution time."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_metric(
                name=f"{operation_name}_duration",
                value=duration,
                unit="seconds"
            )
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        self.metrics.append(metric)
    
    def get_metrics(
        self,
        name_filter: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[PerformanceMetric]:
        """Get metrics with optional filtering."""
        filtered_metrics = self.metrics
        
        if name_filter:
            filtered_metrics = [m for m in filtered_metrics if name_filter in m.name]
        
        if since:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= since]
        
        return filtered_metrics
    
    def clear_metrics(self) -> None:
        """Clear all recorded metrics."""
        self.metrics.clear()


# Decorator utilities
def async_retry(max_retries: int = 3, delay: float = 1.0) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for async functions with retry logic."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            retry_manager = RetryManager(max_retries=max_retries, base_delay=delay)
            return await retry_manager.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def measure_performance(operation_name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to measure function performance."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                logger.info(f"{operation_name} completed in {duration:.3f}s")
        return wrapper
    return decorator


def rate_limit(max_requests: int, time_window: int) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for rate limiting function calls."""
    limiter = RateLimiter(max_requests, time_window)
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Use function name as key, could be enhanced to use user ID
            key = func.__name__
            
            if not limiter.is_allowed(key):
                reset_time = limiter.get_reset_time(key)
                raise Exception(f"Rate limit exceeded. Try again in {reset_time:.1f}s")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Global instances for common use
# Type-annotated to avoid untyped call warning
performance_monitor: PerformanceMonitor = PerformanceMonitor()
text_processor = TextProcessor()
hash_generator = HashGenerator()
telegram_helpers = TelegramHelpers()