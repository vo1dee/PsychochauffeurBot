"""
Base test classes with common patterns and utilities for the PsychoChauffeur Bot test suite.
"""

import pytest
import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from telegram import Update, Message, User, Chat, CallbackQuery, Bot
from telegram.ext import CallbackContext, Application


class BaseTestCase(unittest.TestCase):
    """Base test case with common setup and utilities."""
    
    def setUp(self):
        """Set up test case."""
        self.setup_mocks()
        self.setup_test_data()
    
    def tearDown(self):
        """Clean up after test case."""
        self.cleanup_mocks()
    
    def setup_mocks(self):
        """Set up common mocks."""
        self.mock_bot = Mock(spec=Bot)
        self.mock_bot.token = "test_token"
        self.mock_bot.get_me = AsyncMock(return_value=Mock(username="test_bot"))
        self.mock_bot.send_message = AsyncMock()
        self.mock_bot.send_photo = AsyncMock()
        self.mock_bot.send_sticker = AsyncMock()
        self.mock_bot.send_document = AsyncMock()
        self.mock_bot.get_file = AsyncMock()
        self.mock_bot.get_chat_member = AsyncMock()
    
    def setup_test_data(self):
        """Set up common test data."""
        self.test_user_id = 12345
        self.test_chat_id = 12345
        self.test_group_id = -1001234567890
        self.test_username = "testuser"
        self.test_message_text = "Test message"
    
    def cleanup_mocks(self):
        """Clean up mocks after test."""
        # Reset all mocks
        if hasattr(self, 'mock_bot'):
            self.mock_bot.reset_mock()
    
    def create_mock_user(self, user_id: int = None, username: str = None) -> User:
        """Create a mock Telegram User."""
        return User(
            id=user_id or self.test_user_id,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username=username or self.test_username,
            language_code="en"
        )
    
    def create_mock_private_chat(self, chat_id: int = None, username: str = None) -> Chat:
        """Create a mock private Telegram Chat."""
        return Chat(
            id=chat_id or self.test_chat_id,
            type=Chat.PRIVATE,
            username=username or self.test_username,
            first_name="Test",
            last_name="User"
        )
    
    def create_mock_group_chat(self, chat_id: int = None, title: str = "Test Group") -> Chat:
        """Create a mock group Telegram Chat."""
        return Chat(
            id=chat_id or self.test_group_id,
            type=Chat.SUPERGROUP,
            title=title,
            description="A test group chat"
        )
    
    def create_mock_message(self, text: str = None, user: User = None, chat: Chat = None) -> Mock:
        """Create a mock Telegram Message that can be modified."""
        mock_message = Mock(spec=Message)
        mock_message.message_id = 1
        mock_message.date = Mock()
        mock_message.chat = chat or self.create_mock_private_chat()
        mock_message.from_user = user or self.create_mock_user()
        mock_message.text = text or self.test_message_text
        mock_message.reply_text = AsyncMock()
        mock_message.reply_photo = AsyncMock()
        mock_message.reply_document = AsyncMock()
        mock_message.edit_text = AsyncMock()
        mock_message.delete = AsyncMock()
        return mock_message
    
    def create_mock_update(self, message: Mock = None) -> Mock:
        """Create a mock Telegram Update."""
        mock_update = Mock(spec=Update)
        mock_update.update_id = 1
        mock_update.message = message or self.create_mock_message()
        mock_update.callback_query = None
        mock_update.effective_user = mock_update.message.from_user
        mock_update.effective_chat = mock_update.message.chat
        return mock_update
    
    def create_mock_callback_query(self, data: str = "test_data", user: User = None, chat: Chat = None) -> Mock:
        """Create a mock Telegram CallbackQuery."""
        mock_callback = Mock(spec=CallbackQuery)
        mock_callback.id = "test_callback_query"
        mock_callback.from_user = user or self.create_mock_user()
        mock_callback.chat_instance = "test_chat_instance"
        mock_callback.data = data
        mock_callback.answer = AsyncMock()
        mock_callback.edit_message_text = AsyncMock()
        mock_callback.edit_message_reply_markup = AsyncMock()
        
        # Create associated message
        mock_message = self.create_mock_message(user=mock_callback.from_user, chat=chat)
        mock_callback.message = mock_message
        
        return mock_callback
    
    def create_mock_context(self, bot: Mock = None) -> Mock:
        """Create a mock CallbackContext."""
        mock_context = Mock(spec=CallbackContext)
        mock_context.bot = bot or self.mock_bot
        mock_context.args = []
        mock_context.user_data = {}
        mock_context.chat_data = {}
        mock_context.bot_data = {}
        return mock_context
    
    def assert_mock_called_with_partial(self, mock_obj, **expected_kwargs):
        """Assert that mock was called with at least the specified kwargs."""
        mock_obj.assert_called()
        call_args = mock_obj.call_args
        if call_args is None:
            self.fail(f"Mock {mock_obj} was not called")
        
        actual_kwargs = call_args.kwargs
        for key, expected_value in expected_kwargs.items():
            self.assertIn(key, actual_kwargs, f"Expected key '{key}' not found in call arguments")
            self.assertEqual(actual_kwargs[key], expected_value, 
                           f"Expected {key}={expected_value}, got {actual_kwargs[key]}")


