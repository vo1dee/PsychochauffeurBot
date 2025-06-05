import asyncio
import traceback
from enum import Enum
from typing import Dict, Optional, Any, Type, Callable, Awaitable, Union, List
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes
from modules.logger import error_logger
import functools

# Timezone constants
KYIV_TZ = pytz.timezone("Europe/Kyiv")


class ErrorSeverity(Enum):
    """Error severity levels for categorizing errors"""

    LOW = "low"  # Minor issues that don't affect functionality
    MEDIUM = "medium"  # Significant issues that degrade some functionality
    HIGH = "high"  # Critical issues that break core functionality
    CRITICAL = "critical"  # Fatal errors that require immediate attention


class ErrorCategory(Enum):
    """Categories for classifying different types of errors"""

    NETWORK = "network"  # Network/connection issues
    API = "api"  # External API errors
    DATABASE = "database"  # Database errors
    PARSING = "parsing"  # Data parsing/formatting issues
    INPUT = "input"  # User input validation errors
    PERMISSION = "permission"  # Authorization/permission errors
    RESOURCE = "resource"  # Resource (file/memory) errors
    GENERAL = "general"  # Uncategorized errors


class StandardError(Exception):
    """
    Standard error class for consistent handling across the application.

    Attributes:
        message: Primary error message
        severity: Error severity level
        category: Error category
        context: Additional contextual information
        original_exception: The original exception that was caught
    """

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.GENERAL,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        self.message = message
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.original_exception = original_exception
        self.timestamp = datetime.now(KYIV_TZ)

        # Format the error message for the parent Exception
        formatted_message = f"{message}"
        if original_exception:
            formatted_message += f" | Original error: {str(original_exception)[:50]}"

        super().__init__(formatted_message)

    def __str__(self):
        """String representation of the error"""
        base = f"[{self.severity.value.upper()}] {self.category.value}: {self.message}"
        if self.original_exception:
            exc_name = type(self.original_exception).__name__
            exc_msg = str(self.original_exception)
            base += f" (Caused by: {exc_name}: {exc_msg})"
        return base

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging or serialization"""
        result = {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }

        if self.original_exception:
            result["original_exception"] = {
                "type": type(self.original_exception).__name__,
                "message": str(self.original_exception),
                "traceback": traceback.format_exc(),
            }

        return result


class ErrorHandler:
    """
    Central error handler for managing error processing, logging, and responses.

    This class provides methods for handling different types of errors consistently
    across the application, with appropriate logging and user feedback.
    """

    # Mapping from Python exception types to our error categories
    DEFAULT_EXCEPTION_MAPPING: Dict[Type[Exception], ErrorCategory] = {
        ConnectionError: ErrorCategory.NETWORK,
        TimeoutError: ErrorCategory.NETWORK,
        asyncio.TimeoutError: ErrorCategory.NETWORK,
        PermissionError: ErrorCategory.PERMISSION,
        FileNotFoundError: ErrorCategory.RESOURCE,
        KeyError: ErrorCategory.PARSING,
        ValueError: ErrorCategory.INPUT,
        TypeError: ErrorCategory.PARSING,
    }

    @staticmethod
    def format_error_message(
        error: Union[StandardError, Exception],
        update: Optional[Update] = None,
        prefix: Optional[str] = None,
    ) -> str:
        """
        Format an error message with consistent structure and emoji for logging.

        Args:
            error: The error to format
            update: Optional Telegram update object for context
            prefix: Optional prefix emoji/text

        Returns:
            Formatted error message string
        """
        # Determine emoji based on error type/severity
        emoji = "⚠️"  # Default warning emoji
        if isinstance(error, StandardError):
            if error.severity == ErrorSeverity.HIGH:
                emoji = "🚨"  # Alert emoji for high severity
            elif error.severity == ErrorSeverity.CRITICAL:
                emoji = "💥"  # Explosion emoji for critical errors
            elif error.severity == ErrorSeverity.LOW:
                emoji = "ℹ️"  # Info emoji for low severity

        # Override with custom prefix if provided
        if prefix:
            emoji = prefix

        # Build the message
        parts = [f"{emoji} Error"]

        # Add error details
        if isinstance(error, StandardError):
            parts.append(f"Type: {error.category.value}")
            parts.append(f"Severity: {error.severity.value}")
            parts.append(f"Message: {error.message}")

            # Include context from StandardError
            if error.context:
                for key, value in error.context.items():
                    parts.append(f"{key}: {value}")
        else:
            parts.append(f"Type: {type(error).__name__}")
            parts.append(f"Message: {str(error)}")

        # Add traceback for debugging
        tb = traceback.format_exc()
        if tb and tb != "NoneType: None\n":
            parts.append(f"Traceback: {tb}")

        # Add user and chat context if a valid Update object is available
        if isinstance(update, Update):
            if update.effective_user:
                parts.append(f"User ID: {update.effective_user.id}")
                parts.append(f"Username: @{update.effective_user.username or 'unknown'}")

            if update.effective_chat:
                parts.append(f"Chat ID: {update.effective_chat.id}")
                if update.effective_chat.title:
                    parts.append(f"Chat Title: {update.effective_chat.title}")

        # Join all parts with newlines
        return "\n".join(parts)

    @staticmethod
    async def handle_error(
        error: Exception,
        update: Optional[Update] = None,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
        feedback_message: Optional[str] = None,
        user_feedback_fn: Optional[Callable[[Update, str], Awaitable[None]]] = None,
        context_data: Optional[Dict[str, Any]] = None,
        propagate: bool = False,
    ) -> Optional[StandardError]:
        """Handle an exception with consistent logging and user feedback.

        Args:
            error: The exception to handle
            update: Optional Telegram update for context
            context: Optional callback context
            feedback_message: Custom message to send to the user
            user_feedback_fn: Custom function to handle user feedback
            context_data: Additional context data to include with the error
            propagate: Whether to re-raise the exception after handling

        Returns:
            StandardError: The standardized error object

        Raises:
            Exception: The original exception if propagate is True
        """
        # Import error analytics (imported here to avoid circular imports)
        from modules.error_analytics import track_error

        # Convert to StandardError if it's not already
        if not isinstance(error, StandardError):
            # Determine error category based on exception type
            category = ErrorHandler.DEFAULT_EXCEPTION_MAPPING.get(
                type(error), ErrorCategory.GENERAL
            )

            # Create base context
            base_context = {
                "update_id": update.update_id if update and hasattr(update, 'update_id') else None,
                "chat_id": (
                    update.effective_chat.id
                    if update and hasattr(update, 'effective_chat')
                    else None
                ),
                "user_id": (
                    update.effective_user.id
                    if update and hasattr(update, 'effective_user')
                    else None
                ),
            }

            # Merge with additional context if provided
            if context_data:
                base_context.update(context_data)

            # Create standardized error
            std_error = StandardError(
                message=str(error),
                category=category,
                context=base_context,
                original_exception=error,
            )
        else:
            std_error = error

        # Log the error
        error_message = ErrorHandler.format_error_message(std_error, update)
        error_logger.error(error_message)

        # Track the error for analytics
        try:
            track_error(std_error)
        except Exception as e:
            error_logger.error(f"Failed to track error for analytics: {e}")

        # Provide user feedback if requested
        if update and hasattr(update, 'effective_message') and update.effective_message:
            if user_feedback_fn:
                try:
                    # Use custom feedback function if provided
                    await user_feedback_fn(update, str(std_error))
                except Exception as e:
                    error_logger.error(f"Error in feedback function: {e}")
            elif feedback_message:
                try:
                    # Send custom feedback message
                    await update.effective_message.reply_text(feedback_message)
                except Exception as e:
                    error_logger.error(f"Error sending feedback message: {e}")

        # Re-raise if requested
        if propagate:
            raise error

        return std_error

    @staticmethod
    def create_error(
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.GENERAL,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ) -> StandardError:
        """
        Create a new StandardError instance.

        Args:
            message: Error message
            severity: Error severity level
            category: Error category
            context: Additional contextual information
            original_exception: Original exception if wrapping

        Returns:
            StandardError: The newly created error object
        """
        return StandardError(
            message=message,
            severity=severity,
            category=category,
            context=context,
            original_exception=original_exception,
        )


# Common error handling decorators


def handle_errors(feedback_message: Optional[str] = None):
    """
    Decorator for handling errors in async functions.
    
    Args:
        feedback_message: Optional message to send to the user on error
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Get the update and context objects
                update = next((arg for arg in args if isinstance(arg, Update)), None)
                # Fix: Use the actual imported class instead of subscripted generic
                from telegram.ext import CallbackContext
                context = next((arg for arg in args if isinstance(arg, CallbackContext)), None)
                
                # Handle the error
                await ErrorHandler.handle_error(
                    error=e,
                    update=update,
                    context=context,
                    feedback_message=feedback_message
                )
                return None
        return wrapper
    return decorator


# Helper to send error stickers or messages


async def send_error_feedback(
    update: Update, stickers: Optional[List[str]] = None, message: Optional[str] = None
) -> None:
    """Send error feedback to the user with either a sticker or message.

    Args:
        update: Telegram update object
        stickers: List of sticker IDs to choose from randomly
        message: Text message to send if stickers unavailable
    """
    if not update or not update.effective_message:
        return

    try:
        if stickers:
            import random

            sticker_id = random.choice(stickers)
            await update.effective_message.reply_sticker(sticker=sticker_id)
        elif message:
            await update.effective_message.reply_text(message)
    except Exception as e:
        error_logger.error(f"Failed to send error feedback: {e}")
