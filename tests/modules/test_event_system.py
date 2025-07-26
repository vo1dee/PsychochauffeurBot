"""
Tests for the event system module.

This module tests event publishing, subscription, and notification delivery
functionality of the event system.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from modules.event_system import (
    Event, EventType, EventObserver, AsyncEventObserver, EventBus,
    MessageEvent, CommandEvent, ErrorEvent, LoggingObserver, MetricsObserver,
    event_bus
)


class TestEvent:
    """Test the Event class."""
    
    def test_event_creation(self):
        """Test basic event creation."""
        event_data = {"key": "value", "number": 42}
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test_source",
            timestamp=datetime.now(),
            data=event_data
        )
        
        assert event.event_type == EventType.MESSAGE_RECEIVED
        assert event.source == "test_source"
        assert event.data == event_data
        assert event.event_id is not None
        assert isinstance(event.event_id, str)
    
    def test_event_auto_id_generation(self):
        """Test that event ID is automatically generated."""
        event = Event(
            event_type=EventType.COMMAND_EXECUTED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        assert event.event_id is not None
        assert len(event.event_id) > 0
    
    def test_event_custom_id(self):
        """Test event creation with custom ID."""
        custom_id = "custom-event-id-123"
        event = Event(
            event_type=EventType.ERROR_OCCURRED,
            source="test",
            timestamp=datetime.now(),
            data={},
            event_id=custom_id
        )
        
        assert event.event_id == custom_id


class TestAsyncEventObserver:
    """Test the AsyncEventObserver class."""
    
    def test_observer_creation(self):
        """Test observer creation with callback and interested events."""
        callback = Mock()
        interested_events = [EventType.MESSAGE_RECEIVED, EventType.COMMAND_EXECUTED]
        
        observer = AsyncEventObserver(callback, interested_events)
        
        assert observer.callback == callback
        assert observer.get_interested_events() == interested_events
    
    @pytest.mark.asyncio
    async def test_sync_callback_handling(self):
        """Test handling events with synchronous callback."""
        callback = Mock()
        observer = AsyncEventObserver(callback, [EventType.MESSAGE_RECEIVED])
        
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={"message": "test"}
        )
        
        await observer.handle_event(event)
        
        callback.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_async_callback_handling(self):
        """Test handling events with asynchronous callback."""
        callback = AsyncMock()
        observer = AsyncEventObserver(callback, [EventType.MESSAGE_RECEIVED])
        
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={"message": "test"}
        )
        
        await observer.handle_event(event)
        
        callback.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test error handling in callback execution."""
        def failing_callback(event):
            raise ValueError("Test error")
        
        observer = AsyncEventObserver(failing_callback, [EventType.MESSAGE_RECEIVED])
        
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        # Should not raise exception, error should be logged
        with patch('modules.event_system.logger') as mock_logger:
            await observer.handle_event(event)
            mock_logger.error.assert_called_once()


