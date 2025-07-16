"""
Structured logging utilities for consistent logging across the application.
"""

import logging
import json
from typing import Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum
import traceback
import sys
from pathlib import Path

from modules.const import KYIV_TZ


class LogLevel(Enum):
    """Standard log levels with consistent naming."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogContext:
    """Context manager for structured logging with consistent fields."""
    
    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        **context_fields
    ):
        self.logger = logger
        self.operation = operation
        self.context_fields = context_fields
        self.start_time = None
        self.success = True
        self.error_info = None
    
    def __enter__(self):
        self.start_time = datetime.now(KYIV_TZ)
        self._log_operation_start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.success = False
            self.error_info = {
                "error_type": exc_type.__name__,
                "error_message": str(exc_val),
                "traceback": traceback.format_exc()
            }
        
        self._log_operation_end()
        return False  # Don't suppress exceptions
    
    def _log_operation_start(self):
        """Log the start of an operation."""
        log_data = {
            "event": "operation_start",
            "operation": self.operation,
            "timestamp": self.start_time.isoformat(),
            **self.context_fields
        }
        
        self.logger.info(
            f"Starting operation: {self.operation}",
            extra={"structured_data": log_data}
        )
    
    def _log_operation_end(self):
        """Log the end of an operation."""
        end_time = datetime.now(KYIV_TZ)
        duration = (end_time - self.start_time).total_seconds()
        
        log_data = {
            "event": "operation_end",
            "operation": self.operation,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "success": self.success,
            **self.context_fields
        }
        
        if self.error_info:
            log_data["error"] = self.error_info
        
        if self.success:
            self.logger.info(
                f"Completed operation: {self.operation} ({duration:.3f}s)",
                extra={"structured_data": log_data}
            )
        else:
            self.logger.error(
                f"Failed operation: {self.operation} ({duration:.3f}s)",
                extra={"structured_data": log_data}
            )
    
    def add_context(self, **fields):
        """Add additional context fields."""
        self.context_fields.update(fields)
    
    def log_milestone(self, milestone: str, **data):
        """Log a milestone within the operation."""
        log_data = {
            "event": "operation_milestone",
            "operation": self.operation,
            "milestone": milestone,
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            **self.context_fields,
            **data
        }
        
        self.logger.info(
            f"Operation milestone: {self.operation} - {milestone}",
            extra={"structured_data": log_data}
        )


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""
    
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(name)
        self.name = name
    
    def operation_context(self, operation: str, **context) -> LogContext:
        """Create a context manager for logging operations."""
        return LogContext(self.logger, operation, **context)
    
    def log_event(
        self,
        level: Union[LogLevel, str],
        event: str,
        message: str,
        **data
    ):
        """Log a structured event."""
        log_data = {
            "event": event,
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            **data
        }
        
        level_value = level.value if isinstance(level, LogLevel) else level
        log_method = getattr(self.logger, level_value.lower())
        
        log_method(
            message,
            extra={"structured_data": log_data}
        )
    
    def log_user_action(
        self,
        user_id: int,
        username: Optional[str],
        action: str,
        chat_id: Optional[int] = None,
        chat_type: Optional[str] = None,
        **additional_data
    ):
        """Log user actions with consistent structure."""
        self.log_event(
            LogLevel.INFO,
            "user_action",
            f"User {username or user_id} performed action: {action}",
            user_id=user_id,
            username=username,
            action=action,
            chat_id=chat_id,
            chat_type=chat_type,
            **additional_data
        )
    
    def log_api_call(
        self,
        service: str,
        endpoint: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        duration: Optional[float] = None,
        **additional_data
    ):
        """Log API calls with consistent structure."""
        level = LogLevel.INFO if status_code and status_code < 400 else LogLevel.WARNING
        
        self.log_event(
            level,
            "api_call",
            f"API call to {service}: {method} {endpoint}",
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_seconds=duration,
            **additional_data
        )
    
    def log_database_operation(
        self,
        operation: str,
        table: Optional[str] = None,
        duration: Optional[float] = None,
        rows_affected: Optional[int] = None,
        **additional_data
    ):
        """Log database operations with consistent structure."""
        self.log_event(
            LogLevel.INFO,
            "database_operation",
            f"Database operation: {operation}",
            operation=operation,
            table=table,
            duration_seconds=duration,
            rows_affected=rows_affected,
            **additional_data
        )
    
    def log_performance_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        unit: str = "count",
        **additional_data
    ):
        """Log performance metrics."""
        self.log_event(
            LogLevel.INFO,
            "performance_metric",
            f"Performance metric: {metric_name} = {value} {unit}",
            metric_name=metric_name,
            value=value,
            unit=unit,
            **additional_data
        )
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        **additional_data
    ):
        """Log security events."""
        level = LogLevel.WARNING if severity in ["medium", "high"] else LogLevel.CRITICAL
        
        self.log_event(
            level,
            "security_event",
            f"Security event: {event_type}",
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            **additional_data
        )


class StructuredFormatter(logging.Formatter):
    """Formatter that handles structured logging data."""
    
    def __init__(self, include_structured_data: bool = True):
        super().__init__()
        self.include_structured_data = include_structured_data
    
    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp
        dt = datetime.fromtimestamp(record.created, KYIV_TZ)
        timestamp = dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' ' + dt.strftime('%z')
        
        # Basic log format
        log_parts = [
            timestamp,
            record.levelname,
            record.name,
            record.getMessage()
        ]
        
        # Add structured data if present
        if self.include_structured_data and hasattr(record, 'structured_data'):
            structured_data = record.structured_data
            if isinstance(structured_data, dict):
                # Convert to JSON string
                json_data = json.dumps(structured_data, default=str, separators=(',', ':'))
                log_parts.append(f"DATA:{json_data}")
        
        # Add exception info if present
        if record.exc_info:
            log_parts.append(self.formatException(record.exc_info))
        
        return " | ".join(log_parts)


class JSONFormatter(logging.Formatter):
    """Formatter that outputs logs as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, KYIV_TZ)
        
        log_entry = {
            "timestamp": dt.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add structured data if present
        if hasattr(record, 'structured_data'):
            log_entry["data"] = record.structured_data
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add chat context if present
        for attr in ['chat_id', 'chat_type', 'chattitle', 'username']:
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))


