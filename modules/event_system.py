"""
Event System with Observer Pattern

This module implements an event-driven architecture using the Observer pattern
for decoupled communication between components.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the system."""
    MESSAGE_RECEIVED = "message_received"
    COMMAND_EXECUTED = "command_executed"
    ERROR_OCCURRED = "error_occurred"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CONFIG_CHANGED = "config_changed"
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    DOWNLOAD_STARTED = "download_started"
    DOWNLOAD_COMPLETED = "download_completed"
    DOWNLOAD_FAILED = "download_failed"
    GPT_REQUEST = "gpt_request"
    GPT_RESPONSE = "gpt_response"


@dataclass
class Event:
    """Base event class."""
    event_type: EventType
    source: str
    timestamp: datetime
    data: Dict[str, Any]
    event_id: Optional[str] = None
    
    def __post_init__(self) -> None:
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())


class EventObserver(ABC):
    """Abstract observer interface."""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an event."""
        pass
    
    @abstractmethod
    def get_interested_events(self) -> List[EventType]:
        """Get list of event types this observer is interested in."""
        pass


class AsyncEventObserver(EventObserver):
    """Async observer with callback function."""
    
    def __init__(self, callback: Callable[[Event], None], interested_events: List[EventType]):
        self.callback = callback
        self.interested_events = interested_events
    
    async def handle_event(self, event: Event) -> None:
        """Handle event using callback."""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event)
            else:
                self.callback(event)
        except Exception as e:
            logger.error(f"Error in event observer callback: {e}")
    
    def get_interested_events(self) -> List[EventType]:
        """Get interested event types."""
        return self.interested_events


class EventBus:
    """Central event bus for managing events and observers."""
    
    def __init__(self) -> None:
        self._observers: Dict[EventType, List[EventObserver]] = {}
        self._global_observers: List[EventObserver] = []
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._running = False
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task[None]] = None
    
    def subscribe(self, observer: EventObserver) -> None:
        """Subscribe an observer to events."""
        interested_events = observer.get_interested_events()
        
        if not interested_events:
            # Observer interested in all events
            self._global_observers.append(observer)
        else:
            # Observer interested in specific events
            for event_type in interested_events:
                if event_type not in self._observers:
                    self._observers[event_type] = []
                self._observers[event_type].append(observer)
        
        logger.info(f"Subscribed observer to events: {interested_events or 'ALL'}")
    
    def subscribe_to_event(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe a callback function to a specific event type."""
        observer = AsyncEventObserver(callback, [event_type])
        self.subscribe(observer)
    
    def subscribe_to_all_events(self, callback: Callable[[Event], None]) -> None:
        """Subscribe a callback function to all events."""
        observer = AsyncEventObserver(callback, [])
        self.subscribe(observer)
    
    def unsubscribe(self, observer: EventObserver) -> None:
        """Unsubscribe an observer from events."""
        # Remove from global observers
        if observer in self._global_observers:
            self._global_observers.remove(observer)
        
        # Remove from specific event observers
        for event_type, observers in self._observers.items():
            if observer in observers:
                observers.remove(observer)
        
        logger.info("Unsubscribed observer from events")
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all interested observers."""
        if not self._running:
            await self.start()
        
        await self._event_queue.put(event)
    
    async def publish_event(
        self, 
        event_type: EventType, 
        source: str, 
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Publish an event with the given parameters."""
        event = Event(
            event_type=event_type,
            source=source,
            timestamp=datetime.now(),
            data=data or {}
        )
        await self.publish(event)
    
    async def start(self) -> None:
        """Start the event processing."""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event processing."""
        if not self._running:
            return
        
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Event bus stopped")
    
    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                # Wait for event with timeout to allow checking _running flag
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._notify_observers(event)
                self._add_to_history(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _notify_observers(self, event: Event) -> None:
        """Notify all interested observers about an event."""
        observers_to_notify = []
        
        # Add global observers
        observers_to_notify.extend(self._global_observers)
        
        # Add specific event observers
        if event.event_type in self._observers:
            observers_to_notify.extend(self._observers[event.event_type])
        
        # Notify all observers concurrently
        if observers_to_notify:
            tasks = [observer.handle_event(event) for observer in observers_to_notify]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        self._event_history.append(event)
        
        # Limit history size
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
    
    def get_event_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get event history, optionally filtered by event type."""
        if event_type:
            filtered_events = [e for e in self._event_history if e.event_type == event_type]
        else:
            filtered_events = self._event_history
        
        return filtered_events[-limit:]
    
    def get_observer_count(self) -> Dict[str, int]:
        """Get count of observers by event type."""
        counts = {"global": len(self._global_observers)}
        for event_type, observers in self._observers.items():
            counts[event_type.value] = len(observers)
        return counts


