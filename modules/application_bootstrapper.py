"""
Application Bootstrapper

This module provides the ApplicationBootstrapper class that serves as the
minimal entry point for the bot application. It handles service configuration,
lifecycle management, and application orchestration.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional, Any

from modules.service_registry import ServiceRegistry, ServiceInterface
from modules.application_models import ServiceConfiguration
from modules.const import Config
from modules.logger import general_logger, error_logger

logger = logging.getLogger(__name__)


class ApplicationBootstrapper:
    """
    Minimal application entry point that replaces the current main.py logic.
    
    This class is responsible for:
    - Configuring the service registry with all required services
    - Initializing the application orchestrator
    - Handling top-level error scenarios
    - Managing application lifecycle signals
    
    The bootstrapper follows the single responsibility principle by focusing
    solely on application startup and shutdown coordination.
    """
    
    def __init__(self) -> None:
        """Initialize the application bootstrapper."""
        self.service_registry: Optional[ServiceRegistry] = None
        self.bot_application: Optional[ServiceInterface] = None
        self._shutdown_event = asyncio.Event()
        self._running = False
        
    async def configure_services(self) -> ServiceRegistry:
        """
        Configure the service registry with all required services.
        
        This method sets up the dependency injection container with all
        the services needed for the bot to function properly.
        
        Returns:
            ServiceRegistry: Configured service registry instance
            
        Raises:
            ValueError: If required configuration is missing
            RuntimeError: If service configuration fails
        """
        logger.info("Configuring services...")
        
        try:
            # Create service registry
            service_registry = ServiceRegistry()
            
            # Create service configuration
            service_config = ServiceConfiguration(
                telegram_token=Config.TELEGRAM_BOT_TOKEN,
                error_channel_id=Config.ERROR_CHANNEL_ID,
                debug_mode=getattr(Config, 'DEBUG_MODE', False)
            )
            
            # Register core configuration
            service_registry.register_instance('service_config', service_config)
            
            # Import and register core services
            from config.config_manager import ConfigManager
            from modules.database import Database
            from modules.bot_application import BotApplication
            
            # Register configuration manager as singleton
            service_registry.register_singleton(
                'config_manager',
                ConfigManager,
                ConfigManager
            )
            
            # Register database as singleton
            service_registry.register_singleton(
                'database',
                Database,
                Database
            )
            
            # Register bot application as singleton with service registry dependency
            service_registry.register_factory(
                'bot_application',
                BotApplication,
                lambda registry: BotApplication(registry),
                dependencies=['config_manager', 'database']
            )
            
            # Register additional services that will be needed
            await self._register_specialized_services(service_registry)
            
            logger.info("Services configured successfully")
            return service_registry
            
        except Exception as e:
            logger.error(f"Failed to configure services: {e}")
            raise RuntimeError(f"Service configuration failed: {e}") from e
    
    async def _register_specialized_services(self, service_registry: ServiceRegistry) -> None:
        """
        Register specialized services for the refactored architecture.
        
        This method registers the new specialized services that will be
        implemented in subsequent tasks.
        
        Args:
            service_registry: The service registry to register services with
        """
        # Note: These services will be implemented in later tasks
        # For now, we'll register placeholders or existing services
        
        # Register existing services that are already available
        try:
            from modules.reminders.reminders import ReminderManager
            service_registry.register_singleton(
                'reminder_manager',
                ReminderManager,
                ReminderManager
            )
        except ImportError:
            logger.warning("ReminderManager not available, skipping registration")
        
        try:
            from modules.safety import safety_manager
            service_registry.register_instance('safety_manager', safety_manager)
        except ImportError:
            logger.warning("Safety manager not available, skipping registration")
        
        # Register message counter (global instance from main.py)
        try:
            from modules.utils import MessageCounter
            message_counter = MessageCounter()
            service_registry.register_instance('message_counter', message_counter)
        except ImportError:
            logger.warning("MessageCounter not available, skipping registration")
    
    async def start_application(self) -> None:
        """
        Start the application with proper error handling and lifecycle management.
        
        This method orchestrates the complete application startup process,
        including service initialization, signal handler setup, and
        application execution.
        
        Raises:
            RuntimeError: If application startup fails
        """
        if self._running:
            logger.warning("Application is already running")
            return
            
        logger.info("Starting application...")
        
        try:
            # Configure services
            self.service_registry = await self.configure_services()
            
            # Get bot application service
            self.bot_application = self.service_registry.get_service('bot_application')
            
            # Initialize the bot application
            await self.bot_application.initialize()
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Mark as running
            self._running = True
            
            # Start the bot application
            logger.info("Application started successfully")
            await self.bot_application.start()
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            await self.shutdown_application()
            raise RuntimeError(f"Application startup failed: {e}") from e
    
    def setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown.
        
        This method configures signal handlers to ensure the application
        can be shut down gracefully when receiving termination signals.
        """
        def signal_handler(signum: int, frame: Any) -> None:
            """Handle shutdown signals."""
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_event.set()
            
            # Create a task to shutdown the application
            if self._running:
                asyncio.create_task(self.shutdown_application())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Signal handlers configured")
    
    async def shutdown_application(self) -> None:
        """
        Shutdown the application gracefully.
        
        This method handles the complete application shutdown process,
        including service cleanup and resource deallocation.
        """
        if not self._running:
            logger.info("Application is not running")
            return
            
        logger.info("Shutting down application...")
        
        try:
            # Shutdown bot application
            if self.bot_application:
                try:
                    await self.bot_application.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down bot application: {e}")
            
            # Shutdown service registry
            if self.service_registry:
                try:
                    await self.service_registry.shutdown_services()
                except Exception as e:
                    logger.error(f"Error shutting down service registry: {e}")
            
            logger.info("Application shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            # Don't re-raise here as we're shutting down anyway
        finally:
            self._running = False
    
    @property
    def is_running(self) -> bool:
        """Check if the application is currently running."""
        return self._running
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()


# Main entry point function that will be called from main.py
async def run_application() -> None:
    """
    Main entry point for the application.
    
    This function creates and runs the ApplicationBootstrapper,
    handling any top-level errors and ensuring proper cleanup.
    """
    bootstrapper = ApplicationBootstrapper()
    
    try:
        await bootstrapper.start_application()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed with error: {e}")
        sys.exit(1)
    finally:
        await bootstrapper.shutdown_application()