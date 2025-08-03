"""
Dependency Injection System Demo

This script demonstrates how the dependency injection system works
in the refactored architecture, showing service registration,
dependency resolution, and lifecycle management.
"""

import asyncio
import logging
from typing import Any

from modules.service_registry import ServiceRegistry, ServiceScope
from modules.service_factories import ServiceFactory
from modules.application_bootstrapper import ApplicationBootstrapper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DemoConfigManager:
    """Demo configuration manager."""
    
    def __init__(self):
        self.config = {"demo": True}
        logger.info("DemoConfigManager created")
    
    async def initialize(self):
        logger.info("DemoConfigManager initialized")
    
    async def shutdown(self):
        logger.info("DemoConfigManager shutdown")


class DemoMessageCounter:
    """Demo message counter."""
    
    def __init__(self):
        self.count = 0
        logger.info("DemoMessageCounter created")
    
    def increment(self):
        self.count += 1
        return self.count


class DemoMessageService:
    """Demo message service with dependencies."""
    
    def __init__(self, config_manager: DemoConfigManager, message_counter: DemoMessageCounter):
        self.config_manager = config_manager
        self.message_counter = message_counter
        logger.info("DemoMessageService created with dependencies")
    
    async def initialize(self):
        logger.info("DemoMessageService initialized")
    
    async def shutdown(self):
        logger.info("DemoMessageService shutdown")
    
    def process_message(self, message: str) -> str:
        count = self.message_counter.increment()
        return f"Processed message #{count}: {message}"


class DemoSpeechService:
    """Demo speech service with config dependency."""
    
    def __init__(self, config_manager: DemoConfigManager):
        self.config_manager = config_manager
        logger.info("DemoSpeechService created with config dependency")
    
    async def initialize(self):
        logger.info("DemoSpeechService initialized")
    
    async def shutdown(self):
        logger.info("DemoSpeechService shutdown")


class DemoCallbackService:
    """Demo callback service with speech service dependency."""
    
    def __init__(self, speech_service: DemoSpeechService):
        self.speech_service = speech_service
        logger.info("DemoCallbackService created with speech service dependency")
    
    async def initialize(self):
        logger.info("DemoCallbackService initialized")
    
    async def shutdown(self):
        logger.info("DemoCallbackService shutdown")


async def demonstrate_basic_dependency_injection():
    """Demonstrate basic dependency injection functionality."""
    logger.info("=== Basic Dependency Injection Demo ===")
    
    registry = ServiceRegistry()
    
    # Register services with dependencies
    registry.register_singleton('config_manager', DemoConfigManager)
    registry.register_singleton('message_counter', DemoMessageCounter)
    
    # Register service with dependencies using factory
    registry.register_factory(
        'message_service',
        DemoMessageService,
        lambda reg, **kwargs: DemoMessageService(
            config_manager=reg.get_service('config_manager'),
            message_counter=reg.get_service('message_counter')
        ),
        dependencies=['config_manager', 'message_counter'],
        scope=ServiceScope.SINGLETON
    )
    
    # Register speech service
    registry.register_factory(
        'speech_service',
        DemoSpeechService,
        lambda reg, **kwargs: DemoSpeechService(
            config_manager=reg.get_service('config_manager')
        ),
        dependencies=['config_manager'],
        scope=ServiceScope.SINGLETON
    )
    
    # Register callback service with speech dependency
    registry.register_factory(
        'callback_service',
        DemoCallbackService,
        lambda reg, **kwargs: DemoCallbackService(
            speech_service=reg.get_service('speech_service')
        ),
        dependencies=['speech_service'],
        scope=ServiceScope.SINGLETON
    )
    
    logger.info("Services registered. Getting services...")
    
    # Get services (they will be created with proper dependencies)
    config_manager = registry.get_service('config_manager')
    message_counter = registry.get_service('message_counter')
    message_service = registry.get_service('message_service')
    speech_service = registry.get_service('speech_service')
    callback_service = registry.get_service('callback_service')
    
    logger.info("All services created successfully!")
    
    # Test service functionality
    result = message_service.process_message("Hello, World!")
    logger.info(f"Message processing result: {result}")
    
    # Initialize services in dependency order
    logger.info("Initializing services...")
    await registry.initialize_services()
    
    # Shutdown services
    logger.info("Shutting down services...")
    await registry.shutdown_services()
    
    logger.info("Basic dependency injection demo completed!")


