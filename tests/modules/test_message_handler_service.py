"""
Tests for modules/message_handler_service.py

This module tests the MessageHandlerService class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from telegram.ext import Application

from modules.message_handler_service import MessageHandlerService
from config.config_manager import ConfigManager


class TestMessageHandlerService:
    """Test MessageHandlerService class."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock ConfigManager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock()
        config_manager.save_config = AsyncMock()
        return config_manager

    @pytest.fixture
    def service(self, mock_config_manager):
        """Create a MessageHandlerService instance for testing."""
        return MessageHandlerService(config_manager=mock_config_manager)

    @pytest.fixture
    def mock_application(self):
        """Create a mock Telegram application."""
        return MagicMock(spec=Application)

    def test_init(self, service):
        """Test MessageHandlerService initialization."""
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self, service):
        """Test service initialization."""
        await service.initialize()
        assert service._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self, service):
        """Test service shutdown."""
        # Initialize first
        await service.initialize()
        assert service._initialized is True
        
        # Then shutdown
        await service.shutdown()
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_when_not_initialized(self, service):
        """Test shutdown when service was never initialized."""
        await service.shutdown()
        assert service._initialized is False



    @pytest.mark.asyncio
    async def test_service_lifecycle(self, service, mock_application):
        """Test complete service lifecycle."""
        # Start uninitialized
        assert service._initialized is False
        
        # Initialize
        await service.initialize()
        assert service._initialized is True
        
        # Shutdown
        await service.shutdown()
        assert service._initialized is False
        
        # Re-initialize
        await service.initialize()
        assert service._initialized is True