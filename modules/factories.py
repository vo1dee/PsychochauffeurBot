"""
Factory patterns for service creation.

This module implements various factory patterns to create and configure
services and components in a standardized way.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Type, TypeVar, Optional, List

from modules.service_registry import ServiceRegistry

T = TypeVar('T')
logger = logging.getLogger(__name__)


class ServiceFactory(ABC):
    """Abstract base class for service factories."""
    
    @abstractmethod
    def create(self, service_registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create a service instance."""
        pass
    
    @abstractmethod
    def get_service_type(self) -> Type[Any]:
        """Get the type of service this factory creates."""
        pass


class ConfigurableServiceFactory(ServiceFactory):
    """Factory for creating configurable services."""
    
    def __init__(self, service_type: Type[Any], default_config: Optional[Dict[str, Any]] = None):
        self.service_type = service_type
        self.default_config = default_config or {}
    
    def create(self, service_registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create a configured service instance."""
        # Merge default config with provided kwargs
        config = {**self.default_config, **kwargs}
        
        try:
            # Create instance with configuration
            instance = self.service_type(**config)
            logger.info(f"Created {self.service_type.__name__} with config: {config}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create {self.service_type.__name__}: {e}")
            raise
    
    def get_service_type(self) -> Type[Any]:
        """Get the service type."""
        return self.service_type


class SingletonServiceFactory(ServiceFactory):
    """Factory that ensures only one instance of a service is created."""
    
    def __init__(self, service_type: Type[Any]):
        self.service_type = service_type
        self._instance: Optional[Any] = None
    
    def create(self, service_registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create or return existing singleton instance."""
        if self._instance is None:
            try:
                self._instance = self.service_type(**kwargs)
                logger.info(f"Created singleton {self.service_type.__name__}")
            except Exception as e:
                logger.error(f"Failed to create singleton {self.service_type.__name__}: {e}")
                raise
        
        return self._instance
    
    def get_service_type(self) -> Type[Any]:
        """Get the service type."""
        return self.service_type


class DependencyInjectingFactory(ServiceFactory):
    """Factory that automatically injects dependencies."""
    
    def __init__(self, service_type: Type[Any], dependencies: Optional[Dict[str, str]] = None):
        self.service_type = service_type
        self.dependencies = dependencies or {}
    
    def create(self, service_registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create service with injected dependencies."""
        # Resolve dependencies
        resolved_deps = {}
        for param_name, service_name in self.dependencies.items():
            resolved_deps[param_name] = service_registry.get_service(service_name)
        
        # Merge dependencies with provided kwargs
        config = {**resolved_deps, **kwargs}
        
        try:
            instance = self.service_type(**config)
            logger.info(f"Created {self.service_type.__name__} with dependencies: {list(self.dependencies.keys())}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create {self.service_type.__name__} with dependencies: {e}")
            raise
    
    def get_service_type(self) -> Type[Any]:
        """Get the service type."""
        return self.service_type


class ServiceFactoryRegistry:
    """Registry for managing service factories."""
    
    def __init__(self) -> None:
        self._factories: Dict[str, ServiceFactory] = {}
    
    def register_factory(self, name: str, factory: ServiceFactory) -> None:
        """Register a service factory."""
        self._factories[name] = factory
        logger.info(f"Registered factory: {name} for {factory.get_service_type().__name__}")
    
    def register_configurable(self, name: str, service_type: Type[Any], default_config: Optional[Dict[str, Any]] = None) -> None:
        """Register a configurable service factory."""
        factory = ConfigurableServiceFactory(service_type, default_config)
        self.register_factory(name, factory)
    
    def register_singleton(self, name: str, service_type: Type[Any]) -> None:
        """Register a singleton service factory."""
        factory = SingletonServiceFactory(service_type)
        self.register_factory(name, factory)
    
    def register_with_dependencies(self, name: str, service_type: Type[Any], dependencies: Dict[str, str]) -> None:
        """Register a service factory with dependency injection."""
        factory = DependencyInjectingFactory(service_type, dependencies)
        self.register_factory(name, factory)
    
    def create_service(self, name: str, service_registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create a service using its registered factory."""
        if name not in self._factories:
            raise ValueError(f"No factory registered for service: {name}")
        
        factory = self._factories[name]
        return factory.create(service_registry, **kwargs)
    
    def get_factory(self, name: str) -> Optional[ServiceFactory]:
        """Get a registered factory by name."""
        return self._factories.get(name)
    
    def get_registered_factories(self) -> Dict[str, ServiceFactory]:
        """Get all registered factories."""
        return self._factories.copy()


# Global factory registry
factory_registry = ServiceFactoryRegistry()


# Command Factory Pattern Implementation
class Command(ABC):
    """Abstract command interface."""
    
    @abstractmethod
    async def execute(self) -> Any:
        """Execute the command."""
        pass
    
    @abstractmethod
    async def undo(self) -> Any:
        """Undo the command (if supported)."""
        pass


class TelegramCommand(Command):
    """Base class for Telegram bot commands."""
    
    def __init__(self, update: Any, context: Any, service_registry: ServiceRegistry) -> None:
        self.update = update
        self.context = context
        self.service_registry = service_registry
    
    async def undo(self) -> Any:
        """Default undo implementation (no-op)."""
        pass


class MessageCommand(TelegramCommand):
    """Command for processing messages."""
    
    def __init__(self, update: Any, context: Any, service_registry: ServiceRegistry, message_processor: Any) -> None:
        super().__init__(update, context, service_registry)
        self.message_processor = message_processor
    
    async def execute(self) -> Any:
        """Execute message processing."""
        return await self.message_processor.process_message(self.update, self.context)


class CallbackCommand(TelegramCommand):
    """Command for processing callback queries."""
    
    def __init__(self, update: Any, context: Any, service_registry: ServiceRegistry, callback_processor: Any) -> None:
        super().__init__(update, context, service_registry)
        self.callback_processor = callback_processor
    
    async def execute(self) -> Any:
        """Execute callback processing."""
        return await self.callback_processor.process_callback(self.update, self.context)


class CommandFactory:
    """Factory for creating command objects."""
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
    
    def create_message_command(self, update: Any, context: Any) -> MessageCommand:
        """Create a message command."""
        message_processor = self.service_registry.get_service('message_processor')
        return MessageCommand(update, context, self.service_registry, message_processor)
    
    def create_callback_command(self, update: Any, context: Any) -> CallbackCommand:
        """Create a callback command."""
        callback_processor = self.service_registry.get_service('callback_processor')
        return CallbackCommand(update, context, self.service_registry, callback_processor)


class CommandInvoker:
    """Invoker for executing commands."""
    
    def __init__(self) -> None:
        self._command_history: List[Any] = []
    
    async def execute_command(self, command: Command) -> Any:
        """Execute a command and store it in history."""
        try:
            result = await command.execute()
            self._command_history.append(command)
            return result
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise
    
    async def undo_last_command(self) -> Any:
        """Undo the last executed command."""
        if not self._command_history:
            return None
        
        last_command = self._command_history.pop()
        return await last_command.undo()
    
    def clear_history(self) -> None:
        """Clear command history."""
        self._command_history.clear()