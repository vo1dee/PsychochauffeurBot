"""
Enhanced error handling decorators for consistent error management across the application.
"""

import functools
import asyncio
from typing import Optional, Callable, Any, Dict, Type, Union, List
from datetime import datetime

from telegram import Update
from telegram.ext import CallbackContext

from modules.error_handler import ErrorHandler, StandardError, ErrorSeverity, ErrorCategory
from modules.logger import error_logger


class ErrorHandlingConfig:
    """Configuration for error handling decorators."""
    
    def __init__(
        self,
        feedback_message: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.GENERAL,
        retry_count: int = 0,
        retry_delay: float = 1.0,
        fallback_response: Optional[str] = None,
        log_level: str = "error",
        suppress_errors: bool = False,
        error_stickers: Optional[List[str]] = None
    ):
        self.feedback_message = feedback_message
        self.severity = severity
        self.category = category
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.fallback_response = fallback_response
        self.log_level = log_level
        self.suppress_errors = suppress_errors
        self.error_stickers = error_stickers or []


def handle_command_errors(
    feedback_message: Optional[str] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.GENERAL,
    retry_count: int = 0,
    fallback_response: Optional[str] = None
):
    """
    Decorator for handling errors in command handlers.
    
    Args:
        feedback_message: Custom message to send to the user on error
        severity: Error severity level
        category: Error category
        retry_count: Number of retry attempts
        fallback_response: Fallback response if all retries fail
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract update and context from arguments
            update = next((arg for arg in args if isinstance(arg, Update)), None)
            context = next((arg for arg in args if isinstance(arg, CallbackContext)), None)
            
            last_exception = None
            
            # Retry logic
            for attempt in range(retry_count + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < retry_count:
                        error_logger.warning(
                            f"Command {func.__name__} failed (attempt {attempt + 1}/{retry_count + 1}): {e}"
                        )
                        await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
                        continue
                    
                    # All retries failed, handle the error
                    context_data = {
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "retry_count": retry_count
                    }
                    
                    await ErrorHandler.handle_error(
                        error=e,
                        update=update,
                        context=context,
                        feedback_message=feedback_message or fallback_response,
                        context_data=context_data
                    )
                    
                    return None
            
        return wrapper
    return decorator


def handle_service_errors(
    service_name: str,
    fallback_value: Any = None,
    log_errors: bool = True,
    raise_on_critical: bool = True
):
    """
    Decorator for handling errors in service methods.
    
    Args:
        service_name: Name of the service for logging
        fallback_value: Value to return on error
        log_errors: Whether to log errors
        raise_on_critical: Whether to re-raise critical errors
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Determine if this is a critical error
                is_critical = isinstance(e, (
                    ConnectionError,
                    TimeoutError,
                    PermissionError
                ))
                
                if log_errors:
                    severity = ErrorSeverity.CRITICAL if is_critical else ErrorSeverity.MEDIUM
                    std_error = StandardError(
                        message=f"Service {service_name} error in {func.__name__}: {str(e)}",
                        severity=severity,
                        category=ErrorCategory.API,
                        context={
                            "service": service_name,
                            "function": func.__name__,
                            "args": str(args)[:100],  # Limit length
                            "kwargs": str(kwargs)[:100]
                        },
                        original_exception=e
                    )
                    
                    error_logger.error(str(std_error))
                
                # Re-raise critical errors if configured
                if is_critical and raise_on_critical:
                    raise
                
                return fallback_value
        
        return wrapper
    return decorator


