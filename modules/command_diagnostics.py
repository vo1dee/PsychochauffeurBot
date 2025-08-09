"""
Command diagnostics utilities for applying enhanced error logging to existing commands.

This module provides utilities to retrofit existing command handlers with comprehensive
error logging, metrics tracking, and diagnostic capabilities.

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import functools
import time
from typing import Callable, Any, Dict, Optional
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from modules.enhanced_error_diagnostics import (
    enhanced_diagnostics,
    track_command_execution,
    get_user_friendly_error_message,
    log_external_service_call,
    log_database_operation
)
from modules.structured_logging import StructuredLogger, LogLevel
from modules.error_handler import ErrorHandler, StandardError, ErrorCategory, ErrorSeverity
from modules.const import KYIV_TZ


class CommandDiagnosticsWrapper:
    """
    Wrapper class for adding comprehensive diagnostics to existing command handlers.
    
    This class can be used to wrap existing command functions to add:
    - Execution time tracking
    - Error logging and analytics
    - User-friendly error messages
    - System resource monitoring
    - External service call tracking
    """
    
    def __init__(self, command_name: str, logger_name: str = "command_diagnostics"):
        self.command_name = command_name
        self.logger = StructuredLogger(logger_name)
    
    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Apply diagnostics wrapper to a command function."""
        
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
            # Extract user and chat information
            user_id = update.effective_user.id if update.effective_user else 0
            chat_id = update.effective_chat.id if update.effective_chat else 0
            username = update.effective_user.username if update.effective_user else "unknown"
            chat_type = update.effective_chat.type if update.effective_chat else "unknown"
            
            # Track command execution with comprehensive diagnostics
            async with enhanced_diagnostics.track_command_execution(
                command_name=self.command_name,
                user_id=user_id,
                chat_id=chat_id,
                username=username,
                chat_type=chat_type,
                args=context.args if context.args else [],
                message_text=update.message.text if update.message else None
            ) as metrics:
                
                try:
                    # Execute the original command function
                    result = await func(update, context, *args, **kwargs)
                    
                    # Log successful execution
                    self.logger.log_event(
                        LogLevel.INFO,
                        "command_success",
                        f"Command {self.command_name} executed successfully",
                        command_name=self.command_name,
                        user_id=user_id,
                        chat_id=chat_id,
                        duration_seconds=metrics.duration_seconds if metrics and hasattr(metrics, 'duration_seconds') else None
                    )
                    
                    return result
                    
                except Exception as e:
                    # Handle the error with comprehensive logging
                    await self._handle_command_error(e, update, context, metrics)
                    
                    # Don't re-raise the exception as we've handled it
                    return None
        
        return wrapper
    
    async def _handle_command_error(
        self,
        error: Exception,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        metrics: Any
    ) -> None:
        """Handle command errors with comprehensive logging and user feedback."""
        
        # Create detailed error context
        error_context = {
            "command_name": self.command_name,
            "user_id": update.effective_user.id if update.effective_user else 0,
            "chat_id": update.effective_chat.id if update.effective_chat else 0,
            "username": update.effective_user.username if update.effective_user else "unknown",
            "chat_type": update.effective_chat.type if update.effective_chat else "unknown",
            "args": context.args if context.args else [],
            "message_text": update.message.text if update.message else None,
            "execution_time": metrics.duration_seconds if hasattr(metrics, 'duration_seconds') else None
        }
        
        # Use the enhanced error handler
        await ErrorHandler.handle_error(
            error=error,
            update=update,
            context=context,
            context_data=error_context,
            propagate=False
        )
        
        # Send user-friendly error message
        user_message = get_user_friendly_error_message(error, self.command_name)
        
        if update.message:
            try:
                await update.message.reply_text(user_message)
            except Exception as send_error:
                # Log if we can't send the error message, but don't fail
                self.logger.log_event(
                    LogLevel.ERROR,
                    "error_message_send_failed",
                    f"Failed to send error message to user: {str(send_error)}",
                    original_error=str(error),
                    send_error=str(send_error),
                    **error_context
                )


