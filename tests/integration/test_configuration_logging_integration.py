"""
Integration tests for configuration and logging integration.

This module tests the end-to-end integration of configuration management
and logging across all new components in realistic scenarios.
"""

import asyncio
import logging
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from config.config_manager import ConfigManager
from modules.application_bootstrapper import ApplicationBootstrapper
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.command_registry import CommandRegistry
from modules.callback_handler_service import CallbackHandlerService
from modules.service_registry import ServiceRegistry
from modules.command_processor import CommandProcessor
from modules.utils import MessageCounter


class TestConfigurationIntegrationFlow:
    """Test the complete configuration integration flow."""
    
    @pytest.fixture
    async def temp_config_dir(self):
        """Create a temporary directory for configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    async def real_config_manager(self, temp_config_dir):
        """Create a real ConfigManager with temporary directory."""
        # Mock the config directories to use temp directory
        with patch('config.config_manager.ConfigManager.__init__') as mock_init:
            def init_with_temp_dir(self):
                from pathlib import Path
                self.base_dir = Path(temp_dir)
                self.GLOBAL_CONFIG_DIR = self.base_dir / 'config' / 'global'
                self.PRIVATE_CONFIG_DIR = self.base_dir / 'config' / 'private'
                self.GROUP_CONFIG_DIR = self.base_dir / 'config' / 'group'
                self.BACKUP_DIR = self.base_dir / 'config' / 'backups'
                self.GLOBAL_CONFIG_FILE = self.GLOBAL_CONFIG_DIR / "global_config.json"
                self._file_locks = {}
                self._module_cache = {}
            
            mock_init.side_effect = init_with_temp_dir
            
            config_manager = ConfigManager()
            await config_manager.initialize()
            yield config_manager
    
    @pytest.mark.asyncio
    async def test_end_to_end_configuration_flow(self, real_config_manager):
        """Test complete configuration flow from bootstrapper to services."""
        # Create service registry
        service_registry = ServiceRegistry()
        
        # Register config manager
        service_registry.register_instance('config_manager', real_config_manager)
        
        # Create and register services
        message_counter = MessageCounter()
        message_service = MessageHandlerService(real_config_manager, message_counter)
        speech_service = SpeechRecognitionService(real_config_manager)
        
        service_registry.register_instance('message_handler_service', message_service)
        service_registry.register_instance('speech_recognition_service', speech_service)
        
        # Initialize services
        await service_registry.initialize_services()
        
        # Verify all services are initialized with configuration
        assert message_service._initialized
        assert message_service._service_config is not None
        assert speech_service._service_config is not None
        
        # Test configuration update propagation
        new_config = {"max_retries": 5, "timeout": 60}
        await message_service.update_service_configuration(new_config)
        
        # Verify configuration was updated
        assert message_service.get_service_configuration() == new_config
        
        # Cleanup
        await service_registry.shutdown_services()
    
    @pytest.mark.asyncio
    async def test_configuration_change_notifications(self, real_config_manager):
        """Test that configuration change notifications work across services."""
        # Create services
        message_service = MessageHandlerService(real_config_manager)
        speech_service = SpeechRecognitionService(real_config_manager)
        
        # Initialize services
        await message_service.initialize()
        await speech_service.initialize()
        
        # Mock the configuration change callbacks to track calls
        message_callback_called = False
        speech_callback_called = False
        
        original_message_handler = message_service._handle_configuration_change
        original_speech_handler = speech_service._handle_configuration_change
        
        async def mock_message_handler(module_name, new_config):
            nonlocal message_callback_called
            message_callback_called = True
            await original_message_handler(module_name, new_config)
        
        async def mock_speech_handler(module_name, new_config):
            nonlocal speech_callback_called
            speech_callback_called = True
            await original_speech_handler(module_name, new_config)
        
        message_service._handle_configuration_change = mock_message_handler
        speech_service._handle_configuration_change = mock_speech_handler
        
        # Simulate configuration changes
        await message_service._handle_configuration_change("message_handler", {"overrides": {"new_setting": "value"}})
        await speech_service._handle_configuration_change("speechmatics", {"overrides": {"language": "en"}})
        
        # Verify callbacks were called
        assert message_callback_called
        assert speech_callback_called
        
        # Cleanup
        await message_service.shutdown()
        await speech_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_service_registry_configuration_integration(self):
        """Test configuration integration through service registry."""
        # Create mock config manager
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.initialize = AsyncMock()
        mock_config_manager.get_config = AsyncMock(return_value={"overrides": {}})
        mock_config_manager.register_change_callback = Mock()
        
        # Create service registry and register config manager
        service_registry = ServiceRegistry()
        service_registry.register_instance('config_manager', mock_config_manager)
        
        # Register services that depend on config manager
        service_registry.register_factory(
            'message_handler_service',
            MessageHandlerService,
            lambda: MessageHandlerService(mock_config_manager, MessageCounter()),
            dependencies=['config_manager']
        )
        
        service_registry.register_factory(
            'speech_recognition_service',
            SpeechRecognitionService,
            lambda: SpeechRecognitionService(mock_config_manager),
            dependencies=['config_manager']
        )
        
        # Initialize all services
        await service_registry.initialize_services()
        
        # Verify services were initialized with config manager
        message_service = service_registry.get_service('message_handler_service')
        speech_service = service_registry.get_service('speech_recognition_service')
        
        assert message_service.config_manager is mock_config_manager
        assert speech_service.config_manager is mock_config_manager
        
        # Verify configuration was loaded during initialization
        assert mock_config_manager.get_config.call_count >= 2  # At least once per service
        
        # Cleanup
        await service_registry.shutdown_services()


class TestLoggingIntegrationFlow:
    """Test the complete logging integration flow."""
    
    @pytest.mark.asyncio
    async def test_component_logging_hierarchy(self, caplog):
        """Test that component logging follows proper hierarchy."""
        # Create services
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_config = AsyncMock(return_value={"overrides": {}})
        mock_config_manager.register_change_callback = Mock()
        
        message_service = MessageHandlerService(mock_config_manager, MessageCounter())
        speech_service = SpeechRecognitionService(mock_config_manager)
        
        # Capture logs at INFO level
        with caplog.at_level(logging.INFO):
            await message_service.initialize()
            await speech_service.initialize()
        
        # Verify logs contain component identification
        log_records = caplog.records
        
        # Check for component-specific logger names
        message_logs = [r for r in log_records if r.name == 'message_handler_service']
        speech_logs = [r for r in log_records if r.name == 'speech_recognition_service']
        
        assert len(message_logs) > 0, "No logs found for message_handler_service"
        assert len(speech_logs) > 0, "No logs found for speech_recognition_service"
        
        # Verify log messages contain service identification
        message_log_texts = [r.message for r in message_logs]
        speech_log_texts = [r.message for r in speech_logs]
        
        assert any("MessageHandlerService" in msg for msg in message_log_texts)
        assert any("SpeechRecognitionService" in msg for msg in speech_log_texts)
        
        # Cleanup
        await message_service.shutdown()
        await speech_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_error_logging_with_context(self, caplog):
        """Test that errors are logged with proper context."""
        # Create service with mock that will raise an error
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_config = AsyncMock(side_effect=Exception("Configuration error"))
        mock_config_manager.register_change_callback = Mock()
        
        service = MessageHandlerService(mock_config_manager, MessageCounter())
        
        # Capture logs at ERROR level
        with caplog.at_level(logging.ERROR):
            # This should handle the error gracefully and log it
            await service.initialize()
        
        # Verify error was logged with proper context
        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_logs) > 0, "No error logs found"
        
        # Check that error log contains service identification
        error_messages = [r.message for r in error_logs]
        assert any("MessageHandlerService" in msg for msg in error_messages)
    
    @pytest.mark.asyncio
    async def test_configuration_change_logging(self, caplog):
        """Test that configuration changes are properly logged."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_config = AsyncMock(return_value={"overrides": {"old_setting": "old_value"}})
        mock_config_manager.register_change_callback = Mock()
        
        service = SpeechRecognitionService(mock_config_manager)
        await service.initialize()
        
        # Clear previous logs
        caplog.clear()
        
        # Simulate configuration change with detailed changes
        new_config = {
            "overrides": {
                "new_setting": "new_value",
                "old_setting": "updated_value",
                "another_new": "another_value"
            }
        }
        
        with caplog.at_level(logging.INFO):
            await service._handle_configuration_change("speechmatics", new_config)
        
        # Verify detailed logging of configuration changes
        log_messages = [r.message for r in caplog.records if r.name == 'speech_recognition_service']
        
        assert any("Configuration change detected" in msg for msg in log_messages)
        assert any("Configuration added" in msg for msg in log_messages)
        assert any("Configuration modified" in msg for msg in log_messages)
        
        # Cleanup
        await service.shutdown()
    
    def test_logger_configuration_consistency(self):
        """Test that all component loggers are configured consistently."""
        # Import all component loggers
        from modules.message_handler_service import logger as msg_logger
        from modules.speech_recognition_service import service_logger as speech_logger
        from modules.command_registry import logger as cmd_logger
        from modules.callback_handler_service import service_logger as callback_logger
        from modules.application_bootstrapper import logger as bootstrap_logger
        
        loggers = [
            (msg_logger, 'message_handler_service'),
            (speech_logger, 'speech_recognition_service'),
            (cmd_logger, 'command_registry'),
            (callback_logger, 'callback_handler_service'),
            (bootstrap_logger, 'application_bootstrapper')
        ]
        
        for logger, expected_name in loggers:
            # Verify logger name matches expected
            assert logger.name == expected_name, f"Logger name mismatch: {logger.name} != {expected_name}"
            
            # Verify logger level is appropriate (INFO or lower)
            assert logger.level <= logging.INFO, f"Logger {logger.name} level too high: {logger.level}"
            
            # Verify logger is properly configured
            assert isinstance(logger, logging.Logger), f"Invalid logger type for {logger.name}"


