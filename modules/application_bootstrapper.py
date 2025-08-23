"""
Application Bootstrapper

This module provides the ApplicationBootstrapper class that serves as the
minimal entry point for the bot application. It handles service configuration,
lifecycle management, and application orchestration.
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Optional, Any

from modules.service_registry import ServiceRegistry, ServiceInterface, ServiceScope
from modules.application_models import ServiceConfiguration
from modules.const import Config
from modules.logger import general_logger, error_logger
from config.config_manager import ConfigManager
from modules.bot_application import BotApplication
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.command_registry import CommandRegistry

# Create component-specific logger with clear service identification
logger = logging.getLogger('application_bootstrapper')
logger.setLevel(logging.INFO)


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
        self._signal_received = False
        self._shutting_down = False
        
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
        logger.info("Configuring services with enhanced configuration integration...")
        
        try:
            # Create service registry
            service_registry = ServiceRegistry()
            
            # Create service configuration
            service_config = ServiceConfiguration(
                telegram_token=Config.TELEGRAM_BOT_TOKEN,
                error_channel_id=Config.ERROR_CHANNEL_ID if Config.ERROR_CHANNEL_ID else None,
                debug_mode=getattr(Config, 'DEBUG_MODE', False)
            )
            
            # Register core configuration
            service_registry.register_instance('service_config', service_config)
            logger.debug("Service configuration registered in service registry")
            
            # Import and register core services
            from config.config_manager import ConfigManager
            from modules.database import Database
            from modules.bot_application import BotApplication
            
            # Register configuration manager as singleton with initialization
            service_registry.register_singleton(
                'config_manager',
                ConfigManager,
                ConfigManager
            )
            logger.info("ConfigManager registered as singleton service")
            
            # Initialize configuration manager to ensure it's ready
            config_manager = service_registry.get_service('config_manager')
            if hasattr(config_manager, 'initialize'):
                await config_manager.initialize()
            logger.info("ConfigManager initialized successfully")
            
            # Verify config_manager is properly registered and accessible
            if not service_registry.is_registered('config_manager'):
                raise RuntimeError("ConfigManager failed to register properly")
            
            # Test config_manager access
            test_config_manager = service_registry.get_service('config_manager')
            logger.info(f"ConfigManager verification successful: {type(test_config_manager).__name__}")
            
            # Register database as singleton
            service_registry.register_singleton(
                'database',
                Database,
                Database
            )
            logger.debug("Database service registered")
            
            # Register bot application as singleton with service registry dependency
            from modules.service_factories import ServiceFactory
            service_registry.register_factory(
                'bot_application',
                BotApplication,
                ServiceFactory.create_bot_application,
                dependencies=['config_manager', 'database']
            )
            logger.debug("BotApplication registered with dependencies")
            
            # Register additional services that will be needed
            await self._register_specialized_services(service_registry)
            
            logger.info("Services configured successfully with configuration integration")
            return service_registry
            
        except Exception as e:
            logger.error(f"Failed to configure services: {e}", exc_info=True)
            raise RuntimeError(f"Service configuration failed: {e}") from e
    
    async def _register_specialized_services(self, service_registry: ServiceRegistry) -> None:
        """
        Register specialized services with proper dependency injection using service factories.
        
        This method registers all services with their dependencies properly configured
        to ensure proper initialization order and dependency resolution.
        
        Args:
            service_registry: The service registry to register services with
        """
        logger.info("Registering specialized services with dependency injection...")
        
        from modules.service_factories import ServiceFactory
        
        # Register utility services first (no dependencies)
        try:
            service_registry.register_factory(
                'message_counter',
                type(None),  # Placeholder type
                ServiceFactory.create_message_counter,
                scope=ServiceScope.SINGLETON
            )
        except ImportError:
            logger.warning("MessageCounter not available, skipping registration")
        
        # Register chat history manager
        try:
            from modules.utils import chat_history_manager
            service_registry.register_instance('chat_history_manager', chat_history_manager)
            logger.info("ChatHistoryManager registered successfully")
        except ImportError as e:
            logger.warning(f"ChatHistoryManager not available, skipping registration: {e}")
        except Exception as e:
            logger.error(f"Failed to register ChatHistoryManager: {e}", exc_info=True)
        
        try:
            from modules.safety import safety_manager
            service_registry.register_instance('safety_manager', safety_manager)
        except ImportError:
            logger.warning("Safety manager not available, skipping registration")
        
        # Register command processor (no dependencies)
        try:
            service_registry.register_factory(
                'command_processor',
                type(None),  # Placeholder type
                ServiceFactory.create_command_processor,
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"CommandProcessor not available, skipping registration: {e}")
        
        # Register services with config_manager dependency
        try:
            service_registry.register_factory(
                'message_handler_service',
                type(None),  # Placeholder type
                ServiceFactory.create_message_handler_service,
                dependencies=['config_manager', 'message_counter'],
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"MessageHandlerService not available, skipping registration: {e}")
        
        try:
            service_registry.register_factory(
                'speech_recognition_service',
                type(None),  # Placeholder type
                ServiceFactory.create_speech_recognition_service,
                dependencies=['config_manager'],
                scope=ServiceScope.SINGLETON
            )
            logger.info("SpeechRecognitionService factory registered successfully")
            
            # Test that the service can actually be created
            test_service = service_registry.get_service('speech_recognition_service')
            logger.info(f"SpeechRecognitionService created successfully: {type(test_service).__name__}")
            
        except ImportError as e:
            logger.warning(f"SpeechRecognitionService not available, skipping registration: {e}")
        except Exception as e:
            logger.error(f"Failed to register SpeechRecognitionService: {e}", exc_info=True)
        
        # Register services with command_processor dependency
        try:
            service_registry.register_factory(
                'command_registry',
                type(None),  # Placeholder type
                ServiceFactory.create_command_registry,
                dependencies=['command_processor'],
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"CommandRegistry not available, skipping registration: {e}")
        
        try:
            service_registry.register_factory(
                'handler_registry',
                type(None),  # Placeholder type
                ServiceFactory.create_handler_registry,
                dependencies=['command_processor'],
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"HandlerRegistry not available, skipping registration: {e}")
        
        # Register services with speech_recognition_service dependency
        try:
            service_registry.register_factory(
                'callback_handler_service',
                type(None),  # Placeholder type
                ServiceFactory.create_callback_handler_service,
                dependencies=['speech_recognition_service'],
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"CallbackHandlerService not available, skipping registration: {e}")
        
        # Register domain-specific handlers (no dependencies)
        try:
            service_registry.register_factory(
                'weather_handler',
                type(None),  # Placeholder type
                ServiceFactory.create_weather_handler,
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"WeatherCommandHandler not available, skipping registration: {e}")
        
        try:
            service_registry.register_factory(
                'geomagnetic_handler',
                type(None),  # Placeholder type
                ServiceFactory.create_geomagnetic_handler,
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"GeomagneticCommandHandler not available, skipping registration: {e}")
        
        # Register reminder manager (no dependencies for now)
        try:
            service_registry.register_factory(
                'reminder_manager',
                type(None),  # Placeholder type
                ServiceFactory.create_reminder_manager,
                scope=ServiceScope.SINGLETON
            )
        except ImportError:
            logger.warning("ReminderManager not available, skipping registration")
        
        # Register service error boundary for centralized error handling
        try:
            service_registry.register_factory(
                'service_error_boundary',
                type(None),  # Placeholder type
                ServiceFactory.create_service_error_boundary,
                scope=ServiceScope.SINGLETON
            )
        except ImportError as e:
            logger.warning(f"ServiceErrorBoundary not available, skipping registration: {e}")
        
        # Register user leveling service with config_manager and database dependencies
        try:
            service_registry.register_factory(
                'user_leveling_service',
                type(None),  # Placeholder type
                ServiceFactory.create_user_leveling_service,
                dependencies=['config_manager', 'database'],
                scope=ServiceScope.SINGLETON
            )
            logger.info("UserLevelingService factory registered successfully")
        except ImportError as e:
            logger.warning(f"UserLevelingService not available, skipping registration: {e}")
        except Exception as e:
            logger.error(f"Failed to register UserLevelingService: {e}", exc_info=True)
        
        logger.info("Specialized services registered with dependency injection using service factories")
    
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
            # Configure services first
            self.service_registry = await self.configure_services()
            
            # Get bot application service
            self.bot_application = self.service_registry.get_service('bot_application')
            
            if not self.bot_application:
                raise RuntimeError("Bot application service not found in registry")
            
            # Setup signal handlers before initializing
            self.setup_signal_handlers()
            
            # Initialize the bot application
            await self.bot_application.initialize()
            
            # Mark as running
            self._running = True
            
            # Start the bot application
            if hasattr(self.bot_application, 'start'):
                await self.bot_application.start()
                logger.info("Application started successfully")
            else:
                logger.error("Bot application does not have a start method")
            
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
            """Handle shutdown signals gracefully."""
            if signum == signal.SIGINT:
                signal_name = "SIGINT (Ctrl+C)"
            elif signum == signal.SIGTERM:
                signal_name = "SIGTERM"
            else:
                signal_name = f"Signal {signum}"
            
            logger.info(f"Received signal {signum}, forcing immediate exit...")
            
            # Force exit immediately - no graceful shutdown
            logger.warning("Signal received, exiting immediately...")
            os._exit(0)
        
        # Store the signal handler for testing
        self._signal_handler_func = signal_handler
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers configured for graceful shutdown")
    
    def _create_service_configuration(self) -> Any:
        """Create service configuration from environment variables."""
        from dataclasses import dataclass
        
        @dataclass
        class ServiceConfiguration:
            telegram_token: str
            error_channel_id: str
            database_url: str
            redis_url: str
            debug_mode: bool
        
        # Get environment variables
        telegram_token = os.getenv('TELEGRAM_TOKEN', '')
        error_channel_id = os.getenv('ERROR_CHANNEL_ID', '')
        database_url = os.getenv('DATABASE_URL', '')
        redis_url = os.getenv('REDIS_URL', '')
        debug_mode_str = os.getenv('DEBUG_MODE', 'false').lower()
        
        # Validate required fields
        if not telegram_token:
            raise ValueError("TELEGRAM_TOKEN cannot be empty")
        
        # Parse debug mode
        debug_mode = debug_mode_str in ('true', '1', 'yes', 'on')
        
        return ServiceConfiguration(
            telegram_token=telegram_token,
            error_channel_id=error_channel_id,
            database_url=database_url,
            redis_url=redis_url,
            debug_mode=debug_mode
        )
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        self._shutdown_gracefully()
    
    def _shutdown_gracefully(self) -> None:
        """Initiate graceful shutdown."""
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()
            # Create shutdown task
            asyncio.create_task(self.shutdown_application())
    
    async def shutdown_application(self) -> None:
        """
        Shutdown the application gracefully with timeout protection.
        
        This method handles the complete application shutdown process,
        including service cleanup and resource deallocation.
        """
        if not self._running:
            logger.info("Application is not running, skipping shutdown")
            return
            
        # Prevent multiple shutdown attempts
        if hasattr(self, '_shutting_down') and self._shutting_down:
            logger.info("Shutdown already in progress, waiting for completion...")
            return
            
        self._shutting_down = True
        logger.info("Starting graceful application shutdown...")
        
        shutdown_start_time = asyncio.get_event_loop().time()
        
        try:
            # Shutdown bot application first
            if self.bot_application:
                try:
                    logger.info("Shutting down bot application...")
                    await asyncio.wait_for(self.bot_application.shutdown(), timeout=10.0)
                    logger.info("Bot application shutdown completed")
                except asyncio.TimeoutError:
                    logger.warning("Bot application shutdown timed out, forcing cleanup...")
                    # Force cleanup if timeout
                    if hasattr(self.bot_application, '_force_cleanup'):
                        try:
                            await asyncio.wait_for(self.bot_application._force_cleanup(), timeout=2.0)
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Error shutting down bot application: {e}")
            
            # Always shutdown service registry if it exists
            if self.service_registry:
                try:
                    logger.info("Shutting down service registry...")
                    await asyncio.wait_for(self.service_registry.shutdown_services(), timeout=3.0)
                    logger.info("Service registry shutdown completed")
                except asyncio.TimeoutError:
                    logger.warning("Service registry shutdown timed out")
                except Exception as e:
                    logger.error(f"Error shutting down service registry: {e}")
            
            shutdown_duration = asyncio.get_event_loop().time() - shutdown_start_time
            logger.info(f"Application shutdown completed successfully in {shutdown_duration:.2f}s")
                
        except Exception as e:
            shutdown_duration = asyncio.get_event_loop().time() - shutdown_start_time
            logger.error(f"Error during application shutdown after {shutdown_duration:.2f}s: {e}")
            # Don't re-raise here as we're shutting down anyway
        finally:
            self._running = False
            self._shutting_down = False
            logger.info("Application shutdown process completed")
    
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
