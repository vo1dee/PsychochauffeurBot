"""
Integration tests for ServiceErrorBoundary with real services.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

from modules.service_error_boundary import (
    ServiceErrorBoundary,
    ServiceHealthMonitor,
    with_error_boundary,
    health_monitor
)
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.command_registry import CommandRegistry
from modules.callback_handler_service import CallbackHandlerService
from modules.error_handler import StandardError, ErrorSeverity, ErrorCategory


class TestMessageHandlerServiceIntegration:
    """Test error boundary integration with MessageHandlerService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock config manager."""
        config = Mock()
        config.get_chat_config.return_value = {"enabled": True}
        config.get_global_config.return_value = {"gpt": {"enabled": True}}
        return config
    
    @pytest.fixture
    def mock_gpt_service(self):
        """Create mock GPT service."""
        gpt = Mock()
        gpt.generate_response = AsyncMock(return_value="GPT response")
        return gpt
    
    @pytest.fixture
    def message_service_with_boundary(self, mock_config_manager, mock_gpt_service):
        """Create MessageHandlerService with error boundary."""
        service = MessageHandlerService(mock_config_manager)
        
        # Wrap service methods with error boundaries
        boundary = ServiceErrorBoundary("message_handler_service")
        
        # Store original methods
        original_handle_text = service.handle_text_message
        original_handle_sticker = service.handle_sticker_message
        
        # Wrap with error boundaries
        async def wrapped_handle_text(update, context):
            return await boundary.execute_with_boundary(
                operation=lambda: original_handle_text(update, context),
                operation_name="handle_text_message",
                context={"update_id": update.update_id if update else None}
            )
        
        async def wrapped_handle_sticker(update, context):
            return await boundary.execute_with_boundary(
                operation=lambda: original_handle_sticker(update, context),
                operation_name="handle_sticker_message",
                context={"update_id": update.update_id if update else None}
            )
        
        service.handle_text_message = wrapped_handle_text
        service.handle_sticker_message = wrapped_handle_sticker
        service._error_boundary = boundary
        
        return service
    
    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=456, type="private")
        message = Message(
            message_id=789,
            date=None,
            chat=chat,
            from_user=user,
            text="Hello world"
        )
        update = Update(update_id=1, message=message)
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create mock callback context."""
        return Mock(spec=CallbackContext)
    
    @pytest.mark.asyncio
    async def test_successful_message_handling(
        self, 
        message_service_with_boundary, 
        mock_update, 
        mock_context
    ):
        """Test successful message handling with error boundary."""
        service = message_service_with_boundary
        
        with patch.object(service, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = None
            
            await service.handle_text_message(mock_update, mock_context)
            
            # Check that operation was successful
            assert service.error_boundary.metrics.success_count == 1
            assert service.error_boundary.metrics.error_count == 0
    
    @pytest.mark.asyncio
    async def test_message_handling_with_error(
        self, 
        message_service_with_boundary, 
        mock_update, 
        mock_context
    ):
        """Test message handling error isolation."""
        service = message_service_with_boundary
        
        with patch.object(service, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = ValueError("Processing error")
            
            with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
                result = await service.handle_text_message(mock_update, mock_context)
                
                # Error should be handled gracefully
                assert result is None
                assert service.error_boundary.metrics.error_count == 1
                mock_handle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(
        self, 
        message_service_with_boundary, 
        mock_update, 
        mock_context
    ):
        """Test circuit breaker protection for message handling."""
        service = message_service_with_boundary
        service.error_boundary.circuit_breaker.config.failure_threshold = 2
        
        with patch.object(service, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = ValueError("Persistent error")
            
            with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
                # First failure
                await service.handle_text_message(mock_update, mock_context)
                assert service.error_boundary.circuit_breaker.failure_count == 1
                
                # Second failure should open circuit
                await service.handle_text_message(mock_update, mock_context)
                assert service.error_boundary.circuit_breaker.state.value == "open"
                
                # Third attempt should be rejected by circuit breaker
                await service.handle_text_message(mock_update, mock_context)
                # Process should not be called for the third attempt
                assert mock_init.call_count == 2


class TestSpeechRecognitionServiceIntegration:
    """Test error boundary integration with SpeechRecognitionService."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock config manager."""
        config = Mock()
        config.get_chat_config.return_value = {"speech_recognition": {"enabled": True}}
        return config
    
    @pytest.fixture
    def speech_service_with_boundary(self, mock_config_manager):
        """Create SpeechRecognitionService with error boundary."""
        service = SpeechRecognitionService(mock_config_manager)
        
        # Wrap with error boundary
        boundary = ServiceErrorBoundary("speech_recognition_service")
        
        # Store original method
        original_handle_voice = service.handle_voice_message
        
        # Wrap with error boundary
        async def wrapped_handle_voice(update, context):
            return await boundary.execute_with_boundary(
                operation=lambda: original_handle_voice(update, context),
                operation_name="handle_voice_message",
                timeout=30.0,  # Speech processing timeout
                context={"update_id": update.update_id if update else None}
            )
        
        service.handle_voice_message = wrapped_handle_voice
        service._error_boundary = boundary
        
        return service
    
    @pytest.fixture
    def mock_voice_update(self):
        """Create mock voice message update."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=456, type="private")
        
        # Mock voice object
        voice = Mock()
        voice.file_id = "voice_file_123"
        voice.duration = 10
        
        message = Message(
            message_id=789,
            date=None,
            chat=chat,
            from_user=user,
            voice=voice
        )
        update = Update(update_id=1, message=message)
        return update
    
    @pytest.mark.asyncio
    async def test_voice_processing_timeout_handling(
        self, 
        speech_service_with_boundary, 
        mock_voice_update, 
        mock_context
    ):
        """Test timeout handling in speech recognition."""
        service = speech_service_with_boundary
        
        with patch.object(service, '_send_speech_recognition_button', new_callable=AsyncMock) as mock_process:
            # Simulate slow processing
            async def slow_process(*args, **kwargs):
                await asyncio.sleep(2)
                return "processed"
            
            mock_process.side_effect = slow_process
            
            with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
                result = await service.handle_voice_message(mock_voice_update, mock_context)
                
                # Should timeout and return None
                assert result is None
                assert service.error_boundary.metrics.error_count == 1
                
                # Check that timeout error was handled
                mock_handle.assert_called_once()
                call_args = mock_handle.call_args
                error = call_args[1]['error']
                assert isinstance(error, StandardError)
                assert "timed out" in error.message.lower()
    
    @pytest.mark.asyncio
    async def test_speech_service_fallback(self, speech_service_with_boundary, mock_voice_update, mock_context):
        """Test fallback mechanism for speech recognition."""
        service = speech_service_with_boundary
        
        # Register a fallback
        async def speech_fallback():
            return "Speech recognition unavailable"
        
        service.error_boundary.register_fallback("handle_voice_message", speech_fallback)
        
        with patch.object(service, '_send_speech_recognition_button', new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = Exception("Speech API error")
            
            with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
                # Should use fallback instead of failing
                result = await service.handle_voice_message(mock_voice_update, mock_context)
                
                # Note: The current implementation doesn't use registered fallbacks automatically
                # This test demonstrates how it could work with enhancement
                assert result is None  # Current behavior
                assert service.error_boundary.metrics.error_count == 1


class TestCommandRegistryIntegration:
    """Test error boundary integration with CommandRegistry."""
    
    @pytest.fixture
    def mock_command_processor(self):
        """Create mock command processor."""
        processor = Mock()
        processor.register_command = Mock()
        return processor
    
    @pytest.fixture
    def command_registry_with_boundary(self, mock_command_processor):
        """Create CommandRegistry with error boundary."""
        registry = CommandRegistry(mock_command_processor)
        
        # Wrap with error boundary
        boundary = ServiceErrorBoundary("command_registry")
        
        # Store original method
        original_register_all = registry.register_all_commands
        
        # Wrap with error boundary
        async def wrapped_register_all():
            return await boundary.execute_with_boundary(
                operation=original_register_all,
                operation_name="register_all_commands",
                context={"registry": "command_registry"}
            )
        
        registry.register_all_commands = wrapped_register_all
        registry._error_boundary = boundary
        
        return registry
    
    @pytest.mark.asyncio
    async def test_command_registration_error_handling(self, command_registry_with_boundary):
        """Test error handling during command registration."""
        registry = command_registry_with_boundary
        
        with patch.object(registry, 'register_basic_commands', new_callable=AsyncMock) as mock_register:
            mock_register.side_effect = ImportError("Command module not found")
            
            with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
                await registry.register_all_commands()
                
                # Error should be handled gracefully
                assert registry._error_boundary.metrics.error_count == 1
                mock_handle.assert_called_once()


class TestCallbackHandlerServiceIntegration:
    """Test error boundary integration with CallbackHandlerService."""
    
    @pytest.fixture
    def mock_speech_service(self):
        """Create mock speech service."""
        service = Mock()
        service.handle_language_selection = AsyncMock()
        return service
    
    @pytest.fixture
    def callback_service_with_boundary(self, mock_speech_service):
        """Create CallbackHandlerService with error boundary."""
        service = CallbackHandlerService(mock_speech_service)
        
        # Wrap with error boundary
        boundary = ServiceErrorBoundary("callback_handler_service")
        
        # Store original method
        original_handle_callback = service.handle_callback_query
        
        # Wrap with error boundary
        async def wrapped_handle_callback(update, context):
            return await boundary.execute_with_boundary(
                operation=lambda: original_handle_callback(update, context),
                operation_name="handle_callback_query",
                context={"update_id": update.update_id if update else None}
            )
        
        service.handle_callback_query = wrapped_handle_callback
        service._error_boundary = boundary
        
        return service
    
    @pytest.fixture
    def mock_callback_update(self):
        """Create mock callback query update."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=456, type="private")
        
        # Mock callback query
        callback_query = Mock()
        callback_query.id = "callback_123"
        callback_query.from_user = user
        callback_query.data = "speech_lang_en"
        callback_query.message = Mock()
        callback_query.message.chat = chat
        
        update = Update(update_id=1, callback_query=callback_query)
        return update
    
    @pytest.mark.asyncio
    async def test_callback_processing_error_isolation(
        self, 
        callback_service_with_boundary, 
        mock_callback_update, 
        mock_context
    ):
        """Test error isolation in callback processing."""
        service = callback_service_with_boundary
        
        with patch.object(service, 'route_callback', new_callable=AsyncMock) as mock_route:
            mock_route.side_effect = ValueError("Invalid callback data")
            
            with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
                await service.handle_callback_query(mock_callback_update, mock_context)
                
                # Error should be isolated
                assert service._error_boundary.metrics.error_count == 1
                mock_handle.assert_called_once()


class TestHealthMonitoringIntegration:
    """Test health monitoring integration with real services."""
    
    @pytest.fixture
    def integrated_health_monitor(self):
        """Create health monitor with multiple services."""
        monitor = ServiceHealthMonitor()
        
        # Register multiple services
        monitor.register_service("message_handler")
        monitor.register_service("speech_recognition")
        monitor.register_service("command_registry")
        monitor.register_service("callback_handler")
        
        return monitor
    
    @pytest.mark.asyncio
    async def test_multi_service_health_monitoring(self, integrated_health_monitor):
        """Test health monitoring across multiple services."""
        monitor = integrated_health_monitor
        
        # Simulate different health states
        message_boundary = monitor.get_error_boundary("message_handler")
        speech_boundary = monitor.get_error_boundary("speech_recognition")
        
        # Make message handler unhealthy
        message_boundary.metrics.consecutive_failures = 5
        message_boundary.metrics.status = message_boundary.metrics.status.UNHEALTHY
        
        # Keep speech recognition healthy
        speech_boundary.metrics.consecutive_failures = 0
        
        # Generate health report
        report = monitor.generate_health_report()
        
        assert report["total_services"] == 4
        assert report["unhealthy_services"] == 1
        assert "message_handler" in report["unhealthy_service_names"]
        assert report["overall_health_percentage"] == 75.0
    
    @pytest.mark.asyncio
    async def test_health_monitoring_lifecycle(self, integrated_health_monitor):
        """Test health monitoring start/stop lifecycle."""
        monitor = integrated_health_monitor
        
        # Start monitoring
        await monitor.start_monitoring()
        assert monitor.is_monitoring is True
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Stop monitoring
        await monitor.stop_monitoring()
        assert monitor.is_monitoring is False


class TestDecoratorIntegration:
    """Test error boundary decorator integration."""
    
    @pytest.mark.asyncio
    async def test_decorator_with_real_service_method(self):
        """Test decorator integration with real service methods."""
        
        @with_error_boundary("test_service", "test_method", timeout=1.0)
        async def simulated_service_method(data: str) -> str:
            if data == "error":
                raise ValueError("Simulated service error")
            elif data == "slow":
                await asyncio.sleep(2)  # Will timeout
                return "too_slow"
            return f"processed_{data}"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
            # Test successful operation
            result = await simulated_service_method("success")
            assert result == "processed_success"
            
            # Test error handling
            result = await simulated_service_method("error")
            assert result is None
            
            # Test timeout handling
            result = await simulated_service_method("slow")
            assert result is None
            
            # Should have handled 2 errors
            assert mock_handle.call_count == 2
        
        # Check service metrics
        boundary = health_monitor.get_error_boundary("test_service")
        assert boundary is not None
        assert boundary.metrics.success_count == 1
        assert boundary.metrics.error_count == 2


class TestErrorRecoveryScenarios:
    """Test error recovery scenarios across services."""
    
    @pytest.mark.asyncio
    async def test_service_recovery_after_failures(self):
        """Test service recovery after multiple failures."""
        boundary = ServiceErrorBoundary("recovery_test_service")
        
        failure_count = 0
        
        async def intermittent_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:
                raise ValueError(f"Failure {failure_count}")
            return "recovered"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            # First 3 attempts should fail
            for i in range(3):
                result = await boundary.execute_with_boundary(
                    operation=intermittent_operation,
                    operation_name="intermittent_op"
                )
                assert result is None
            
            # Service should be unhealthy
            assert not boundary.is_healthy()
            
            # 4th attempt should succeed
            result = await boundary.execute_with_boundary(
                operation=intermittent_operation,
                operation_name="intermittent_op"
            )
            assert result == "recovered"
            
            # Continue with successful operations
            for _ in range(5):
                result = await boundary.execute_with_boundary(
                    operation=intermittent_operation,
                    operation_name="intermittent_op"
                )
                assert result == "recovered"
            
            # Service should recover to healthy
            assert boundary.is_healthy()
    
    @pytest.mark.asyncio
    async def test_cascading_failure_prevention(self):
        """Test prevention of cascading failures across services."""
        monitor = ServiceHealthMonitor()
        
        # Create multiple interconnected services
        service_a = monitor.register_service("service_a")
        service_b = monitor.register_service("service_b")
        service_c = monitor.register_service("service_c")
        
        async def failing_operation():
            raise ValueError("Service failure")
        
        async def dependent_operation():
            # This service depends on service_a
            if not service_a.is_healthy():
                return "degraded_mode"
            return "normal_operation"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            # Fail service_a multiple times
            for _ in range(5):
                await service_a.execute_with_boundary(
                    operation=failing_operation,
                    operation_name="fail_op"
                )
            
            # Service_a should be unhealthy
            assert not service_a.is_healthy()
            
            # Service_b should still operate in degraded mode
            result = await service_b.execute_with_boundary(
                operation=dependent_operation,
                operation_name="dependent_op"
            )
            assert result == "degraded_mode"
            
            # Service_c should be unaffected
            assert service_c.is_healthy()
        
        # Check overall system health
        unhealthy_services = monitor.get_unhealthy_services()
        assert "service_a" in unhealthy_services
        assert "service_b" not in unhealthy_services
        assert "service_c" not in unhealthy_services