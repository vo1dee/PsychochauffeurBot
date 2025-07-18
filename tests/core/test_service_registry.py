"""
Unit tests for the ServiceRegistry and dependency injection system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import List

from modules.service_registry import (
    ServiceRegistry, ServiceScope, ServiceDescriptor, ServiceInterface, inject
)


class MockService(ServiceInterface):
    """Mock service for testing."""
    
    def __init__(self, name: str = "mock"):
        self.name = name
        self.initialized = False
        self.shutdown_called = False
    
    async def initialize(self) -> None:
        self.initialized = True
    
    async def shutdown(self) -> None:
        self.shutdown_called = True


class MockServiceWithDependency(ServiceInterface):
    """Mock service with dependencies for testing.
    
    This service is designed to work with the ServiceRegistry's dependency injection
    system. It expects dependencies to be passed as keyword arguments where the
    key is the dependency name and the value is the resolved service instance.
    """
    
    def __init__(self, **kwargs):
        """Initialize the service with injected dependencies.
        
        Args:
            **kwargs: Dependencies injected by the service registry.
                     The service registry passes dependencies as keyword arguments
                     where the key is the dependency name from the registration.
        
        Raises:
            ValueError: If no dependencies are provided when at least one is expected.
        """
        # Store all injected dependencies for inspection
        self.injected_dependencies = kwargs.copy()
        
        # Extract primary dependency - support common dependency names used in tests
        self.dependency = (
            kwargs.get('dependency') or 
            kwargs.get('base_service') or
            kwargs.get('service') or
            kwargs.get('dep')
        )
        
        # If no known dependency names found, take the first available dependency
        if self.dependency is None and kwargs:
            self.dependency = next(iter(kwargs.values()))
        
        # Validate that we received at least one dependency
        if self.dependency is None:
            raise ValueError(
                f"MockServiceWithDependency requires at least one dependency parameter. "
                f"Expected one of: 'dependency', 'base_service', 'service', 'dep', "
                f"or any other dependency name. Received: {list(kwargs.keys())}"
            )
        
        # Service lifecycle tracking
        self.initialized = False
        self.shutdown_called = False
    
    async def initialize(self) -> None:
        """Initialize the service asynchronously."""
        self.initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown the service asynchronously."""
        self.shutdown_called = True
    
    def get_dependency(self, name: str):
        """Get a specific injected dependency by name.
        
        Args:
            name: The name of the dependency to retrieve.
            
        Returns:
            The dependency instance, or None if not found.
        """
        return self.injected_dependencies.get(name)
    
    def has_dependency(self, name: str) -> bool:
        """Check if a specific dependency was injected.
        
        Args:
            name: The name of the dependency to check.
            
        Returns:
            True if the dependency was injected, False otherwise.
        """
        return name in self.injected_dependencies
    
    @property
    def dependency_count(self) -> int:
        """Get the number of injected dependencies."""
        return len(self.injected_dependencies)


class MockServiceFactory:
    """Factory for creating mock services."""
    
    @staticmethod
    def create_service(registry: ServiceRegistry) -> MockService:
        return MockService("factory_created")


