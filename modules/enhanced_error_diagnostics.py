"""
Enhanced error logging and diagnostics system for comprehensive command monitoring.

This module provides structured logging for all command executions with metrics tracking,
detailed error context capture, configuration diagnostics, external service monitoring,
and graceful error handling with user-friendly messages.

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import json
import time
import traceback
import psutil
import socket
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging
from contextlib import asynccontextmanager
import aiohttp
import asyncpg
from telegram import Update
from telegram.ext import ContextTypes

from modules.const import Config, KYIV_TZ
from modules.structured_logging import StructuredLogger, LogLevel
from modules.error_handler import StandardError, ErrorCategory, ErrorSeverity
from modules.diagnostics import run_diagnostics


class ServiceStatus(Enum):
    """External service status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CommandExecutionStatus(Enum):
    """Command execution status enumeration."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class CommandMetrics:
    """Metrics for command execution tracking."""
    command_name: str
    user_id: int
    chat_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: CommandExecutionStatus = CommandExecutionStatus.STARTED
    error_count: int = 0
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    database_queries: int = 0
    api_calls: int = 0
    success: bool = False
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class ServiceHealthMetrics:
    """Health metrics for external services."""
    service_name: str
    status: ServiceStatus
    response_time_ms: Optional[float] = None
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    availability_percent: float = 100.0


@dataclass
class SystemDiagnostics:
    """System diagnostic information."""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    active_connections: int
    database_pool_size: int
    database_active_connections: int
    log_file_sizes: Dict[str, int]
    configuration_status: Dict[str, Any]


class EnhancedErrorDiagnostics:
    """
    Enhanced error logging and diagnostics system.
    
    Provides comprehensive logging, metrics tracking, and diagnostic capabilities
    for all command executions and system operations.
    """
    
    def __init__(self) -> None:
        self.logger = StructuredLogger("enhanced_diagnostics")
        self.command_metrics: Dict[str, CommandMetrics] = {}
        self.service_health: Dict[str, ServiceHealthMetrics] = {}
        self.system_diagnostics: List[SystemDiagnostics] = []
        self.monitoring_tasks: List[asyncio.Task[Any]] = []
        
        # Initialize service monitoring
        self._initialize_service_monitoring()
    
    def _initialize_service_monitoring(self) -> None:
        """Initialize monitoring for external services."""
        services = {
            "openrouter_api": Config.OPENROUTER_BASE_URL,
            "database": "postgresql://localhost:5432",
            "meteoagent_api": "https://api.meteoagent.com",
            "telegram_api": "https://api.telegram.org"
        }
        
        for service_name, endpoint in services.items():
            self.service_health[service_name] = ServiceHealthMetrics(
                service_name=service_name,
                status=ServiceStatus.UNKNOWN
            )
    
    @asynccontextmanager
    async def track_command_execution(
        self,
        command_name: str,
        user_id: int,
        chat_id: int,
        **additional_context: Any
    ) -> AsyncGenerator[CommandMetrics, None]:
        """
        Context manager for tracking command execution with comprehensive metrics.
        
        Args:
            command_name: Name of the command being executed
            user_id: ID of the user executing the command
            chat_id: ID of the chat where command is executed
            **additional_context: Additional context information
        """
        execution_id = f"{command_name}_{user_id}_{chat_id}_{int(time.time())}"
        start_time = datetime.now(KYIV_TZ)
        
        # Initialize metrics
        metrics = CommandMetrics(
            command_name=command_name,
            user_id=user_id,
            chat_id=chat_id,
            start_time=start_time
        )
        
        self.command_metrics[execution_id] = metrics
        
        # Log command start
        self.logger.log_event(
            LogLevel.INFO,
            "command_execution_start",
            f"Starting command execution: {command_name}",
            execution_id=execution_id,
            command_name=command_name,
            user_id=user_id,
            chat_id=chat_id,
            **additional_context
        )
        
        try:
            # Capture initial system metrics
            initial_memory = self._get_memory_usage()
            initial_cpu = self._get_cpu_usage()
            
            yield metrics
            
            # Command completed successfully
            metrics.status = CommandExecutionStatus.COMPLETED
            metrics.success = True
            
        except Exception as e:
            # Command failed
            metrics.status = CommandExecutionStatus.FAILED
            metrics.success = False
            metrics.error_count += 1
            
            # Capture detailed error information
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "system_state": await self._capture_system_state()
            }
            metrics.error_details = error_details
            
            # Log the error with full context
            await self._log_command_error(execution_id, e, error_details)
            
            raise
        
        finally:
            # Finalize metrics
            end_time = datetime.now(KYIV_TZ)
            metrics.end_time = end_time
            metrics.duration_seconds = (end_time - start_time).total_seconds()
            
            # Capture final system metrics
            metrics.memory_usage_mb = self._get_memory_usage()
            metrics.cpu_usage_percent = self._get_cpu_usage()
            
            # Log command completion
            await self._log_command_completion(execution_id, metrics)
            
            # Clean up old metrics to prevent memory leaks
            await self._cleanup_old_metrics()
    
    async def _log_command_error(
        self,
        execution_id: str,
        error: Exception,
        error_details: Dict[str, Any]
    ) -> None:
        """Log detailed command error information."""
        metrics = self.command_metrics.get(execution_id)
        if not metrics:
            return
        
        # Create comprehensive error context
        error_context = {
            "execution_id": execution_id,
            "command_name": metrics.command_name,
            "user_id": metrics.user_id,
            "chat_id": metrics.chat_id,
            "execution_duration": metrics.duration_seconds,
            "error_details": error_details,
            "system_diagnostics": await self._capture_system_state(),
            "service_health": {
                name: asdict(health) for name, health in self.service_health.items()
            }
        }
        
        self.logger.log_event(
            LogLevel.ERROR,
            "command_execution_error",
            f"Command execution failed: {metrics.command_name} - {str(error)}",
            **error_context
        )
        
        # Also log to error analytics for tracking
        from modules.error_analytics import track_error
        
        standard_error = StandardError(
            message=f"Command {metrics.command_name} failed: {str(error)}",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.GENERAL,
            context=error_context,
            original_exception=error
        )
        
        track_error(standard_error)
    
    async def _log_command_completion(
        self,
        execution_id: str,
        metrics: CommandMetrics
    ) -> None:
        """Log command completion with performance metrics."""
        completion_data = {
            "execution_id": execution_id,
            "command_name": metrics.command_name,
            "user_id": metrics.user_id,
            "chat_id": metrics.chat_id,
            "duration_seconds": metrics.duration_seconds,
            "status": metrics.status.value,
            "success": metrics.success,
            "error_count": metrics.error_count,
            "memory_usage_mb": metrics.memory_usage_mb,
            "cpu_usage_percent": metrics.cpu_usage_percent,
            "database_queries": metrics.database_queries,
            "api_calls": metrics.api_calls
        }
        
        log_level = LogLevel.INFO if metrics.success else LogLevel.ERROR
        event_type = "command_execution_completed" if metrics.success else "command_execution_failed"
        
        self.logger.log_event(
            log_level,
            event_type,
            f"Command execution {metrics.status.value}: {metrics.command_name} "
            f"({metrics.duration_seconds:.3f}s)",
            **completion_data
        )
        
        # Log performance metrics
        self.logger.log_performance_metric(
            f"command_duration_{metrics.command_name}",
            metrics.duration_seconds or 0,
            unit="seconds",
            user_id=metrics.user_id,
            chat_id=metrics.chat_id,
            success=metrics.success
        )
    
    async def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state for diagnostics."""
        try:
            return {
                "timestamp": datetime.now(KYIV_TZ).isoformat(),
                "cpu_usage": self._get_cpu_usage(),
                "memory_usage": self._get_memory_usage(),
                "disk_usage": self._get_disk_usage(),
                "active_connections": self._get_active_connections(),
                "database_status": await self._check_database_status(),
                "log_file_sizes": self._get_log_file_sizes(),
                "configuration_status": await self._check_configuration_status()
            }
        except Exception as e:
            return {
                "error": f"Failed to capture system state: {str(e)}",
                "timestamp": datetime.now(KYIV_TZ).isoformat()
            }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return float(process.memory_info().rss / 1024 / 1024)
        except Exception:
            return 0.0
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return float(psutil.cpu_percent(interval=0.1))
        except Exception:
            return 0.0
    
    def _get_disk_usage(self) -> float:
        """Get current disk usage percentage."""
        try:
            return float(psutil.disk_usage('/').percent)
        except Exception:
            return 0.0
    
    def _get_active_connections(self) -> int:
        """Get number of active network connections."""
        try:
            return len(psutil.net_connections())
        except Exception:
            return 0
    
    async def _check_database_status(self) -> Dict[str, Any]:
        """Check database connection status and pool information."""
        try:
            from modules.database import Database
            
            # Check if database is healthy
            is_healthy = await Database.health_check()
            
            status = {
                "healthy": is_healthy,
                "pool_size": 0,
                "active_connections": 0,
                "last_check": datetime.now(KYIV_TZ).isoformat()
            }
            
            if hasattr(Database, '_pool') and Database._pool:
                status["pool_size"] = Database._pool.get_size()
                status["active_connections"] = Database._pool.get_size() - Database._pool.get_idle_size()
            
            return status
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "last_check": datetime.now(KYIV_TZ).isoformat()
            }
    
    def _get_log_file_sizes(self) -> Dict[str, int]:
        """Get sizes of log files for monitoring."""
        log_dir = Path("logs")
        sizes = {}
        
        try:
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    sizes[log_file.name] = log_file.stat().st_size
        except Exception:
            pass
        
        return sizes
    
    async def _check_configuration_status(self) -> Dict[str, Any]:
        """Check configuration status and identify potential issues."""
        config_status: Dict[str, Any] = {
            "valid": True,
            "issues": [],
            "last_check": datetime.now(KYIV_TZ).isoformat()
        }
        
        try:
            # Check required configuration values
            required_configs = [
                ("OPENROUTER_API_KEY", Config.OPENROUTER_API_KEY),
                ("TELEGRAM_BOT_TOKEN", Config.TELEGRAM_BOT_TOKEN),
                ("DATABASE_URL", getattr(Config, 'DATABASE_URL', None))
            ]
            
            for config_name, config_value in required_configs:
                if not config_value:
                    config_status["valid"] = False
                    config_status["issues"].append(f"Missing {config_name}")
            
            # Check file permissions
            log_dir = Path("logs")
            if not log_dir.exists():
                config_status["issues"].append("Log directory does not exist")
            elif not log_dir.is_dir():
                config_status["issues"].append("Log path is not a directory")
            
            # Check external tool availability
            try:
                subprocess.run(["wkhtmltoimage", "--version"], 
                             capture_output=True, timeout=5)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                config_status["issues"].append("wkhtmltoimage tool not available")
            
        except Exception as e:
            config_status["valid"] = False
            config_status["issues"].append(f"Configuration check error: {str(e)}")
        
        return config_status
    
    async def monitor_external_services(self) -> None:
        """Monitor external service availability and performance."""
        while True:
            try:
                await self._check_all_services()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_event(
                    LogLevel.ERROR,
                    "service_monitoring_error",
                    f"Error in service monitoring: {str(e)}"
                )
                await asyncio.sleep(60)  # Retry after 1 minute on error
    
    async def _check_all_services(self) -> None:
        """Check all monitored external services."""
        tasks = []
        
        for service_name in self.service_health.keys():
            task = asyncio.create_task(self._check_service_health(service_name))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_service_health(self, service_name: str) -> None:
        """Check health of a specific external service."""
        health_metric = self.service_health[service_name]
        start_time = time.time()
        
        try:
            if service_name == "openrouter_api":
                await self._check_openrouter_health()
            elif service_name == "database":
                await self._check_database_health()
            elif service_name == "meteoagent_api":
                await self._check_meteoagent_health()
            elif service_name == "telegram_api":
                await self._check_telegram_health()
            
            # Service is healthy
            response_time = (time.time() - start_time) * 1000
            health_metric.status = ServiceStatus.HEALTHY
            health_metric.response_time_ms = response_time
            health_metric.consecutive_failures = 0
            health_metric.last_check = datetime.now(KYIV_TZ)
            health_metric.last_error = None
            
            # Update availability percentage
            health_metric.availability_percent = min(100.0, 
                health_metric.availability_percent + 0.1)
            
        except Exception as e:
            # Service is unhealthy
            health_metric.status = ServiceStatus.UNHEALTHY
            health_metric.consecutive_failures += 1
            health_metric.last_check = datetime.now(KYIV_TZ)
            health_metric.last_error = str(e)
            
            # Update availability percentage
            health_metric.availability_percent = max(0.0, 
                health_metric.availability_percent - 1.0)
            
            # Log service failure
            self.logger.log_event(
                LogLevel.WARNING,
                "service_health_check_failed",
                f"Service {service_name} health check failed",
                service_name=service_name,
                consecutive_failures=health_metric.consecutive_failures,
                error=str(e),
                availability_percent=health_metric.availability_percent
            )
    
    async def _check_openrouter_health(self) -> None:
        """Check OpenRouter API health."""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{Config.OPENROUTER_BASE_URL}/models") as response:
                if response.status != 200:
                    raise Exception(f"OpenRouter API returned status {response.status}")
    
    async def _check_database_health(self) -> None:
        """Check database health."""
        from modules.database import Database
        
        if not await Database.health_check():
            raise Exception("Database health check failed")
    
    async def _check_meteoagent_health(self) -> None:
        """Check MeteoAgent API health."""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("https://api.meteoagent.com") as response:
                if response.status >= 500:
                    raise Exception(f"MeteoAgent API returned status {response.status}")
    
    async def _check_telegram_health(self) -> None:
        """Check Telegram API health."""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("https://api.telegram.org") as response:
                if response.status >= 500:
                    raise Exception(f"Telegram API returned status {response.status}")
    
    async def _cleanup_old_metrics(self) -> None:
        """Clean up old command metrics to prevent memory leaks."""
        cutoff_time = datetime.now(KYIV_TZ) - timedelta(hours=24)
        
        to_remove = []
        for execution_id, metrics in self.command_metrics.items():
            if metrics.start_time < cutoff_time:
                to_remove.append(execution_id)
        
        for execution_id in to_remove:
            del self.command_metrics[execution_id]
    
    def get_service_health_summary(self) -> Dict[str, Any]:
        """Get summary of all service health metrics."""
        return {
            service_name: {
                "status": health.status.value,
                "response_time_ms": health.response_time_ms,
                "consecutive_failures": health.consecutive_failures,
                "availability_percent": health.availability_percent,
                "last_check": health.last_check.isoformat() if health.last_check else None,
                "last_error": health.last_error
            }
            for service_name, health in self.service_health.items()
        }
    
    def get_command_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of command execution metrics."""
        if not self.command_metrics:
            return {"total_commands": 0, "summary": {}}
        
        # Calculate summary statistics
        total_commands = len(self.command_metrics)
        successful_commands = sum(1 for m in self.command_metrics.values() if m.success)
        failed_commands = total_commands - successful_commands
        
        avg_duration = sum(
            m.duration_seconds for m in self.command_metrics.values() 
            if m.duration_seconds is not None
        ) / total_commands if total_commands > 0 else 0
        
        command_counts: Dict[str, int] = {}
        for metrics in self.command_metrics.values():
            command_counts[metrics.command_name] = command_counts.get(metrics.command_name, 0) + 1
        
        return {
            "total_commands": total_commands,
            "successful_commands": successful_commands,
            "failed_commands": failed_commands,
            "success_rate": (successful_commands / total_commands * 100) if total_commands > 0 else 0,
            "average_duration_seconds": avg_duration,
            "command_counts": command_counts
        }
    
    async def generate_diagnostic_report(self) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report."""
        return {
            "timestamp": datetime.now(KYIV_TZ).isoformat(),
            "system_state": await self._capture_system_state(),
            "service_health": self.get_service_health_summary(),
            "command_metrics": self.get_command_metrics_summary(),
            "configuration_status": await self._check_configuration_status(),
            "recent_errors": self._get_recent_errors()
        }
    
    def _get_recent_errors(self) -> List[Dict[str, Any]]:
        """Get recent error information."""
        try:
            from modules.error_analytics import get_recent_errors
            return get_recent_errors(10)
        except Exception:
            return []
    
    async def start_monitoring(self) -> None:
        """Start all monitoring tasks."""
        # Start service monitoring
        service_task = asyncio.create_task(self.monitor_external_services())
        self.monitoring_tasks.append(service_task)
        
        self.logger.log_event(
            LogLevel.INFO,
            "monitoring_started",
            "Enhanced error diagnostics monitoring started"
        )
    
    async def stop_monitoring(self) -> None:
        """Stop all monitoring tasks."""
        for task in self.monitoring_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.monitoring_tasks.clear()
        
        self.logger.log_event(
            LogLevel.INFO,
            "monitoring_stopped",
            "Enhanced error diagnostics monitoring stopped"
        )


