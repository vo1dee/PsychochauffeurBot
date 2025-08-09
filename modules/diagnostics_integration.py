"""
Integration guide and utilities for applying enhanced diagnostics to existing commands.

This module provides utilities and examples for integrating the enhanced error
logging and diagnostics system with existing command handlers.

Requirements addressed: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
from typing import Dict, Any, Callable, List, Optional, Coroutine
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, Application

from modules.enhanced_analyze_command import enhanced_analyze_command
from modules.enhanced_flares_command import enhanced_flares_command
from modules.diagnostics_command import diagnostics_command
from modules.diagnostics_init import (
    initialize_diagnostics,
    shutdown_diagnostics,
    diagnostics_health_command,
    on_application_startup,
    on_application_shutdown
)
from modules.command_diagnostics import enhance_command_with_diagnostics
from modules.structured_logging import StructuredLogger, LogLevel
from modules.logger import general_logger, error_logger


class DiagnosticsIntegration:
    """
    Integration manager for enhanced diagnostics system.
    
    This class provides utilities for integrating the enhanced diagnostics
    system with existing Telegram bot applications.
    """
    
    def __init__(self) -> None:
        self.logger = StructuredLogger("diagnostics_integration")
        self.enhanced_commands: Dict[str, Callable[..., Any]] = {}
        self.original_commands: Dict[str, Callable[..., Any]] = {}
    
    def register_enhanced_commands(self) -> Dict[str, Callable[..., Any]]:
        """
        Register enhanced command handlers.
        
        Returns:
            Dict mapping command names to enhanced handlers
        """
        enhanced_commands = {
            "analyze": enhanced_analyze_command,
            "flares": enhanced_flares_command,
            "diagnostics": diagnostics_command,
            "diagnostics_health": diagnostics_health_command
        }
        
        self.enhanced_commands.update(enhanced_commands)
        
        self.logger.log_event(
            LogLevel.INFO,
            "enhanced_commands_registered",
            f"Registered {len(enhanced_commands)} enhanced command handlers",
            commands=list(enhanced_commands.keys())
        )
        
        return enhanced_commands
    
    def wrap_existing_command(self, command_name: str, original_handler: Callable[..., Any]) -> Callable[..., Any]:
        """
        Wrap an existing command handler with enhanced diagnostics.
        
        Args:
            command_name: Name of the command
            original_handler: Original command handler function
            
        Returns:
            Enhanced command handler with diagnostics
        """
        self.original_commands[command_name] = original_handler
        
        @enhance_command_with_diagnostics(command_name)
        async def enhanced_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
            return await original_handler(update, context)
        
        self.enhanced_commands[command_name] = enhanced_handler
        
        self.logger.log_event(
            LogLevel.INFO,
            "command_wrapped_with_diagnostics",
            f"Wrapped command {command_name} with enhanced diagnostics",
            command_name=command_name
        )
        
        return enhanced_handler
    
    def get_integration_summary(self) -> Dict[str, Any]:
        """
        Get summary of diagnostics integration status.
        
        Returns:
            Dictionary with integration status information
        """
        return {
            "enhanced_commands": list(self.enhanced_commands.keys()),
            "original_commands": list(self.original_commands.keys()),
            "total_enhanced": len(self.enhanced_commands),
            "timestamp": datetime.now().isoformat()
        }
    
    async def setup_application_lifecycle(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """
        Set up application lifecycle hooks for diagnostics.
        
        Args:
            application: Telegram bot application instance
        """
        try:
            # Add startup hook
            if application.post_init:
                application.post_init = self._create_startup_hook(application.post_init)
            
            # Add shutdown hook
            if application.post_shutdown:
                application.post_shutdown = self._create_shutdown_hook(application.post_shutdown)
            
            self.logger.log_event(
                LogLevel.INFO,
                "application_lifecycle_setup",
                "Application lifecycle hooks set up for diagnostics"
            )
            
        except Exception as e:
            self.logger.log_event(
                LogLevel.ERROR,
                "application_lifecycle_setup_failed",
                f"Failed to set up application lifecycle hooks: {str(e)}",
                error=str(e)
            )
            raise
    
    def _create_startup_hook(
        self, existing_hook: Optional[Callable[[Application[Any, Any, Any, Any, Any, Any]], Coroutine[Any, Any, None]]] = None
    ) -> Callable[[Application[Any, Any, Any, Any, Any, Any]], Coroutine[Any, Any, None]]:
        """Create startup hook that includes diagnostics initialization."""
        async def startup_hook(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
            try:
                # Call existing hook first if it exists
                if existing_hook:
                    await existing_hook(application)
                
                # Initialize diagnostics
                await on_application_startup()
                
            except Exception as e:
                error_logger.error(f"Error in startup hook: {e}", exc_info=True)
                raise
        
        return startup_hook
    
    def _create_shutdown_hook(
        self, existing_hook: Optional[Callable[[Application[Any, Any, Any, Any, Any, Any]], Coroutine[Any, Any, None]]] = None
    ) -> Callable[[Application[Any, Any, Any, Any, Any, Any]], Coroutine[Any, Any, None]]:
        """Create shutdown hook that includes diagnostics cleanup."""
        async def shutdown_hook(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
            try:
                # Shutdown diagnostics first
                await on_application_shutdown()
                
                # Call existing hook if it exists
                if existing_hook:
                    await existing_hook(application)
                
            except Exception as e:
                error_logger.error(f"Error in shutdown hook: {e}", exc_info=True)
                # Don't raise during shutdown
        
        return shutdown_hook


# Global integration manager
integration_manager = DiagnosticsIntegration()


def setup_enhanced_diagnostics(application: Application[Any, Any, Any, Any, Any, Any]) -> Dict[str, Callable[..., Any]]:
    """
    Set up enhanced diagnostics for a Telegram bot application.
    
    This is the main function to call for integrating enhanced diagnostics
    into an existing bot application.
    
    Args:
        application: Telegram bot application instance
        
    Returns:
        Dictionary of enhanced command handlers
    """
    try:
        general_logger.info("Setting up enhanced diagnostics integration...")
        
        # Register enhanced command handlers
        enhanced_commands = integration_manager.register_enhanced_commands()
        
        # Set up application lifecycle hooks
        asyncio.create_task(integration_manager.setup_application_lifecycle(application))
        
        general_logger.info(
            f"Enhanced diagnostics integration complete. "
            f"Enhanced {len(enhanced_commands)} commands."
        )
        
        return enhanced_commands
        
    except Exception as e:
        error_logger.error(f"Failed to set up enhanced diagnostics: {e}", exc_info=True)
        raise


def wrap_command_with_diagnostics(command_name: str, handler: Callable[..., Any]) -> Callable[..., Any]:
    """
    Wrap a single command handler with enhanced diagnostics.
    
    Args:
        command_name: Name of the command
        handler: Original command handler
        
    Returns:
        Enhanced command handler
    """
    return integration_manager.wrap_existing_command(command_name, handler)


def get_enhanced_command_handlers() -> Dict[str, Callable[..., Any]]:
    """
    Get all enhanced command handlers.
    
    Returns:
        Dictionary mapping command names to enhanced handlers
    """
    return integration_manager.enhanced_commands.copy()


def get_integration_status() -> Dict[str, Any]:
    """
    Get current integration status.
    
    Returns:
        Dictionary with integration status information
    """
    return integration_manager.get_integration_summary()


# Example integration for existing applications
class ExampleIntegration:
    """
    Example of how to integrate enhanced diagnostics with an existing bot.
    
    This class shows the recommended patterns for integrating the enhanced
    diagnostics system with existing Telegram bot applications.
    """
    
    @staticmethod
    def integrate_with_existing_bot(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """
        Example integration with an existing bot application.
        
        Args:
            application: Existing Telegram bot application
        """
        try:
            # Step 1: Set up enhanced diagnostics
            enhanced_commands = setup_enhanced_diagnostics(application)
            
            # Step 2: Replace existing command handlers with enhanced versions
            for command_name, enhanced_handler in enhanced_commands.items():
                # Remove existing handler if it exists
                # Note: This is a simplified approach. A more robust implementation
                # would involve finding the specific handler instance to remove.
                # For this context, we assume this is sufficient.
                handlers_to_remove = []
                if 0 in application.handlers:
                    for handler in application.handlers[0]:
                        if hasattr(handler, 'command') and command_name in handler.command:
                            handlers_to_remove.append(handler)
                
                for handler in handlers_to_remove:
                    application.remove_handler(handler)

                
                # Add enhanced handler
                from telegram.ext import CommandHandler
                application.add_handler(CommandHandler(command_name, enhanced_handler))
            
            # Step 3: Add diagnostics-specific commands
            application.add_handler(CommandHandler("diagnostics", diagnostics_command))
            application.add_handler(CommandHandler("diagnostics_health", diagnostics_health_command))
            
            general_logger.info("Enhanced diagnostics integration completed successfully")
            
        except Exception as e:
            error_logger.error(f"Failed to integrate enhanced diagnostics: {e}", exc_info=True)
            raise
    
    @staticmethod
    def wrap_existing_commands(application: Application[Any, Any, Any, Any, Any, Any], command_handlers: Dict[str, Callable[..., Any]]) -> None:
        """
        Wrap existing command handlers with enhanced diagnostics.
        
        Args:
            application: Telegram bot application
            command_handlers: Dictionary of existing command handlers
        """
        try:
            enhanced_handlers = {}
            
            for command_name, original_handler in command_handlers.items():
                # Wrap with diagnostics
                enhanced_handler = wrap_command_with_diagnostics(command_name, original_handler)
                enhanced_handlers[command_name] = enhanced_handler
                
                # Replace in application
                # Note: This is a simplified approach. A more robust implementation
                # would involve finding the specific handler instance to remove.
                handlers_to_remove = []
                if 0 in application.handlers:
                    for h in application.handlers[0]:
                        if hasattr(h, 'command') and command_name in h.command:
                            handlers_to_remove.append(h)

                for h in handlers_to_remove:
                    application.remove_handler(h)
                from telegram.ext import CommandHandler
                application.add_handler(CommandHandler(command_name, enhanced_handler))
            
            general_logger.info(
                f"Wrapped {len(enhanced_handlers)} existing commands with enhanced diagnostics"
            )
            
        except Exception as e:
            error_logger.error(f"Failed to wrap existing commands: {e}", exc_info=True)
            raise


# Usage examples and documentation
INTEGRATION_EXAMPLES = {
    "basic_setup": """
