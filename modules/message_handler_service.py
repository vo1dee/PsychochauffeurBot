"""
Message Handler Service

Provides message handling and logging functionality as a service.
"""

import logging
from telegram.ext import Application

from modules.service_registry import ServiceInterface
from modules.message_handler import setup_message_handlers

logger = logging.getLogger(__name__)


class MessageHandlerService(ServiceInterface):
    """Service for managing message handlers and logging."""
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the message handler service."""
        self._initialized = True
        logger.info("Message Handler Service initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the message handler service."""
        self._initialized = False
        logger.info("Message Handler Service shutdown")
    
    async def setup_handlers(self, application: Application) -> None:
        """Setup message handlers with the Telegram application."""
        if not self._initialized:
            await self.initialize()
        
        setup_message_handlers(application)
        logger.info("Message handlers setup completed")