class TestEventBus:
    """Test the EventBus class."""
    
    @pytest.fixture
    def event_bus_instance(self):
        """Create a fresh EventBus instance for testing."""
        return EventBus()
    
    @pytest.fixture
    def mock_observer(self):
        """Create a mock observer."""
        observer = Mock(spec=EventObserver)
        observer.get_interested_events.return_value = [EventType.MESSAGE_RECEIVED]
        observer.handle_event = AsyncMock()
        return observer
    
    @pytest.fixture
    def global_observer(self):
        """Create a mock global observer (interested in all events)."""
        observer = Mock(spec=EventObserver)
        observer.get_interested_events.return_value = []
        observer.handle_event = AsyncMock()
        return observer
    
    def test_event_bus_initialization(self, event_bus_instance):
        """Test EventBus initialization."""
        assert event_bus_instance._observers == {}
        assert event_bus_instance._global_observers == []
        assert event_bus_instance._event_history == []
        assert event_bus_instance._running is False
    
    def test_subscribe_specific_events(self, event_bus_instance, mock_observer):
        """Test subscribing observer to specific events."""
        event_bus_instance.subscribe(mock_observer)
        
        assert EventType.MESSAGE_RECEIVED in event_bus_instance._observers
        assert mock_observer in event_bus_instance._observers[EventType.MESSAGE_RECEIVED]
        assert mock_observer not in event_bus_instance._global_observers
    
    def test_subscribe_global_observer(self, event_bus_instance, global_observer):
        """Test subscribing observer to all events."""
        event_bus_instance.subscribe(global_observer)
        
        assert global_observer in event_bus_instance._global_observers
        assert len(event_bus_instance._observers) == 0
    
    def test_subscribe_to_event_callback(self, event_bus_instance):
        """Test subscribing callback function to specific event."""
        callback = Mock()
        
        event_bus_instance.subscribe_to_event(EventType.COMMAND_EXECUTED, callback)
        
        assert EventType.COMMAND_EXECUTED in event_bus_instance._observers
        assert len(event_bus_instance._observers[EventType.COMMAND_EXECUTED]) == 1
    
    def test_subscribe_to_all_events_callback(self, event_bus_instance):
        """Test subscribing callback function to all events."""
        callback = Mock()
        
        event_bus_instance.subscribe_to_all_events(callback)
        
        assert len(event_bus_instance._global_observers) == 1
    
    def test_unsubscribe_specific_observer(self, event_bus_instance, mock_observer):
        """Test unsubscribing observer from specific events."""
        event_bus_instance.subscribe(mock_observer)
        event_bus_instance.unsubscribe(mock_observer)
        
        assert mock_observer not in event_bus_instance._observers.get(EventType.MESSAGE_RECEIVED, [])
    
    def test_unsubscribe_global_observer(self, event_bus_instance, global_observer):
        """Test unsubscribing global observer."""
        event_bus_instance.subscribe(global_observer)
        event_bus_instance.unsubscribe(global_observer)
        
        assert global_observer not in event_bus_instance._global_observers
    
    @pytest.mark.asyncio
    async def test_publish_event_starts_bus(self, event_bus_instance):
        """Test that publishing an event starts the bus if not running."""
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        assert event_bus_instance._running is False
        
        await event_bus_instance.publish(event)
        
        assert event_bus_instance._running is True
        
        # Clean up
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_publish_event_helper(self, event_bus_instance):
        """Test the publish_event helper method."""
        with patch.object(event_bus_instance, 'publish') as mock_publish:
            await event_bus_instance.publish_event(
                EventType.COMMAND_EXECUTED,
                "test_source",
                {"command": "test_command"}
            )
            
            mock_publish.assert_called_once()
            event_arg = mock_publish.call_args[0][0]
            assert event_arg.event_type == EventType.COMMAND_EXECUTED
            assert event_arg.source == "test_source"
            assert event_arg.data == {"command": "test_command"}
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self, event_bus_instance):
        """Test starting and stopping the event bus."""
        assert event_bus_instance._running is False
        
        await event_bus_instance.start()
        assert event_bus_instance._running is True
        assert event_bus_instance._processor_task is not None
        
        await event_bus_instance.stop()
        assert event_bus_instance._running is False
    
    @pytest.mark.asyncio
    async def test_multiple_start_calls(self, event_bus_instance):
        """Test that multiple start calls don't create multiple tasks."""
        await event_bus_instance.start()
        first_task = event_bus_instance._processor_task
        
        await event_bus_instance.start()
        second_task = event_bus_instance._processor_task
        
        assert first_task is second_task
        
        # Clean up
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, event_bus_instance):
        """Test stopping when bus is not running."""
        assert event_bus_instance._running is False
        
        # Should not raise exception
        await event_bus_instance.stop()
        
        assert event_bus_instance._running is False
    
    def test_get_observer_count(self, event_bus_instance, mock_observer, global_observer):
        """Test getting observer counts."""
        event_bus_instance.subscribe(mock_observer)
        event_bus_instance.subscribe(global_observer)
        
        counts = event_bus_instance.get_observer_count()
        
        assert counts["global"] == 1
        assert counts[EventType.MESSAGE_RECEIVED.value] == 1
    
    def test_event_history_management(self, event_bus_instance):
        """Test event history storage and retrieval."""
        event1 = Event(EventType.MESSAGE_RECEIVED, "source1", datetime.now(), {})
        event2 = Event(EventType.COMMAND_EXECUTED, "source2", datetime.now(), {})
        
        event_bus_instance._add_to_history(event1)
        event_bus_instance._add_to_history(event2)
        
        history = event_bus_instance.get_event_history()
        assert len(history) == 2
        assert event1 in history
        assert event2 in history
    
    def test_event_history_filtering(self, event_bus_instance):
        """Test filtering event history by event type."""
        event1 = Event(EventType.MESSAGE_RECEIVED, "source1", datetime.now(), {})
        event2 = Event(EventType.COMMAND_EXECUTED, "source2", datetime.now(), {})
        
        event_bus_instance._add_to_history(event1)
        event_bus_instance._add_to_history(event2)
        
        message_history = event_bus_instance.get_event_history(EventType.MESSAGE_RECEIVED)
        assert len(message_history) == 1
        assert event1 in message_history
        assert event2 not in message_history
    
    def test_event_history_limit(self, event_bus_instance):
        """Test event history size limit."""
        # Set a small limit for testing
        event_bus_instance._max_history_size = 3
        
        for i in range(5):
            event = Event(EventType.MESSAGE_RECEIVED, f"source{i}", datetime.now(), {})
            event_bus_instance._add_to_history(event)
        
        history = event_bus_instance.get_event_history()
        assert len(history) == 3