# Basic setup for new applications
from telegram.ext import Application
from modules.diagnostics_integration import setup_enhanced_diagnostics

# Create your application
application = Application.builder().token("YOUR_BOT_TOKEN").build()

# Set up enhanced diagnostics
enhanced_commands = setup_enhanced_diagnostics(application)

# Add command handlers
from telegram.ext import CommandHandler
for command_name, handler in enhanced_commands.items():
    application.add_handler(CommandHandler(command_name, handler))

# Run the application
application.run_polling()
""",
    
    "existing_app_integration": """
# Integration with existing applications
from modules.diagnostics_integration import ExampleIntegration

# Integrate with your existing application
ExampleIntegration.integrate_with_existing_bot(your_existing_application)
""",
    
    "manual_command_wrapping": """
# Manual command wrapping
from modules.diagnostics_integration import wrap_command_with_diagnostics

# Wrap individual commands
async def my_existing_command(update, context):
    # Your existing command logic
    pass

# Wrap with diagnostics
enhanced_command = wrap_command_with_diagnostics("my_command", my_existing_command)

# Use the enhanced command
application.add_handler(CommandHandler("my_command", enhanced_command))
""",
    
    "lifecycle_integration": """
# Application lifecycle integration
from modules.diagnostics_init import on_application_startup, on_application_shutdown