class AsyncBaseTestCase(BaseTestCase):
    """Base test case for async tests with proper event loop management."""
    
    def setUp(self):
        """Set up async test case."""
        super().setUp()
        self.setup_async_environment()
    
    def tearDown(self):
        """Clean up async test case."""
        self.cleanup_async_environment()
        super().tearDown()
    
    def setup_async_environment(self):
        """Set up async test environment."""
        # Ensure we have an event loop
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
    
    def cleanup_async_environment(self):
        """Clean up async test environment."""
        # Cancel any pending tasks
        if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                if not task.done():
                    task.cancel()
    
    async def run_async_test(self, coro):
        """Run an async test with proper error handling."""
        try:
            return await coro
        except Exception as e:
            self.fail(f"Async test failed: {e}")
    
    def run_async(self, coro):
        """Helper to run async code in sync test methods."""
        if hasattr(self, 'loop') and self.loop:
            return self.loop.run_until_complete(coro)
        else:
            return asyncio.run(coro)


class DatabaseTestCase(AsyncBaseTestCase):
    """Base test case for database-related tests."""
    
    def setUp(self):
        """Set up database test case."""
        super().setUp()
        self.setup_test_database()
    
    def tearDown(self):
        """Clean up database test case."""
        self.cleanup_test_database()
        super().tearDown()
    
    def setup_test_database(self):
        """Set up test database."""
        # This will be implemented when we have database utilities
        pass
    
    def cleanup_test_database(self):
        """Clean up test database."""
        # This will be implemented when we have database utilities
        pass


class IntegrationTestCase(AsyncBaseTestCase):
    """Base test case for integration tests."""
    
    def setUp(self):
        """Set up integration test case."""
        super().setUp()
        self.setup_integration_environment()
    
    def tearDown(self):
        """Clean up integration test case."""
        self.cleanup_integration_environment()
        super().tearDown()
    
    def setup_integration_environment(self):
        """Set up integration test environment."""
        # Set up external service mocks
        self.setup_external_service_mocks()
    
    def cleanup_integration_environment(self):
        """Clean up integration test environment."""
        # Clean up external service mocks
        pass
    
    def setup_external_service_mocks(self):
        """Set up mocks for external services."""
        # OpenAI mock
        self.mock_openai_client = Mock()
        self.mock_openai_response = Mock()
        self.mock_openai_response.choices = [Mock()]
        self.mock_openai_response.choices[0].message = Mock()
        self.mock_openai_response.choices[0].message.content = "Test AI response"
        self.mock_openai_client.chat.completions.create = AsyncMock(return_value=self.mock_openai_response)
        
        # Weather API mock
        self.mock_weather_api = Mock()
        self.mock_weather_api.get_current_weather = AsyncMock(return_value={
            "temperature": 20.5,
            "description": "Clear sky",
            "humidity": 65,
            "wind_speed": 3.2
        })
        
        # Video downloader mock
        self.mock_video_downloader = Mock()
        self.mock_video_downloader.download = AsyncMock(return_value={
            "success": True,
            "file_path": "/tmp/test_video.mp4",
            "title": "Test Video",
            "duration": 120
        })


class MockTestCase(BaseTestCase):
    """Base test case with enhanced mocking utilities."""
    
    def setUp(self):
        """Set up mock test case."""
        super().setUp()
        self.active_patches = []
    
    def tearDown(self):
        """Clean up mock test case."""
        self.stop_all_patches()
        super().tearDown()
    
    def patch_object(self, target, attribute, new=None, **kwargs):
        """Create and start a patch, keeping track for cleanup."""
        patcher = patch.object(target, attribute, new=new, **kwargs)
        mock_obj = patcher.start()
        self.active_patches.append(patcher)
        return mock_obj
    
    def patch_module(self, target, new=None, **kwargs):
        """Create and start a module patch, keeping track for cleanup."""
        patcher = patch(target, new=new, **kwargs)
        mock_obj = patcher.start()
        self.active_patches.append(patcher)
        return mock_obj
    
    def stop_all_patches(self):
        """Stop all active patches."""
        for patcher in self.active_patches:
            try:
                patcher.stop()
            except RuntimeError:
                # Patch was already stopped
                pass
        self.active_patches.clear()


