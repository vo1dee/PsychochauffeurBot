"""
Unit tests for factories.py module.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Type

from modules.factories import (
    ServiceFactory,
    ConfigurableServiceFactory,
    SingletonServiceFactory,
    DependencyInjectingFactory,
    ServiceFactoryRegistry,
    factory_registry,
    Command,
    TelegramCommand,
    MessageCommand,
    CallbackCommand,
    CommandFactory,
    CommandInvoker
)
from modules.service_registry import ServiceRegistry


class TestServiceFactory:
    """Test ServiceFactory abstract base class."""
    
    def test_service_factory_is_abstract(self):
        """Test that ServiceFactory cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ServiceFactory()


class TestConfigurableServiceFactory:
    """Test ConfigurableServiceFactory class."""
    
    def test_initialization(self):
        """Test ConfigurableServiceFactory initialization."""
        mock_service_type = Mock()
        default_config = {"key": "value"}
        
        factory = ConfigurableServiceFactory(mock_service_type, default_config)
        
        assert factory.service_type == mock_service_type
        assert factory.default_config == default_config
    
    def test_initialization_without_default_config(self):
        """Test ConfigurableServiceFactory initialization without default config."""
        mock_service_type = Mock()
        
        factory = ConfigurableServiceFactory(mock_service_type)
        
        assert factory.service_type == mock_service_type
        assert factory.default_config == {}
    
    def test_get_service_type(self):
        """Test get_service_type method."""
        mock_service_type = Mock()
        factory = ConfigurableServiceFactory(mock_service_type)
        
        result = factory.get_service_type()
        
        assert result == mock_service_type
    
    def test_create_success(self):
        """Test successful service creation."""
        mock_service_type = Mock()
        mock_service_type.__name__ = "TestService"
        mock_instance = Mock()
        mock_service_type.return_value = mock_instance
        
        default_config = {"default_key": "default_value"}
        factory = ConfigurableServiceFactory(mock_service_type, default_config)
        
        mock_service_registry = Mock()
        kwargs = {"custom_key": "custom_value"}
        
        with patch('modules.factories.logger') as mock_logger:
            result = factory.create(mock_service_registry, **kwargs)
        
        # Verify service was created with merged config
        expected_config = {"default_key": "default_value", "custom_key": "custom_value"}
        mock_service_type.assert_called_once_with(**expected_config)
        assert result == mock_instance
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_create_with_exception(self):
        """Test service creation with exception."""
        mock_service_type = Mock()
        mock_service_type.__name__ = "TestService"
        mock_service_type.side_effect = ValueError("Creation failed")
        
        factory = ConfigurableServiceFactory(mock_service_type)
        mock_service_registry = Mock()
        
        with patch('modules.factories.logger') as mock_logger:
            with pytest.raises(ValueError, match="Creation failed"):
                factory.create(mock_service_registry)
        
        # Verify error logging
        mock_logger.error.assert_called_once()


class TestSingletonServiceFactory:
    """Test SingletonServiceFactory class."""
    
    def test_initialization(self):
        """Test SingletonServiceFactory initialization."""
        mock_service_type = Mock()
        factory = SingletonServiceFactory(mock_service_type)
        
        assert factory.service_type == mock_service_type
        assert factory._instance is None
    
    def test_get_service_type(self):
        """Test get_service_type method."""
        mock_service_type = Mock()
        factory = SingletonServiceFactory(mock_service_type)
        
        result = factory.get_service_type()
        
        assert result == mock_service_type
    
    def test_create_first_instance(self):
        """Test creating first singleton instance."""
        mock_service_type = Mock()
        mock_service_type.__name__ = "TestService"
        mock_instance = Mock()
        mock_service_type.return_value = mock_instance
        
        factory = SingletonServiceFactory(mock_service_type)
        mock_service_registry = Mock()
        kwargs = {"key": "value"}
        
        with patch('modules.factories.logger') as mock_logger:
            result = factory.create(mock_service_registry, **kwargs)
        
        # Verify service was created
        mock_service_type.assert_called_once_with(**kwargs)
        assert result == mock_instance
        assert factory._instance == mock_instance
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_create_subsequent_instances(self):
        """Test that subsequent create calls return the same instance."""
        mock_service_type = Mock()
        mock_service_type.__name__ = "TestService"
        mock_instance = Mock()
        mock_service_type.return_value = mock_instance
        
        factory = SingletonServiceFactory(mock_service_type)
        mock_service_registry = Mock()
        
        # Create first instance
        result1 = factory.create(mock_service_registry)
        
        # Create second instance
        result2 = factory.create(mock_service_registry, key="different_value")
        
        # Should return same instance
        assert result1 == result2
        assert result1 == mock_instance
        
        # Service type should only be called once
        mock_service_type.assert_called_once()
    
    def test_create_with_exception(self):
        """Test singleton creation with exception."""
        mock_service_type = Mock()
        mock_service_type.side_effect = ValueError("Creation failed")
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        
        factory = SingletonServiceFactory(mock_service_type)
        mock_service_registry = Mock()
        
        with patch('modules.factories.logger') as mock_logger:
            with pytest.raises(ValueError, match="Creation failed"):
                factory.create(mock_service_registry)
        
        # Verify error logging
        mock_logger.error.assert_called_once()