async def demonstrate_service_factory_patterns():
    """Demonstrate different service factory patterns."""
    logger.info("=== Service Factory Patterns Demo ===")
    
    registry = ServiceRegistry()
    
    # Register using direct factory functions
    registry.register_factory(
        'config_manager',
        DemoConfigManager,
        lambda reg, **kwargs: DemoConfigManager(),
        scope=ServiceScope.SINGLETON
    )
    
    registry.register_factory(
        'message_counter',
        DemoMessageCounter,
        lambda reg, **kwargs: DemoMessageCounter(),
        scope=ServiceScope.SINGLETON
    )
    
    # Register using ServiceFactory class methods (if we had them for demo classes)
    def create_message_service(registry: ServiceRegistry, **kwargs) -> DemoMessageService:
        return DemoMessageService(
            config_manager=registry.get_service('config_manager'),
            message_counter=registry.get_service('message_counter')
        )
    
    registry.register_factory(
        'message_service',
        DemoMessageService,
        create_message_service,
        dependencies=['config_manager', 'message_counter'],
        scope=ServiceScope.SINGLETON
    )
    
    # Test singleton behavior
    service1 = registry.get_service('message_service')
    service2 = registry.get_service('message_service')
    
    logger.info(f"Singleton test: service1 is service2 = {service1 is service2}")
    
    # Test transient behavior
    registry.register_factory(
        'transient_counter',
        DemoMessageCounter,
        lambda reg, **kwargs: DemoMessageCounter(),
        scope=ServiceScope.TRANSIENT
    )
    
    counter1 = registry.get_service('transient_counter')
    counter2 = registry.get_service('transient_counter')
    
    logger.info(f"Transient test: counter1 is counter2 = {counter1 is counter2}")
    
    logger.info("Service factory patterns demo completed!")


async def demonstrate_dependency_order_resolution():
    """Demonstrate dependency order resolution."""
    logger.info("=== Dependency Order Resolution Demo ===")
    
    registry = ServiceRegistry()
    
    initialization_order = []
    
    class ServiceA:
        async def initialize(self):
            initialization_order.append('A')
            logger.info("Service A initialized")
    
    class ServiceB:
        def __init__(self, service_a: ServiceA):
            self.service_a = service_a
        
        async def initialize(self):
            initialization_order.append('B')
            logger.info("Service B initialized")
    
    class ServiceC:
        def __init__(self, service_b: ServiceB):
            self.service_b = service_b
        
        async def initialize(self):
            initialization_order.append('C')
            logger.info("Service C initialized")
    
    # Register services with dependencies (in reverse order to test resolution)
    registry.register_factory(
        'service_c',
        ServiceC,
        lambda reg, **kwargs: ServiceC(reg.get_service('service_b')),
        dependencies=['service_b']
    )
    
    registry.register_factory(
        'service_b',
        ServiceB,
        lambda reg, **kwargs: ServiceB(reg.get_service('service_a')),
        dependencies=['service_a']
    )
    
    registry.register_singleton('service_a', ServiceA)
    
    logger.info("Services registered. Calculating initialization order...")
    
    # Calculate and show initialization order
    registry._calculate_initialization_order()
    logger.info(f"Calculated initialization order: {registry._initialization_order}")
    
    # Initialize services
    await registry.initialize_services()
    
    logger.info(f"Actual initialization order: {initialization_order}")
    
    # Verify dependency injection worked
    service_c = registry.get_service('service_c')
    logger.info(f"Service C has Service B: {service_c.service_b is not None}")
    logger.info(f"Service B has Service A: {service_c.service_b.service_a is not None}")
    
    logger.info("Dependency order resolution demo completed!")


async def demonstrate_error_handling():
    """Demonstrate error handling in dependency injection."""
    logger.info("=== Error Handling Demo ===")
    
    registry = ServiceRegistry()
    
    class FailingService:
        def __init__(self):
            raise RuntimeError("Service initialization failed!")
    
    class WorkingService:
        def __init__(self):
            logger.info("WorkingService created successfully")
    
    # Register both services
    registry.register_singleton('failing_service', FailingService)
    registry.register_singleton('working_service', WorkingService)
    
    # Test error handling
    try:
        failing_service = registry.get_service('failing_service')
    except RuntimeError as e:
        logger.info(f"Expected error caught: {e}")
    
    # Test that other services still work
    working_service = registry.get_service('working_service')
    logger.info("Working service retrieved successfully despite failing service")
    
    logger.info("Error handling demo completed!")


async def main():
    """Run all dependency injection demonstrations."""
    logger.info("Starting Dependency Injection System Demonstrations")
    logger.info("=" * 60)
    
    try:
        await demonstrate_basic_dependency_injection()
        print()
        
        await demonstrate_service_factory_patterns()
        print()
        
        await demonstrate_dependency_order_resolution()
        print()
        
        await demonstrate_error_handling()
        print()
        
        logger.info("All demonstrations completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())