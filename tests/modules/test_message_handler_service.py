"""
Tests for modules/message_handler_service.py

This module tests the MessageHandlerService class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.ext import Application

from modules.message_handler_service import MessageHandlerService


class TestMessageHandlerService:
    """Test MessageHandlerService class."""

    @pytest.fixture
    def service(self):
        """Create a MessageHandlerService instance for testing."""
        return MessageHandlerService()

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
    @patch('modules.message_handler_service.setup_message_handlers')
    async def test_setup_handlers_when_initialized(self, mock_setup_message_handlers, service, mock_application):
        """Test setup_handlers when service is already initialized."""
        # Initialize service first
        await service.initialize()
        
        # Setup handlers
        await service.setup_handlers(mock_application)
        
        # Verify setup_message_handlers was called with correct parameters
        mock_setup_message_handlers.assert_called_once_with(mock_application)

    @pytest.mark.asyncio
    @patch('modules.message_handler_service.setup_message_handlers')
    async def test_setup_handlers_when_not_initialized(self, mock_setup_message_handlers, service, mock_application):
        """Test setup_handlers when service is not initialized."""
        # Don't initialize service
        assert service._initialized is False
        
        # Setup handlers should auto-initialize
        await service.setup_handlers(mock_application)
        
        # Verify service was initialized
        assert service._initialized is True
        
        # Verify setup_message_handlers was called
        mock_setup_message_handlers.assert_called_once_with(mock_application)

    @pytest.mark.asyncio
    @patch('modules.message_handler_service.setup_message_handlers')
    async def test_setup_handlers_multiple_calls(self, mock_setup_message_handlers, service, mock_application):
        """Test multiple calls to setup_handlers."""
        # First call
        await service.setup_handlers(mock_application)
        assert service._initialized is True
        
        # Second call
        await service.setup_handlers(mock_application)
        assert service._initialized is True
        
        # Verify setup_message_handlers was called twice
        assert mock_setup_message_handlers.call_count == 2

    @pytest.mark.asyncio
    @patch('modules.message_handler_service.setup_message_handlers', side_effect=Exception("Setup failed"))
    async def test_setup_handlers_with_exception(self, mock_setup_message_handlers, service, mock_application):
        """Test setup_handlers when setup_message_handlers raises an exception."""
        with pytest.raises(Exception, match="Setup failed"):
            await service.setup_handlers(mock_application)
        
        # Service should still be initialized even if setup fails
        assert service._initialized is True

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