# In your application startup
async def startup():
    await on_application_startup()
    # Your other startup code

# In your application shutdown
async def shutdown():
    await on_application_shutdown()
    # Your other shutdown code
"""
}


def print_integration_examples() -> None:
    """Print integration examples for documentation."""
    print("Enhanced Diagnostics Integration Examples:")
    print("=" * 50)
    
    for example_name, example_code in INTEGRATION_EXAMPLES.items():
        print(f"\n{example_name.upper()}:")
        print("-" * 30)
        print(example_code)


# Validation and testing utilities
async def validate_integration() -> Dict[str, Any]:
    """
    Validate that the diagnostics integration is working correctly.
    
    Returns:
        Dictionary with validation results
    """
    validation_results: Dict[str, Any] = {
        "valid": True,
        "issues": [],
        "warnings": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Check if diagnostics system is initialized
        from modules.diagnostics_init import get_diagnostics_status
        status = get_diagnostics_status()
        
        if not status["initialized"]:
            validation_results["valid"] = False
            validation_results["issues"].append("Diagnostics system not initialized")
        
        if not status["monitoring_active"]:
            validation_results["warnings"].append("Monitoring is not active")
        
        # Check enhanced commands
        enhanced_commands = get_enhanced_command_handlers()
        if not enhanced_commands:
            validation_results["warnings"].append("No enhanced commands registered")
        
        # Check service health
        service_health = status.get("service_health", {})
        unhealthy_services = [
            name for name, health in service_health.items()
            if health.get("status") != "healthy"
        ]
        
        if unhealthy_services:
            validation_results["warnings"].append(
                f"Some services are unhealthy: {', '.join(unhealthy_services)}"
            )
        
        # Log validation results
        integration_manager.logger.log_event(
            LogLevel.INFO,
            "integration_validation_completed",
            f"Integration validation completed: {'PASSED' if validation_results['valid'] else 'FAILED'}",
            **validation_results
        )
        
    except Exception as e:
        validation_results["valid"] = False
        validation_results["issues"].append(f"Validation error: {str(e)}")
    
    return validation_results


if __name__ == "__main__":
    # Print integration examples when run directly
    print_integration_examples()