def enhance_command_with_diagnostics(command_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator factory for enhancing existing commands with comprehensive diagnostics.
    
    Usage:
        @enhance_command_with_diagnostics("analyze")
        async def analyze_command(update, context):
            # Command implementation
            pass
    
    Args:
        command_name: Name of the command for logging and metrics
    """
    return CommandDiagnosticsWrapper(command_name)


class DatabaseOperationTracker:
    """Context manager for tracking database operations within commands."""
    
    def __init__(self, operation: str, table: Optional[str] = None):
        self.operation = operation
        self.table = table
        self.start_time: Optional[float] = None
        self.rows_affected: Optional[int] = None
    
    async def __aenter__(self) -> 'DatabaseOperationTracker':
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        duration = time.time() - (self.start_time or 0)
        
        if exc_type is None:
            # Operation succeeded
            await log_database_operation(
                operation=self.operation,
                table=self.table,
                duration=duration,
                rows_affected=self.rows_affected
            )
        else:
            # Operation failed
            await log_database_operation(
                operation=self.operation,
                table=self.table,
                duration=duration,
                error=str(exc_val)
            )
    
    def set_rows_affected(self, count: int) -> None:
        """Set the number of rows affected by the operation."""
        self.rows_affected = count


class ExternalServiceCallTracker:
    """Context manager for tracking external service API calls within commands."""
    
    def __init__(self, service_name: str, endpoint: str, method: str = "GET"):
        self.service_name = service_name
        self.endpoint = endpoint
        self.method = method
        self.start_time: Optional[float] = None
        self.status_code: Optional[int] = None
    
    async def __aenter__(self) -> 'ExternalServiceCallTracker':
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        duration = time.time() - (self.start_time or 0)
        
        if exc_type is None:
            # Call succeeded
            await log_external_service_call(
                service_name=self.service_name,
                endpoint=self.endpoint,
                method=self.method,
                status_code=self.status_code,
                duration=duration
            )
        else:
            # Call failed
            await log_external_service_call(
                service_name=self.service_name,
                endpoint=self.endpoint,
                method=self.method,
                duration=duration,
                error=str(exc_val)
            )
    
    def set_status_code(self, code: int) -> None:
        """Set the HTTP status code for the API call."""
        self.status_code = code


# Utility functions for manual instrumentation
def track_database_query(operation: str, table: Optional[str] = None) -> DatabaseOperationTracker:
    """Create a database operation tracker context manager."""
    return DatabaseOperationTracker(operation, table)


def track_api_call(service_name: str, endpoint: str, method: str = "GET") -> ExternalServiceCallTracker:
    """Create an external service call tracker context manager."""
    return ExternalServiceCallTracker(service_name, endpoint, method)


def log_command_milestone(command_name: str, milestone: str, **data: Any) -> None:
    """
    Log a milestone within command execution.
    
    Args:
        command_name: Name of the command
        milestone: Description of the milestone
        **data: Additional data to log
    """
    logger = StructuredLogger("command_milestones")
    logger.log_event(
        LogLevel.INFO,
        "command_milestone",
        f"Command {command_name} milestone: {milestone}",
        command_name=command_name,
        milestone=milestone,
        timestamp=datetime.now(KYIV_TZ).isoformat(),
        **data
    )


def log_command_performance_metric(
    command_name: str,
    metric_name: str,
    value: float,
    unit: str = "count",
    **additional_data: Any
) -> None:
    """
    Log a performance metric for a command.
    
    Args:
        command_name: Name of the command
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        **additional_data: Additional context data
    """
    logger = StructuredLogger("command_performance")
    logger.log_performance_metric(
        f"{command_name}_{metric_name}",
        value,
        unit=unit,
        command_name=command_name,
        **additional_data
    )


# Configuration diagnostics utilities
async def validate_command_configuration(command_name: str) -> Dict[str, Any]:
    """
    Validate configuration required for a specific command.
    
    Args:
        command_name: Name of the command to validate configuration for
        
    Returns:
        Dictionary with validation results
    """
    from modules.const import Config
    
    validation_result: Dict[str, Any] = {
        "command_name": command_name,
        "valid": True,
        "issues": [],
        "warnings": [],
        "timestamp": datetime.now(KYIV_TZ).isoformat()
    }
    
    try:
        # Common configuration checks
        if not Config.TELEGRAM_BOT_TOKEN:
            validation_result["valid"] = False
            validation_result["issues"].append("BOT_TOKEN is not configured")
        
        # Command-specific configuration checks
        if command_name == "analyze":
            if not Config.OPENROUTER_API_KEY:
                validation_result["valid"] = False
                validation_result["issues"].append("OPENROUTER_API_KEY required for analyze command")
            
            if not hasattr(Config, 'DATABASE_URL') or not Config.DATABASE_URL:
                validation_result["valid"] = False
                validation_result["issues"].append("DATABASE_URL required for analyze command")
        
        elif command_name == "flares":
            import subprocess
            try:
                subprocess.run(["wkhtmltoimage", "--version"], 
                             capture_output=True, timeout=5, check=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                validation_result["valid"] = False
                validation_result["issues"].append("wkhtmltoimage tool not available for flares command")
            
            if not hasattr(Config, 'SCREENSHOT_DIR') or not Config.SCREENSHOT_DIR:
                validation_result["warnings"].append("SCREENSHOT_DIR not configured, using default")
        
        # Log validation results
        logger = StructuredLogger("command_config_validation")
        log_level = LogLevel.ERROR if not validation_result["valid"] else LogLevel.INFO
        
        logger.log_event(
            log_level,
            "command_configuration_validation",
            f"Configuration validation for {command_name}: {'PASSED' if validation_result['valid'] else 'FAILED'}",
            **validation_result
        )
        
    except Exception as e:
        validation_result["valid"] = False
        validation_result["issues"].append(f"Configuration validation error: {str(e)}")
    
    return validation_result


# Health check utilities for commands
async def check_command_dependencies(command_name: str) -> Dict[str, Any]:
    """
    Check if all dependencies for a command are available and healthy.
    
    Args:
        command_name: Name of the command to check dependencies for
        
    Returns:
        Dictionary with dependency health status
    """
    health_status: Dict[str, Any] = {
        "command_name": command_name,
        "healthy": True,
        "dependencies": {},
        "timestamp": datetime.now(KYIV_TZ).isoformat()
    }
    
    try:
        # Check common dependencies
        health_status["dependencies"]["database"] = await _check_database_dependency()
        
        # Command-specific dependency checks
        if command_name == "analyze":
            health_status["dependencies"]["openrouter_api"] = await _check_openrouter_dependency()
        
        elif command_name == "flares":
            health_status["dependencies"]["meteoagent_api"] = await _check_meteoagent_dependency()
            health_status["dependencies"]["wkhtmltoimage"] = await _check_wkhtmltoimage_dependency()
        
        # Determine overall health
        health_status["healthy"] = all(
            dep.get("healthy", False) for dep in health_status["dependencies"].values()
        )
        
    except Exception as e:
        health_status["healthy"] = False
        health_status["error"] = str(e)
    
    return health_status


async def _check_database_dependency() -> Dict[str, Any]:
    """Check database dependency health."""
    try:
        from modules.database import Database
        is_healthy = await Database.health_check()
        return {
            "healthy": is_healthy,
            "service": "database",
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "service": "database",
            "error": str(e),
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }


async def _check_openrouter_dependency() -> Dict[str, Any]:
    """Check OpenRouter API dependency health."""
    try:
        import aiohttp
        from modules.const import Config
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{Config.OPENROUTER_BASE_URL}/models") as response:
                healthy = response.status == 200
                return {
                    "healthy": healthy,
                    "service": "openrouter_api",
                    "status_code": response.status,
                    "last_check": datetime.now(KYIV_TZ).isoformat()
                }
    except Exception as e:
        return {
            "healthy": False,
            "service": "openrouter_api",
            "error": str(e),
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }


async def _check_meteoagent_dependency() -> Dict[str, Any]:
    """Check MeteoAgent API dependency health."""
    try:
        import aiohttp
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("https://api.meteoagent.com") as response:
                healthy = response.status < 500
                return {
                    "healthy": healthy,
                    "service": "meteoagent_api",
                    "status_code": response.status,
                    "last_check": datetime.now(KYIV_TZ).isoformat()
                }
    except Exception as e:
        return {
            "healthy": False,
            "service": "meteoagent_api",
            "error": str(e),
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }


async def _check_wkhtmltoimage_dependency() -> Dict[str, Any]:
    """Check wkhtmltoimage tool dependency health."""
    try:
        import subprocess
        
        result = subprocess.run(
            ["wkhtmltoimage", "--version"],
            capture_output=True,
            timeout=5,
            text=True
        )
        
        return {
            "healthy": result.returncode == 0,
            "service": "wkhtmltoimage",
            "version": result.stdout.strip() if result.returncode == 0 else None,
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "service": "wkhtmltoimage",
            "error": str(e),
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }