"""
Tests for configuration integration in new components.

This module tests the configuration integration functionality added to
the new components including MessageHandlerService, SpeechRecognitionService,
CommandRegistry, and CallbackHandlerService.
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

from config.config_manager import ConfigManager
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.command_registry import CommandRegistry
from modules.callback_handler_service import CallbackHandlerService
from modules.command_processor import CommandProcessor
from modules.utils import MessageCounter


class TestMessageHandlerServiceConfiguration:
    """Test configuration integration for MessageHandlerService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock ConfigManager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock()
        config_manager.save_config = AsyncMock()
        config_manager.register_change_callback = Mock()
        return config_manager
    
    @pytest.fixture
    def message_counter(self):
        """Create a mock MessageCounter."""
        return Mock(spec=MessageCounter)
    
    @pytest.fixture
    def message_handler_service(self, mock_config_manager, message_counter):
        """Create MessageHandlerService with mocked dependencies."""
        return MessageHandlerService(mock_config_manager, message_counter)
    
    @pytest.mark.asyncio
    async def test_initialization_loads_configuration(self, message_handler_service, mock_config_manager):
        """Test that initialization loads service configuration."""
        # Setup mock configuration
        mock_config = {
            "enabled": True,
            "overrides": {
                "max_message_length": 2048,
                "rate_limit_enabled": True
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # Initialize service
        await message_handler_service.initialize()
        
        # Verify configuration was loaded
        mock_config_manager.get_config.assert_called_once_with(module_name="message_handler")
        assert message_handler_service._service_config == mock_config["overrides"]
        assert message_handler_service._initialized is True
    
    @pytest.mark.asyncio
    async def test_initialization_handles_missing_configuration(self, message_handler_service, mock_config_manager):
        """Test that initialization handles missing configuration gracefully."""
        # Setup mock to return None (no configuration)
        mock_config_manager.get_config.return_value = None
        
        # Initialize service
        await message_handler_service.initialize()
        
        # Verify service still initializes with empty configuration
        assert message_handler_service._service_config == {}
        assert message_handler_service._initialized is True
    
    @pytest.mark.asyncio
    async def test_configuration_change_notification_setup(self, message_handler_service, mock_config_manager):
        """Test that configuration change notifications are set up."""
        mock_config_manager.get_config.return_value = {"overrides": {}}
        
        # Initialize service
        await message_handler_service.initialize()
        
        # Verify change callback was registered
        mock_config_manager.register_change_callback.assert_called_once_with(
            "message_handler", 
            message_handler_service._handle_configuration_change
        )
    
    @pytest.mark.asyncio
    async def test_configuration_change_handling(self, message_handler_service, mock_config_manager):
        """Test handling of configuration changes."""
        # Initialize service first
        mock_config_manager.get_config.return_value = {"overrides": {"old_setting": "old_value"}}
        await message_handler_service.initialize()
        
        # Simulate configuration change
        new_config = {
            "enabled": True,
            "overrides": {
                "new_setting": "new_value",
                "updated_setting": "updated_value"
            }
        }
        
        await message_handler_service._handle_configuration_change("message_handler", new_config)
        
        # Verify configuration was updated
        assert message_handler_service._service_config == new_config["overrides"]
    
    @pytest.mark.asyncio
    async def test_configuration_change_ignores_other_modules(self, message_handler_service, mock_config_manager):
        """Test that configuration changes for other modules are ignored."""
        # Initialize service
        mock_config_manager.get_config.return_value = {"overrides": {"setting": "value"}}
        await message_handler_service.initialize()
        
        original_config = message_handler_service._service_config.copy()
        
        # Simulate configuration change for different module
        await message_handler_service._handle_configuration_change("other_module", {"overrides": {"other": "value"}})
        
        # Verify configuration was not changed
        assert message_handler_service._service_config == original_config
    
    @pytest.mark.asyncio
    async def test_update_service_configuration(self, message_handler_service, mock_config_manager):
        """Test updating service configuration."""
        # Initialize service
        mock_config_manager.get_config.return_value = {"overrides": {}}
        await message_handler_service.initialize()
        
        # Update configuration
        new_config = {"max_retries": 3, "timeout": 30}
        await message_handler_service.update_service_configuration(new_config)
        
        # Verify configuration was saved and updated
        mock_config_manager.save_config.assert_called_once_with(
            config_data={"enabled": True, "overrides": new_config},
            module_name="message_handler"
        )
        assert message_handler_service._service_config == new_config
    
    def test_get_service_configuration(self, message_handler_service):
        """Test getting current service configuration."""
        # Set some configuration
        test_config = {"setting1": "value1", "setting2": "value2"}
        message_handler_service._service_config = test_config
        
        # Get configuration
        result = message_handler_service.get_service_configuration()
        
        # Verify it returns a copy
        assert result == test_config
        assert result is not test_config  # Should be a copy
    
    @pytest.mark.asyncio
    async def test_shutdown_clears_configuration(self, message_handler_service, mock_config_manager):
        """Test that shutdown clears configuration properly."""
        # Initialize service with configuration
        mock_config_manager.get_config.return_value = {"overrides": {"setting": "value"}}
        await message_handler_service.initialize()
        
        # Verify configuration is set
        assert message_handler_service._service_config
        assert message_handler_service._config_change_callbacks
        
        # Shutdown service
        await message_handler_service.shutdown()
        
        # Verify configuration is cleared
        assert message_handler_service._service_config == {}
        assert message_handler_service._config_change_callbacks == []
        assert message_handler_service._initialized is False


class TestSpeechRecognitionServiceConfiguration:
    """Test configuration integration for SpeechRecognitionService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock ConfigManager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock()
        config_manager.save_config = AsyncMock()
        config_manager.register_change_callback = Mock()
        return config_manager
    
    @pytest.fixture
    def speech_service(self, mock_config_manager):
        """Create SpeechRecognitionService with mocked dependencies."""
        return SpeechRecognitionService(mock_config_manager)
    
    @pytest.mark.asyncio
    async def test_initialization_loads_configuration(self, speech_service, mock_config_manager):
        """Test that initialization loads service configuration."""
        # Setup mock configuration
        mock_config = {
            "enabled": True,
            "overrides": {
                "default_language": "en",
                "timeout_seconds": 60
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # Initialize service
        await speech_service.initialize()
        
        # Verify configuration was loaded
        mock_config_manager.get_config.assert_called_once_with(module_name="speechmatics")
        assert speech_service._service_config == mock_config["overrides"]
    
    @pytest.mark.asyncio
    async def test_configuration_change_handling(self, speech_service, mock_config_manager):
        """Test handling of configuration changes."""
        # Initialize service first
        mock_config_manager.get_config.return_value = {"overrides": {"timeout_seconds": 30}}
        await speech_service.initialize()
        
        # Simulate configuration change
        new_config = {
            "enabled": True,
            "overrides": {
                "timeout_seconds": 60,
                "max_file_size": 10485760
            }
        }
        
        await speech_service._handle_configuration_change("speechmatics", new_config)
        
        # Verify configuration was updated
        assert speech_service._service_config == new_config["overrides"]
    
    @pytest.mark.asyncio
    async def test_update_service_configuration(self, speech_service, mock_config_manager):
        """Test updating service configuration."""
        # Initialize service
        mock_config_manager.get_config.return_value = {"overrides": {}}
        await speech_service.initialize()
        
        # Update configuration
        new_config = {"default_language": "uk", "timeout_seconds": 45}
        await speech_service.update_service_configuration(new_config)
        
        # Verify configuration was saved and updated
        mock_config_manager.save_config.assert_called_once_with(
            config_data={"enabled": True, "overrides": new_config},
            module_name="speechmatics"
        )
        assert speech_service._service_config == new_config


class TestCommandRegistryConfiguration:
    """Test configuration integration for CommandRegistry."""
    
    @pytest.fixture
    def mock_command_processor(self):
        """Create a mock CommandProcessor."""
        return Mock(spec=CommandProcessor)
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock ConfigManager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock()
        config_manager.save_config = AsyncMock()
        config_manager.register_change_callback = Mock()
        return config_manager
    
    @pytest.fixture
    def command_registry(self, mock_command_processor):
        """Create CommandRegistry with mocked dependencies."""
        return CommandRegistry(mock_command_processor)
    
    @pytest.mark.asyncio
    async def test_initialization_without_config_manager(self, command_registry):
        """Test initialization when ConfigManager is not available."""
        # Mock service registry to not have config manager
        with patch('modules.service_registry.service_registry') as mock_registry:
            mock_registry.get_service.side_effect = Exception("Service not found")
            
            # Initialize should succeed without config manager
            await command_registry.initialize()
            
            # Verify service initialized without configuration
            assert command_registry._config_manager is None
            assert command_registry._service_config == {}
    
    @pytest.mark.asyncio
    async def test_initialization_with_config_manager(self, mock_command_processor, mock_config_manager):
        """Test initialization when ConfigManager is available."""
        # Create mock service registry
        mock_service_registry = Mock()
        mock_service_registry.get_service.return_value = mock_config_manager
        mock_config_manager.get_config.return_value = {"overrides": {"max_commands": 100}}
        
        # Create command registry with service registry
        command_registry = CommandRegistry(mock_command_processor, mock_service_registry)
        
        # Initialize service
        await command_registry.initialize()
        
        # Verify config manager was set and configuration loaded
        assert command_registry._config_manager is mock_config_manager
        assert command_registry._service_config == {"max_commands": 100}
    
    @pytest.mark.asyncio
    async def test_configuration_change_handling(self, command_registry, mock_config_manager):
        """Test handling of configuration changes."""
        # Setup command registry with config manager
        command_registry._config_manager = mock_config_manager
        command_registry._service_config = {"old_setting": "old_value"}
        
        # Simulate configuration change
        new_config = {
            "enabled": True,
            "overrides": {
                "new_setting": "new_value"
            }
        }
        
        await command_registry._handle_configuration_change("command_registry", new_config)
        
        # Verify configuration was updated
        assert command_registry._service_config == new_config["overrides"]
    
    @pytest.mark.asyncio
    async def test_update_service_configuration_without_config_manager(self, command_registry):
        """Test updating configuration when ConfigManager is not available."""
        # Ensure config manager is None
        command_registry._config_manager = None
        
        # Attempt to update configuration should log warning but not fail
        await command_registry.update_service_configuration({"setting": "value"})
        
        # Configuration should remain empty
        assert command_registry._service_config == {}


class TestCallbackHandlerServiceConfiguration:
    """Test configuration integration for CallbackHandlerService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock ConfigManager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock()
        config_manager.save_config = AsyncMock()
        config_manager.register_change_callback = Mock()
        return config_manager
    
    @pytest.fixture
    def callback_service(self):
        """Create CallbackHandlerService."""
        mock_service_registry = Mock()
        return CallbackHandlerService(service_registry=mock_service_registry)
    
    @pytest.mark.asyncio
    async def test_initialization_loads_configuration(self, mock_config_manager):
        """Test that initialization loads service configuration."""
        # Create service with mocked service registry
        mock_service_registry = Mock()
        mock_service_registry.get_service.return_value = mock_config_manager
        callback_service = CallbackHandlerService(service_registry=mock_service_registry)
        
        mock_config = {
            "enabled": True,
            "overrides": {
                "callback_expiry_seconds": 7200
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # Initialize service
        await callback_service.initialize()
        
        # Verify configuration was loaded and applied
        assert callback_service._service_config == mock_config["overrides"]
        assert callback_service.callback_expiry_seconds == 7200
    
    @pytest.mark.asyncio
    async def test_configuration_change_updates_expiry(self, callback_service, mock_config_manager):
        """Test that configuration changes update callback expiry."""
        # Setup service with config manager
        callback_service._config_manager = mock_config_manager
        callback_service.callback_expiry_seconds = 3600  # Default value
        
        # Simulate configuration change
        new_config = {
            "enabled": True,
            "overrides": {
                "callback_expiry_seconds": 1800
            }
        }
        
        await callback_service._handle_configuration_change("callback_handler", new_config)
        
        # Verify expiry was updated
        assert callback_service.callback_expiry_seconds == 1800
        assert callback_service._service_config == new_config["overrides"]
    
    @pytest.mark.asyncio
    async def test_update_service_configuration(self, callback_service, mock_config_manager):
        """Test updating service configuration."""
        # Setup service with config manager
        callback_service._config_manager = mock_config_manager
        
        # Update configuration
        new_config = {"callback_expiry_seconds": 900, "max_callbacks": 1000}
        await callback_service.update_service_configuration(new_config)
        
        # Verify configuration was saved and updated
        mock_config_manager.save_config.assert_called_once_with(
            config_data={"enabled": True, "overrides": new_config},
            module_name="callback_handler"
        )
        assert callback_service._service_config == new_config
        assert callback_service.callback_expiry_seconds == 900


class TestLoggingIntegration:
    """Test logging integration across all services."""
    
    def test_component_specific_loggers(self):
        """Test that each component has its own logger with proper naming."""
        # Test MessageHandlerService logger
        from modules.message_handler_service import logger as msg_logger
        assert msg_logger.name == 'message_handler_service'
        
        # Test SpeechRecognitionService logger
        from modules.speech_recognition_service import service_logger as speech_logger
        assert speech_logger.name == 'speech_recognition_service'
        
        # Test CommandRegistry logger
        from modules.command_registry import logger as cmd_logger
        assert cmd_logger.name == 'command_registry'
        
        # Test CallbackHandlerService logger
        from modules.callback_handler_service import service_logger as callback_logger
        assert callback_logger.name == 'callback_handler_service'
    
    @pytest.mark.asyncio
    async def test_logging_during_initialization(self, caplog):
        """Test that proper logging occurs during service initialization."""
        from config.config_manager import ConfigManager
        from modules.utils import MessageCounter
        
        # Create service with real dependencies
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock(return_value={"overrides": {}})
        config_manager.register_change_callback = Mock()
        
        message_counter = Mock(spec=MessageCounter)
        service = MessageHandlerService(config_manager, message_counter)
        
        # Capture logs during initialization
        with caplog.at_level(logging.INFO):
            await service.initialize()
        
        # Verify proper logging occurred
        log_messages = [record.message for record in caplog.records]
        assert any("MessageHandlerService instance created" in msg for msg in log_messages)
        assert any("Initializing MessageHandlerService" in msg for msg in log_messages)
        assert any("initialized successfully" in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_logging_during_configuration_changes(self, caplog):
        """Test that configuration changes are properly logged."""
        from config.config_manager import ConfigManager
        
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock(return_value={"overrides": {"old_setting": "old_value"}})
        config_manager.register_change_callback = Mock()
        
        service = SpeechRecognitionService(config_manager)
        await service.initialize()
        
        # Clear previous logs
        caplog.clear()
        
        # Simulate configuration change
        new_config = {
            "overrides": {
                "new_setting": "new_value",
                "old_setting": "updated_value"
            }
        }
        
        with caplog.at_level(logging.INFO):
            await service._handle_configuration_change("speechmatics", new_config)
        
        # Verify configuration change was logged
        log_messages = [record.message for record in caplog.records]
        assert any("Configuration change detected" in msg for msg in log_messages)
        assert any("Configuration added" in msg for msg in log_messages)
        assert any("Configuration modified" in msg for msg in log_messages)
    
    def test_logger_levels_are_set(self):
        """Test that logger levels are properly set for all components."""
        # Import all component loggers
        from modules.message_handler_service import logger as msg_logger
        from modules.speech_recognition_service import service_logger as speech_logger
        from modules.command_registry import logger as cmd_logger
        from modules.callback_handler_service import service_logger as callback_logger
        from modules.application_bootstrapper import logger as bootstrap_logger
        
        # Verify all loggers have INFO level or higher
        loggers = [msg_logger, speech_logger, cmd_logger, callback_logger, bootstrap_logger]
        for logger in loggers:
            assert logger.level <= logging.INFO, f"Logger {logger.name} level is too high: {logger.level}"


if __name__ == "__main__":
    pytest.main([__file__])