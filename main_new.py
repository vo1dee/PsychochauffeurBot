"""
Main entry point for the PsychoChauffeur Telegram bot.

This is the refactored version using service registry and dependency injection
with comprehensive type annotations and performance monitoring.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, NoReturn

# Apply nest_asyncio at the very beginning
import nest_asyncio
nest_asyncio.apply()

# Local imports
from modules.service_registry import service_registry
from modules.bot_application import BotApplication
from modules.command_processor import CommandProcessor
from modules.handler_registry import HandlerRegistry
from modules.logger import general_logger, error_logger, init_telegram_error_handler, shutdown_logging
from modules.utils import init_directories, MessageCounter, chat_history_manager
from modules.database import Database
from modules.reminders.reminders import ReminderManager
from modules.safety import safety_manager
from modules.weather import WeatherCommandHandler
from modules.geomagnetic import GeomagneticCommandHandler
from modules.message_handler_service import MessageHandlerService
from modules.video_handler_service import VideoHandlerService
from config.config_manager import ConfigManager
from modules.const import Config
from modules.performance_monitor import performance_monitor, monitor_performance
from modules.memory_optimizer import memory_optimizer
from modules.types import ServiceInstance
from modules.shared_constants import APP_NAME, APP_VERSION
from telegram import Bot

logger = logging.getLogger(__name__)


@monitor_performance("register_core_services")
async def register_core_services() -> None:
    """Register all core services with the service registry."""
    logger.info(f"Registering core services for {APP_NAME} v{APP_VERSION}...")
    
    # Register configuration manager
    config_manager: ConfigManager = ConfigManager()
    service_registry.register_instance('config_manager', config_manager)
    
    # Register database
    service_registry.register_singleton('database', Database)
    
    # Register utility services
    message_counter: MessageCounter = MessageCounter()
    service_registry.register_instance('message_counter', message_counter)
    service_registry.register_instance('chat_history_manager', chat_history_manager)
    
    # Register reminder manager
    reminder_manager: ReminderManager = ReminderManager()
    service_registry.register_instance('reminder_manager', reminder_manager)
    
    # Register safety manager
    service_registry.register_instance('safety_manager', safety_manager)
    
    # Register weather handler
    weather_handler: WeatherCommandHandler = WeatherCommandHandler()
    service_registry.register_instance('weather_handler', weather_handler)
    
    # Register geomagnetic handler
    geomagnetic_handler: GeomagneticCommandHandler = GeomagneticCommandHandler()
    service_registry.register_instance('geomagnetic_handler', geomagnetic_handler)
    
    # Register command processor
    command_processor: CommandProcessor = CommandProcessor()
    service_registry.register_instance('command_processor', command_processor)
    
    # Register message handler service
    message_handler_service: MessageHandlerService = MessageHandlerService()
    service_registry.register_instance('message_handler', message_handler_service)
    
    # Register video handler service
    video_handler_service: VideoHandlerService = VideoHandlerService()
    service_registry.register_instance('video_handler', video_handler_service)
    
    # Register handler registry
    handler_registry: HandlerRegistry = HandlerRegistry(command_processor)
    service_registry.register_instance('handler_registry', handler_registry)
    
    # Register bot application
    bot_app: BotApplication = BotApplication(service_registry)
    service_registry.register_instance('bot_application', bot_app)
    
    # Register performance monitoring services
    service_registry.register_instance('performance_monitor', performance_monitor)
    service_registry.register_instance('memory_optimizer', memory_optimizer)
    
    logger.info("Core services registered successfully")


@monitor_performance("initialize_application")
async def initialize_application() -> None:
    """Initialize the entire application with performance monitoring."""
    logger.info("Initializing application...")
    
    try:
        # Initialize directories
        init_directories()
        
        # Start performance monitoring
        await performance_monitor.start_monitoring(interval=60)
        await memory_optimizer.start_monitoring(interval=120)
        
        # Register all services
        await register_core_services()
        
        # Create Bot instance and initialize error handler
        bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        await init_telegram_error_handler(bot, Config.ERROR_CHANNEL_ID)
        
        # Initialize all services through service registry
        await service_registry.initialize_services()
        
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


@monitor_performance("run_application")
async def run_application() -> None:
    """Run the main application with comprehensive monitoring."""
    try:
        # Initialize application
        await initialize_application()
        
        # Get bot application and start it
        bot_app: BotApplication = service_registry.get_service('bot_application')
        await bot_app.start()
        
    except (SystemExit, KeyboardInterrupt):
        logger.info("Application stopped by user or system signal")
    except Exception as e:
        logger.error(f"Application stopped due to unhandled exception: {e}", exc_info=True)
    finally:
        # Cleanup
        await cleanup_application()


@monitor_performance("cleanup_application")
async def cleanup_application() -> None:
    """Cleanup all application components with monitoring."""
    logger.info("Cleaning up application...")
    
    try:
        # Stop performance monitoring
        await performance_monitor.stop_monitoring()
        await memory_optimizer.stop_monitoring()
        
        # Shutdown all services
        await service_registry.shutdown_services()
        
        # Shutdown logging
        await shutdown_logging()
        
        logger.info("Application cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)


def main() -> NoReturn:
    """Main entry point with proper type annotations."""
    if not Config.TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set. The bot cannot start.")
        sys.exit(1)
    
    try:
        logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
        # Run the application
        asyncio.run(run_application())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()