class TestSpecificEventClasses:
    """Test specific event classes."""
    
    def test_message_event_creation(self):
        """Test MessageEvent creation."""
        event = MessageEvent(
            user_id=123,
            chat_id=456,
            message_text="Hello, world!",
            source="test_handler"
        )
        
        assert event.event_type == EventType.MESSAGE_RECEIVED
        assert event.source == "test_handler"
        assert event.user_id == 123
        assert event.chat_id == 456
        assert event.message_text == "Hello, world!"
        assert event.data["user_id"] == 123
        assert event.data["chat_id"] == 456
        assert event.data["message_text"] == "Hello, world!"
    
    def test_command_event_creation(self):
        """Test CommandEvent creation."""
        event = CommandEvent(
            command_name="test_command",
            user_id=123,
            chat_id=456,
            success=True,
            source="test_processor"
        )
        
        assert event.event_type == EventType.COMMAND_EXECUTED
        assert event.source == "test_processor"
        assert event.command_name == "test_command"
        assert event.user_id == 123
        assert event.chat_id == 456
        assert event.success is True
        assert event.data["command_name"] == "test_command"
        assert event.data["success"] is True
    
    def test_error_event_creation(self):
        """Test ErrorEvent creation."""
        event = ErrorEvent(
            error_type="ValueError",
            error_message="Test error message",
            user_id=123,
            chat_id=456,
            source="test_handler"
        )
        
        assert event.event_type == EventType.ERROR_OCCURRED
        assert event.source == "test_handler"
        assert event.error_type == "ValueError"
        assert event.error_message == "Test error message"
        assert event.user_id == 123
        assert event.chat_id == 456
        assert event.data["error_type"] == "ValueError"
        assert event.data["error_message"] == "Test error message"
    
    def test_error_event_optional_fields(self):
        """Test ErrorEvent creation with optional fields."""
        event = ErrorEvent(
            error_type="RuntimeError",
            error_message="System error"
        )
        
        assert event.user_id is None
        assert event.chat_id is None
        assert event.data["user_id"] is None
        assert event.data["chat_id"] is None