class TestApplicationBootstrapperIntegration:
    """Test ApplicationBootstrapper configuration and logging integration."""
    
    @pytest.mark.asyncio
    async def test_bootstrapper_configuration_setup(self):
        """Test that ApplicationBootstrapper properly sets up configuration."""
        # Mock the Config module
        with patch('modules.application_bootstrapper.Config') as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "test_token"
            mock_config.ERROR_CHANNEL_ID = "test_channel"
            
            # Mock ConfigManager
            with patch('modules.application_bootstrapper.ConfigManager') as mock_config_manager_class:
                mock_config_manager = Mock()
                mock_config_manager.initialize = AsyncMock()
                mock_config_manager_class.return_value = mock_config_manager
                
                # Create bootstrapper
                bootstrapper = ApplicationBootstrapper()
                
                # Configure services
                service_registry = await bootstrapper.configure_services()
                
                # Verify config manager was initialized
                mock_config_manager.initialize.assert_called_once()
                
                # Verify service registry contains config manager
                config_manager = service_registry.get_service('config_manager')
                assert config_manager is mock_config_manager
    
    @pytest.mark.asyncio
    async def test_bootstrapper_logging_during_startup(self, caplog):
        """Test that ApplicationBootstrapper logs properly during startup."""
        # Mock dependencies to avoid actual initialization
        with patch('modules.application_bootstrapper.Config') as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "test_token"
            mock_config.ERROR_CHANNEL_ID = "test_channel"
            
            with patch('modules.application_bootstrapper.ConfigManager') as mock_config_manager_class:
                mock_config_manager = Mock()
                mock_config_manager.initialize = AsyncMock()
                mock_config_manager_class.return_value = mock_config_manager
                
                with patch('modules.application_bootstrapper.ServiceFactory'):
                    bootstrapper = ApplicationBootstrapper()
                    
                    # Capture logs during configuration
                    with caplog.at_level(logging.INFO):
                        await bootstrapper.configure_services()
                    
                    # Verify proper logging occurred
                    bootstrap_logs = [r for r in caplog.records if r.name == 'application_bootstrapper']
                    assert len(bootstrap_logs) > 0, "No logs found for application_bootstrapper"
                    
                    log_messages = [r.message for r in bootstrap_logs]
                    assert any("Configuring services" in msg for msg in log_messages)
                    assert any("ConfigManager initialized" in msg for msg in log_messages)
                    assert any("Services configured successfully" in msg for msg in log_messages)


