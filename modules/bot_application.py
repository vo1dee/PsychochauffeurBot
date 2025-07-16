"""
Bot Application Orchestrator

This module provides the main application class that orchestrates
the entire bot lifecycle and manages all components.
"""

import asyncio
import logging
import signal
from datetime import datetime
from typing import Optional

from telegram import Bot, Update
from telegram.ext import Application, ApplicationBuilder

from modules.service_registry import ServiceRegistry, ServiceInterface
from modules.const import Config, KYIV_TZ
from modules.logger import general_logger, error_logger

logger = logging.getLogger(__name__)


class BotApplication(ServiceInterface):
    """
    Main bot application orchestrator.
    
    Manages the entire bot lifecycle including initialization,
    startup, shutdown, and component coordination.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.telegram_app: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self._shutdown_event = asyncio.Event()
        self._running = False
        
    async def initialize(self) -> None:
        """Initialize the bot application and all components."""
        logger.info("Initializing Bot Application...")
        
        try:
            # Validate configuration
            if not Config.TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN is not set")
            
            # Create Telegram application
            self.telegram_app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
            self.bot = self.telegram_app.bot
            
            # Register bot instance in service registry
            self.service_registry.register_instance('telegram_bot', self.bot)
            self.service_registry.register_instance('telegram_app', self.telegram_app)
            
            # Initialize all services
            await self.service_registry.initialize_services()
            
            # Register handlers
            await self._register_handlers()
            
            logger.info("Bot Application initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Bot Application: {e}")
            raise
    
    async def start(self) -> None:
        """Start the bot application."""
        if self._running:
            logger.warning("Bot Application is already running")
            return
            
        logger.info("Starting Bot Application...")
        
        try:
            self._running = True
            
            # Send startup notification
            await self._send_startup_notification()
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Start polling
            logger.info("Bot polling started")
            await self.telegram_app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                stop_signals=None  # We handle signals ourselves
            )
            
        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
            raise
        finally:
            self._running = False
    
    async def shutdown(self) -> None:
        """Shutdown the bot application gracefully."""
        if not self._running:
            logger.info("Bot Application is not running")
            return
            
        logger.info("Shutting down Bot Application...")
        
        try:
            # Stop polling
            if self.telegram_app:
                await self.telegram_app.stop()
            
            # Shutdown all services
            await self.service_registry.shutdown_services()
            
            # Send shutdown notification
            await self._send_shutdown_notification()
            
            self._running = False
            logger.info("Bot Application shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _register_handlers(self) -> None:
        """Register all command and message handlers."""
        # Get handler registry service
        handler_registry = self.service_registry.get_service('handler_registry')
        await handler_registry.register_all_handlers(self.telegram_app)
    
    async def _send_startup_notification(self) -> None:
        """Send startup notification to error channel."""
        try:
            if not Config.ERROR_CHANNEL_ID:
                return
                
            startup_time = datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
            startup_message = (
                "🚀 *Bot Started Successfully*\\n\\n"
                f"*Time:* `{startup_time}`\\n"
                "*Status:* `Online`\\n"
                "*Components:* All services initialized ✅"
            )
            
            # Parse channel ID and topic ID
            if ':' in Config.ERROR_CHANNEL_ID:
                channel_id, topic_id = Config.ERROR_CHANNEL_ID.split(':')
                message_params = {
                    'chat_id': channel_id,
                    'text': startup_message,
                    'parse_mode': 'MarkdownV2',
                    'message_thread_id': int(topic_id)
                }
            else:
                message_params = {
                    'chat_id': Config.ERROR_CHANNEL_ID,
                    'text': startup_message,
                    'parse_mode': 'MarkdownV2'
                }
                
            await self.bot.send_message(**message_params)
            
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")
    
    async def _send_shutdown_notification(self) -> None:
        """Send shutdown notification to error channel."""
        try:
            if not Config.ERROR_CHANNEL_ID or not self.bot:
                return
                
            shutdown_time = datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
            shutdown_message = (
                "🛑 *Bot Shutdown*\\n\\n"
                f"*Time:* `{shutdown_time}`\\n"
                "*Status:* `Offline`"
            )
            
            # Parse channel ID and topic ID
            if ':' in Config.ERROR_CHANNEL_ID:
                channel_id, topic_id = Config.ERROR_CHANNEL_ID.split(':')
                message_params = {
                    'chat_id': channel_id,
                    'text': shutdown_message,
                    'parse_mode': 'MarkdownV2',
                    'message_thread_id': int(topic_id)
                }
            else:
                message_params = {
                    'chat_id': Config.ERROR_CHANNEL_ID,
                    'text': shutdown_message,
                    'parse_mode': 'MarkdownV2'
                }
                
            await self.bot.send_message(**message_params)
            
        except Exception as e:
            logger.error(f"Failed to send shutdown notification: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    @property
    def is_running(self) -> bool:
        """Check if the bot application is running."""
        return self._running