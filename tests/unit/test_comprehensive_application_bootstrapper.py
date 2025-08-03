"""
Comprehensive unit tests for ApplicationBootstrapper.
Ensures 90% coverage target for the bootstrapper component.
"""

import pytest
import asyncio
import signal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry
from modules.bot_application import BotApplication
from modules.application_models import ServiceConfiguration


class TestApplicationBootstrapperComprehensive:
    """Comprehensive tests for ApplicationBootstrapper."""

    @pytest.fixture
    def bootstrapper(self):
        """Create ApplicationBootstrapper instance for testing."""
        return ApplicationBootstrapper()

    @pytest.fixture
    def mock_service_registry(self):
        """Create mock service registry."""
        registry = Mock(spec=ServiceRegistry)
        registry.initialize_all_services = AsyncMock()
        registry.shutdown_all_services = AsyncMock()
        registry.get_service = Mock()
        return registry

    @pytest.fixture
    def mock_bot_application(self):
        """Create mock bot application."""
        app = Mock(spec=BotApplication)
        app.initialize = AsyncMock()
        app.start = AsyncMock()
        app.shutdown = AsyncMock()
        app.is_running = False
        return app

    @pytest.fixture
    def service_config(self):
        """Create service configuration for testing."""
        return ServiceConfiguration(
            telegram_token="test_token",
            error_channel_id="test_channel",
            database_url="sqlite:///test.db",
            redis_url="redis://localhost:6379",
            debug_mode=True
        )

    @pytest.mark.asyncio
    async def test_initialization_success(self, bootstrapper):
        """Test successful initialization."""
        assert bootstrapper.service_registry is None
        assert bootstrapper.bot_application is None
        assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_configure_services_success(self, bootstrapper, service_config):
        """Test successful service configuration."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': service_config.telegram_token,
            'ERROR_CHANNEL_ID': service_config.error_channel_id,
            'DATABASE_URL': service_config.database_url,
            'REDIS_URL': service_config.redis_url,
            'DEBUG_MODE': 'true'
        }):
            with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class:
                mock_registry = Mock(spec=ServiceRegistry)
                mock_registry.register_service = Mock()
                mock_registry_class.return_value = mock_registry
                
                registry = await bootstrapper.configure_services()
                
                assert registry is not None
                assert bootstrapper.service_registry == registry
                mock_registry_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_services_missing_token(self, bootstrapper):
        """Test service configuration with missing token."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="TELEGRAM_TOKEN environment variable is required"):
                await bootstrapper.configure_services()

    @pytest.mark.asyncio
    async def test_configure_services_missing_error_channel(self, bootstrapper):
        """Test service configuration with missing error channel."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token'
        }, clear=True):
            with pytest.raises(ValueError, match="ERROR_CHANNEL_ID environment variable is required"):
                await bootstrapper.configure_services()

    @pytest.mark.asyncio
    async def test_configure_services_with_defaults(self, bootstrapper):
        """Test service configuration with default values."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': 'test_channel'
        }, clear=True):
            with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class:
                mock_registry = Mock(spec=ServiceRegistry)
                mock_registry.register_service = Mock()
                mock_registry_class.return_value = mock_registry
                
                registry = await bootstrapper.configure_services()
                
                assert registry is not None
                # Verify default values are used
                mock_registry.register_service.assert_called()

    @pytest.mark.asyncio
    async def test_start_application_success(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test successful application startup."""
        bootstrapper.service_registry = mock_service_registry
        mock_service_registry.get_service.return_value = mock_bot_application
        
        with patch.object(bootstrapper, 'setup_signal_handlers') as mock_setup_signals:
            await bootstrapper.start_application()
            
            mock_service_registry.initialize_all_services.assert_called_once()
            mock_bot_application.initialize.assert_called_once()
            mock_bot_application.start.assert_called_once()
            mock_setup_signals.assert_called_once()
            assert bootstrapper.bot_application == mock_bot_application
            assert bootstrapper.is_running is True

    @pytest.mark.asyncio
    async def test_start_application_no_registry(self, bootstrapper):
        """Test application startup without configured registry."""
        with pytest.raises(RuntimeError, match="Service registry not configured"):
            await bootstrapper.start_application()

    @pytest.mark.asyncio
    async def test_start_application_already_running(self, bootstrapper, mock_service_registry):
        """Test application startup when already running."""
        bootstrapper.service_registry = mock_service_registry
        bootstrapper.is_running = True
        
        with pytest.raises(RuntimeError, match="Application is already running"):
            await bootstrapper.start_application()

    @pytest.mark.asyncio
    async def test_start_application_initialization_failure(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test application startup with initialization failure."""
        bootstrapper.service_registry = mock_service_registry
        mock_service_registry.get_service.return_value = mock_bot_application
        mock_service_registry.initialize_all_services.side_effect = Exception("Init failed")
        
        with pytest.raises(Exception, match="Init failed"):
            await bootstrapper.start_application()
        
        assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_start_application_bot_start_failure(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test application startup with bot start failure."""
        bootstrapper.service_registry = mock_service_registry
        mock_service_registry.get_service.return_value = mock_bot_application
        mock_bot_application.start.side_effect = Exception("Start failed")
        
        with pytest.raises(Exception, match="Start failed"):
            await bootstrapper.start_application()
        
        assert bootstrapper.is_running is False

    def test_setup_signal_handlers(self, bootstrapper):
        """Test signal handler setup."""
        with patch('signal.signal') as mock_signal:
            bootstrapper.setup_signal_handlers()
            
            # Verify signal handlers are set up
            expected_calls = [
                ((signal.SIGINT, bootstrapper._signal_handler),),
                ((signal.SIGTERM, bootstrapper._signal_handler),)
            ]
            
            for expected_call in expected_calls:
                assert expected_call in mock_signal.call_args_list

    def test_signal_handler_sigint(self, bootstrapper):
        """Test SIGINT signal handling."""
        with patch.object(bootstrapper, '_shutdown_gracefully') as mock_shutdown:
            bootstrapper._signal_handler(signal.SIGINT, None)
            mock_shutdown.assert_called_once()

    def test_signal_handler_sigterm(self, bootstrapper):
        """Test SIGTERM signal handling."""
        with patch.object(bootstrapper, '_shutdown_gracefully') as mock_shutdown:
            bootstrapper._signal_handler(signal.SIGTERM, None)
            mock_shutdown.assert_called_once()

    def test_signal_handler_unknown_signal(self, bootstrapper):
        """Test handling of unknown signals."""
        with patch.object(bootstrapper, '_shutdown_gracefully') as mock_shutdown:
            bootstrapper._signal_handler(signal.SIGUSR1, None)
            mock_shutdown.assert_called_once()

    def test_shutdown_gracefully(self, bootstrapper):
        """Test graceful shutdown initiation."""
        with patch('asyncio.create_task') as mock_create_task:
            bootstrapper._shutdown_gracefully()
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_application_success(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test successful application shutdown."""
        bootstrapper.service_registry = mock_service_registry
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.is_running = True
        
        await bootstrapper.shutdown_application()
        
        mock_bot_application.shutdown.assert_called_once()
        mock_service_registry.shutdown_all_services.assert_called_once()
        assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_application_not_running(self, bootstrapper):
        """Test shutdown when application is not running."""
        bootstrapper.is_running = False
        
        # Should not raise an exception
        await bootstrapper.shutdown_application()
        
        assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_application_bot_shutdown_failure(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test shutdown with bot shutdown failure."""
        bootstrapper.service_registry = mock_service_registry
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.is_running = True
        mock_bot_application.shutdown.side_effect = Exception("Shutdown failed")
        
        with patch('modules.application_bootstrapper.logger') as mock_logger:
            await bootstrapper.shutdown_application()
            
            mock_logger.error.assert_called()
            mock_service_registry.shutdown_all_services.assert_called_once()
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_application_registry_shutdown_failure(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test shutdown with registry shutdown failure."""
        bootstrapper.service_registry = mock_service_registry
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.is_running = True
        mock_service_registry.shutdown_all_services.side_effect = Exception("Registry shutdown failed")
        
        with patch('modules.application_bootstrapper.logger') as mock_logger:
            await bootstrapper.shutdown_application()
            
            mock_logger.error.assert_called()
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_create_service_configuration_from_env(self, bootstrapper):
        """Test service configuration creation from environment variables."""
        test_env = {
            'TELEGRAM_TOKEN': 'test_token_123',
            'ERROR_CHANNEL_ID': 'error_channel_456',
            'DATABASE_URL': 'postgresql://test:test@localhost/testdb',
            'REDIS_URL': 'redis://localhost:6380',
            'DEBUG_MODE': 'true'
        }
        
        with patch.dict('os.environ', test_env):
            config = bootstrapper._create_service_configuration()
            
            assert config.telegram_token == 'test_token_123'
            assert config.error_channel_id == 'error_channel_456'
            assert config.database_url == 'postgresql://test:test@localhost/testdb'
            assert config.redis_url == 'redis://localhost:6380'
            assert config.debug_mode is True

    @pytest.mark.asyncio
    async def test_create_service_configuration_debug_false(self, bootstrapper):
        """Test service configuration with debug mode false."""
        test_env = {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': 'error_channel',
            'DEBUG_MODE': 'false'
        }
        
        with patch.dict('os.environ', test_env):
            config = bootstrapper._create_service_configuration()
            assert config.debug_mode is False

    @pytest.mark.asyncio
    async def test_create_service_configuration_debug_invalid(self, bootstrapper):
        """Test service configuration with invalid debug mode."""
        test_env = {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': 'error_channel',
            'DEBUG_MODE': 'invalid'
        }
        
        with patch.dict('os.environ', test_env):
            config = bootstrapper._create_service_configuration()
            assert config.debug_mode is False  # Should default to False

    @pytest.mark.asyncio
    async def test_register_core_services(self, bootstrapper, mock_service_registry, service_config):
        """Test core service registration."""
        with patch('modules.application_bootstrapper.ConfigManager') as mock_config_class, \
             patch('modules.application_bootstrapper.BotApplication') as mock_bot_class:
            
            mock_config = Mock()
            mock_bot = Mock()
            mock_config_class.return_value = mock_config
            mock_bot_class.return_value = mock_bot
            
            await bootstrapper._register_core_services(mock_service_registry, service_config)
            
            # Verify services are registered
            assert mock_service_registry.register_service.call_count >= 2
            mock_config_class.assert_called_once()
            mock_bot_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_specialized_services(self, bootstrapper, mock_service_registry):
        """Test specialized service registration."""
        with patch('modules.application_bootstrapper.MessageHandlerService') as mock_msg_class, \
             patch('modules.application_bootstrapper.SpeechRecognitionService') as mock_speech_class, \
             patch('modules.application_bootstrapper.CommandRegistry') as mock_cmd_class, \
             patch('modules.application_bootstrapper.CallbackHandlerService') as mock_callback_class:
            
            mock_config = Mock()
            mock_service_registry.get_service.return_value = mock_config
            
            await bootstrapper._register_specialized_services(mock_service_registry)
            
            # Verify specialized services are created and registered
            mock_msg_class.assert_called_once()
            mock_speech_class.assert_called_once()
            mock_cmd_class.assert_called_once()
            mock_callback_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_lifecycle_integration(self, bootstrapper):
        """Test complete application lifecycle."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': 'test_channel'
        }):
            with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class, \
                 patch.object(bootstrapper, 'setup_signal_handlers') as mock_setup_signals:
                
                mock_registry = Mock(spec=ServiceRegistry)
                mock_registry.register_service = Mock()
                mock_registry.initialize_all_services = AsyncMock()
                mock_registry.shutdown_all_services = AsyncMock()
                mock_registry.get_service = Mock()
                
                mock_bot = Mock(spec=BotApplication)
                mock_bot.initialize = AsyncMock()
                mock_bot.start = AsyncMock()
                mock_bot.shutdown = AsyncMock()
                mock_registry.get_service.return_value = mock_bot
                
                mock_registry_class.return_value = mock_registry
                
                # Configure services
                registry = await bootstrapper.configure_services()
                assert registry == mock_registry
                
                # Start application
                await bootstrapper.start_application()
                assert bootstrapper.is_running is True
                
                # Shutdown application
                await bootstrapper.shutdown_application()
                assert bootstrapper.is_running is False
                
                # Verify all calls were made
                mock_registry.initialize_all_services.assert_called_once()
                mock_bot.initialize.assert_called_once()
                mock_bot.start.assert_called_once()
                mock_bot.shutdown.assert_called_once()
                mock_registry.shutdown_all_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_during_configuration(self, bootstrapper):
        """Test error handling during service configuration."""
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': 'test_channel'
        }):
            with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class:
                mock_registry_class.side_effect = Exception("Registry creation failed")
                
                with pytest.raises(Exception, match="Registry creation failed"):
                    await bootstrapper.configure_services()

    @pytest.mark.asyncio
    async def test_concurrent_shutdown_calls(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test handling of concurrent shutdown calls."""
        bootstrapper.service_registry = mock_service_registry
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.is_running = True
        
        # Simulate concurrent shutdown calls
        tasks = [
            bootstrapper.shutdown_application(),
            bootstrapper.shutdown_application(),
            bootstrapper.shutdown_application()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should only shutdown once
        mock_bot_application.shutdown.assert_called_once()
        mock_service_registry.shutdown_all_services.assert_called_once()
        assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_service_configuration_validation(self, bootstrapper):
        """Test service configuration validation."""
        # Test with empty token
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': '',
            'ERROR_CHANNEL_ID': 'test_channel'
        }):
            with pytest.raises(ValueError, match="TELEGRAM_TOKEN cannot be empty"):
                bootstrapper._create_service_configuration()
        
        # Test with empty error channel
        with patch.dict('os.environ', {
            'TELEGRAM_TOKEN': 'test_token',
            'ERROR_CHANNEL_ID': ''
        }):
            with pytest.raises(ValueError, match="ERROR_CHANNEL_ID cannot be empty"):
                bootstrapper._create_service_configuration()

    @pytest.mark.asyncio
    async def test_logging_during_operations(self, bootstrapper, mock_service_registry, mock_bot_application):
        """Test logging during various operations."""
        with patch('modules.application_bootstrapper.logger') as mock_logger:
            # Test startup logging
            bootstrapper.service_registry = mock_service_registry
            mock_service_registry.get_service.return_value = mock_bot_application
            
            with patch.object(bootstrapper, 'setup_signal_handlers'):
                await bootstrapper.start_application()
            
            # Verify startup logging
            mock_logger.info.assert_called()
            
            # Test shutdown logging
            await bootstrapper.shutdown_application()
            
            # Verify shutdown logging
            assert mock_logger.info.call_count > 1

    def test_property_access(self, bootstrapper):
        """Test property access methods."""
        # Test initial state
        assert bootstrapper.is_running is False
        
        # Test after setting running state
        bootstrapper.is_running = True
        assert bootstrapper.is_running is True
        
        # Test service registry access
        mock_registry = Mock()
        bootstrapper.service_registry = mock_registry
        assert bootstrapper.service_registry == mock_registry
        
        # Test bot application access
        mock_bot = Mock()
        bootstrapper.bot_application = mock_bot
        assert bootstrapper.bot_application == mock_bot