class TestErrorHandlingIntegration:
    """Test error handling in configuration and logging integration."""
    
    @pytest.mark.asyncio
    async def test_configuration_error_recovery(self, caplog):
        """Test that services recover gracefully from configuration errors."""
        # Create config manager that fails on first call but succeeds on second
        call_count = 0
        
        async def failing_get_config(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Configuration temporarily unavailable")
            return {"overrides": {"recovered": True}}
        
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_config = failing_get_config
        mock_config_manager.register_change_callback = Mock()
        
        service = MessageHandlerService(mock_config_manager, MessageCounter())
        
        # Capture logs during initialization
        with caplog.at_level(logging.WARNING):
            await service.initialize()
        
        # Verify service still initialized despite configuration error
        assert service._initialized
        
        # Verify warning was logged
        warning_logs = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_logs) > 0
        
        warning_messages = [r.message for r in warning_logs]
        assert any("Failed to load service configuration" in msg for msg in warning_messages)
        
        # Cleanup
        await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_logging_error_handling(self, caplog):
        """Test that logging errors don't break service functionality."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_config = AsyncMock(return_value={"overrides": {}})
        mock_config_manager.register_change_callback = Mock()
        
        service = CallbackHandlerService()
        
        # Mock logger to raise exception
        with patch.object(service, 'logger') as mock_logger:
            mock_logger.info.side_effect = Exception("Logging system error")
            mock_logger.error = Mock()  # Don't let error logging fail too
            
            # Service should still initialize despite logging errors
            await service.initialize()
            
            # Verify error was handled (error logger should be called)
            assert mock_logger.error.called or not mock_logger.info.called
        
        # Cleanup
        await service.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])