def handle_database_errors(
    operation: str,
    fallback_value: Any = None,
    retry_count: int = 2
):
    """
    Decorator for handling database operation errors.
    
    Args:
        operation: Description of the database operation
        fallback_value: Value to return on error
        retry_count: Number of retry attempts for transient errors
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_count + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is a transient error worth retrying
                    is_transient = isinstance(e, (
                        ConnectionError,
                        TimeoutError,
                        asyncio.TimeoutError
                    ))
                    
                    if is_transient and attempt < retry_count:
                        error_logger.warning(
                            f"Database {operation} failed (attempt {attempt + 1}), retrying: {e}"
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    
                    # Log the error
                    std_error = StandardError(
                        message=f"Database {operation} failed: {str(e)}",
                        severity=ErrorSeverity.HIGH,
                        category=ErrorCategory.DATABASE,
                        context={
                            "operation": operation,
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "retry_count": retry_count
                        },
                        original_exception=e
                    )
                    
                    error_logger.error(str(std_error))
                    
                    # Track the error for analytics
                    from modules.error_analytics import track_error
                    try:
                        track_error(std_error)
                    except Exception:
                        pass  # Don't let error tracking break the flow
                    
                    return fallback_value
            
        return wrapper
    return decorator


def handle_network_errors(
    service: str,
    timeout: float = 30.0,
    retry_count: int = 3,
    fallback_value: Any = None
):
    """
    Decorator for handling network/API errors.
    
    Args:
        service: Name of the external service
        timeout: Request timeout in seconds
        retry_count: Number of retry attempts
        fallback_value: Value to return on error
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_count + 1):
                try:
                    # Apply timeout to the function call
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
                    last_exception = e
                    
                    if attempt < retry_count:
                        delay = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                        error_logger.warning(
                            f"{service} request failed (attempt {attempt + 1}), "
                            f"retrying in {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                        continue
                    
                    # All retries failed
                    std_error = StandardError(
                        message=f"{service} service unavailable: {str(e)}",
                        severity=ErrorSeverity.HIGH,
                        category=ErrorCategory.NETWORK,
                        context={
                            "service": service,
                            "function": func.__name__,
                            "timeout": timeout,
                            "retry_count": retry_count,
                            "final_attempt": attempt + 1
                        },
                        original_exception=e
                    )
                    
                    error_logger.error(str(std_error))
                    return fallback_value
                
                except Exception as e:
                    # Non-network error, don't retry
                    std_error = StandardError(
                        message=f"{service} service error: {str(e)}",
                        severity=ErrorSeverity.MEDIUM,
                        category=ErrorCategory.API,
                        context={
                            "service": service,
                            "function": func.__name__
                        },
                        original_exception=e
                    )
                    
                    error_logger.error(str(std_error))
                    return fallback_value
            
        return wrapper
    return decorator


def handle_validation_errors(
    input_name: str,
    default_value: Any = None,
    log_invalid_input: bool = True
):
    """
    Decorator for handling input validation errors.
    
    Args:
        input_name: Name of the input being validated
        default_value: Default value to return on validation error
        log_invalid_input: Whether to log invalid input attempts
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except (ValueError, TypeError, KeyError) as e:
                if log_invalid_input:
                    std_error = StandardError(
                        message=f"Invalid {input_name}: {str(e)}",
                        severity=ErrorSeverity.LOW,
                        category=ErrorCategory.INPUT,
                        context={
                            "input_name": input_name,
                            "function": func.__name__,
                            "args": str(args)[:200],
                            "kwargs": str(kwargs)[:200]
                        },
                        original_exception=e
                    )
                    
                    error_logger.warning(str(std_error))
                
                return default_value
            
        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
):
    """
    Circuit breaker decorator to prevent cascade failures.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time to wait before attempting recovery
        expected_exception: Exception type that triggers the circuit breaker
    """
    def decorator(func):
        # Circuit breaker state
        func._failure_count = 0
        func._last_failure_time = None
        func._circuit_open = False
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            now = datetime.now()
            
            # Check if circuit is open and recovery timeout has passed
            if func._circuit_open:
                if (func._last_failure_time and 
                    (now - func._last_failure_time).total_seconds() > recovery_timeout):
                    func._circuit_open = False
                    func._failure_count = 0
                    error_logger.info(f"Circuit breaker for {func.__name__} attempting recovery")
                else:
                    error_logger.warning(f"Circuit breaker for {func.__name__} is open")
                    raise StandardError(
                        message=f"Circuit breaker is open for {func.__name__}",
                        severity=ErrorSeverity.HIGH,
                        category=ErrorCategory.GENERAL,
                        context={
                            "function": func.__name__,
                            "failure_count": func._failure_count,
                            "last_failure": func._last_failure_time.isoformat() if func._last_failure_time else None
                        }
                    )
            
            try:
                result = await func(*args, **kwargs)
                # Success - reset failure count
                if func._failure_count > 0:
                    func._failure_count = 0
                    error_logger.info(f"Circuit breaker for {func.__name__} reset after success")
                return result
                
            except expected_exception as e:
                func._failure_count += 1
                func._last_failure_time = now
                
                if func._failure_count >= failure_threshold:
                    func._circuit_open = True
                    error_logger.error(
                        f"Circuit breaker for {func.__name__} opened after "
                        f"{func._failure_count} failures"
                    )
                
                raise e
        
        return wrapper
    return decorator


# Convenience decorators for common scenarios

def telegram_command(
    feedback_message: str = "An error occurred while processing your command.",
    fallback_response: Optional[str] = None
):
    """Convenience decorator for Telegram command handlers."""
    return handle_command_errors(
        feedback_message=feedback_message,
        severity=ErrorSeverity.MEDIUM,
        category=ErrorCategory.GENERAL,
        fallback_response=fallback_response
    )


def external_api(service_name: str, timeout: float = 30.0):
    """Convenience decorator for external API calls."""
    return handle_network_errors(
        service=service_name,
        timeout=timeout,
        retry_count=3,
        fallback_value=None
    )


def database_operation(operation_name: str):
    """Convenience decorator for database operations."""
    return handle_database_errors(
        operation=operation_name,
        fallback_value=None,
        retry_count=2
    )


def user_input_validation(input_type: str):
    """Convenience decorator for user input validation."""
    return handle_validation_errors(
        input_name=input_type,
        default_value=None,
        log_invalid_input=True
    )