"""
Unit tests for error handling decorators.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

from modules.error_decorators import (
    handle_command_errors, handle_service_errors, handle_database_errors,
    handle_network_errors, handle_validation_errors, circuit_breaker,
    telegram_command, external_api, database_operation, user_input_validation,
    ErrorHandlingConfig
)
from modules.error_handler import ErrorSeverity, ErrorCategory, StandardError


class TestErrorHandlingConfig:
    """Test cases for ErrorHandlingConfig."""
    
    def test_default_config(self):
        """Test ErrorHandlingConfig with default values."""
        config = ErrorHandlingConfig()
        
        assert config.feedback_message is None
        assert config.severity == ErrorSeverity.MEDIUM
        assert config.category == ErrorCategory.GENERAL
        assert config.retry_count == 0
        assert config.retry_delay == 1.0
        assert config.fallback_response is None
        assert config.log_level == "error"
        assert config.suppress_errors is False
        assert config.error_stickers == []
    
    def test_custom_config(self):
        """Test ErrorHandlingConfig with custom values."""
        config = ErrorHandlingConfig(
            feedback_message="Custom error message",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE,
            retry_count=3,
            retry_delay=2.0,
            fallback_response="Fallback",
            log_level="warning",
            suppress_errors=True,
            error_stickers=["sticker1", "sticker2"]
        )
        
        assert config.feedback_message == "Custom error message"
        assert config.severity == ErrorSeverity.HIGH
        assert config.category == ErrorCategory.DATABASE
        assert config.retry_count == 3
        assert config.retry_delay == 2.0
        assert config.fallback_response == "Fallback"
        assert config.log_level == "warning"
        assert config.suppress_errors is True
        assert config.error_stickers == ["sticker1", "sticker2"]


class TestHandleCommandErrors:
    """Test cases for handle_command_errors decorator."""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="/test"
        )
        return Update(update_id=1, message=message)
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock callback context."""
        return Mock(spec=CallbackContext)
    
    @pytest.mark.asyncio
    async def test_successful_command_execution(self, mock_update, mock_context):
        """Test decorator with successful command execution."""
        @handle_command_errors()
        async def test_command(update, context):
            return "success"
        
        result = await test_command(mock_update, mock_context)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_command_error_handling(self, mock_update, mock_context):
        """Test decorator with command error."""
        @handle_command_errors(feedback_message="Test error occurred")
        async def test_command(update, context):
            raise ValueError("Test error")
        
        with patch('modules.error_decorators.ErrorHandler.handle_error', new_callable=AsyncMock) as mock_handle:
            result = await test_command(mock_update, mock_context)
            
            assert result is None
            mock_handle.assert_called_once()
            call_args = mock_handle.call_args
            assert isinstance(call_args[1]['error'], ValueError)
            assert call_args[1]['update'] is mock_update
            assert call_args[1]['context'] is mock_context
            assert call_args[1]['feedback_message'] == "Test error occurred"
    
    @pytest.mark.asyncio
    async def test_command_retry_logic(self, mock_update, mock_context):
        """Test decorator retry logic."""
        call_count = 0
        
        @handle_command_errors(retry_count=2)
        async def test_command(update, context):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await test_command(mock_update, mock_context)
            
            assert result == "success"
            assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_command_retry_exhausted(self, mock_update, mock_context):
        """Test decorator when all retries are exhausted."""
        @handle_command_errors(retry_count=2, fallback_response="Fallback")
        async def test_command(update, context):
            raise ConnectionError("Persistent error")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('modules.error_decorators.ErrorHandler.handle_error', new_callable=AsyncMock) as mock_handle:
                result = await test_command(mock_update, mock_context)
                
                assert result is None
                mock_handle.assert_called_once()
                call_args = mock_handle.call_args
                assert call_args[1]['feedback_message'] == "Fallback"
                assert call_args[1]['context_data']['retry_count'] == 2


