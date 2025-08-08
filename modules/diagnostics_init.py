"""
Initialization module for enhanced error diagnostics system.

This module provides initialization functions to set up the comprehensive
error logging and diagnostics system for the application.

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from modules.enhanced_error_diagnostics import (
    enhanced_diagnostics,
    initialize_enhanced_diagnostics,
    shutdown_enhanced_diagnostics
)
from modules.structured_logging import StructuredLogger, LogLevel
from modules.logger import general_logger, error_logger
from modules.const import KYIV_TZ


class DiagnosticsInitializer:
    """
    Initializer for the enhanced diagnostics system.
    
    This class manages the lifecycle of the diagnostics system,
    including startup, monitoring, and shutdown procedures.
    """
    
    def __init__(self) -> None:
        self.logger = StructuredLogger("diagnostics_init")
        self.initialized = False
        self.monitoring_active = False
    
    async def initialize_system(self) -> bool:
        """
        Initialize the enhanced diagnostics system.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if self.initialized:
            self.logger.log_event(
                LogLevel.WARNING,
                "diagnostics_already_initialized",
                "Diagnostics system is already initialized"
            )
            return True
        
        try:
            self.logger.log_event(
                LogLevel.INFO,
                "diagnostics_initialization_start",
                "Starting enhanced diagnostics system initialization"
            )
            
            # Initialize the enhanced diagnostics system
            await initialize_enhanced_diagnostics()
            
            # Initialize error analytics if available
            try:
                from modules.error_analytics import error_tracker
                await error_tracker.initialize()
                
                self.logger.log_event(
                    LogLevel.INFO,
                    "error_analytics_initialized",
                    "Error analytics system initialized successfully"
                )
            except Exception as e:
                self.logger.log_event(
                    LogLevel.WARNING,
                    "error_analytics_init_failed",
                    f"Failed to initialize error analytics: {str(e)}",
                    error=str(e)
                )
            
            # Mark as initialized
            self.initialized = True
            self.monitoring_active = True
            
            self.logger.log_event(
                LogLevel.INFO,
                "diagnostics_initialization_complete",
                "Enhanced diagnostics system initialized successfully"
            )
            
            # Log system startup information
            await self._log_system_startup_info()
            
            return True
            
        except Exception as e:
            self.logger.log_event(
                LogLevel.ERROR,
                "diagnostics_initialization_failed",
                f"Failed to initialize diagnostics system: {str(e)}",
                error=str(e)
            )
            
            error_logger.error(f"Diagnostics system initialization failed: {e}", exc_info=True)
            return False
    
    async def shutdown_system(self) -> bool:
        """
        Shutdown the enhanced diagnostics system.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        if not self.initialized:
            self.logger.log_event(
                LogLevel.WARNING,
                "diagnostics_not_initialized",
                "Diagnostics system is not initialized, nothing to shutdown"
            )
            return True
        
        try:
            self.logger.log_event(
                LogLevel.INFO,
                "diagnostics_shutdown_start",
                "Starting enhanced diagnostics system shutdown"
            )
            
            # Shutdown the enhanced diagnostics system
            await shutdown_enhanced_diagnostics()
            
            # Shutdown error analytics if available
            try:
                from modules.error_analytics import error_tracker
                await error_tracker.stop()
                
                self.logger.log_event(
                    LogLevel.INFO,
                    "error_analytics_shutdown",
                    "Error analytics system shutdown successfully"
                )
            except Exception as e:
                self.logger.log_event(
                    LogLevel.WARNING,
                    "error_analytics_shutdown_failed",
                    f"Failed to shutdown error analytics: {str(e)}",
                    error=str(e)
                )
            
            # Mark as shutdown
            self.initialized = False
            self.monitoring_active = False
            
            self.logger.log_event(
                LogLevel.INFO,
                "diagnostics_shutdown_complete",
                "Enhanced diagnostics system shutdown successfully"
            )
            
            return True
            
        except Exception as e:
            self.logger.log_event(
                LogLevel.ERROR,
                "diagnostics_shutdown_failed",
                f"Failed to shutdown diagnostics system: {str(e)}",
                error=str(e)
            )
            
            error_logger.error(f"Diagnostics system shutdown failed: {e}", exc_info=True)
            return False
    
    async def _log_system_startup_info(self) -> None:
        """Log system startup information for diagnostics."""
        try:
            import platform
            import sys
            import os
            from datetime import datetime
            from modules.const import KYIV_TZ
            
            startup_info = {
                "timestamp": datetime.now(KYIV_TZ).isoformat(),
                "python_version": sys.version,
                "platform": platform.platform(),
                "architecture": platform.architecture(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "working_directory": os.getcwd(),
                "process_id": os.getpid(),
                "environment": {
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                    "USER": os.environ.get("USER", "unknown"),
                    "HOME": os.environ.get("HOME", "unknown")
                }
            }
            
            self.logger.log_event(
                LogLevel.INFO,
                "system_startup_info",
                "System startup information logged",
                **startup_info
            )
            
            # Also log to general logger for visibility
            general_logger.info(
                f"Enhanced diagnostics system started - "
                f"Python {sys.version.split()[0]}, "
                f"Platform: {platform.platform()}, "
                f"PID: {os.getpid()}"
            )
            
        except Exception as e:
            self.logger.log_event(
                LogLevel.WARNING,
                "startup_info_logging_failed",
                f"Failed to log system startup info: {str(e)}",
                error=str(e)
            )
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current status of the diagnostics system.
        
        Returns:
            dict: Status information
        """
        return {
            "initialized": self.initialized,
            "monitoring_active": self.monitoring_active,
            "service_health": enhanced_diagnostics.get_service_health_summary() if self.initialized else {},
            "command_metrics": enhanced_diagnostics.get_command_metrics_summary() if self.initialized else {}
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the diagnostics system.
        
        Returns:
            dict: Health check results
        """
        health_status: Dict[str, Any] = {
            "healthy": True,
            "issues": [],
            "timestamp": datetime.now(KYIV_TZ).isoformat()
        }
        
        try:
            # Check if system is initialized
            if not self.initialized:
                health_status["healthy"] = False
                health_status["issues"].append("Diagnostics system not initialized")
                return health_status
            
            # Check monitoring status
            if not self.monitoring_active:
                health_status["healthy"] = False
                health_status["issues"].append("Monitoring is not active")
            
            # Check service health
            service_health = enhanced_diagnostics.get_service_health_summary()
            unhealthy_services = [
                name for name, health in service_health.items()
                if health.get("status") != "healthy"
            ]
            
            if unhealthy_services:
                health_status["issues"].append(f"Unhealthy services: {', '.join(unhealthy_services)}")
            
            # Check error analytics
            try:
                from modules.error_analytics import get_error_summary
                error_summary = get_error_summary()
                
                # Check for high error rates
                total_errors = error_summary.get("total_errors", 0)
                if total_errors > 100:  # Arbitrary threshold
                    health_status["issues"].append(f"High error count: {total_errors}")
                
            except Exception as e:
                health_status["issues"].append(f"Error analytics check failed: {str(e)}")
            
            # Update overall health status
            if health_status["issues"]:
                health_status["healthy"] = len(health_status["issues"]) <= 2  # Allow minor issues
            
        except Exception as e:
            health_status["healthy"] = False
            health_status["issues"].append(f"Health check failed: {str(e)}")
        
        return health_status


# Global initializer instance
diagnostics_initializer = DiagnosticsInitializer()


# Convenience functions for external use
async def initialize_diagnostics() -> bool:
    """Initialize the enhanced diagnostics system."""
    return await diagnostics_initializer.initialize_system()


async def shutdown_diagnostics() -> bool:
    """Shutdown the enhanced diagnostics system."""
    return await diagnostics_initializer.shutdown_system()


def get_diagnostics_status() -> Dict[str, Any]:
    """Get current diagnostics system status."""
    return diagnostics_initializer.get_system_status()


async def check_diagnostics_health() -> Dict[str, Any]:
    """Perform diagnostics system health check."""
    return await diagnostics_initializer.health_check()


# Application lifecycle integration
async def on_application_startup() -> None:
    """
    Function to be called during application startup.
    
    This should be integrated into the main application startup sequence.
    """
    try:
        general_logger.info("Initializing enhanced diagnostics system...")
        
        success = await initialize_diagnostics()
        
        if success:
            general_logger.info("Enhanced diagnostics system initialized successfully")
        else:
            error_logger.error("Failed to initialize enhanced diagnostics system")
            
    except Exception as e:
        error_logger.error(f"Error during diagnostics initialization: {e}", exc_info=True)


async def on_application_shutdown() -> None:
    """
    Function to be called during application shutdown.
    
    This should be integrated into the main application shutdown sequence.
    """
    try:
        general_logger.info("Shutting down enhanced diagnostics system...")
        
        success = await shutdown_diagnostics()
        
        if success:
            general_logger.info("Enhanced diagnostics system shutdown successfully")
        else:
            error_logger.error("Failed to shutdown enhanced diagnostics system")
            
    except Exception as e:
        error_logger.error(f"Error during diagnostics shutdown: {e}", exc_info=True)


# Health check command for administrators
async def diagnostics_health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command handler for checking diagnostics system health.
    
    Usage: /diagnostics_health
    """
    try:
        if not update.message:
            return
        
        # Perform health check
        health_status = await check_diagnostics_health()
        
        # Format health status message
        status_emoji = "✅" if health_status["healthy"] else "❌"
        status_text = "Здоровий" if health_status["healthy"] else "Проблеми"
        
        message_lines = [
            f"{status_emoji} **Стан системи діагностики**",
            f"Статус: {status_text}",
            ""
        ]
        
        if health_status["issues"]:
            message_lines.append("🚨 **Виявлені проблеми:**")
            for issue in health_status["issues"]:
                message_lines.append(f"• {issue}")
            message_lines.append("")
        
        # Add system status
        system_status = get_diagnostics_status()
        message_lines.extend([
            "📊 **Системна інформація:**",
            f"• Ініціалізовано: {'✅' if system_status['initialized'] else '❌'}",
            f"• Моніторинг активний: {'✅' if system_status['monitoring_active'] else '❌'}",
            ""
        ])
        
        # Add service health summary
        service_health = system_status.get("service_health", {})
        if service_health:
            healthy_services = sum(1 for s in service_health.values() if s.get("status") == "healthy")
            total_services = len(service_health)
            message_lines.append(f"🔧 **Сервіси:** {healthy_services}/{total_services} здорові")
        
        message_lines.append(f"🕐 **Час перевірки:** {health_status['timestamp']}")
        
        await update.message.reply_text("\n".join(message_lines), parse_mode='Markdown')
        
    except Exception as e:
        error_message = f"❌ Помилка при перевірці стану діагностики: {str(e)}"
        if update.message:
            await update.message.reply_text(error_message)