# Global event bus instance
event_bus = EventBus()


# Specific Event Classes
class MessageEvent(Event):
    """Event for message-related activities."""
    
    def __init__(self, user_id: int, chat_id: int, message_text: str, source: str = "message_handler"):
        super().__init__(
            event_type=EventType.MESSAGE_RECEIVED,
            source=source,
            timestamp=datetime.now(),
            data={
                "user_id": user_id,
                "chat_id": chat_id,
                "message_text": message_text
            }
        )
        self.user_id = user_id
        self.chat_id = chat_id
        self.message_text = message_text


class CommandEvent(Event):
    """Event for command execution."""
    
    def __init__(self, command_name: str, user_id: int, chat_id: int, success: bool, source: str = "command_processor"):
        super().__init__(
            event_type=EventType.COMMAND_EXECUTED,
            source=source,
            timestamp=datetime.now(),
            data={
                "command_name": command_name,
                "user_id": user_id,
                "chat_id": chat_id,
                "success": success
            }
        )
        self.command_name = command_name
        self.user_id = user_id
        self.chat_id = chat_id
        self.success = success


class ErrorEvent(Event):
    """Event for error occurrences."""
    
    def __init__(self, error_type: str, error_message: str, user_id: Optional[int] = None, 
                 chat_id: Optional[int] = None, source: str = "error_handler"):
        super().__init__(
            event_type=EventType.ERROR_OCCURRED,
            source=source,
            timestamp=datetime.now(),
            data={
                "error_type": error_type,
                "error_message": error_message,
                "user_id": user_id,
                "chat_id": chat_id
            }
        )
        self.error_type = error_type
        self.error_message = error_message
        self.user_id = user_id
        self.chat_id = chat_id


# Event-driven service observers
class LoggingObserver(EventObserver):
    """Observer that logs all events."""
    
    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.LoggingObserver")
    
    async def handle_event(self, event: Event) -> None:
        """Log the event."""
        self.logger.info(f"Event: {event.event_type.value} from {event.source} at {event.timestamp}")
    
    def get_interested_events(self) -> List[EventType]:
        """Interested in all events."""
        return []


class MetricsObserver(EventObserver):
    """Observer that collects metrics from events."""
    
    def __init__(self) -> None:
        self.metrics: Dict[str, Any] = {
            "total_events": 0,
            "events_by_type": {},
            "errors_count": 0,
            "commands_executed": 0
        }
    
    async def handle_event(self, event: Event) -> None:
        """Update metrics based on event."""
        self.metrics["total_events"] += 1
        
        event_type_str = event.event_type.value
        if event_type_str not in self.metrics["events_by_type"]:
            self.metrics["events_by_type"][event_type_str] = 0
        self.metrics["events_by_type"][event_type_str] += 1
        
        if event.event_type == EventType.ERROR_OCCURRED:
            self.metrics["errors_count"] += 1
        elif event.event_type == EventType.COMMAND_EXECUTED:
            self.metrics["commands_executed"] += 1
    
    def get_interested_events(self) -> List[EventType]:
        """Interested in all events."""
        return []
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return self.metrics.copy()