class TestHandleServiceErrors:
    """Test cases for handle_service_errors decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_service_call(self):
        """Test decorator with successful service call."""
        @handle_service_errors("test_service")
        async def test_service():
            return "success"
        
        result = await test_service()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_service_error_with_fallback(self):
        """Test decorator with service error and fallback value."""
        @handle_service_errors("test_service", fallback_value="fallback")
        async def test_service():
            raise ValueError("Service error")
        
        with patch('modules.error_decorators.error_logger') as mock_logger:
            result = await test_service()
            
            assert result == "fallback"
            mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_critical_error_re_raised(self):
        """Test that critical errors are re-raised."""
        @handle_service_errors("test_service", raise_on_critical=True)
        async def test_service():
            raise ConnectionError("Critical error")
        
        with pytest.raises(ConnectionError):
            await test_service()
    
    @pytest.mark.asyncio
    async def test_non_critical_error_not_raised(self):
        """Test that non-critical errors are not re-raised."""
        @handle_service_errors("test_service", fallback_value="fallback")
        async def test_service():
            raise ValueError("Non-critical error")
        
        result = await test_service()
        assert result == "fallback"


class TestHandleDatabaseErrors:
    """Test cases for handle_database_errors decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_database_operation(self):
        """Test decorator with successful database operation."""
        @handle_database_errors("select")
        async def test_db_operation():
            return "success"
        
        result = await test_db_operation()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_database_error_with_retry(self):
        """Test decorator with transient database error and retry."""
        call_count = 0
        
        @handle_database_errors("select", retry_count=2)
        async def test_db_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection lost")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await test_db_operation()
            
            assert result == "success"
            assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_database_error_retry_exhausted(self):
        """Test decorator when database retries are exhausted."""
        @handle_database_errors("insert", fallback_value=None, retry_count=1)
        async def test_db_operation():
            raise TimeoutError("Database timeout")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('modules.error_decorators.error_logger') as mock_logger:
                with patch('modules.error_decorators.track_error') as mock_track:
                    result = await test_db_operation()
                    
                    assert result is None
                    mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_non_transient_database_error(self):
        """Test decorator with non-transient database error."""
        @handle_database_errors("select", fallback_value="fallback")
        async def test_db_operation():
            raise ValueError("Invalid query")
        
        with patch('modules.error_decorators.error_logger') as mock_logger:
            result = await test_db_operation()
            
            assert result == "fallback"
            mock_logger.error.assert_called_once()


class TestHandleNetworkErrors:
    """Test cases for handle_network_errors decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_network_call(self):
        """Test decorator with successful network call."""
        @handle_network_errors("test_api")
        async def test_api_call():
            return "success"
        
        result = await test_api_call()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test decorator with network timeout."""
        @handle_network_errors("test_api", timeout=0.1)
        async def test_api_call():
            await asyncio.sleep(1)  # Longer than timeout
            return "success"
        
        with patch('modules.error_decorators.error_logger') as mock_logger:
            result = await test_api_call()
            
            assert result is None
            mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_network_error_with_retry(self):
        """Test decorator with network error and retry."""
        call_count = 0
        
        @handle_network_errors("test_api", retry_count=2)
        async def test_api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await test_api_call()
            
            assert result == "success"
            assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_non_network_error(self):
        """Test decorator with non-network error."""
        @handle_network_errors("test_api", fallback_value="fallback")
        async def test_api_call():
            raise ValueError("Invalid response")
        
        with patch('modules.error_decorators.error_logger') as mock_logger:
            result = await test_api_call()
            
            assert result == "fallback"
            mock_logger.error.assert_called_once()


class TestHandleValidationErrors:
    """Test cases for handle_validation_errors decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_validation(self):
        """Test decorator with successful validation."""
        @handle_validation_errors("user_input")
        async def test_validation(value):
            if not isinstance(value, str):
                raise ValueError("Must be string")
            return value.upper()
        
        result = await test_validation("test")
        assert result == "TEST"
    
    @pytest.mark.asyncio
    async def test_validation_error(self):
        """Test decorator with validation error."""
        @handle_validation_errors("user_input", default_value="default")
        async def test_validation(value):
            raise ValueError("Invalid input")
        
        with patch('modules.error_decorators.error_logger') as mock_logger:
            result = await test_validation("invalid")
            
            assert result == "default"
            mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validation_error_no_logging(self):
        """Test decorator with validation error and no logging."""
        @handle_validation_errors("user_input", log_invalid_input=False)
        async def test_validation(value):
            raise TypeError("Type error")
        
        with patch('modules.error_decorators.error_logger') as mock_logger:
            result = await test_validation("invalid")
            
            assert result is None
            mock_logger.warning.assert_not_called()


class TestCircuitBreaker:
    """Test cases for circuit_breaker decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test circuit breaker with successful calls."""
        @circuit_breaker(failure_threshold=3)
        async def test_function():
            return "success"
        
        # Multiple successful calls should work
        for _ in range(5):
            result = await test_function()
            assert result == "success"
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test that circuit opens after threshold failures."""
        call_count = 0
        
        @circuit_breaker(failure_threshold=3)
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        # First 3 calls should raise the original exception
        for i in range(3):
            with pytest.raises(ValueError):
                await test_function()
        
        # 4th call should raise StandardError (circuit open)
        with pytest.raises(StandardError, match="Circuit breaker is open"):
            await test_function()
        
        assert call_count == 3  # Function should not be called when circuit is open
    
    @pytest.mark.asyncio
    async def test_circuit_recovery(self):
        """Test circuit breaker recovery after timeout."""
        call_count = 0
        
        @circuit_breaker(failure_threshold=2, recovery_timeout=0.1)
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("Test error")
            return "success"
        
        # Trigger circuit opening
        for _ in range(2):
            with pytest.raises(ValueError):
                await test_function()
        
        # Circuit should be open
        with pytest.raises(StandardError):
            await test_function()
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Circuit should attempt recovery and succeed
        result = await test_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_circuit_reset_on_success(self):
        """Test that circuit resets failure count on success."""
        call_count = 0
        
        @circuit_breaker(failure_threshold=3)
        async def test_function(should_fail=True):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Two failures
        for _ in range(2):
            with pytest.raises(ValueError):
                await test_function(True)
        
        # One success (should reset counter)
        result = await test_function(False)
        assert result == "success"
        
        # Two more failures (should not open circuit yet)
        for _ in range(2):
            with pytest.raises(ValueError):
                await test_function(True)
        
        # Circuit should still be closed (counter was reset)
        with pytest.raises(ValueError):  # Should be original exception, not circuit breaker
            await test_function(True)


