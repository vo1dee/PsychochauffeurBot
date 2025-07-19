"""
Example demonstrating proper async test patterns and best practices.

This file shows how to write async tests using the standardized patterns
provided by the test infrastructure.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from tests.base_test_classes import ComprehensiveTestCase


class TestAsyncPatterns(ComprehensiveTestCase):
    """Example test class demonstrating proper async test patterns."""
    
    def setUp(self):
        """Set up test case with async environment."""
        super().setUp()
        # Setup any additional test-specific mocks or data
        self.test_data = {"key": "value"}
    
    async def test_basic_async_operation(self) -> None:
        """Example of testing a basic async operation."""
        # Create an async mock
        async_service = self.create_async_mock(return_value="success")
        
        # Test the async operation
        result = await async_service()
        
        # Assert the result
        self.assertEqual(result, "success")
        self.assert_async_mock_called(async_service)
    
    async def test_async_operation_with_timeout(self) -> None:
        """Example of testing async operation with timeout."""
        async def slow_operation():
            await asyncio.sleep(0.1)  # Simulate work
            return "completed"
        
        # Test with timeout
        result = await self.run_async_test_with_timeout(slow_operation(), timeout=1.0)
        self.assertEqual(result, "completed")
    
    async def test_async_exception_handling(self) -> None:
        """Example of testing async exception handling."""
        async def failing_operation():
            raise ValueError("Test error")
        
        # Assert that the exception is raised
        await self.assert_async_raises(ValueError, failing_operation())
    
    async def test_multiple_async_operations(self):
        """Example of testing multiple async operations."""
        async def operation1():
            await asyncio.sleep(0.01)
            return "result1"
        
        async def operation2():
            await asyncio.sleep(0.01)
            return "result2"
        
        # Wait for multiple operations
        results = await self.wait_for_multiple_async_operations(
            operation1(),
            operation2(),
            timeout=5.0
        )
        
        self.assertEqual(results, ["result1", "result2"])
    
    async def test_async_context_manager(self):
        """Example of testing async context managers."""
        # Create a mock async context manager
        mock_cm = self.create_async_context_manager_mock(return_value="context_value")
        
        # Test using the context manager
        async with mock_cm as value:
            self.assertEqual(value, "context_value")
        
        # Assert context manager methods were called
        mock_cm.__aenter__.assert_called_once()
        mock_cm.__aexit__.assert_called_once()
    
    async def test_async_mock_chain(self):
        """Example of testing chained async method calls."""
        # Create a mock with chained async methods
        service_mock = Mock()
        self.setup_async_mock_chain(
            service_mock, 
            ["get_client", "authenticate", "fetch_data"],
            final_return_value="data"
        )
        
        # Test the chain
        result = await service_mock.get_client().authenticate().fetch_data()
        self.assertEqual(result, "data")
    
    @pytest.mark.asyncio
    async def test_with_pytest_asyncio_decorator(self):
        """Example using pytest.mark.asyncio decorator."""
        # This test can also use pytest's async support
        async_mock = AsyncMock(return_value="pytest_result")
        
        result = await async_mock()
        
        assert result == "pytest_result"
        async_mock.assert_awaited_once()
    
    async def test_async_generator(self):
        """Example of testing async generators."""
        async def async_data_generator():
            for i in range(3):
                await asyncio.sleep(0.001)  # Simulate async work
                yield f"item_{i}"
        
        # Test the async generator
        values = await self.consume_async_generator(async_data_generator())
        expected_values = ["item_0", "item_1", "item_2"]
        
        self.assertEqual(values, expected_values)
    
    async def test_async_with_external_service_mock(self):
        """Example of testing with external service mocks."""
        # Use the standardized external service mocks
        external_mocks = self.setup_external_service_mocks()
        openai_mock = external_mocks['openai']
        
        # Test using the mock
        response = await openai_mock.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "test"}]
        )
        
        self.assertEqual(response.choices[0].message.content, "Test AI response")
    
    async def test_async_database_operations(self):
        """Example of testing async database operations."""
        # Setup database mock
        db_mock = AsyncMock()
        db_mock.fetch_one.return_value = {"id": 1, "name": "test"}
        db_mock.execute.return_value = True
        
        # Test database operations
        result = await db_mock.fetch_one("SELECT * FROM users WHERE id = ?", (1,))
        success = await db_mock.execute("INSERT INTO users (name) VALUES (?)", ("test",))
        
        self.assertEqual(result["name"], "test")
        self.assertTrue(success)
        
        # Assert calls were made correctly
        db_mock.fetch_one.assert_called_once()
        db_mock.execute.assert_called_once()
    
    async def test_async_error_recovery(self):
        """Example of testing async error recovery patterns."""
        call_count = 0
        
        async def unreliable_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        # Test retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await unreliable_operation()
                break
            except ConnectionError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.01)  # Brief delay before retry
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)


class TestAsyncTelegramPatterns(ComprehensiveTestCase):
    """Example test class for async Telegram-specific patterns."""
    
    async def test_async_message_handling(self) -> None:
        """Example of testing async message handling."""
        # Create standard Telegram objects
        telegram_objects = self.setup_standard_telegram_objects()
        message_mock = self.create_standard_message_mock(text="Hello, bot!")
        
        # Mock an async message handler
        async def handle_message(message):
            await asyncio.sleep(0.001)  # Simulate processing
            await message.reply_text("Hello, user!")
            return "handled"
        
        # Test the handler
        result = await handle_message(message_mock)
        
        self.assertEqual(result, "handled")
        message_mock.reply_text.assert_called_once_with("Hello, user!")
    
    async def test_async_callback_query_handling(self) -> None:
        """Example of testing async callback query handling."""
        # Create callback query mock
        callback_mock = self.create_standard_callback_query_mock(data="button_clicked")
        
        # Mock an async callback handler
        async def handle_callback(callback_query):
            await callback_query.answer("Processing...")
            await callback_query.edit_message_text("Button was clicked!")
            return "callback_handled"
        
        # Test the handler
        result = await handle_callback(callback_mock)
        
        self.assertEqual(result, "callback_handled")
        self.assert_callback_answered(callback_mock, text="Processing...")
        self.assert_message_edited(callback_mock, text="Button was clicked!")


# Example of how to run these tests
if __name__ == "__main__":
    import unittest
    
    # Run with unittest
    unittest.main()
    
    # Or run with pytest
    # pytest tests/examples/async_test_patterns_example.py -v