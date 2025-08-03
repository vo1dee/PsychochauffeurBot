"""
Integration tests for the enhanced BotApplication with specialized service integration.

These tests verify that the BotApplication correctly integrates with specialized
services, handles errors gracefully, and manages service dependencies properly.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from modules.bot_application import BotApplication, ApplicationState
from modules.service_registry import ServiceRegistry
from modules.application_models import ServiceHealth
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.command_registry import CommandRegistry
from modules.callback_handler_service import CallbackHandlerService
from config.config_manager import ConfigManager


class MockService:
    """Mock service for testing."""
    
    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail
        self.initialized = False
        self.shutdown_called = False
        
    async def initialize(self) -> None:
        if self.should_fail:
            raise RuntimeError(f"Mock service {self.name} initialization failed")
        self.initialized = True
        
    async def shutdown(self) -> None:
        self.shutdown_called = True
        
    async def health_check(self) -> Dict[str, Any]:
        return {
            "is_healthy": not self.should_fail,
            "status": "healthy" if not self.should_fail else "unhealthy",
            "error_message": None if not self.should_fail else "Mock error"
        }


@pytest.fixture
def mock_config():
    """Mock configuration."""
    with patch('modules.bot_application.Config') as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        mock_config.ERROR_CHANNEL_ID = "test_channel"
        yield mock_config


@pytest.fixture
def service_registry():
    """Create a service registry with mock services."""
    registry = ServiceRegistry()
    
    # Register mock services
    config_manager = Mock(spec=ConfigManager)
    registry.register_instance('config_manager', config_manager)
    
    message_service = Mock(spec=MessageHandlerService)
    message_service.initialize = AsyncMock()
    message_service.shutdown = AsyncMock()
    registry.register_instance('message_handler_service', message_service)
    
    speech_service = Mock(spec=SpeechRecognitionService)
    speech_service.initialize = AsyncMock()
    speech_service.shutdown = AsyncMock()
    registry.register_instance('speech_recognition_service', speech_service)
    
    command_registry = Mock(spec=CommandRegistry)
    command_registry.initialize = AsyncMock()
    command_registry.shutdown = AsyncMock()
    registry.register_instance('command_registry', command_registry)
    
    callback_service = Mock(spec=CallbackHandlerService)
    callback_service.initialize = AsyncMock()
    callback_service.shutdown = AsyncMock()
    registry.register_instance('callback_handler_service', callback_service)
    
    handler_registry = Mock()
    handler_registry.initialize = AsyncMock()
    handler_registry.shutdown = AsyncMock()
    handler_registry.register_all_handlers = AsyncMock()
    registry.register_instance('handler_registry', handler_registry)
    
    return registry


@pytest.fixture
def bot_application(service_registry):
    """Create a BotApplication instance."""
    return BotApplication(service_registry)


@pytest.mark.asyncio
class TestBotApplicationIntegration:
    """Integration tests for BotApplication."""
    
    async def test_initialization_with_all_services(self, bot_application, mock_config):
        """Test successful initialization with all services."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            assert bot_application.state == ApplicationState.INITIALIZED
            assert bot_application.telegram_app == mock_app
            assert bot_application.bot == mock_bot
            assert len(bot_application.service_health) > 0
            
    async def test_initialization_with_service_failure(self, service_registry, mock_config):
        """Test initialization handling when a service fails."""
        # Add a failing service
        failing_service = MockService("failing_service", should_fail=True)
        service_registry.register_instance('failing_service', failing_service)
        
        bot_application = BotApplication(service_registry)
        
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            # This should raise an error due to the failing service
            with pytest.raises(RuntimeError):
                await bot_application.initialize()
            
            # Application should be in error state
            assert bot_application.state == ApplicationState.ERROR
                
    async def test_service_dependency_management(self, bot_application, mock_config):
        """Test that services are initialized in dependency order."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Verify service registry initialization was called
            bot_application.service_registry.initialize_services = AsyncMock()
            await bot_application._initialize_specialized_services()
            
            # Should have been called to initialize services in dependency order
            bot_application.service_registry.initialize_services.assert_called_once()
            
    async def test_handler_registration_integration(self, bot_application, mock_config):
        """Test that specialized service handlers are registered correctly."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_app.add_handler = Mock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Verify handlers were registered
            assert mock_app.add_handler.call_count > 0
            
    async def test_startup_coordination(self, bot_application, mock_config):
        """Test startup coordination with specialized services."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_app.run_polling = Mock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Mock the polling to avoid blocking and set state properly
            async def mock_polling():
                bot_application._state = ApplicationState.RUNNING
                
            with patch.object(bot_application, '_start_polling_with_recovery', side_effect=mock_polling):
                await bot_application.start()
                
                assert bot_application.state == ApplicationState.RUNNING
                
    async def test_shutdown_coordination(self, bot_application, mock_config):
        """Test shutdown coordination with specialized services."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_app.stop = AsyncMock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            bot_application._state = ApplicationState.RUNNING
            
            # Reset the mock to count only shutdown calls
            mock_app.stop.reset_mock()
            
            await bot_application.shutdown()
            
            assert bot_application.state == ApplicationState.STOPPED
            mock_app.stop.assert_called_once()
            
    async def test_error_handling_and_recovery(self, bot_application, mock_config):
        """Test error handling and recovery mechanisms."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            # Simulate initialization error
            mock_builder.return_value.token.return_value.build.side_effect = RuntimeError("Telegram API error")
            
            with pytest.raises(RuntimeError):
                await bot_application.initialize()
                
            assert bot_application.state == ApplicationState.ERROR
            assert len(bot_application.initialization_errors) > 0
            
    async def test_health_monitoring(self, bot_application, mock_config):
        """Test service health monitoring functionality."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Perform health check
            health_status = await bot_application.perform_health_check()
            
            assert isinstance(health_status, dict)
            assert len(health_status) > 0
            
            # Check service status
            service_status = await bot_application.get_service_status()
            assert "application_state" in service_status
            assert "total_services" in service_status
            assert "healthy_services" in service_status
            
    async def test_service_restart_functionality(self, service_registry, mock_config):
        """Test service restart functionality."""
        # Add a service that can be restarted
        restartable_service = MockService("restartable_service")
        service_registry.register_instance('restartable_service', restartable_service)
        
        bot_application = BotApplication(service_registry)
        
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Restart the service
            result = await bot_application.restart_service('restartable_service')
            
            assert result is True
            assert restartable_service.shutdown_called
            assert restartable_service.initialized
            
    async def test_enhanced_notifications(self, bot_application, mock_config):
        """Test enhanced startup and shutdown notifications."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Test startup notification
            await bot_application._send_enhanced_startup_notification()
            mock_bot.send_message.assert_called()
            
            # Verify notification contains service status
            call_args = mock_bot.send_message.call_args
            if call_args and len(call_args) > 1 and 'text' in call_args[1]:
                message_text = call_args[1]['text']
                assert "Enhanced Bot Started Successfully" in message_text
                assert "Service Status" in message_text
            
    async def test_signal_handling_integration(self, bot_application, mock_config):
        """Test enhanced signal handling integration."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            bot_application._state = ApplicationState.RUNNING
            
            # Setup signal handlers
            bot_application._setup_enhanced_signal_handlers()
            
            # Simulate signal
            import signal
            with patch('signal.signal') as mock_signal:
                bot_application._setup_enhanced_signal_handlers()
                
                # Verify signal handlers were registered
                assert mock_signal.call_count >= 2  # SIGINT and SIGTERM
                
    async def test_polling_recovery_mechanism(self, bot_application, mock_config):
        """Test polling recovery mechanism."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_app.run_polling = Mock(side_effect=RuntimeError("Polling error"))
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            await bot_application.initialize()
            
            # Mock asyncio.sleep to speed up the test
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Test recovery attempt - should eventually raise after max attempts
                with pytest.raises(RuntimeError, match="Maximum recovery attempts exceeded"):
                    await bot_application._start_polling_with_recovery()
                    
                # Verify recovery attempts were tracked
                assert "polling" in bot_application._recovery_attempts
                assert bot_application._recovery_attempts["polling"] == bot_application._max_recovery_attempts
            
    async def test_service_integration_error_boundaries(self, bot_application, mock_config):
        """Test that service integration has proper error boundaries."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock()
            mock_bot = Mock()
            mock_app.bot = mock_bot
            mock_app.add_handler = Mock(side_effect=RuntimeError("Handler registration failed"))
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            # Should not fail completely due to handler registration error
            await bot_application.initialize()
            
            # Application should still be initialized despite handler errors
            assert bot_application.state == ApplicationState.INITIALIZED
            
    async def test_configuration_validation(self, service_registry):
        """Test configuration validation during initialization."""
        bot_application = BotApplication(service_registry)
        
        # Test with missing token
        with patch('modules.bot_application.Config') as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = ""
            mock_config.ERROR_CHANNEL_ID = "test_channel"
            
            with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN is not set"):
                await bot_application.initialize()
                
    async def test_partial_initialization_cleanup(self, service_registry):
        """Test cleanup when initialization fails partway through."""
        bot_application = BotApplication(service_registry)
        
        with patch('modules.bot_application.Config') as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "test_token"
            mock_config.ERROR_CHANNEL_ID = "test_channel"
            
            with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
                # Fail during Telegram app creation
                mock_builder.side_effect = RuntimeError("API error")
                
                with pytest.raises(RuntimeError):
                    await bot_application.initialize()
                    
                # Verify cleanup was attempted
                assert bot_application.state == ApplicationState.ERROR
                assert len(bot_application._service_health) == 0