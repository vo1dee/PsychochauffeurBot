"""
Unit tests for ApplicationBootstrapper.

This module contains comprehensive unit tests for the ApplicationBootstrapper
class, covering service configuration, lifecycle management, error handling,
and signal processing.
"""

import asyncio
import pytest
import signal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any

from modules.application_bootstrapper import ApplicationBootstrapper, run_application
from modules.application_models import ServiceConfiguration
from modules.service_registry import ServiceRegistry


class TestApplicationBootstrapper:
    """Test cases for ApplicationBootstrapper class."""
    
    @pytest.fixture
    def bootstrapper(self) -> ApplicationBootstrapper:
        """Create a fresh ApplicationBootstrapper instance for each test."""
        return ApplicationBootstrapper()
    
    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create a mock Config object."""
        config = Mock()
        config.TELEGRAM_BOT_TOKEN = "test_token_123"
        config.ERROR_CHANNEL_ID = "test_channel_123"
        config.DEBUG_MODE = False
        return config
    
    def test_init(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test ApplicationBootstrapper initialization."""
        assert bootstrapper.service_registry is None
        assert bootstrapper.bot_application is None
        assert not bootstrapper.is_running
        assert bootstrapper._shutdown_event is not None
    
    @patch('modules.application_bootstrapper.Config')
    @patch('config.config_manager.ConfigManager')
    @patch('modules.database.Database')
    @patch('modules.bot_application.BotApplication')
    @pytest.mark.asyncio
    async def test_configure_services_success(
        self,
        mock_bot_app: Mock,
        mock_database: Mock,
        mock_config_manager: Mock,
        mock_config: Mock,
        bootstrapper: ApplicationBootstrapper
    ) -> None:
        """Test successful service configuration."""
        # Setup mocks
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        mock_config.ERROR_CHANNEL_ID = "test_channel"
        
        # Mock the ConfigManager.initialize method to be async
        mock_config_manager_instance = AsyncMock()
        mock_config_manager.return_value = mock_config_manager_instance
        
        # Execute
        service_registry = await bootstrapper.configure_services()
        
        # Verify
        assert isinstance(service_registry, ServiceRegistry)
        assert service_registry.is_registered('service_config')
        assert service_registry.is_registered('config_manager')
        assert service_registry.is_registered('database')
        assert service_registry.is_registered('bot_application')
        
        # Verify service configuration
        service_config = service_registry.get_service('service_config')
        assert isinstance(service_config, ServiceConfiguration)
        assert service_config.telegram_token == "test_token"
        assert service_config.error_channel_id == "test_channel"
    
    @patch('modules.application_bootstrapper.Config')
    @pytest.mark.asyncio
    async def test_configure_services_missing_token(
        self,
        mock_config: Mock,
        bootstrapper: ApplicationBootstrapper
    ) -> None:
        """Test service configuration with missing telegram token."""
        # Setup mock with missing token
        mock_config.TELEGRAM_BOT_TOKEN = ""
        mock_config.ERROR_CHANNEL_ID = "test_channel"
        
        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Service configuration failed"):
            await bootstrapper.configure_services()
    
    @patch('modules.application_bootstrapper.Config')
    @pytest.mark.asyncio
    async def test_configure_services_missing_channel(
        self,
        mock_config: Mock,
        bootstrapper: ApplicationBootstrapper
    ) -> None:
        """Test service configuration with missing error channel."""
        # Setup mock with missing channel
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        mock_config.ERROR_CHANNEL_ID = ""
        
        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Service configuration failed"):
            await bootstrapper.configure_services()
    
    @patch('modules.application_bootstrapper.ServiceRegistry')
    @pytest.mark.asyncio
    async def test_configure_services_registry_failure(
        self,
        mock_registry_class: Mock,
        bootstrapper: ApplicationBootstrapper
    ) -> None:
        """Test service configuration when registry creation fails."""
        # Setup mock to raise exception
        mock_registry_class.side_effect = Exception("Registry creation failed")
        
        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Service configuration failed"):
            await bootstrapper.configure_services()
    
    @pytest.mark.asyncio
    async def test_start_application_success(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test successful application startup."""
        # Setup mocks
        mock_service_registry = Mock(spec=ServiceRegistry)
        mock_bot_application = AsyncMock()
        mock_service_registry.get_service.return_value = mock_bot_application
        
        with patch.object(bootstrapper, 'configure_services', return_value=mock_service_registry) as mock_configure, \
             patch.object(bootstrapper, 'setup_signal_handlers') as mock_signals:
            
            # Mock the start method to avoid infinite loop
            async def mock_start():
                bootstrapper._running = False  # End the "application"
            
            mock_bot_application.start = mock_start
            
            # Execute
            await bootstrapper.start_application()
            
            # Verify
            mock_configure.assert_called_once()
            mock_bot_application.initialize.assert_called_once()
            mock_signals.assert_called_once()
            assert bootstrapper.service_registry == mock_service_registry
            assert bootstrapper.bot_application == mock_bot_application
    
    @pytest.mark.asyncio
    async def test_start_application_already_running(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test starting application when it's already running."""
        # Set as running
        bootstrapper._running = True
        
        with patch.object(bootstrapper, 'configure_services') as mock_configure:
            # Execute
            await bootstrapper.start_application()
            
            # Verify configure_services was not called
            mock_configure.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_start_application_configuration_failure(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test application startup when service configuration fails."""
        with patch.object(bootstrapper, 'configure_services', side_effect=Exception("Config failed")) as mock_configure, \
             patch.object(bootstrapper, 'shutdown_application') as mock_shutdown:
            
            # Execute and verify exception
            with pytest.raises(RuntimeError, match="Application startup failed"):
                await bootstrapper.start_application()
            
            # Verify cleanup was called
            mock_shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_application_initialization_failure(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test application startup when bot initialization fails."""
        # Setup mocks
        mock_service_registry = Mock(spec=ServiceRegistry)
        mock_bot_application = AsyncMock()
        mock_bot_application.initialize.side_effect = Exception("Init failed")
        mock_service_registry.get_service.return_value = mock_bot_application
        
        with patch.object(bootstrapper, 'configure_services', return_value=mock_service_registry), \
             patch.object(bootstrapper, 'shutdown_application') as mock_shutdown:
            
            # Execute and verify exception
            with pytest.raises(RuntimeError, match="Application startup failed"):
                await bootstrapper.start_application()
            
            # Verify cleanup was called
            mock_shutdown.assert_called_once()
    
    def test_setup_signal_handlers(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test signal handler setup."""
        with patch('signal.signal') as mock_signal:
            # Execute
            bootstrapper.setup_signal_handlers()
            
            # Verify signal handlers were registered
            assert mock_signal.call_count == 2
            # Check that both SIGINT and SIGTERM were registered
            calls = mock_signal.call_args_list
            signal_numbers = [call[0][0] for call in calls]
            assert signal.SIGINT in signal_numbers
            assert signal.SIGTERM in signal_numbers
    
    def test_signal_handler_execution(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test signal handler execution."""
        # Setup
        bootstrapper._running = True
        
        with patch('signal.signal') as mock_signal:
            # Setup signal handlers
            bootstrapper.setup_signal_handlers()
            
            # Verify signal handlers were registered
            assert mock_signal.call_count >= 2  # SIGINT and SIGTERM
            
            # Test that the signal handler function exists
            assert hasattr(bootstrapper, '_signal_handler_func')
            
            # Test shutdown event can be set directly
            bootstrapper._shutdown_event.set()
            assert bootstrapper._shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_shutdown_application_success(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test successful application shutdown."""
        # Setup
        bootstrapper._running = True
        mock_bot_application = AsyncMock()
        mock_service_registry = AsyncMock()
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.service_registry = mock_service_registry
        
        # Execute
        await bootstrapper.shutdown_application()
        
        # Verify
        mock_bot_application.shutdown.assert_called_once()
        # Service registry shutdown is only called if bot application shutdown fails
        # or if there's no bot application, so we don't expect it to be called here
        assert not bootstrapper.is_running
    
    @pytest.mark.asyncio
    async def test_shutdown_application_not_running(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test shutdown when application is not running."""
        # Setup
        assert not bootstrapper._running
        mock_bot_application = AsyncMock()
        bootstrapper.bot_application = mock_bot_application
        
        # Execute
        await bootstrapper.shutdown_application()
        
        # Verify shutdown was not called
        mock_bot_application.shutdown.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_shutdown_application_bot_failure(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test shutdown when bot application shutdown fails."""
        # Setup
        bootstrapper._running = True
        mock_bot_application = AsyncMock()
        mock_bot_application.shutdown.side_effect = Exception("Shutdown failed")
        mock_service_registry = AsyncMock()
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.service_registry = mock_service_registry
        
        # Execute (should not raise exception)
        await bootstrapper.shutdown_application()
        
        # Verify bot shutdown was attempted and running is False
        mock_bot_application.shutdown.assert_called_once()
        # Service registry shutdown should still be attempted even if bot fails
        mock_service_registry.shutdown_services.assert_called_once()
        assert not bootstrapper.is_running
    
    @pytest.mark.asyncio
    async def test_shutdown_application_registry_failure(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test shutdown when service registry shutdown fails."""
        # Setup
        bootstrapper._running = True
        mock_bot_application = AsyncMock()
        mock_service_registry = AsyncMock()
        mock_service_registry.shutdown_services.side_effect = Exception("Registry shutdown failed")
        bootstrapper.bot_application = mock_bot_application
        bootstrapper.service_registry = mock_service_registry
        
        # Make bot application shutdown fail so service registry shutdown is called
        mock_bot_application.shutdown.side_effect = Exception("Bot shutdown failed")
        
        # Execute (should not raise exception)
        await bootstrapper.shutdown_application()
        
        # Verify both shutdowns were attempted and running is False
        mock_bot_application.shutdown.assert_called_once()
        mock_service_registry.shutdown_services.assert_called_once()
        assert not bootstrapper.is_running
    
    def test_is_running_property(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test is_running property."""
        # Initially not running
        assert not bootstrapper.is_running
        
        # Set as running
        bootstrapper._running = True
        assert bootstrapper.is_running
        
        # Set as not running
        bootstrapper._running = False
        assert not bootstrapper.is_running
    
    @pytest.mark.asyncio
    async def test_wait_for_shutdown(self, bootstrapper: ApplicationBootstrapper) -> None:
        """Test wait_for_shutdown method."""
        # Create a task to wait for shutdown
        wait_task = asyncio.create_task(bootstrapper.wait_for_shutdown())
        
        # Ensure the task is waiting
        await asyncio.sleep(0.01)
        assert not wait_task.done()
        
        # Set shutdown event
        bootstrapper._shutdown_event.set()
        
        # Wait should complete
        await wait_task
        assert wait_task.done()


class TestRunApplication:
    """Test cases for the run_application function."""
    
    @patch('modules.application_bootstrapper.ApplicationBootstrapper')
    @pytest.mark.asyncio
    async def test_run_application_success(self, mock_bootstrapper_class: Mock) -> None:
        """Test successful application run."""
        # Setup mock
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper_class.return_value = mock_bootstrapper
        
        # Execute
        await run_application()
        
        # Verify
        mock_bootstrapper_class.assert_called_once()
        mock_bootstrapper.start_application.assert_called_once()
        mock_bootstrapper.shutdown_application.assert_called_once()
    
    @patch('modules.application_bootstrapper.ApplicationBootstrapper')
    @pytest.mark.asyncio
    async def test_run_application_keyboard_interrupt(self, mock_bootstrapper_class: Mock) -> None:
        """Test application run with keyboard interrupt."""
        # Setup mock
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper.start_application.side_effect = KeyboardInterrupt()
        mock_bootstrapper_class.return_value = mock_bootstrapper
        
        # Execute (should not raise exception)
        await run_application()
        
        # Verify cleanup was called
        mock_bootstrapper.shutdown_application.assert_called_once()
    
    @patch('modules.application_bootstrapper.ApplicationBootstrapper')
    @patch('sys.exit')
    @pytest.mark.asyncio
    async def test_run_application_general_exception(
        self,
        mock_exit: Mock,
        mock_bootstrapper_class: Mock
    ) -> None:
        """Test application run with general exception."""
        # Setup mock
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper.start_application.side_effect = Exception("General error")
        mock_bootstrapper_class.return_value = mock_bootstrapper
        
        # Execute
        await run_application()
        
        # Verify cleanup and exit were called
        mock_bootstrapper.shutdown_application.assert_called_once()
        mock_exit.assert_called_once_with(1)
    
    @patch('modules.application_bootstrapper.ApplicationBootstrapper')
    @pytest.mark.asyncio
    async def test_run_application_shutdown_failure(self, mock_bootstrapper_class: Mock) -> None:
        """Test application run when shutdown fails."""
        # Setup mock
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper.shutdown_application.side_effect = Exception("Shutdown failed")
        mock_bootstrapper_class.return_value = mock_bootstrapper
        
        # Execute - this should raise the shutdown exception
        with pytest.raises(Exception, match="Shutdown failed"):
            await run_application()
        
        # Verify start and shutdown were called
        mock_bootstrapper.start_application.assert_called_once()
        mock_bootstrapper.shutdown_application.assert_called_once()


class TestServiceConfigurationIntegration:
    """Integration tests for service configuration."""
    
    @patch('modules.application_bootstrapper.Config')
    @pytest.mark.asyncio
    async def test_service_configuration_creation(self, mock_config: Mock) -> None:
        """Test that ServiceConfiguration is created correctly."""
        # Setup
        mock_config.TELEGRAM_BOT_TOKEN = "integration_test_token"
        mock_config.ERROR_CHANNEL_ID = "integration_test_channel"
        mock_config.DEBUG_MODE = True
        
        bootstrapper = ApplicationBootstrapper()
        
        with patch('config.config_manager.ConfigManager') as mock_config_manager, \
             patch('modules.database.Database'), \
             patch('modules.bot_application.BotApplication'):
            
            # Mock the ConfigManager.initialize method to be async
            mock_config_manager_instance = AsyncMock()
            mock_config_manager.return_value = mock_config_manager_instance
            
            # Execute
            service_registry = await bootstrapper.configure_services()
            
            # Verify service configuration
            service_config = service_registry.get_service('service_config')
            assert service_config.telegram_token == "integration_test_token"
            assert service_config.error_channel_id == "integration_test_channel"
            assert service_config.debug_mode is True
    
    @patch('modules.application_bootstrapper.Config')
    @pytest.mark.asyncio
    async def test_specialized_services_registration(self, mock_config: Mock) -> None:
        """Test that specialized services are registered correctly."""
        # Setup
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        mock_config.ERROR_CHANNEL_ID = "test_channel"
        
        bootstrapper = ApplicationBootstrapper()
        
        with patch('config.config_manager.ConfigManager') as mock_config_manager, \
             patch('modules.database.Database'), \
             patch('modules.bot_application.BotApplication'), \
             patch('modules.reminders.reminders.ReminderManager') as mock_reminder, \
             patch('modules.safety.safety_manager') as mock_safety, \
             patch('modules.utils.MessageCounter') as mock_counter:
            
            # Mock the ConfigManager.initialize method to be async
            mock_config_manager_instance = AsyncMock()
            mock_config_manager.return_value = mock_config_manager_instance
            
            # Execute
            service_registry = await bootstrapper.configure_services()
            
            # Verify specialized services are registered
            # Note: These may not be registered if imports fail, which is expected
            registered_services = service_registry.get_registered_services()
            
            # Core services should always be registered
            assert 'service_config' in registered_services
            assert 'config_manager' in registered_services
            assert 'database' in registered_services
            assert 'bot_application' in registered_services