class TestObserverImplementations:
    """Test built-in observer implementations."""
    
    @pytest.mark.asyncio
    async def test_logging_observer(self):
        """Test LoggingObserver functionality."""
        observer = LoggingObserver()
        
        assert observer.get_interested_events() == []  # Interested in all events
        
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        with patch.object(observer.logger, 'info') as mock_info:
            await observer.handle_event(event)
            mock_info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_metrics_observer(self):
        """Test MetricsObserver functionality."""
        observer = MetricsObserver()
        
        assert observer.get_interested_events() == []  # Interested in all events
        
        # Test message event
        message_event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await observer.handle_event(message_event)
        
        metrics = observer.get_metrics()
        assert metrics["total_events"] == 1
        assert metrics["events_by_type"]["message_received"] == 1
        assert metrics["errors_count"] == 0
        assert metrics["commands_executed"] == 0
        
        # Test error event
        error_event = Event(
            event_type=EventType.ERROR_OCCURRED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await observer.handle_event(error_event)
        
        metrics = observer.get_metrics()
        assert metrics["total_events"] == 2
        assert metrics["events_by_type"]["error_occurred"] == 1
        assert metrics["errors_count"] == 1
        
        # Test command event
        command_event = Event(
            event_type=EventType.COMMAND_EXECUTED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await observer.handle_event(command_event)
        
        metrics = observer.get_metrics()
        assert metrics["total_events"] == 3
        assert metrics["events_by_type"]["command_executed"] == 1
        assert metrics["commands_executed"] == 1


class TestEventFiltering:
    """Test event filtering and routing logic."""
    
    @pytest.fixture
    def event_bus_instance(self):
        """Create a fresh EventBus instance for testing."""
        return EventBus()
    
    @pytest.mark.asyncio
    async def test_specific_event_filtering(self, event_bus_instance):
        """Test that observers only receive events they're interested in."""
        message_callback = Mock()
        command_callback = Mock()
        
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, message_callback)
        event_bus_instance.subscribe_to_event(EventType.COMMAND_EXECUTED, command_callback)
        
        # Start the bus
        await event_bus_instance.start()
        
        # Publish a message event
        message_event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await event_bus_instance.publish(message_event)
        
        # Give some time for event processing
        await asyncio.sleep(0.1)
        
        # Only message callback should be called
        message_callback.assert_called_once_with(message_event)
        command_callback.assert_not_called()
        
        # Clean up
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_global_observer_receives_all_events(self, event_bus_instance):
        """Test that global observers receive all events."""
        global_callback = Mock()
        specific_callback = Mock()
        
        event_bus_instance.subscribe_to_all_events(global_callback)
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, specific_callback)
        
        # Start the bus
        await event_bus_instance.start()
        
        # Publish different types of events
        message_event = Event(EventType.MESSAGE_RECEIVED, "test", datetime.now(), {})
        command_event = Event(EventType.COMMAND_EXECUTED, "test", datetime.now(), {})
        
        await event_bus_instance.publish(message_event)
        await event_bus_instance.publish(command_event)
        
        # Give some time for event processing
        await asyncio.sleep(0.1)
        
        # Global callback should receive both events
        assert global_callback.call_count == 2
        
        # Specific callback should only receive message event
        specific_callback.assert_called_once_with(message_event)
        
        # Clean up
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_observers_same_event(self, event_bus_instance):
        """Test multiple observers for the same event type."""
        callback1 = Mock()
        callback2 = Mock()
        
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, callback1)
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, callback2)
        
        # Start the bus
        await event_bus_instance.start()
        
        # Publish an event
        event = Event(EventType.MESSAGE_RECEIVED, "test", datetime.now(), {})
        await event_bus_instance.publish(event)
        
        # Give some time for event processing
        await asyncio.sleep(0.1)
        
        # Both callbacks should be called
        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)
        
        # Clean up
        await event_bus_instance.stop()


class TestGlobalEventBus:
    """Test the global event bus instance."""
    
    def test_global_event_bus_exists(self):
        """Test that global event bus instance exists."""
        from modules.event_system import event_bus
        assert isinstance(event_bus, EventBus)
    
    def test_global_event_bus_is_singleton(self):
        """Test that importing event_bus gives the same instance."""
        from modules.event_system import event_bus as bus1
        from modules.event_system import event_bus as bus2
        
        assert bus1 is bus2