class LoggingConfigManager:
    """Manager for logging configuration."""
    
    def __init__(self):
        self.config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structured": {
                    "()": StructuredFormatter,
                    "include_structured_data": True
                },
                "json": {
                    "()": JSONFormatter
                }
            },
            "handlers": {},
            "loggers": {},
            "root": {
                "level": "INFO",
                "handlers": []
            }
        }
    
    def add_console_handler(
        self,
        name: str = "console",
        level: str = "INFO",
        formatter: str = "structured"
    ):
        """Add a console handler."""
        self.config["handlers"][name] = {
            "class": "logging.StreamHandler",
            "level": level,
            "formatter": formatter,
            "stream": "ext://sys.stdout"
        }
    
    def add_file_handler(
        self,
        name: str,
        filename: str,
        level: str = "INFO",
        formatter: str = "structured",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5
    ):
        """Add a rotating file handler."""
        self.config["handlers"][name] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": formatter,
            "filename": filename,
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8"
        }
    
    def add_logger(
        self,
        name: str,
        level: str = "INFO",
        handlers: Optional[list] = None,
        propagate: bool = False
    ):
        """Add a logger configuration."""
        self.config["loggers"][name] = {
            "level": level,
            "handlers": handlers or [],
            "propagate": propagate
        }
    
    def apply_config(self):
        """Apply the logging configuration."""
        import logging.config
        logging.config.dictConfig(self.config)


# Global structured loggers
def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


# Convenience functions
def log_user_action(
    logger_name: str,
    user_id: int,
    username: Optional[str],
    action: str,
    **kwargs
):
    """Convenience function for logging user actions."""
    logger = get_structured_logger(logger_name)
    logger.log_user_action(user_id, username, action, **kwargs)


def log_api_call(
    logger_name: str,
    service: str,
    endpoint: str,
    **kwargs
):
    """Convenience function for logging API calls."""
    logger = get_structured_logger(logger_name)
    logger.log_api_call(service, endpoint, **kwargs)


def log_performance_metric(
    logger_name: str,
    metric_name: str,
    value: Union[int, float],
    **kwargs
):
    """Convenience function for logging performance metrics."""
    logger = get_structured_logger(logger_name)
    logger.log_performance_metric(metric_name, value, **kwargs)


# Context managers for common operations
class DatabaseOperationLogger:
    """Context manager for logging database operations."""
    
    def __init__(self, logger_name: str, operation: str, table: Optional[str] = None):
        self.logger = get_structured_logger(logger_name)
        self.operation = operation
        self.table = table
        self.start_time = None
        self.rows_affected = None
    
    def __enter__(self):
        self.start_time = datetime.now(KYIV_TZ)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now(KYIV_TZ) - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.log_database_operation(
                self.operation,
                table=self.table,
                duration=duration,
                rows_affected=self.rows_affected
            )
        else:
            self.logger.log_event(
                LogLevel.ERROR,
                "database_error",
                f"Database operation failed: {self.operation}",
                operation=self.operation,
                table=self.table,
                duration=duration,
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )
        
        return False
    
    def set_rows_affected(self, count: int):
        """Set the number of rows affected by the operation."""
        self.rows_affected = count


class APICallLogger:
    """Context manager for logging API calls."""
    
    def __init__(self, logger_name: str, service: str, endpoint: str, method: str = "GET"):
        self.logger = get_structured_logger(logger_name)
        self.service = service
        self.endpoint = endpoint
        self.method = method
        self.start_time = None
        self.status_code = None
    
    def __enter__(self):
        self.start_time = datetime.now(KYIV_TZ)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now(KYIV_TZ) - self.start_time).total_seconds()
        
        self.logger.log_api_call(
            self.service,
            self.endpoint,
            method=self.method,
            status_code=self.status_code,
            duration=duration,
            success=exc_type is None
        )
        
        return False
    
    def set_status_code(self, code: int):
        """Set the HTTP status code."""
        self.status_code = code