# Global instance
enhanced_diagnostics = EnhancedErrorDiagnostics()


# Decorator for command execution tracking
def track_command_execution(command_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to automatically track command execution with comprehensive diagnostics.
    
    Args:
        command_name: Name of the command being tracked
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
            user_id = update.effective_user.id if update.effective_user else 0
            chat_id = update.effective_chat.id if update.effective_chat else 0
            
            async with enhanced_diagnostics.track_command_execution(
                command_name=command_name,
                user_id=user_id,
                chat_id=chat_id,
                username=update.effective_user.username if update.effective_user else "unknown",
                chat_type=update.effective_chat.type if update.effective_chat else "unknown"
            ) as metrics:
                try:
                    result = await func(update, context, *args, **kwargs)
                    return result
                except Exception as e:
                    # Provide user-friendly error message
                    error_message = get_user_friendly_error_message(e, command_name)
                    
                    if update.message:
                        try:
                            await update.message.reply_text(error_message)
                        except Exception:
                            pass  # Don't fail if we can't send the error message
                    
                    raise
        
        return wrapper
    return decorator


def get_user_friendly_error_message(error: Exception, command_name: str) -> str:
    """
    Generate user-friendly error messages based on error type and command.
    
    Args:
        error: The exception that occurred
        command_name: Name of the command that failed
        
    Returns:
        User-friendly error message in Ukrainian
    """
    error_type = type(error).__name__
    
    # Database-related errors
    if "database" in str(error).lower() or error_type in ["ConnectionError", "TimeoutError"]:
        return (
            "❌ Виникла проблема з підключенням до бази даних.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )
    
    # Network-related errors
    if error_type in ["aiohttp.ClientError", "asyncio.TimeoutError"] or "network" in str(error).lower():
        return (
            "❌ Проблема з мережевим підключенням.\n"
            "Перевірте інтернет-з'єднання та спробуйте пізніше."
        )
    
    # API-related errors
    if "api" in str(error).lower() or "openrouter" in str(error).lower():
        return (
            "❌ Сервіс тимчасово недоступний.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )
    
    # Command-specific error messages
    if command_name == "analyze":
        return (
            "❌ Не вдалося проаналізувати повідомлення.\n"
            "Перевірте правильність команди та спробуйте пізніше."
        )
    elif command_name == "flares":
        return (
            "❌ Не вдалося отримати знімок сонячних спалахів.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )
    
    # Generic error message
    return (
        "❌ Під час виконання команди сталася помилка.\n"
        "Спробуйте пізніше або зверніться до адміністратора."
    )


# Utility functions for external use
async def log_external_service_call(
    service_name: str,
    endpoint: str,
    method: str = "GET",
    status_code: Optional[int] = None,
    duration: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """
    Log external service API calls for monitoring.
    
    Args:
        service_name: Name of the external service
        endpoint: API endpoint called
        method: HTTP method used
        status_code: Response status code
        duration: Request duration in seconds
        error: Error message if request failed
    """
    enhanced_diagnostics.logger.log_api_call(
        service_name,
        endpoint,
        method=method,
        status_code=status_code,
        duration=duration,
        success=error is None,
        error=error
    )


async def log_database_operation(
    operation: str,
    table: Optional[str] = None,
    duration: Optional[float] = None,
    rows_affected: Optional[int] = None,
    error: Optional[str] = None
) -> None:
    """
    Log database operations for monitoring.
    
    Args:
        operation: Type of database operation
        table: Database table involved
        duration: Operation duration in seconds
        rows_affected: Number of rows affected
        error: Error message if operation failed
    """
    enhanced_diagnostics.logger.log_database_operation(
        operation,
        table=table,
        duration=duration,
        rows_affected=rows_affected,
        success=error is None,
        error=error
    )


async def get_system_health_report() -> Dict[str, Any]:
    """Get comprehensive system health report."""
    return await enhanced_diagnostics.generate_diagnostic_report()


async def initialize_enhanced_diagnostics() -> None:
    """Initialize the enhanced diagnostics system."""
    await enhanced_diagnostics.start_monitoring()


async def shutdown_enhanced_diagnostics() -> None:
    """Shutdown the enhanced diagnostics system."""
    await enhanced_diagnostics.stop_monitoring()