class TestDependencyInjectingFactory:
    """Test DependencyInjectingFactory class."""
    
    def test_initialization(self):
        """Test DependencyInjectingFactory initialization."""
        mock_service_type = Mock()
        dependencies = {"dep1": "service1", "dep2": "service2"}
        
        factory = DependencyInjectingFactory(mock_service_type, dependencies)
        
        assert factory.service_type == mock_service_type
        assert factory.dependencies == dependencies
    
    def test_initialization_without_dependencies(self):
        """Test DependencyInjectingFactory initialization without dependencies."""
        mock_service_type = Mock()
        
        factory = DependencyInjectingFactory(mock_service_type)
        
        assert factory.service_type == mock_service_type
        assert factory.dependencies == {}
    
    def test_get_service_type(self):
        """Test get_service_type method."""
        mock_service_type = Mock()
        factory = DependencyInjectingFactory(mock_service_type)
        
        result = factory.get_service_type()
        
        assert result == mock_service_type
    
    def test_create_with_dependencies(self):
        """Test service creation with dependency injection."""
        mock_service_type = Mock()
        mock_instance = Mock()
        mock_service_type.return_value = mock_instance
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        
        dependencies = {"dep1": "service1", "dep2": "service2"}
        factory = DependencyInjectingFactory(mock_service_type, dependencies)
        
        mock_service_registry = Mock()
        mock_service1 = Mock()
        mock_service2 = Mock()
        mock_service_registry.get_service.side_effect = [mock_service1, mock_service2]
        
        kwargs = {"custom_key": "custom_value"}
        
        with patch('modules.factories.logger') as mock_logger:
            result = factory.create(mock_service_registry, **kwargs)
        
        # Verify dependencies were resolved
        assert mock_service_registry.get_service.call_count == 2
        mock_service_registry.get_service.assert_any_call("service1")
        mock_service_registry.get_service.assert_any_call("service2")
        
        # Verify service was created with merged config
        expected_config = {
            "dep1": mock_service1,
            "dep2": mock_service2,
            "custom_key": "custom_value"
        }
        mock_service_type.assert_called_once_with(**expected_config)
        assert result == mock_instance
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_create_with_exception(self):
        """Test dependency injection with exception."""
        mock_service_type = Mock()
        mock_service_type.side_effect = ValueError("Creation failed")
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        
        dependencies = {"dep1": "service1"}
        factory = DependencyInjectingFactory(mock_service_type, dependencies)
        
        mock_service_registry = Mock()
        mock_service_registry.get_service.return_value = Mock()
        
        with patch('modules.factories.logger') as mock_logger:
            with pytest.raises(ValueError, match="Creation failed"):
                factory.create(mock_service_registry)
        
        # Verify error logging
        mock_logger.error.assert_called_once()