class TestAsyncEventHandling:
    """Test async event handling patterns and execution."""
    
    @pytest.fixture
    def event_bus_instance(self):
        """Create a fresh EventBus instance for testing."""
        return EventBus()
    
    @pytest.mark.asyncio
    async def test_async_event_processing(self, event_bus_instance):
        """Test that events are processed asynchronously."""
        processed_events = []
        
        async def async_handler(event):
            await asyncio.sleep(0.01)  # Simulate async work
            processed_events.append(event.event_id)
        
        event_bus_instance.subscribe_to_all_events(async_handler)
        await event_bus_instance.start()
        
        # Publish multiple events quickly
        events = []
        for i in range(3):
            event = Event(
                event_type=EventType.MESSAGE_RECEIVED,
                source=f"test_{i}",
                timestamp=datetime.now(),
                data={"index": i}
            )
            events.append(event)
            await event_bus_instance.publish(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # All events should be processed
        assert len(processed_events) == 3
        for event in events:
            assert event.event_id in processed_events
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_event_handling(self, event_bus_instance):
        """Test that multiple observers handle events concurrently."""
        handler_start_times = []
        handler_end_times = []
        
        async def slow_handler_1(event):
            handler_start_times.append(("handler_1", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.05)
            handler_end_times.append(("handler_1", asyncio.get_event_loop().time()))
        
        async def slow_handler_2(event):
            handler_start_times.append(("handler_2", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.05)
            handler_end_times.append(("handler_2", asyncio.get_event_loop().time()))
        
        event_bus_instance.subscribe_to_all_events(slow_handler_1)
        event_bus_instance.subscribe_to_all_events(slow_handler_2)
        await event_bus_instance.start()
        
        # Publish an event
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        start_time = asyncio.get_event_loop().time()
        await event_bus_instance.publish(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Both handlers should have started and finished
        assert len(handler_start_times) == 2
        assert len(handler_end_times) == 2
        
        # Handlers should start around the same time (concurrent execution)
        start_time_diff = abs(handler_start_times[0][1] - handler_start_times[1][1])
        assert start_time_diff < 0.01  # Should start within 10ms of each other
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_queue_management(self, event_bus_instance):
        """Test event queue management and processing order."""
        processed_events = []
        
        async def ordered_handler(event):
            processed_events.append(event.data["order"])
        
        event_bus_instance.subscribe_to_all_events(ordered_handler)
        await event_bus_instance.start()
        
        # Publish events in order
        for i in range(5):
            event = Event(
                event_type=EventType.MESSAGE_RECEIVED,
                source="test",
                timestamp=datetime.now(),
                data={"order": i}
            )
            await event_bus_instance.publish(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Events should be processed in order
        assert processed_events == [0, 1, 2, 3, 4]
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_processing_with_slow_observer(self, event_bus_instance):
        """Test that slow observers don't block other observers."""
        fast_handler_calls = []
        slow_handler_calls = []
        
        async def fast_handler(event):
            fast_handler_calls.append(event.event_id)
        
        async def slow_handler(event):
            await asyncio.sleep(0.05)  # Slow processing
            slow_handler_calls.append(event.event_id)
        
        event_bus_instance.subscribe_to_all_events(fast_handler)
        event_bus_instance.subscribe_to_all_events(slow_handler)
        await event_bus_instance.start()
        
        # Publish a single event to test concurrent processing
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await event_bus_instance.publish(event)
        
        # Wait for processing to complete
        await asyncio.sleep(0.1)
        
        # Both handlers should have processed the event
        assert len(fast_handler_calls) == 1
        assert len(slow_handler_calls) == 1
        assert fast_handler_calls[0] == slow_handler_calls[0] == event.event_id
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_processing_error_isolation(self, event_bus_instance):
        """Test that errors in one observer don't affect others."""
        successful_calls = []
        
        async def failing_handler(event):
            raise ValueError("Handler error")
        
        async def successful_handler(event):
            successful_calls.append(event.event_id)
        
        event_bus_instance.subscribe_to_all_events(failing_handler)
        event_bus_instance.subscribe_to_all_events(successful_handler)
        await event_bus_instance.start()
        
        # Publish an event
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        with patch('modules.event_system.logger') as mock_logger:
            await event_bus_instance.publish(event)
            await asyncio.sleep(0.1)
            
            # Successful handler should still be called
            assert len(successful_calls) == 1
            assert successful_calls[0] == event.event_id
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_bus_stop_cancels_processing(self, event_bus_instance):
        """Test that stopping the event bus cancels event processing."""
        processed_events = []
        
        async def handler(event):
            await asyncio.sleep(0.1)  # Slow processing
            processed_events.append(event.event_id)
        
        event_bus_instance.subscribe_to_all_events(handler)
        await event_bus_instance.start()
        
        # Publish events
        for i in range(3):
            event = Event(
                event_type=EventType.MESSAGE_RECEIVED,
                source=f"test_{i}",
                timestamp=datetime.now(),
                data={}
            )
            await event_bus_instance.publish(event)
        
        # Stop immediately
        await event_bus_instance.stop()
        
        # Processing should be cancelled, so not all events may be processed
        # This tests that the stop method properly cancels the processor task
        assert event_bus_instance._running is False
        assert event_bus_instance._processor_task is None or event_bus_instance._processor_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_event_processing_timeout_handling(self, event_bus_instance):
        """Test event processing with timeout scenarios."""
        # This tests the internal timeout mechanism in _process_events
        await event_bus_instance.start()
        
        # Let the processor run for a bit without events
        await asyncio.sleep(0.1)
        
        # Should still be running
        assert event_bus_instance._running is True
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_async_observers_same_event_type(self, event_bus_instance):
        """Test multiple async observers for the same event type."""
        handler1_calls = []
        handler2_calls = []
        handler3_calls = []
        
        async def async_handler_1(event):
            await asyncio.sleep(0.01)
            handler1_calls.append(event.event_id)
        
        async def async_handler_2(event):
            await asyncio.sleep(0.02)
            handler2_calls.append(event.event_id)
        
        async def async_handler_3(event):
            await asyncio.sleep(0.005)
            handler3_calls.append(event.event_id)
        
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, async_handler_1)
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, async_handler_2)
        event_bus_instance.subscribe_to_event(EventType.MESSAGE_RECEIVED, async_handler_3)
        
        await event_bus_instance.start()
        
        # Publish an event
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await event_bus_instance.publish(event)
        await asyncio.sleep(0.1)  # Wait for all handlers
        
        # All handlers should have been called
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1
        assert len(handler3_calls) == 1
        
        # All should have the same event ID
        assert handler1_calls[0] == handler2_calls[0] == handler3_calls[0] == event.event_id
        
        await event_bus_instance.stop()


class TestEventProcessingPipeline:
    """Test error handling in event processing pipelines."""
    
    @pytest.fixture
    def event_bus_instance(self):
        """Create a fresh EventBus instance for testing."""
        return EventBus()
    
    @pytest.mark.asyncio
    async def test_event_processing_pipeline_error_recovery(self, event_bus_instance):
        """Test that the event processing pipeline recovers from errors."""
        processed_events = []
        error_count = 0
        
        async def sometimes_failing_handler(event):
            nonlocal error_count
            if error_count < 2:  # Fail first 2 events
                error_count += 1
                raise RuntimeError("Simulated error")
            processed_events.append(event.event_id)
        
        event_bus_instance.subscribe_to_all_events(sometimes_failing_handler)
        
        with patch('modules.event_system.logger') as mock_logger:
            await event_bus_instance.start()
            
            # Publish multiple events
            events = []
            for i in range(4):
                event = Event(
                    event_type=EventType.MESSAGE_RECEIVED,
                    source=f"test_{i}",
                    timestamp=datetime.now(),
                    data={"index": i}
                )
                events.append(event)
                await event_bus_instance.publish(event)
            
            await asyncio.sleep(0.1)
            
            # First 2 events should have failed, last 2 should succeed
            assert len(processed_events) == 2
            assert processed_events[0] == events[2].event_id
            assert processed_events[1] == events[3].event_id
            
            # Errors should have been logged
            assert mock_logger.error.call_count >= 2
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_processing_with_mixed_sync_async_handlers(self, event_bus_instance):
        """Test event processing with both sync and async handlers."""
        sync_calls = []
        async_calls = []
        
        def sync_handler(event):
            sync_calls.append(event.event_id)
        
        async def async_handler(event):
            await asyncio.sleep(0.01)
            async_calls.append(event.event_id)
        
        # Create observers manually to test mixed handler types
        sync_observer = AsyncEventObserver(sync_handler, [EventType.MESSAGE_RECEIVED])
        async_observer = AsyncEventObserver(async_handler, [EventType.MESSAGE_RECEIVED])
        
        event_bus_instance.subscribe(sync_observer)
        event_bus_instance.subscribe(async_observer)
        
        await event_bus_instance.start()
        
        # Publish an event
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        await event_bus_instance.publish(event)
        await asyncio.sleep(0.05)
        
        # Both handlers should have been called
        assert len(sync_calls) == 1
        assert len(async_calls) == 1
        assert sync_calls[0] == async_calls[0] == event.event_id
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_processing_exception_gathering(self, event_bus_instance):
        """Test that exceptions in concurrent event processing are properly handled."""
        successful_calls = []
        
        async def handler_1(event):
            raise ValueError("Error in handler 1")
        
        async def handler_2(event):
            successful_calls.append("handler_2")
        
        async def handler_3(event):
            raise RuntimeError("Error in handler 3")
        
        async def handler_4(event):
            successful_calls.append("handler_4")
        
        event_bus_instance.subscribe_to_all_events(handler_1)
        event_bus_instance.subscribe_to_all_events(handler_2)
        event_bus_instance.subscribe_to_all_events(handler_3)
        event_bus_instance.subscribe_to_all_events(handler_4)
        
        await event_bus_instance.start()
        
        # Publish an event
        event = Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            timestamp=datetime.now(),
            data={}
        )
        
        with patch('modules.event_system.logger'):
            await event_bus_instance.publish(event)
            await asyncio.sleep(0.1)
            
            # Successful handlers should still be called despite errors in others
            assert "handler_2" in successful_calls
            assert "handler_4" in successful_calls
            assert len(successful_calls) == 2
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_event_history_with_async_processing(self, event_bus_instance):
        """Test that event history is maintained during async processing."""
        await event_bus_instance.start()
        
        # Publish multiple events
        events = []
        for i in range(5):
            event = Event(
                event_type=EventType.MESSAGE_RECEIVED,
                source=f"test_{i}",
                timestamp=datetime.now(),
                data={"index": i}
            )
            events.append(event)
            await event_bus_instance.publish(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Check event history
        history = event_bus_instance.get_event_history()
        assert len(history) == 5
        
        # Events should be in history in the order they were published
        for i, event in enumerate(events):
            assert event in history
        
        await event_bus_instance.stop()
    
    @pytest.mark.asyncio
    async def test_async_observer_cleanup_on_unsubscribe(self, event_bus_instance):
        """Test that async observers are properly cleaned up when unsubscribed."""
        handler_calls = []
        
        async def test_handler(event):
            handler_calls.append(event.event_id)
        
        # Subscribe observer
        observer = AsyncEventObserver(test_handler, [EventType.MESSAGE_RECEIVED])
        event_bus_instance.subscribe(observer)
        
        await event_bus_instance.start()
        
        # Publish event - should be handled
        event1 = Event(EventType.MESSAGE_RECEIVED, "test", datetime.now(), {})
        await event_bus_instance.publish(event1)
        await asyncio.sleep(0.05)
        
        assert len(handler_calls) == 1
        
        # Unsubscribe observer
        event_bus_instance.unsubscribe(observer)
        
        # Publish another event - should not be handled
        event2 = Event(EventType.MESSAGE_RECEIVED, "test", datetime.now(), {})
        await event_bus_instance.publish(event2)
        await asyncio.sleep(0.05)
        
        # Handler should not have been called for second event
        assert len(handler_calls) == 1
        
        await event_bus_instance.stop()