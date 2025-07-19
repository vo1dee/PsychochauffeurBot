"""
Handler Registry

This module manages the registration and organization of all bot handlers
including commands, message handlers, and callback handlers.
"""

import logging
from typing import List

from telegram.ext import Application
from typing import Any, filters

from modules.service_registry import ServiceInterface, service_registry
from modules.command_processor import CommandProcessor

logger = logging.getLogger(__name__)


class HandlerRegistry(ServiceInterface):
    """
    Central registry for all bot handlers.
    
    Coordinates the registration of commands, message handlers,
    and callback handlers with the Telegram application.
    """
    
    def __init__(self, command_processor: CommandProcessor):
        self.command_processor = command_processor
        self._registered = False
    
    async def initialize(self) -> None:
        """Initialize the handler registry."""
        await self._register_all_commands()
        logger.info("Handler Registry initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the handler registry."""
        logger.info("Handler Registry shutdown")
    
    async def register_all_handlers(self, application: Application) -> None:
        """Register all handlers with the Telegram application."""
        if self._registered:
            logger.warning("Handlers already registered")
            return
        
        # Register message handlers first (group 0)
        await self._register_message_handlers(application)
        
        # Register command handlers
        await self._register_command_handlers(application)
        
        # Register callback handlers
        await self._register_callback_handlers(application)
        
        # Register video handlers (group 1)
        await self._register_video_handlers(application)
        
        self._registered = True
        logger.info("All handlers registered with Telegram application")
    
    async def _register_all_commands(self) -> None:
        """Register all command handlers with the command processor."""
        # Import handler functions
        from modules.handlers.basic_commands import (
            start_command, ping_command, help_command
        )
        from modules.handlers.gpt_commands import (
            ask_gpt_command, analyze_command, mystats_command
        )
        from modules.handlers.utility_commands import (
            cat_command, screenshot_command, count_command, missing_command,
            error_report_command
        )
        from modules.handlers.speech_commands import (
            speech_command
        )
        from modules.handlers.message_handlers import (
            handle_message, handle_photo_analysis, handle_sticker,
            handle_location, handle_voice_or_video_note
        )
        from modules.handlers.callback_handlers import (
            button_callback, speechrec_callback, language_selection_callback
        )
        
        # Register basic commands
        self.command_processor.register_text_command(
            "start", start_command, "Start the bot and show welcome message"
        )
        self.command_processor.register_text_command(
            "help", help_command, "Show help information"
        )
        self.command_processor.register_text_command(
            "ping", ping_command, "Test bot responsiveness"
        )
        
        # Register GPT commands
        self.command_processor.register_text_command(
            "ask", ask_gpt_command, "Ask GPT a question"
        )
        self.command_processor.register_text_command(
            "analyze", analyze_command, "Analyze text with GPT"
        )
        self.command_processor.register_text_command(
            "mystats", mystats_command, "Show your usage statistics"
        )
        
        # Register utility commands
        self.command_processor.register_text_command(
            "cat", cat_command, "Get a random cat photo"
        )
        self.command_processor.register_text_command(
            "flares", screenshot_command, "Get solar flares screenshot"
        )
        self.command_processor.register_text_command(
            "count", count_command, "Count messages in chat"
        )
        self.command_processor.register_text_command(
            "missing", missing_command, "Show missing features"
        )
        self.command_processor.register_text_command(
            "error_report", error_report_command, "Generate error report", admin_only=True
        )
        
        # Register speech commands
        self.command_processor.register_text_command(
            "speech", speech_command, "Toggle speech recognition", admin_only=True
        )
        
        # Register weather and geomagnetic commands
        weather_handler = service_registry.get_service('weather_handler')
        geomagnetic_handler = service_registry.get_service('geomagnetic_handler')
        reminder_manager = service_registry.get_service('reminder_manager')
        
        self.command_processor.register_text_command(
            "weather", weather_handler, "Get weather information"
        )
        self.command_processor.register_text_command(
            "gm", geomagnetic_handler, "Get geomagnetic activity"
        )
        self.command_processor.register_text_command(
            "remind", reminder_manager.remind, "Set a reminder"
        )
        
        # Register message handlers
        self.command_processor.register_message_handler(
            "text_messages", handle_message, filters.TEXT & ~filters.COMMAND,
            "Handle text messages"
        )
        self.command_processor.register_message_handler(
            "photo_messages", handle_photo_analysis, filters.PHOTO,
            "Handle photo messages"
        )
        self.command_processor.register_message_handler(
            "sticker_messages", handle_sticker, filters.Sticker.ALL,
            "Handle sticker messages"
        )
        self.command_processor.register_message_handler(
            "location_messages", handle_location, filters.LOCATION,
            "Handle location messages"
        )
        self.command_processor.register_message_handler(
            "voice_messages", handle_voice_or_video_note, 
            filters.VOICE | filters.VIDEO_NOTE,
            "Handle voice and video note messages"
        )
        
        # Register callback handlers
        self.command_processor.register_callback_handler(
            "button_callbacks", button_callback, description="Handle button callbacks"
        )
        self.command_processor.register_callback_handler(
            "speech_recognition", speechrec_callback, pattern=r"^speechrec_",
            description="Handle speech recognition callbacks"
        )
        self.command_processor.register_callback_handler(
            "language_selection", language_selection_callback, pattern=r"^lang_",
            description="Handle language selection callbacks"
        )
    
    async def _register_message_handlers(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """Register message handlers."""
        # Setup message logging handler first
        message_handler_service = service_registry.get_service('message_handler')
        await message_handler_service.setup_handlers(application)
    
    async def _register_command_handlers(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """Register command handlers."""
        handlers = self.command_processor.get_telegram_handlers()
        for handler in handlers:
            application.add_handler(handler)
        logger.info(f"Registered {len(handlers)} command handlers")
    
    async def _register_callback_handlers(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """Register callback handlers."""
        # Callback handlers are already included in command processor handlers
        pass
    
    async def _register_video_handlers(self, application: Application) -> None:
        """Register video download handlers."""
        video_handler_service = service_registry.get_service('video_handler')
        await video_handler_service.setup_handlers(application)