class TestServiceFactoryRegistry:
    """Test ServiceFactoryRegistry class."""
    
    def test_initialization(self):
        """Test ServiceFactoryRegistry initialization."""
        registry = ServiceFactoryRegistry()
        
        assert registry._factories == {}
    
    def test_register_factory(self):
        """Test registering a factory."""
        registry = ServiceFactoryRegistry()
        mock_factory = Mock()
        mock_service_type = Mock()
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        mock_factory.get_service_type.return_value = mock_service_type
        
        with patch('modules.factories.logger') as mock_logger:
            registry.register_factory("test_service", mock_factory)
        
        assert "test_service" in registry._factories
        assert registry._factories["test_service"] == mock_factory
        
        # Verify logging
        mock_logger.info.assert_called_once()
    
    def test_register_configurable(self):
        """Test registering a configurable service factory."""
        registry = ServiceFactoryRegistry()
        mock_service_type = Mock()
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        default_config = {"key": "value"}
        
        with patch('modules.factories.logger') as mock_logger:
            registry.register_configurable("test_service", mock_service_type, default_config)
        
        assert "test_service" in registry._factories
        factory = registry._factories["test_service"]
        assert isinstance(factory, ConfigurableServiceFactory)
        assert factory.service_type == mock_service_type
        assert factory.default_config == default_config
        
        # Verify logging
        assert mock_logger.info.call_count == 1  # Only once for registration
    
    def test_register_singleton(self):
        """Test registering a singleton service factory."""
        registry = ServiceFactoryRegistry()
        mock_service_type = Mock()
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        
        with patch('modules.factories.logger') as mock_logger:
            registry.register_singleton("test_service", mock_service_type)
        
        assert "test_service" in registry._factories
        factory = registry._factories["test_service"]
        assert isinstance(factory, SingletonServiceFactory)
        assert factory.service_type == mock_service_type
        
        # Verify logging
        assert mock_logger.info.call_count == 1  # Only once for registration
    
    def test_register_with_dependencies(self):
        """Test registering a service factory with dependencies."""
        registry = ServiceFactoryRegistry()
        mock_service_type = Mock()
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        dependencies = {"dep1": "service1"}
        
        with patch('modules.factories.logger') as mock_logger:
            registry.register_with_dependencies("test_service", mock_service_type, dependencies)
        
        assert "test_service" in registry._factories
        factory = registry._factories["test_service"]
        assert isinstance(factory, DependencyInjectingFactory)
        assert factory.service_type == mock_service_type
        assert factory.dependencies == dependencies
        
        # Verify logging
        assert mock_logger.info.call_count == 1  # Only once for registration
    
    def test_create_service_success(self):
        """Test successful service creation."""
        registry = ServiceFactoryRegistry()
        mock_factory = Mock()
        mock_instance = Mock()
        mock_factory.create.return_value = mock_instance
        
        registry._factories["test_service"] = mock_factory
        mock_service_registry = Mock()
        kwargs = {"key": "value"}
        
        result = registry.create_service("test_service", mock_service_registry, **kwargs)
        
        mock_factory.create.assert_called_once_with(mock_service_registry, **kwargs)
        assert result == mock_instance
    
    def test_create_service_not_found(self):
        """Test service creation when factory is not registered."""
        registry = ServiceFactoryRegistry()
        mock_service_registry = Mock()
        
        with pytest.raises(ValueError, match="No factory registered for service: test_service"):
            registry.create_service("test_service", mock_service_registry)
    
    def test_get_factory_found(self):
        """Test getting a registered factory."""
        registry = ServiceFactoryRegistry()
        mock_factory = Mock()
        registry._factories["test_service"] = mock_factory
        
        result = registry.get_factory("test_service")
        
        assert result == mock_factory
    
    def test_get_factory_not_found(self):
        """Test getting a non-registered factory."""
        registry = ServiceFactoryRegistry()
        
        result = registry.get_factory("test_service")
        
        assert result is None
    
    def test_get_registered_factories(self):
        """Test getting all registered factories."""
        registry = ServiceFactoryRegistry()
        mock_factory1 = Mock()
        mock_factory2 = Mock()
        
        registry._factories["service1"] = mock_factory1
        registry._factories["service2"] = mock_factory2
        
        result = registry.get_registered_factories()
        
        assert result == {"service1": mock_factory1, "service2": mock_factory2}
        # Verify it's a copy, not the original
        assert result is not registry._factories


class TestGlobalFactoryRegistry:
    """Test global factory registry."""
    
    def test_global_registry_initialization(self):
        """Test that global factory registry is properly initialized."""
        assert isinstance(factory_registry, ServiceFactoryRegistry)
        assert factory_registry._factories == {}


