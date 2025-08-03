"""
Integration tests for dependency injection system.

This module tests the complete dependency injection system including
service registration, initialization, and lifecycle management.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Any

from modules.service_registry import ServiceRegistry, ServiceScope
from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_factories import ServiceFactory


class TestDependencyInjectionIntegration:
    """Integration tests for the complete dependency injection system."""
    
    @pytest.mark.asyncio
    async def test_complete_service_registration_and_initialization(self):
        """Test complete service registration and initialization flow."""
        registry = ServiceRegistry()
        
        # Mock all required dependencies
        mock_config_manager = Mock()
        mock_database = Mock()
        mock_message_counter = Mock()
        mock_command_processor = Mock()
        
        # Register core services
        registry.register_instance('config_manager', mock_config_manager)
        registry.register_instance('database', mock_database)
        registry.register_instance('message_counter', mock_message_counter)
        registry.register_instance('command_processor', mock_command_processor)
        
        # Register services with dependencies using factories
        with patch('modules.message_handler_service.MessageHandlerService') as mock_mhs, \
             patch('modules.speech_recognition_service.SpeechRecognitionService') as mock_srs, \
             patch('modules.callback_handler_service.CallbackHandlerService') as mock_chs, \
             patch('modules.command_registry.CommandRegistry') as mock_cr, \
             patch('modules.handler_registry.HandlerRegistry') as mock_hr:
            
            # Setup mock returns
            mock_mhs_instance = Mock()
            mock_srs_instance = Mock()
            mock_chs_instance = Mock()
            mock_cr_instance = Mock()
            mock_hr_instance = Mock()
            
            mock_mhs.return_value = mock_mhs_instance
            mock_srs.return_value = mock_srs_instance
            mock_chs.return_value = mock_chs_instance
            mock_cr.return_value = mock_cr_instance
            mock_hr.return_value = mock_hr_instance
            
            # Add async initialize methods
            mock_mhs_instance.initialize = AsyncMock()
            mock_srs_instance.initialize = AsyncMock()
            mock_chs_instance.initialize = AsyncMock()
            mock_cr_instance.initialize = AsyncMock()
            mock_hr_instance.initialize = AsyncMock()
            
            # Register services
            registry.register_factory(
                'message_handler_service',
                type(None),
                ServiceFactory.create_message_handler_service,
                dependencies=['config_manager', 'message_counter'],
                scope=ServiceScope.SINGLETON
            )
            
            registry.register_factory(
                'speech_recognition_service',
                type(None),
                ServiceFactory.create_speech_recognition_service,
                dependencies=['config_manager'],
                scope=ServiceScope.SINGLETON
            )
            
            registry.register_factory(
                'callback_handler_service',
                type(None),
                ServiceFactory.create_callback_handler_service,
                dependencies=['speech_recognition_service'],
                scope=ServiceScope.SINGLETON
            )
            
            registry.register_factory(
                'command_registry',
                type(None),
                ServiceFactory.create_command_registry,
                dependencies=['command_processor'],
                scope=ServiceScope.SINGLETON
            )
            
            registry.register_factory(
                'handler_registry',
                type(None),
                ServiceFactory.create_handler_registry,
                dependencies=['command_processor'],
                scope=ServiceScope.SINGLETON
            )
            
            # Test service creation with proper dependency injection
            mhs = registry.get_service('message_handler_service')
            srs = registry.get_service('speech_recognition_service')
            chs = registry.get_service('callback_handler_service')
            cr = registry.get_service('command_registry')
            hr = registry.get_service('handler_registry')
            
            # Verify services were created
            assert mhs == mock_mhs_instance
            assert srs == mock_srs_instance
            assert chs == mock_chs_instance
            assert cr == mock_cr_instance
            assert hr == mock_hr_instance
            
            # Verify dependencies were injected correctly
            mock_mhs.assert_called_once_with(
                config_manager=mock_config_manager,
                message_counter=mock_message_counter
            )
            mock_srs.assert_called_once_with(config_manager=mock_config_manager)
            mock_chs.assert_called_once_with(speech_service=mock_srs_instance)
            mock_cr.assert_called_once_with(command_processor=mock_command_processor)
            mock_hr.assert_called_once_with(
                command_processor=mock_command_processor,
                service_registry=registry
            )
            
            # Test service initialization
            await registry.initialize_services()
            
            # Verify all services were initialized
            mock_mhs_instance.initialize.assert_called_once()
            mock_srs_instance.initialize.assert_called_once()
            mock_chs_instance.initialize.assert_called_once()
            mock_cr_instance.initialize.assert_called_once()
            mock_hr_instance.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_service_dependency_order_resolution(self):
        """Test that services are initialized in correct dependency order."""
        registry = ServiceRegistry()
        
        initialization_order = []
        
        class ServiceA:
            async def initialize(self):
                initialization_order.append('A')
        
        class ServiceB:
            def __init__(self, service_a: ServiceA):
                self.service_a = service_a
            
            async def initialize(self):
                initialization_order.append('B')
        
        class ServiceC:
            def __init__(self, service_b: ServiceB):
                self.service_b = service_b
            
            async def initialize(self):
                initialization_order.append('C')
        
        # Register services with dependencies
        registry.register_singleton('service_a', ServiceA)
        
        registry.register_factory(
            'service_b',
            ServiceB,
            lambda reg, **kwargs: ServiceB(reg.get_service('service_a')),
            dependencies=['service_a']
        )
        
        registry.register_factory(
            'service_c',
            ServiceC,
            lambda reg, **kwargs: ServiceC(reg.get_service('service_b')),
            dependencies=['service_b']
        )
        
        # Initialize services
        await registry.initialize_services()
        
        # Verify initialization order
        assert initialization_order == ['A', 'B', 'C']
    
    @pytest.mark.asyncio
    async def test_application_bootstrapper_service_configuration(self):
        """Test that ApplicationBootstrapper properly configures all services."""
        with patch('modules.const.Config') as mock_config, \
             patch('config.config_manager.ConfigManager') as mock_config_manager_class, \
             patch('modules.database.Database') as mock_database_class, \
             patch('modules.bot_application.BotApplication') as mock_bot_app_class:
            
            # Setup mock configuration
            mock_config.TELEGRAM_BOT_TOKEN = "test_token"
            mock_config.ERROR_CHANNEL_ID = "test_channel"
            
            # Setup mock class returns
            mock_config_manager = Mock()
            mock_database = Mock()
            mock_bot_app = Mock()
            
            mock_config_manager_class.return_value = mock_config_manager
            mock_database_class.return_value = mock_database
            mock_bot_app_class.return_value = mock_bot_app
            
            # Create bootstrapper and configure services
            bootstrapper = ApplicationBootstrapper()
            registry = await bootstrapper.configure_services()
            
            # Verify registry was created
            assert registry is not None
            assert isinstance(registry, ServiceRegistry)
            
            # Verify core services are registered
            registered_services = registry.get_registered_services()
            assert 'service_config' in registered_services
            assert 'config_manager' in registered_services
            assert 'database' in registered_services
            assert 'bot_application' in registered_services
            
            # Verify services can be retrieved
            service_config = registry.get_service('service_config')
            config_manager = registry.get_service('config_manager')
            database = registry.get_service('database')
            bot_application = registry.get_service('bot_application')
            
            assert service_config is not None
            assert config_manager == mock_config_manager
            assert database == mock_database
            assert bot_application == mock_bot_app
    
    @pytest.mark.asyncio
    async def test_service_error_handling_and_recovery(self):
        """Test that service errors are handled gracefully."""
        registry = ServiceRegistry()
        
        class FailingService:
            def __init__(self):
                raise RuntimeError("Service initialization failed")
        
        class WorkingService:
            def __init__(self):
                self.initialized = False
            
            async def initialize(self):
                self.initialized = True
        
        # Register both services
        registry.register_singleton('failing_service', FailingService)
        registry.register_singleton('working_service', WorkingService)
        
        # Test that failing service raises error
        with pytest.raises(RuntimeError, match="Service initialization failed"):
            registry.get_service('failing_service')
        
        # Test that working service still works
        working_service = registry.get_service('working_service')
        assert working_service is not None
        
        # Test initialization of working service
        await registry.initialize_services()
        assert working_service.initialized is True
    
    def test_service_factory_patterns(self):
        """Test different service factory patterns."""
        registry = ServiceRegistry()
        
        # Test no-dependency service
        class SimpleService:
            def __init__(self):
                self.value = "simple"
        
        registry.register_factory(
            'simple_service',
            SimpleService,
            lambda reg: SimpleService()
        )
        
        simple = registry.get_service('simple_service')
        assert simple.value == "simple"
        
        # Test service with dependencies
        class DependentService:
            def __init__(self, simple_service: SimpleService):
                self.simple_service = simple_service
                self.value = "dependent"
        
        registry.register_factory(
            'dependent_service',
            DependentService,
            lambda reg, **kwargs: DependentService(reg.get_service('simple_service')),
            dependencies=['simple_service']
        )
        
        dependent = registry.get_service('dependent_service')
        assert dependent.value == "dependent"
        assert dependent.simple_service == simple
        
        # Test singleton behavior
        dependent2 = registry.get_service('dependent_service')
        assert dependent is dependent2  # Same instance
    
    @pytest.mark.asyncio
    async def test_service_lifecycle_management(self):
        """Test complete service lifecycle management."""
        registry = ServiceRegistry()
        
        lifecycle_events = []
        
        class LifecycleService:
            def __init__(self):
                lifecycle_events.append('created')
            
            async def initialize(self):
                lifecycle_events.append('initialized')
            
            async def shutdown(self):
                lifecycle_events.append('shutdown')
        
        # Register service
        registry.register_singleton('lifecycle_service', LifecycleService)
        
        # Create service
        service = registry.get_service('lifecycle_service')
        assert 'created' in lifecycle_events
        
        # Initialize services
        await registry.initialize_services()
        assert 'initialized' in lifecycle_events
        
        # Shutdown services
        await registry.shutdown_services()
        assert 'shutdown' in lifecycle_events
        
        # Verify complete lifecycle
        assert lifecycle_events == ['created', 'initialized', 'shutdown']
    
    def test_service_registry_validation_and_introspection(self):
        """Test service registry validation and introspection capabilities."""
        registry = ServiceRegistry()
        
        class TestService:
            def __init__(self):
                self.name = "test"
        
        # Test service registration
        registry.register_singleton('test_service', TestService)
        
        # Test introspection
        assert registry.is_registered('test_service') is True
        assert registry.is_registered('non_existent') is False
        
        registered_services = registry.get_registered_services()
        assert 'test_service' in registered_services
        
        # Test service retrieval
        service = registry.get_service('test_service')
        assert service.name == "test"
        
        # Test error handling for non-existent service
        with pytest.raises(ValueError, match="Service 'non_existent' is not registered"):
            registry.get_service('non_existent')
        
        # Test clearing registry
        registry.clear()
        assert len(registry.get_registered_services()) == 0
        assert registry.is_registered('test_service') is False