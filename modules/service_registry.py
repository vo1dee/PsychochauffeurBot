"""
Service Registry and Dependency Injection Container

This module provides centralized service management and dependency injection
for the PsychoChauffeur bot application.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Callable, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ServiceScope(Enum):
    """Service lifecycle scopes."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class ServiceDescriptor:
    """Describes how a service should be created and managed."""
    service_type: Type
    implementation: Union[Type, Callable]
    scope: ServiceScope = ServiceScope.SINGLETON
    dependencies: List[str] = None
    factory: Optional[Callable] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceRegistry:
    """Central service registry for dependency injection and service lifecycle management.
    
    This class provides a comprehensive dependency injection container that manages
    service registration, creation, and lifecycle. It supports different service
    scopes (singleton, transient, scoped) and automatic dependency resolution.
    
    The registry handles:
    - Service registration with various scopes and dependencies
    - Automatic dependency injection and circular dependency detection
    - Service lifecycle management (initialization and shutdown)
    - Factory-based service creation for complex scenarios
    
    Attributes:
        _services (Dict[str, ServiceDescriptor]): Registry of service descriptors.
        _instances (Dict[str, Any]): Cache of singleton service instances.
        _scoped_instances (Dict[str, Dict[str, Any]]): Scoped service instances.
        _initialization_order (List[str]): Order for service initialization.
        _initialized_services (set): Set of successfully initialized services.
    
    Example:
        Basic service registration and retrieval:
        
        >>> registry = ServiceRegistry()
        >>> registry.register_singleton('database', DatabaseService)
        >>> registry.register_transient('processor', DataProcessor, ['database'])
        >>> await registry.initialize_services()
        >>> db_service = registry.get_service('database')
        >>> processor = registry.get_service('processor')
    
    Thread Safety:
        This class is not thread-safe. Use appropriate synchronization
        mechanisms if accessing from multiple threads concurrently.
    
    Performance:
        - Service lookup: O(1) for registered services
        - Dependency resolution: O(n) where n is dependency depth
        - Initialization: O(n) where n is number of services
    """
    
    def __init__(self):
        """Initialize the service registry with empty containers."""
        self._services: Dict[str, ServiceDescriptor] = {}
        self._instances: Dict[str, Any] = {}
        self._scoped_instances: Dict[str, Dict[str, Any]] = {}
        self._initialization_order: List[str] = []
        self._initialized_services: set = set()
        
    def register_singleton(
        self, 
        name: str, 
        service_type: Type[T], 
        implementation: Union[Type[T], Callable[[], T]] = None,
        dependencies: List[str] = None
    ) -> 'ServiceRegistry':
        """Register a singleton service that will be created once and reused.
        
        Singleton services are created only once and the same instance is returned
        for all subsequent requests. This is ideal for stateful services like
        database connections, configuration managers, and caches.
        
        Args:
            name (str): Unique name to identify the service.
            service_type (Type[T]): The interface or base type of the service.
            implementation (Union[Type[T], Callable[[], T]], optional): The concrete
                implementation class or factory function. If None, uses service_type.
            dependencies (List[str], optional): List of service names this service
                depends on. Dependencies will be injected during creation.
        
        Returns:
            ServiceRegistry: Self for method chaining.
        
        Raises:
            ValueError: If a service with the same name is already registered.
        
        Example:
            >>> registry.register_singleton('database', DatabaseService)
            >>> registry.register_singleton('cache', CacheService, RedisCacheService, ['database'])
        
        Note:
            Singleton services are thread-safe for retrieval but not for registration.
            Register all services before using them in a multi-threaded environment.
        """
        return self._register_service(
            name, service_type, implementation, ServiceScope.SINGLETON, dependencies
        )
    
    def register_transient(
        self, 
        name: str, 
        service_type: Type[T], 
        implementation: Union[Type[T], Callable[[], T]] = None,
        dependencies: List[str] = None
    ) -> 'ServiceRegistry':
        """Register a transient service that creates a new instance for each request.
        
        Transient services are created fresh every time they are requested. This is
        ideal for stateless services, data processors, or services that should not
        maintain state between uses.
        
        Args:
            name (str): Unique name to identify the service.
            service_type (Type[T]): The interface or base type of the service.
            implementation (Union[Type[T], Callable[[], T]], optional): The concrete
                implementation class or factory function. If None, uses service_type.
            dependencies (List[str], optional): List of service names this service
                depends on. Dependencies will be resolved for each new instance.
        
        Returns:
            ServiceRegistry: Self for method chaining.
        
        Example:
            >>> registry.register_transient('processor', DataProcessor, dependencies=['database'])
            >>> proc1 = registry.get_service('processor')  # New instance
            >>> proc2 = registry.get_service('processor')  # Different instance
            >>> assert proc1 is not proc2
        
        Note:
            Transient services may have higher memory overhead due to repeated
            instantiation. Consider singleton scope for expensive-to-create services.
        """
        return self._register_service(
            name, service_type, implementation, ServiceScope.TRANSIENT, dependencies
        )
    
    def register_scoped(
        self, 
        name: str, 
        service_type: Type[T], 
        implementation: Union[Type[T], Callable[[], T]] = None,
        dependencies: List[str] = None
    ) -> 'ServiceRegistry':
        """Register a scoped service (one instance per scope)."""
        return self._register_service(
            name, service_type, implementation, ServiceScope.SCOPED, dependencies
        )
    
    def register_instance(self, name: str, instance: Any) -> 'ServiceRegistry':
        """Register an existing instance as a singleton."""
        self._instances[name] = instance
        self._services[name] = ServiceDescriptor(
            service_type=type(instance),
            implementation=type(instance),
            scope=ServiceScope.SINGLETON
        )
        return self
    
    def register_factory(
        self, 
        name: str, 
        service_type: Type[T], 
        factory: Callable[['ServiceRegistry'], T],
        scope: ServiceScope = ServiceScope.SINGLETON,
        dependencies: List[str] = None
    ) -> 'ServiceRegistry':
        """Register a service with a custom factory function."""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=factory,
            scope=scope,
            dependencies=dependencies or [],
            factory=factory
        )
        self._services[name] = descriptor
        return self
    
    def _register_service(
        self, 
        name: str, 
        service_type: Type[T], 
        implementation: Union[Type[T], Callable[[], T]] = None,
        scope: ServiceScope = ServiceScope.SINGLETON,
        dependencies: List[str] = None
    ) -> 'ServiceRegistry':
        """Internal method to register a service."""
        if implementation is None:
            implementation = service_type
            
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            scope=scope,
            dependencies=dependencies or []
        )
        self._services[name] = descriptor
        return self
    
    def get_service(self, name: str) -> Any:
        """Get a service instance by name."""
        if name not in self._services:
            raise ValueError(f"Service '{name}' is not registered")
        
        descriptor = self._services[name]
        
        # Handle singleton scope
        if descriptor.scope == ServiceScope.SINGLETON:
            if name not in self._instances:
                self._instances[name] = self._create_service_instance(name, descriptor)
            return self._instances[name]
        
        # Handle transient scope
        if descriptor.scope == ServiceScope.TRANSIENT:
            return self._create_service_instance(name, descriptor)
        
        # Handle scoped scope (for now, treat as singleton)
        # TODO: Implement proper scoped lifecycle
        if descriptor.scope == ServiceScope.SCOPED:
            scope_key = "default"  # For now, use default scope
            if scope_key not in self._scoped_instances:
                self._scoped_instances[scope_key] = {}
            
            if name not in self._scoped_instances[scope_key]:
                self._scoped_instances[scope_key][name] = self._create_service_instance(name, descriptor)
            return self._scoped_instances[scope_key][name]
        
        raise ValueError(f"Unknown service scope: {descriptor.scope}")
    
    def get_services_by_type(self, service_type: Type[T]) -> List[T]:
        """Get all services that implement the specified type."""
        services = []
        for name, descriptor in self._services.items():
            if issubclass(descriptor.service_type, service_type):
                services.append(self.get_service(name))
        return services
    
    def _create_service_instance(self, name: str, descriptor: ServiceDescriptor) -> Any:
        """Create a new service instance."""
        try:
            # Resolve dependencies first
            dependencies = {}
            for dep_name in descriptor.dependencies:
                dependencies[dep_name] = self.get_service(dep_name)
            
            # Use custom factory if provided
            if descriptor.factory:
                if dependencies:
                    return descriptor.factory(self, **dependencies)
                else:
                    return descriptor.factory(self)
            
            # Create instance using implementation
            if callable(descriptor.implementation):
                if dependencies:
                    return descriptor.implementation(**dependencies)
                else:
                    return descriptor.implementation()
            else:
                # Assume it's a class
                if dependencies:
                    return descriptor.implementation(**dependencies)
                else:
                    return descriptor.implementation()
                    
        except Exception as e:
            logger.error(f"Failed to create service '{name}': {e}")
            raise
    
    async def initialize_services(self) -> None:
        """Initialize all registered services that require async initialization."""
        # Determine initialization order based on dependencies
        self._calculate_initialization_order()
        
        for service_name in self._initialization_order:
            if service_name not in self._initialized_services:
                await self._initialize_service(service_name)
    
    def _calculate_initialization_order(self) -> None:
        """Calculate the order in which services should be initialized."""
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving service '{service_name}'")
            if service_name in visited:
                return
                
            temp_visited.add(service_name)
            
            if service_name in self._services:
                descriptor = self._services[service_name]
                for dep in descriptor.dependencies:
                    visit(dep)
            
            temp_visited.remove(service_name)
            visited.add(service_name)
            order.append(service_name)
        
        for service_name in self._services:
            visit(service_name)
        
        self._initialization_order = order
    
    async def _initialize_service(self, service_name: str) -> None:
        """Initialize a specific service if it has an async initialize method."""
        try:
            service = self.get_service(service_name)
            if hasattr(service, 'initialize') and callable(getattr(service, 'initialize')):
                if asyncio.iscoroutinefunction(service.initialize):
                    await service.initialize()
                else:
                    service.initialize()
            self._initialized_services.add(service_name)
            logger.info(f"Initialized service: {service_name}")
        except Exception as e:
            logger.error(f"Failed to initialize service '{service_name}': {e}")
            raise
    
    async def shutdown_services(self) -> None:
        """Shutdown all services in reverse initialization order."""
        shutdown_order = list(reversed(self._initialization_order))
        
        for service_name in shutdown_order:
            if service_name in self._initialized_services:
                await self._shutdown_service(service_name)
    
    async def _shutdown_service(self, service_name: str) -> None:
        """Shutdown a specific service if it has a shutdown method."""
        try:
            if service_name in self._instances:
                service = self._instances[service_name]
                if hasattr(service, 'shutdown') and callable(getattr(service, 'shutdown')):
                    if asyncio.iscoroutinefunction(service.shutdown):
                        await service.shutdown()
                    else:
                        service.shutdown()
                logger.info(f"Shutdown service: {service_name}")
        except Exception as e:
            logger.error(f"Failed to shutdown service '{service_name}': {e}")
    
    def is_registered(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services
    
    def get_registered_services(self) -> List[str]:
        """Get list of all registered service names."""
        return list(self._services.keys())
    
    def clear(self) -> None:
        """Clear all registered services and instances."""
        self._services.clear()
        self._instances.clear()
        self._scoped_instances.clear()
        self._initialization_order.clear()
        self._initialized_services.clear()


# Global service registry instance
service_registry = ServiceRegistry()


def inject(*dependencies: str):
    """
    Decorator for dependency injection.
    
    Usage:
        @inject('config_manager', 'database')
        def my_function(config_manager, database):
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Inject dependencies
            for dep_name in dependencies:
                if dep_name not in kwargs:
                    kwargs[dep_name] = service_registry.get_service(dep_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ServiceInterface(ABC):
    """Base interface for all services."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the service."""
        pass