class TestServiceRegistry:
    """Test cases for ServiceRegistry."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh service registry for each test."""
        return ServiceRegistry()
    
    def test_register_singleton(self, registry):
        """Test singleton service registration."""
        registry.register_singleton('test_service', MockService)
        
        assert registry.is_registered('test_service')
        assert 'test_service' in registry.get_registered_services()
    
    def test_register_transient(self, registry):
        """Test transient service registration."""
        registry.register_transient('test_service', MockService)
        
        assert registry.is_registered('test_service')
        service_descriptor = registry._services['test_service']
        assert service_descriptor.scope == ServiceScope.TRANSIENT
    
    def test_register_scoped(self, registry):
        """Test scoped service registration."""
        registry.register_scoped('test_service', MockService)
        
        assert registry.is_registered('test_service')
        service_descriptor = registry._services['test_service']
        assert service_descriptor.scope == ServiceScope.SCOPED
    
    def test_register_instance(self, registry):
        """Test instance registration."""
        instance = MockService("test_instance")
        registry.register_instance('test_service', instance)
        
        retrieved = registry.get_service('test_service')
        assert retrieved is instance
        assert retrieved.name == "test_instance"
    
    def test_register_factory(self, registry):
        """Test factory registration."""
        registry.register_factory(
            'test_service',
            MockService,
            MockServiceFactory.create_service
        )
        
        service = registry.get_service('test_service')
        assert isinstance(service, MockService)
        assert service.name == "factory_created"
    
    def test_singleton_scope_behavior(self, registry):
        """Test that singleton services return the same instance."""
        registry.register_singleton('test_service', MockService)
        
        service1 = registry.get_service('test_service')
        service2 = registry.get_service('test_service')
        
        assert service1 is service2
    
    def test_transient_scope_behavior(self, registry):
        """Test that transient services return new instances."""
        registry.register_transient('test_service', MockService)
        
        service1 = registry.get_service('test_service')
        service2 = registry.get_service('test_service')
        
        assert service1 is not service2
        assert isinstance(service1, MockService)
        assert isinstance(service2, MockService)
    
    def test_dependency_injection(self, registry):
        """Test dependency injection between services."""
        registry.register_singleton('dependency', MockService)
        registry.register_singleton(
            'service_with_dep',
            MockServiceWithDependency,
            dependencies=['dependency']
        )
        
        service = registry.get_service('service_with_dep')
        assert isinstance(service, MockServiceWithDependency)
        assert isinstance(service.dependency, MockService)
        assert service.has_dependency('dependency')
        assert service.dependency_count == 1
    
    def test_circular_dependency_detection(self, registry):
        """Test that circular dependencies are detected."""
        # Create services with circular dependencies
        registry._services['service_a'] = ServiceDescriptor(
            service_type=MockService,
            implementation=MockService,
            dependencies=['service_b']
        )
        registry._services['service_b'] = ServiceDescriptor(
            service_type=MockService,
            implementation=MockService,
            dependencies=['service_a']
        )
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            registry._calculate_initialization_order()
    
    def test_get_services_by_type(self, registry):
        """Test getting services by type."""
        registry.register_singleton('service1', MockService)
        registry.register_singleton('service2', MockService)
        registry.register_singleton('service3', str)  # Different type
        
        mock_services = registry.get_services_by_type(MockService)
        assert len(mock_services) == 2
        assert all(isinstance(s, MockService) for s in mock_services)
    
    def test_service_not_found(self, registry):
        """Test error when requesting non-existent service."""
        with pytest.raises(ValueError, match="Service 'nonexistent' is not registered"):
            registry.get_service('nonexistent')
    
    @pytest.mark.asyncio
    async def test_initialize_services(self, registry):
        """Test service initialization."""
        registry.register_singleton('test_service', MockService)
        
        await registry.initialize_services()
        
        service = registry.get_service('test_service')
        assert service.initialized
    
    @pytest.mark.asyncio
    async def test_initialize_services_with_dependencies(self, registry):
        """Test service initialization with dependencies."""
        registry.register_singleton('dependency', MockService)
        registry.register_singleton(
            'service_with_dep',
            MockServiceWithDependency,
            dependencies=['dependency']
        )
        
        await registry.initialize_services()
        
        dependency = registry.get_service('dependency')
        service = registry.get_service('service_with_dep')
        
        assert dependency.initialized
        assert service.initialized
    
    @pytest.mark.asyncio
    async def test_shutdown_services(self, registry):
        """Test service shutdown."""
        registry.register_singleton('test_service', MockService)
        
        await registry.initialize_services()
        service = registry.get_service('test_service')
        
        await registry.shutdown_services()
        
        assert service.shutdown_called
    
    def test_clear_registry(self, registry):
        """Test clearing the registry."""
        registry.register_singleton('test_service', MockService)
        registry.register_instance('test_instance', MockService())
        
        assert len(registry.get_registered_services()) == 2
        
        registry.clear()
        
        assert len(registry.get_registered_services()) == 0
        assert not registry.is_registered('test_service')
        assert not registry.is_registered('test_instance')
    
    def test_multiple_dependency_injection(self, registry):
        """Test service with multiple dependencies."""
        registry.register_singleton('service1', MockService)
        registry.register_singleton('service2', MockService)
        registry.register_singleton(
            'service_with_multiple_deps',
            MockServiceWithDependency,
            dependencies=['service1', 'service2']
        )
        
        service = registry.get_service('service_with_multiple_deps')
        assert isinstance(service, MockServiceWithDependency)
        assert service.dependency_count == 2
        assert service.has_dependency('service1')
        assert service.has_dependency('service2')
        assert isinstance(service.get_dependency('service1'), MockService)
        assert isinstance(service.get_dependency('service2'), MockService)
    
    def test_dependency_injection_with_custom_names(self, registry):
        """Test dependency injection with various dependency names."""
        registry.register_singleton('base_service', MockService)
        registry.register_singleton(
            'dependent_service',
            MockServiceWithDependency,
            dependencies=['base_service']
        )
        
        service = registry.get_service('dependent_service')
        assert isinstance(service, MockServiceWithDependency)
        assert isinstance(service.dependency, MockService)
        assert service.has_dependency('base_service')
        assert service.get_dependency('base_service') is service.dependency
    
    def test_mock_service_with_dependency_error_handling(self):
        """Test MockServiceWithDependency error handling for missing dependencies."""
        # Test that creating MockServiceWithDependency without dependencies raises clear error
        with pytest.raises(ValueError) as exc_info:
            MockServiceWithDependency()
        
        error_message = str(exc_info.value)
        assert "MockServiceWithDependency requires at least one dependency parameter" in error_message
        assert "Expected one of: 'dependency', 'base_service', 'service', 'dep'" in error_message
        assert "Received: []" in error_message
    
    def test_mock_service_with_dependency_unknown_params(self):
        """Test MockServiceWithDependency with unknown parameter names."""
        mock_service = MockService("test")
        service = MockServiceWithDependency(unknown_param=mock_service)
        
        # Should still work by taking the first available dependency
        assert service.dependency is mock_service
        assert service.has_dependency('unknown_param')
        assert service.get_dependency('unknown_param') is mock_service