class TestCommand:
    """Test Command abstract base class."""
    
    def test_command_is_abstract(self):
        """Test that Command cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Command()


class TestTelegramCommand:
    """Test TelegramCommand class."""
    
    def test_initialization(self):
        """Test TelegramCommand initialization."""
        mock_update = Mock()
        mock_context = Mock()
        mock_service_registry = Mock()
        
        # Create a concrete subclass for testing since TelegramCommand is abstract
        class TestCommand(TelegramCommand):
            async def execute(self):
                return "test"
        
        command = TestCommand(mock_update, mock_context, mock_service_registry)
        
        assert command.update == mock_update
        assert command.context == mock_context
        assert command.service_registry == mock_service_registry
    
    @pytest.mark.asyncio
    async def test_undo_default_implementation(self):
        """Test default undo implementation."""
        mock_update = Mock()
        mock_context = Mock()
        mock_service_registry = Mock()
        
        # Create a concrete subclass for testing since TelegramCommand is abstract
        class TestCommand(TelegramCommand):
            async def execute(self):
                return "test"
        
        command = TestCommand(mock_update, mock_context, mock_service_registry)
        
        result = await command.undo()
        
        assert result is None


class TestMessageCommand:
    """Test MessageCommand class."""
    
    def test_initialization(self):
        """Test MessageCommand initialization."""
        mock_update = Mock()
        mock_context = Mock()
        mock_service_registry = Mock()
        mock_message_processor = Mock()
        
        command = MessageCommand(mock_update, mock_context, mock_service_registry, mock_message_processor)
        
        assert command.update == mock_update
        assert command.context == mock_context
        assert command.service_registry == mock_service_registry
        assert command.message_processor == mock_message_processor
    
    @pytest.mark.asyncio
    async def test_execute(self):
        """Test message command execution."""
        mock_update = Mock()
        mock_context = Mock()
        mock_service_registry = Mock()
        mock_message_processor = AsyncMock()
        mock_result = Mock()
        mock_message_processor.process_message.return_value = mock_result
        
        command = MessageCommand(mock_update, mock_context, mock_service_registry, mock_message_processor)
        
        result = await command.execute()
        
        mock_message_processor.process_message.assert_called_once_with(mock_update, mock_context)
        assert result == mock_result


class TestCallbackCommand:
    """Test CallbackCommand class."""
    
    def test_initialization(self):
        """Test CallbackCommand initialization."""
        mock_update = Mock()
        mock_context = Mock()
        mock_service_registry = Mock()
        mock_callback_processor = Mock()
        
        command = CallbackCommand(mock_update, mock_context, mock_service_registry, mock_callback_processor)
        
        assert command.update == mock_update
        assert command.context == mock_context
        assert command.service_registry == mock_service_registry
        assert command.callback_processor == mock_callback_processor
    
    @pytest.mark.asyncio
    async def test_execute(self):
        """Test callback command execution."""
        mock_update = Mock()
        mock_context = Mock()
        mock_service_registry = Mock()
        mock_callback_processor = AsyncMock()
        mock_result = Mock()
        mock_callback_processor.process_callback.return_value = mock_result
        
        command = CallbackCommand(mock_update, mock_context, mock_service_registry, mock_callback_processor)
        
        result = await command.execute()
        
        mock_callback_processor.process_callback.assert_called_once_with(mock_update, mock_context)
        assert result == mock_result


class TestCommandFactory:
    """Test CommandFactory class."""
    
    def test_initialization(self):
        """Test CommandFactory initialization."""
        mock_service_registry = Mock()
        
        factory = CommandFactory(mock_service_registry)
        
        assert factory.service_registry == mock_service_registry
    
    def test_create_message_command(self):
        """Test creating a message command."""
        mock_service_registry = Mock()
        mock_message_processor = Mock()
        mock_service_registry.get_service.return_value = mock_message_processor
        
        factory = CommandFactory(mock_service_registry)
        mock_update = Mock()
        mock_context = Mock()
        
        command = factory.create_message_command(mock_update, mock_context)
        
        assert isinstance(command, MessageCommand)
        assert command.update == mock_update
        assert command.context == mock_context
        assert command.service_registry == mock_service_registry
        assert command.message_processor == mock_message_processor
        
        mock_service_registry.get_service.assert_called_once_with('message_processor')
    
    def test_create_callback_command(self):
        """Test creating a callback command."""
        mock_service_registry = Mock()
        mock_callback_processor = Mock()
        mock_service_registry.get_service.return_value = mock_callback_processor
        
        factory = CommandFactory(mock_service_registry)
        mock_update = Mock()
        mock_context = Mock()
        
        command = factory.create_callback_command(mock_update, mock_context)
        
        assert isinstance(command, CallbackCommand)
        assert command.update == mock_update
        assert command.context == mock_context
        assert command.service_registry == mock_service_registry
        assert command.callback_processor == mock_callback_processor
        
        mock_service_registry.get_service.assert_called_once_with('callback_processor')


class TestCommandInvoker:
    """Test CommandInvoker class."""
    
    def test_initialization(self):
        """Test CommandInvoker initialization."""
        invoker = CommandInvoker()
        
        assert invoker._command_history == []
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        """Test successful command execution."""
        invoker = CommandInvoker()
        mock_command = AsyncMock()
        mock_result = Mock()
        mock_command.execute.return_value = mock_result
        
        result = await invoker.execute_command(mock_command)
        
        mock_command.execute.assert_called_once()
        assert result == mock_result
        assert len(invoker._command_history) == 1
        assert invoker._command_history[0] == mock_command
    
    @pytest.mark.asyncio
    async def test_execute_command_with_exception(self):
        """Test command execution with exception."""
        invoker = CommandInvoker()
        mock_command = AsyncMock()
        mock_command.execute.side_effect = ValueError("Execution failed")
        
        with patch('modules.factories.logger') as mock_logger:
            with pytest.raises(ValueError, match="Execution failed"):
                await invoker.execute_command(mock_command)
        
        # Verify error logging
        mock_logger.error.assert_called_once()
        # Verify command was not added to history
        assert len(invoker._command_history) == 0
    
    @pytest.mark.asyncio
    async def test_undo_last_command_success(self):
        """Test successful command undo."""
        invoker = CommandInvoker()
        mock_command = AsyncMock()
        mock_result = Mock()
        mock_command.undo.return_value = mock_result
        
        # Add command to history
        invoker._command_history.append(mock_command)
        
        result = await invoker.undo_last_command()
        
        mock_command.undo.assert_called_once()
        assert result == mock_result
        assert len(invoker._command_history) == 0
    
    @pytest.mark.asyncio
    async def test_undo_last_command_empty_history(self):
        """Test undo when command history is empty."""
        invoker = CommandInvoker()
        
        result = await invoker.undo_last_command()
        
        assert result is None
        assert len(invoker._command_history) == 0
    
    def test_clear_history(self):
        """Test clearing command history."""
        invoker = CommandInvoker()
        mock_command1 = Mock()
        mock_command2 = Mock()
        
        # Add commands to history
        invoker._command_history = [mock_command1, mock_command2]
        
        invoker.clear_history()
        
        assert len(invoker._command_history) == 0


class TestFactoriesIntegration:
    """Integration tests for factories."""
    
    def test_factory_registry_integration(self):
        """Test integration between factory registry and factories."""
        registry = ServiceFactoryRegistry()
        mock_service_type = Mock()
        mock_service_type.__name__ = "MockService"  # Add __name__ attribute
        mock_instance = Mock()
        mock_service_type.return_value = mock_instance
        
        # Register a configurable factory
        registry.register_configurable("test_service", mock_service_type, {"default": "value"})
        
        # Create service
        mock_service_registry = Mock()
        result = registry.create_service("test_service", mock_service_registry, custom="value")
        
        # Verify service was created with merged config
        expected_config = {"default": "value", "custom": "value"}
        mock_service_type.assert_called_once_with(**expected_config)
        assert result == mock_instance
    
    @pytest.mark.asyncio
    async def test_command_invoker_integration(self):
        """Test integration between command factory and invoker."""
        mock_service_registry = Mock()
        mock_message_processor = AsyncMock()
        mock_service_registry.get_service.return_value = mock_message_processor
        
        factory = CommandFactory(mock_service_registry)
        invoker = CommandInvoker()
        
        mock_update = Mock()
        mock_context = Mock()
        
        # Create and execute command
        command = factory.create_message_command(mock_update, mock_context)
        await invoker.execute_command(command)
        
        # Verify command was executed and added to history
        mock_message_processor.process_message.assert_called_once_with(mock_update, mock_context)
        assert len(invoker._command_history) == 1
        assert invoker._command_history[0] == command 