class TestConvenienceDecorators:
    """Test cases for convenience decorators."""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="/test"
        )
        return Update(update_id=1, message=message)
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock callback context."""
        return Mock(spec=CallbackContext)
    
    @pytest.mark.asyncio
    async def test_telegram_command_decorator(self, mock_update, mock_context):
        """Test telegram_command convenience decorator."""
        @telegram_command(feedback_message="Command failed")
        async def test_command(update, context):
            raise ValueError("Test error")
        
        with patch('modules.error_decorators.ErrorHandler.handle_error', new_callable=AsyncMock) as mock_handle:
            result = await test_command(mock_update, mock_context)
            
            assert result is None
            mock_handle.assert_called_once()
            assert mock_handle.call_args[1]['feedback_message'] == "Command failed"
    
    @pytest.mark.asyncio
    async def test_external_api_decorator(self):
        """Test external_api convenience decorator."""
        @external_api("test_service", timeout=0.1)
        async def test_api():
            await asyncio.sleep(1)  # Longer than timeout
            return "success"
        
        with patch('modules.error_decorators.error_logger'):
            result = await test_api()
            assert result is None
    
    @pytest.mark.asyncio
    async def test_database_operation_decorator(self):
        """Test database_operation convenience decorator."""
        @database_operation("select_users")
        async def test_db():
            raise ConnectionError("DB error")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('modules.error_decorators.error_logger'):
                result = await test_db()
                assert result is None
    
    @pytest.mark.asyncio
    async def test_user_input_validation_decorator(self):
        """Test user_input_validation convenience decorator."""
        @user_input_validation("email")
        async def test_validation(email):
            if "@" not in email:
                raise ValueError("Invalid email")
            return email
        
        with patch('modules.error_decorators.error_logger'):
            result = await test_validation("invalid-email")
            assert result is None


class TestDecoratorIntegration:
    """Integration tests for error decorators."""
    
    @pytest.mark.asyncio
    async def test_multiple_decorators(self):
        """Test combining multiple error decorators."""
        call_count = 0
        
        @handle_command_errors(retry_count=1)
        @handle_network_errors("api", retry_count=1)
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        # This will be complex due to nested decorators
        # The outer decorator (command_errors) will handle the final error
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('modules.error_decorators.ErrorHandler.handle_error', new_callable=AsyncMock):
                result = await test_function()
                # The exact behavior depends on decorator order and implementation
    
    @pytest.mark.asyncio
    async def test_decorator_with_real_error_types(self):
        """Test decorators with realistic error scenarios."""
        @handle_network_errors("weather_api", timeout=5.0, retry_count=2)
        async def get_weather(city):
            if city == "invalid":
                raise ValueError("Invalid city")
            if city == "timeout":
                raise asyncio.TimeoutError("Request timeout")
            if city == "network":
                raise ConnectionError("Network error")
            return f"Weather for {city}: Sunny"
        
        # Successful call
        result = await get_weather("London")
        assert result == "Weather for London: Sunny"
        
        # Non-network error (should not retry)
        with patch('modules.error_decorators.error_logger'):
            result = await get_weather("invalid")
            assert result is None
        
        # Network error (should retry)
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('modules.error_decorators.error_logger'):
                result = await get_weather("network")
                assert result is None