class TestServiceDescriptor:
    """Test cases for ServiceDescriptor."""
    
    def test_service_descriptor_creation(self):
        """Test ServiceDescriptor creation."""
        descriptor = ServiceDescriptor(
            service_type=MockService,
            implementation=MockService,
            scope=ServiceScope.SINGLETON,
            dependencies=['dep1', 'dep2']
        )
        
        assert descriptor.service_type == MockService
        assert descriptor.implementation == MockService
        assert descriptor.scope == ServiceScope.SINGLETON
        assert descriptor.dependencies == ['dep1', 'dep2']
    
    def test_service_descriptor_defaults(self):
        """Test ServiceDescriptor default values."""
        descriptor = ServiceDescriptor(
            service_type=MockService,
            implementation=MockService
        )
        
        assert descriptor.scope == ServiceScope.SINGLETON
        assert descriptor.dependencies == []
        assert descriptor.factory is None


class TestDependencyInjectionDecorator:
    """Test cases for the @inject decorator."""
    
    @pytest.fixture
    def registry_with_services(self):
        """Create a registry with test services."""
        registry = ServiceRegistry()
        registry.register_instance('service1', MockService("service1"))
        registry.register_instance('service2', MockService("service2"))
        return registry
    
    def test_inject_decorator(self, registry_with_services, monkeypatch):
        """Test the @inject decorator."""
        # Mock the global service registry
        import modules.service_registry
        monkeypatch.setattr(modules.service_registry, 'service_registry', registry_with_services)
        
        @inject('service1', 'service2')
        def test_function(arg1, service1=None, service2=None):
            return arg1, service1.name, service2.name
        
        result = test_function("test_arg")
        assert result == ("test_arg", "service1", "service2")
    
    def test_inject_decorator_with_existing_kwargs(self, registry_with_services, monkeypatch):
        """Test @inject decorator when kwargs are already provided."""
        import modules.service_registry
        monkeypatch.setattr(modules.service_registry, 'service_registry', registry_with_services)
        
        @inject('service1')
        def test_function(service1=None):
            return service1.name
        
        # Provide service1 explicitly
        custom_service = MockService("custom")
        result = test_function(service1=custom_service)
        assert result == "custom"


class TestServiceInterface:
    """Test cases for ServiceInterface."""
    
    def test_service_interface_is_abstract(self):
        """Test that ServiceInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ServiceInterface()
    
    def test_mock_service_implements_interface(self):
        """Test that MockService properly implements ServiceInterface."""
        service = MockService()
        assert isinstance(service, ServiceInterface)
        assert hasattr(service, 'initialize')
        assert hasattr(service, 'shutdown')


class TestServiceRegistryIntegration:
    """Integration tests for ServiceRegistry."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete service lifecycle."""
        registry = ServiceRegistry()
        
        # Register services
        registry.register_singleton('base_service', MockService)
        registry.register_singleton(
            'dependent_service',
            MockServiceWithDependency,
            dependencies=['base_service']
        )
        
        # Initialize
        await registry.initialize_services()
        
        # Verify services are initialized
        base_service = registry.get_service('base_service')
        dependent_service = registry.get_service('dependent_service')
        
        assert base_service.initialized
        assert dependent_service.initialized
        assert dependent_service.dependency is base_service
        
        # Shutdown
        await registry.shutdown_services()
        
        assert base_service.shutdown_called
        assert dependent_service.shutdown_called
    
    @pytest.mark.asyncio
    async def test_error_handling_during_initialization(self):
        """Test error handling during service initialization."""
        class FailingService(ServiceInterface):
            async def initialize(self):
                raise RuntimeError("Initialization failed")
            
            async def shutdown(self):
                pass
        
        registry = ServiceRegistry()
        registry.register_singleton('failing_service', FailingService)
        
        with pytest.raises(RuntimeError, match="Initialization failed"):
            await registry.initialize_services()
    
    @pytest.mark.asyncio
    async def test_partial_initialization_cleanup(self):
        """Test cleanup when initialization partially fails."""
        class FailingService(ServiceInterface):
            async def initialize(self):
                raise RuntimeError("Initialization failed")
            
            async def shutdown(self):
                pass
        
        registry = ServiceRegistry()
        registry.register_singleton('good_service', MockService)
        registry.register_singleton('failing_service', FailingService)
        
        try:
            await registry.initialize_services()
        except RuntimeError:
            pass
        
        # Good service should still be initialized
        good_service = registry.get_service('good_service')
        assert good_service.initialized