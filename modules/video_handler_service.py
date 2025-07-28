"""
Video Handler Service

Provides video download handling functionality as a service.
"""

import logging
from typing import Any
from telegram.ext import Application

from modules.service_registry import ServiceInterface
from modules.video_downloader import setup_video_handlers
from modules.url_processor import extract_urls

logger = logging.getLogger(__name__)


class VideoHandlerService(ServiceInterface):
    """Service for managing video download handlers."""
    
    def __init__(self) -> None:
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the video handler service."""
        self._initialized = True
        logger.info("Video Handler Service initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the video handler service."""
        self._initialized = False
        logger.info("Video Handler Service shutdown")
    
    async def setup_handlers(self, application: Application[Any, Any, Any, Any, Any, Any]) -> None:
        """Setup video handlers with the Telegram application."""
        if not self._initialized:
            await self.initialize()
        
        setup_video_handlers(application, extract_urls_func=extract_urls)
        logger.info("Video handlers setup completed")