class ParametrizedTestCase(BaseTestCase):
    """Base test case with utilities for parametrized tests."""
    
    def run_parametrized_test(self, test_func, test_cases: List[Dict[str, Any]]):
        """Run a test function with multiple parameter sets."""
        for i, test_case in enumerate(test_cases):
            with self.subTest(case=i, **test_case):
                test_func(**test_case)
    
    async def run_async_parametrized_test(self, test_func, test_cases: List[Dict[str, Any]]):
        """Run an async test function with multiple parameter sets."""
        for i, test_case in enumerate(test_cases):
            with self.subTest(case=i, **test_case):
                await test_func(**test_case)


# ============================================================================
# Test Mixins for Common Functionality
# ============================================================================

class TelegramTestMixin:
    """Mixin providing Telegram-specific test utilities."""
    
    def assert_message_sent(self, mock_bot, chat_id: int = None, text: str = None):
        """Assert that a message was sent via the bot."""
        mock_bot.send_message.assert_called()
        if chat_id is not None or text is not None:
            call_args = mock_bot.send_message.call_args
            if chat_id is not None:
                self.assertEqual(call_args.kwargs.get('chat_id'), chat_id)
            if text is not None:
                self.assertIn(text, call_args.kwargs.get('text', ''))
    
    def assert_callback_answered(self, mock_callback_query):
        """Assert that a callback query was answered."""
        mock_callback_query.answer.assert_called()
    
    def assert_message_edited(self, mock_callback_query, text: str = None):
        """Assert that a message was edited."""
        mock_callback_query.edit_message_text.assert_called()
        if text is not None:
            call_args = mock_callback_query.edit_message_text.call_args
            self.assertIn(text, call_args.kwargs.get('text', ''))


class ConfigTestMixin:
    """Mixin providing configuration-related test utilities."""
    
    def create_test_config(self, **overrides) -> Dict[str, Any]:
        """Create a test configuration with optional overrides."""
        base_config = {
            "chat_metadata": {
                "chat_id": "test_chat",
                "chat_type": "private",
                "chat_name": "Test Chat",
                "created_at": "2025-07-15T10:00:00",
                "last_updated": "2025-07-15T10:00:00",
                "custom_config_enabled": True
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {
                        "temperature": 0.8,
                        "max_tokens": 1000
                    }
                }
            }
        }
        
        # Apply overrides
        for key, value in overrides.items():
            if '.' in key:
                # Handle nested keys like "config_modules.gpt.enabled"
                keys = key.split('.')
                current = base_config
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
            else:
                base_config[key] = value
        
        return base_config


class ErrorTestMixin:
    """Mixin providing error handling test utilities."""
    
    def assert_error_logged(self, caplog, error_message: str = None, level: str = "ERROR"):
        """Assert that an error was logged."""
        error_records = [record for record in caplog.records if record.levelname == level]
        self.assertTrue(error_records, f"No {level} level logs found")
        
        if error_message:
            error_messages = [record.message for record in error_records]
            self.assertTrue(
                any(error_message in msg for msg in error_messages),
                f"Error message '{error_message}' not found in logs: {error_messages}"
            )
    
    def assert_exception_handled(self, test_func, expected_exception, *args, **kwargs):
        """Assert that a function properly handles an expected exception."""
        with self.assertRaises(expected_exception):
            if asyncio.iscoroutinefunction(test_func):
                self.run_async(test_func(*args, **kwargs))
            else:
                test_func(*args, **kwargs)


# ============================================================================
# Combined Base Classes
# ============================================================================

class ComprehensiveTestCase(AsyncBaseTestCase, MockTestCase, TelegramTestMixin, 
                          ConfigTestMixin, ErrorTestMixin):
    """Comprehensive test case combining all mixins and utilities."""
    
    def setUp(self):
        """Set up comprehensive test case."""
        AsyncBaseTestCase.setUp(self)
        MockTestCase.setUp(self)
    
    def tearDown(self):
        """Clean up comprehensive test case."""
        MockTestCase.tearDown(self)
        AsyncBaseTestCase.tearDown(self)


class IntegrationTestCaseWithMixins(IntegrationTestCase, TelegramTestMixin, 
                                   ConfigTestMixin, ErrorTestMixin):
    """Integration test case with all mixins."""
    pass


class DatabaseTestCaseWithMixins(DatabaseTestCase, ConfigTestMixin, ErrorTestMixin):
    """Database test case with configuration and error mixins."""
    pass