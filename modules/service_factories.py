"""
Service Factories for Dependency Injection

This module provides factory functions for creating services with proper
dependency injection. These factories are used by the ServiceRegistry
to create service instances with their dependencies properly resolved.
"""

import logging
from typing import Any, Callable, Optional

from modules.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory class for creating services with dependency injection."""
    
    @staticmethod
    def create_message_handler_service(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create MessageHandlerService with injected dependencies."""
        from modules.message_handler_service import MessageHandlerService
        
        config_manager = registry.get_service('config_manager')
        message_counter = registry.get_service('message_counter')
        
        logger.debug("Creating MessageHandlerService with injected dependencies")
        return MessageHandlerService(
            config_manager=config_manager,
            message_counter=message_counter
        )
    
    @staticmethod
    def create_speech_recognition_service(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create SpeechRecognitionService with injected dependencies."""
        try:
            from modules.speech_recognition_service import SpeechRecognitionService
            
            config_manager = registry.get_service('config_manager')
            logger.info(f"Creating SpeechRecognitionService with config_manager: {type(config_manager).__name__}")
            
            service = SpeechRecognitionService(config_manager=config_manager)
            logger.info("SpeechRecognitionService created successfully")
            return service
        except Exception as e:
            logger.error(f"Failed to create SpeechRecognitionService: {e}", exc_info=True)
            raise
    
    @staticmethod
    def create_callback_handler_service(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create CallbackHandlerService with injected dependencies."""
        from modules.callback_handler_service import CallbackHandlerService
        
        speech_service = registry.get_service('speech_recognition_service')
        
        logger.debug("Creating CallbackHandlerService with injected dependencies")
        return CallbackHandlerService(speech_service=speech_service, service_registry=registry)
    
    @staticmethod
    def create_command_registry(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create CommandRegistry with injected dependencies."""
        from modules.command_registry import CommandRegistry
        
        command_processor = registry.get_service('command_processor')
        
        logger.debug("Creating CommandRegistry with injected dependencies")
        return CommandRegistry(command_processor=command_processor, service_registry=registry)
    
    @staticmethod
    def create_handler_registry(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create HandlerRegistry with injected dependencies."""
        from modules.handler_registry import HandlerRegistry
        
        command_processor = registry.get_service('command_processor')
        
        logger.debug("Creating HandlerRegistry with injected dependencies")
        return HandlerRegistry(command_processor=command_processor, service_registry=registry)
    
    @staticmethod
    def create_bot_application(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create BotApplication with injected dependencies."""
        from modules.bot_application import BotApplication
        
        logger.debug("Creating BotApplication with injected ServiceRegistry")
        return BotApplication(service_registry=registry)
    
    @staticmethod
    def create_message_counter(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create MessageCounter (no dependencies)."""
        from modules.utils import MessageCounter
        
        logger.debug("Creating MessageCounter")
        return MessageCounter()
    
    @staticmethod
    def create_command_processor(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create CommandProcessor (no dependencies)."""
        from modules.command_processor import CommandProcessor
        
        logger.debug("Creating CommandProcessor")
        return CommandProcessor()
    
    @staticmethod
    def create_weather_handler(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create WeatherCommandHandler (no dependencies)."""
        from modules.weather import WeatherCommandHandler
        
        logger.debug("Creating WeatherCommandHandler")
        return WeatherCommandHandler()
    
    @staticmethod
    def create_geomagnetic_handler(registry: ServiceRegistry, **kwargs: Any) -> Any:
        """Create GeomagneticCommandHandler (no dependencies)."""
        from modules.geomagnetic import GeomagneticCommandHandler
        
        logger.debug("Creating GeomagneticCommandHandler")
        return GeomagneticCommandHandler()
    
    @staticmethod
    def create_reminder_manager(registry: ServiceRegistry) -> Any:
        """Create ReminderManager (no dependencies for now)."""
        try:
            from modules.reminders.reminders import ReminderManager
            logger.debug("Creating ReminderManager")
            return ReminderManager()
        except (ImportError, TypeError) as e:
            logger.warning(f"ReminderManager not available due to compatibility issue: {e}")
            # Return a dummy object that has the required interface
            class DummyReminderManager:
                async def shutdown(self) -> None:
                    pass
            return DummyReminderManager()
    
    @staticmethod
    def create_service_error_boundary(registry: ServiceRegistry) -> Any:
        """Create ServiceErrorBoundary for global error handling."""
        from modules.service_error_boundary import ServiceErrorBoundary
        
        logger.debug("Creating global ServiceErrorBoundary")
        return ServiceErrorBoundary("global")


# Convenience functions for common service creation patterns
def create_singleton_service(service_class: type, *dependencies: str) -> Callable[[ServiceRegistry], Any]:
    """Create a factory function for a singleton service with dependencies."""
    def factory(registry: ServiceRegistry) -> Any:
        deps = {dep: registry.get_service(dep) for dep in dependencies}
        logger.debug(f"Creating {service_class.__name__} with dependencies: {list(dependencies)}")
        return service_class(**deps)
    return factory


def create_transient_service(service_class: type, *dependencies: str) -> Callable[[ServiceRegistry], Any]:
    """Create a factory function for a transient service with dependencies."""
    def factory(registry: ServiceRegistry) -> Any:
        deps = {dep: registry.get_service(dep) for dep in dependencies}
        logger.debug(f"Creating transient {service_class.__name__} with dependencies: {list(dependencies)}")
        return service_class(**deps)
    return factory


def create_no_dependency_service(service_class: type) -> Callable[[ServiceRegistry], Any]:
    """Create a factory function for a service with no dependencies."""
    def factory(registry: ServiceRegistry) -> Any:
        logger.debug(f"Creating {service_class.__name__} with no dependencies")
        return service_class()
    return factory