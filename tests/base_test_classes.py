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
from datetime import datetime, timezone


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
    
    def create_mock_message(self, text: str = None, user: User = None, chat: Chat = None, **kwargs) -> Mock:
        """Create a mock Telegram Message that can be modified with proper isolation."""
        mock_message = Mock(spec=Message)
        
        # Core attributes
        mock_message.message_id = 1
        mock_message.date = Mock()
        mock_message.chat = chat or self.create_mock_private_chat()
        mock_message.from_user = user or self.create_mock_user()
        mock_message.text = text or self.test_message_text
        mock_message.chat_id = mock_message.chat.id
        mock_message.id = mock_message.message_id
        
        # Apply any additional kwargs for customization
        for key, value in kwargs.items():
            setattr(mock_message, key, value)
        
        # Content attributes - set to None by default to avoid AttributeError
        default_attrs = {
            'reply_markup': None,
            'entities': [],
            'caption': None,
            'caption_entities': [],
            'photo': None,
            'document': None,
            'video': None,
            'audio': None,
            'voice': None,
            'sticker': None,
            'animation': None,
            'contact': None,
            'location': None,
            'venue': None,
            'poll': None,
            'dice': None,
            'game': None,
            'edit_date': None,
            'media_group_id': None,
            'forward_from': None,
            'forward_from_chat': None,
            'forward_date': None,
            'reply_to_message': None,
            'via_bot': None,
            'sender_chat': None,
            'is_topic_message': False,
            'message_thread_id': None,
            'has_protected_content': False,
            'new_chat_members': [],
            'left_chat_member': None,
            'new_chat_title': None,
            'new_chat_photo': [],
            'delete_chat_photo': False,
            'group_chat_created': False,
            'supergroup_chat_created': False,
            'channel_chat_created': False,
            'pinned_message': None
        }
        
        # Only set attributes that haven't been explicitly set via kwargs
        for attr, default_value in default_attrs.items():
            if not hasattr(mock_message, attr):
                setattr(mock_message, attr, default_value)
        
        # Async methods - create fresh mocks for each message to ensure isolation
        mock_message.reply_text = AsyncMock()
        mock_message.reply_photo = AsyncMock()
        mock_message.reply_document = AsyncMock()
        mock_message.reply_audio = AsyncMock()
        mock_message.reply_video = AsyncMock()
        mock_message.reply_voice = AsyncMock()
        mock_message.reply_sticker = AsyncMock()
        mock_message.reply_animation = AsyncMock()
        mock_message.reply_contact = AsyncMock()
        mock_message.reply_location = AsyncMock()
        mock_message.reply_venue = AsyncMock()
        mock_message.reply_poll = AsyncMock()
        mock_message.reply_dice = AsyncMock()
        mock_message.reply_game = AsyncMock()
        mock_message.reply_invoice = AsyncMock()
        mock_message.reply_media_group = AsyncMock()
        mock_message.reply_html = AsyncMock()
        mock_message.reply_markdown = AsyncMock()
        mock_message.reply_markdown_v2 = AsyncMock()
        mock_message.reply_copy = AsyncMock()
        mock_message.reply_chat_action = AsyncMock()
        
        mock_message.edit_text = AsyncMock()
        mock_message.edit_caption = AsyncMock()
        mock_message.edit_media = AsyncMock()
        mock_message.edit_reply_markup = AsyncMock()
        mock_message.edit_live_location = AsyncMock()
        mock_message.stop_live_location = AsyncMock()
        
        mock_message.delete = AsyncMock()
        mock_message.forward = AsyncMock()
        mock_message.copy = AsyncMock()
        mock_message.pin = AsyncMock()
        mock_message.unpin = AsyncMock()
        mock_message.stop_poll = AsyncMock()
        
        # Properties - ensure they're always available
        mock_message.text_html = getattr(mock_message, 'text', '')
        mock_message.text_markdown = getattr(mock_message, 'text', '')
        mock_message.text_markdown_v2 = getattr(mock_message, 'text', '')
        mock_message.caption_html = getattr(mock_message, 'caption', None)
        mock_message.caption_markdown = getattr(mock_message, 'caption', None)
        mock_message.caption_markdown_v2 = getattr(mock_message, 'caption', None)
        
        # Utility methods - create fresh mocks for isolation
        mock_message.parse_entities = Mock(return_value={})
        mock_message.parse_entity = Mock(return_value="")
        mock_message.parse_caption_entities = Mock(return_value={})
        mock_message.parse_caption_entity = Mock(return_value="")
        
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
    
    def create_mock_callback_query(self, data: str = "test_data", user: User = None, chat: Chat = None, **kwargs) -> Mock:
        """Create a mock Telegram CallbackQuery with proper isolation."""
        mock_callback = Mock(spec=CallbackQuery)
        mock_callback.id = "test_callback_query"
        mock_callback.from_user = user or self.create_mock_user()
        mock_callback.chat_instance = "test_chat_instance"
        mock_callback.data = data
        mock_callback.inline_message_id = None
        mock_callback.game_short_name = None
        
        # Apply any additional kwargs for customization
        for key, value in kwargs.items():
            setattr(mock_callback, key, value)
        
        # Create associated message with proper isolation
        mock_message = self.create_mock_message(user=mock_callback.from_user, chat=chat, text="Original message")
        mock_callback.message = mock_message
        
        # CallbackQuery methods - create fresh mocks for each callback query to ensure isolation
        mock_callback.answer = AsyncMock()
        mock_callback.edit_message_text = AsyncMock()
        mock_callback.edit_message_reply_markup = AsyncMock()
        mock_callback.edit_message_caption = AsyncMock()
        mock_callback.edit_message_media = AsyncMock()
        mock_callback.edit_message_live_location = AsyncMock()
        mock_callback.stop_message_live_location = AsyncMock()
        mock_callback.delete_message = AsyncMock()
        mock_callback.copy_message = AsyncMock()
        mock_callback.pin_message = AsyncMock()
        mock_callback.unpin_message = AsyncMock()
        mock_callback.set_game_score = AsyncMock()
        mock_callback.get_game_high_scores = AsyncMock()
        
        # Utility methods - create fresh mocks for isolation
        mock_callback.to_dict = Mock(return_value={
            'id': mock_callback.id,
            'from': mock_callback.from_user.to_dict() if hasattr(mock_callback.from_user, 'to_dict') else {},
            'chat_instance': mock_callback.chat_instance,
            'data': mock_callback.data
        })
        mock_callback.to_json = Mock(return_value=f'{{"id": "{mock_callback.id}"}}')
        
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
    """Base test case for async tests with proper event loop management and standardized patterns."""
    
    def setUp(self):
        """Set up async test case."""
        super().setUp()
        self.setup_async_environment()
        self.async_mocks = {}
    
    def tearDown(self):
        """Clean up async test case."""
        self.cleanup_async_mocks()
        self.cleanup_async_environment()
        super().tearDown()
    
    def setup_async_environment(self):
        """Set up async test environment with proper isolation."""
        # Ensure we have an event loop
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        # Store original event loop policy for restoration
        self.original_policy = asyncio.get_event_loop_policy()
    
    def cleanup_async_environment(self):
        """Clean up async test environment with proper task cancellation."""
        # Cancel any pending tasks
        if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                if not task.done():
                    task.cancel()
            
            # Wait for cancelled tasks to complete
            if pending:
                try:
                    self.loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except RuntimeError:
                    pass  # Loop might be closed
    
    def setup_async_mocks(self) -> None:
        """Set up async mocks with proper coroutine handling."""
        # Common async mock patterns
        self.async_mocks['database'] = AsyncMock()
        self.async_mocks['config_manager'] = AsyncMock()
        self.async_mocks['external_api'] = AsyncMock()
        
        return self.async_mocks
    
    def cleanup_async_mocks(self) -> None:
        """Clean up async mocks to prevent cross-test contamination."""
        for mock_name, mock_obj in self.async_mocks.items():
            if hasattr(mock_obj, 'reset_mock'):
                mock_obj.reset_mock()
        self.async_mocks.clear()
    
    async def run_async_test(self, coro) -> None:
        """Run an async test with proper error handling and timeout."""
        try:
            # Add timeout to prevent hanging tests
            return await asyncio.wait_for(coro, timeout=30.0)
        except asyncio.TimeoutError:
            self.fail("Async test timed out after 30 seconds")
        except Exception as e:
            self.fail(f"Async test failed: {e}")
    
    def run_async(self, coro) -> None:
        """Helper to run async code in sync test methods with proper error handling."""
        try:
            if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
                return self.loop.run_until_complete(coro)
            else:
                return asyncio.run(coro)
        except Exception as e:
            self.fail(f"Failed to run async code: {e}")
    
    def create_async_mock(self, return_value=None, side_effect=None, **kwargs) -> AsyncMock:
        """Create an AsyncMock with standardized configuration."""
        mock = AsyncMock(**kwargs)
        
        if return_value is not None:
            mock.return_value = return_value
        
        if side_effect is not None:
            mock.side_effect = side_effect
        
        return mock
    
    def assert_async_mock_called(self, async_mock, *args, **kwargs) -> None:
        """Assert that an async mock was called with specific arguments."""
        async_mock.assert_called()
        
        if args or kwargs:
            async_mock.assert_called_with(*args, **kwargs)
    
    async def assert_async_mock_awaited(self, async_mock, *args, **kwargs) -> None:
        """Assert that an async mock was awaited with specific arguments."""
        async_mock.assert_awaited()
        
        if args or kwargs:
            async_mock.assert_awaited_with(*args, **kwargs)
    
    def patch_async_method(self, target, method_name, return_value=None, side_effect=None) -> AsyncMock:
        """Patch an async method with proper AsyncMock configuration."""
        async_mock = self.create_async_mock(return_value=return_value, side_effect=side_effect)
        patcher = patch.object(target, method_name, async_mock)
        mock_obj = patcher.start()
        self.active_patches.append(patcher)
        return mock_obj


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
    """Base test case with enhanced mocking utilities and standardized patterns."""
    
    def setUp(self):
        """Set up mock test case."""
        super().setUp()
        self.active_patches = []
        self.standard_mocks = {}
    
    def tearDown(self):
        """Clean up mock test case."""
        self.cleanup_standard_mocks()
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
    
    def setup_telegram_mocks(self):
        """Set up standardized Telegram mocks."""
        if 'telegram' not in self.standard_mocks:
            self.standard_mocks['telegram'] = self._create_telegram_mocks()
        return self.standard_mocks['telegram']
    
    def setup_external_service_mocks(self):
        """Set up standardized external service mocks."""
        if 'external_services' not in self.standard_mocks:
            self.standard_mocks['external_services'] = self._create_external_service_mocks()
        return self.standard_mocks['external_services']
    
    def _create_telegram_mocks(self):
        """Create standardized Telegram mocks."""
        mocks = {}
        
        # Bot mock
        bot_mock = Mock(spec=Bot)
        bot_mock.token = "test_token"
        bot_mock.send_message = AsyncMock()
        bot_mock.send_photo = AsyncMock()
        bot_mock.send_document = AsyncMock()
        bot_mock.get_me = AsyncMock(return_value=Mock(username="test_bot"))
        bot_mock.answer_callback_query = AsyncMock()
        mocks['bot'] = bot_mock
        
        # Application mock
        app_mock = Mock(spec=Application)
        app_mock.bot = bot_mock
        app_mock.add_handler = Mock()
        app_mock.run_polling = AsyncMock()
        mocks['application'] = app_mock
        
        return mocks
    
    def _create_external_service_mocks(self):
        """Create standardized external service mocks."""
        mocks = {}
        
        # OpenAI mock
        openai_mock = Mock()
        openai_response = Mock()
        openai_response.choices = [Mock()]
        openai_response.choices[0].message = Mock()
        openai_response.choices[0].message.content = "Test AI response"
        openai_mock.chat.completions.create = AsyncMock(return_value=openai_response)
        mocks['openai'] = openai_mock
        
        return mocks
    
    def cleanup_standard_mocks(self):
        """Clean up all standard mocks."""
        for mock_category, mock_dict in self.standard_mocks.items():
            for mock_name, mock_obj in mock_dict.items():
                if hasattr(mock_obj, 'reset_mock'):
                    mock_obj.reset_mock()
        self.standard_mocks.clear()
    
    def stop_all_patches(self):
        """Stop all active patches."""
        for patcher in self.active_patches:
            try:
                patcher.stop()
            except RuntimeError:
                # Patch was already stopped
                pass
        self.active_patches.clear()
    
    def assert_mock_called_with_pattern(self, mock_obj, call_pattern):
        """Assert that mock was called with a specific pattern."""
        mock_obj.assert_called()
        call_args = mock_obj.call_args
        
        if call_args is None:
            self.fail(f"Mock {mock_obj} was not called")
        
        # Check positional args
        if 'args' in call_pattern:
            expected_args = call_pattern['args']
            actual_args = call_args.args
            self.assertEqual(len(actual_args), len(expected_args), 
                           f"Expected {len(expected_args)} args, got {len(actual_args)}")
            for i, (expected, actual) in enumerate(zip(expected_args, actual_args)):
                self.assertEqual(actual, expected, f"Arg {i}: expected {expected}, got {actual}")
        
        # Check keyword args
        if 'kwargs' in call_pattern:
            expected_kwargs = call_pattern['kwargs']
            actual_kwargs = call_args.kwargs
            for key, expected_value in expected_kwargs.items():
                self.assertIn(key, actual_kwargs, f"Expected key '{key}' not found in call arguments")
                self.assertEqual(actual_kwargs[key], expected_value, 
                               f"Expected {key}={expected_value}, got {actual_kwargs[key]}")


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
    """Mixin providing Telegram-specific test utilities with standardized patterns."""
    
    def setup_standard_telegram_objects(self):
        """Set up standard Telegram objects for testing."""
        objects = {}
        
        # Standard user
        objects['user'] = User(
            id=12345,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
            language_code="en"
        )
        
        # Standard private chat
        objects['private_chat'] = Chat(
            id=12345,
            type=Chat.PRIVATE,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
        
        # Standard group chat
        objects['group_chat'] = Chat(
            id=-1001234567890,
            type=Chat.SUPERGROUP,
            title="Test Group",
            description="A test group chat"
        )
        
        return objects
    
    def create_standard_message_mock(self, **overrides):
        """Create a standardized message mock with consistent configuration."""
        defaults = {
            'message_id': 1,
            'text': 'Test message',
            'chat_id': 12345,
            'date': datetime.now(timezone.utc)
        }
        defaults.update(overrides)
        
        message_mock = Mock(spec=Message)
        
        # Configure with defaults and overrides
        for attr, value in defaults.items():
            setattr(message_mock, attr, value)
        
        # Standard async methods
        message_mock.reply_text = AsyncMock()
        message_mock.reply_photo = AsyncMock()
        message_mock.edit_text = AsyncMock()
        message_mock.delete = AsyncMock()
        message_mock.pin = AsyncMock()
        message_mock.unpin = AsyncMock()
        
        # Standard attributes that should always be present
        if not hasattr(message_mock, 'reply_markup'):
            message_mock.reply_markup = None
        if not hasattr(message_mock, 'entities'):
            message_mock.entities = []
        if not hasattr(message_mock, 'photo'):
            message_mock.photo = None
        if not hasattr(message_mock, 'document'):
            message_mock.document = None
        
        return message_mock
    
    def create_standard_callback_query_mock(self, **overrides):
        """Create a standardized callback query mock with consistent configuration."""
        defaults = {
            'id': 'test_callback',
            'data': 'test_data',
            'chat_instance': 'test_chat_instance'
        }
        defaults.update(overrides)
        
        callback_mock = Mock(spec=CallbackQuery)
        
        # Configure with defaults and overrides
        for attr, value in defaults.items():
            setattr(callback_mock, attr, value)
        
        # Standard async methods
        callback_mock.answer = AsyncMock()
        callback_mock.edit_message_text = AsyncMock()
        callback_mock.edit_message_reply_markup = AsyncMock()
        callback_mock.delete_message = AsyncMock()
        
        # Create associated message if not provided
        if not hasattr(callback_mock, 'message') or callback_mock.message is None:
            callback_mock.message = self.create_standard_message_mock(text="Original message")
        
        return callback_mock
    
    def assert_message_sent(self, mock_bot, chat_id: int = None, text: str = None, **expected_kwargs):
        """Assert that a message was sent via the bot with enhanced pattern matching."""
        mock_bot.send_message.assert_called()
        
        call_args = mock_bot.send_message.call_args
        if call_args is None:
            self.fail("send_message was not called")
        
        actual_kwargs = call_args.kwargs
        
        # Check specific parameters
        if chat_id is not None:
            self.assertEqual(actual_kwargs.get('chat_id'), chat_id, 
                           f"Expected chat_id={chat_id}, got {actual_kwargs.get('chat_id')}")
        
        if text is not None:
            actual_text = actual_kwargs.get('text', '')
            self.assertIn(text, actual_text, 
                         f"Expected text '{text}' not found in '{actual_text}'")
        
        # Check additional expected kwargs
        for key, expected_value in expected_kwargs.items():
            self.assertIn(key, actual_kwargs, f"Expected key '{key}' not found in call arguments")
            self.assertEqual(actual_kwargs[key], expected_value, 
                           f"Expected {key}={expected_value}, got {actual_kwargs[key]}")
    
    def assert_callback_answered(self, mock_callback_query, text: str = None, show_alert: bool = None):
        """Assert that a callback query was answered with enhanced checking."""
        mock_callback_query.answer.assert_called()
        
        if text is not None or show_alert is not None:
            call_args = mock_callback_query.answer.call_args
            if call_args is not None:
                actual_kwargs = call_args.kwargs
                
                if text is not None:
                    self.assertEqual(actual_kwargs.get('text'), text)
                
                if show_alert is not None:
                    self.assertEqual(actual_kwargs.get('show_alert'), show_alert)
    
    def assert_message_edited(self, mock_callback_query, text: str = None, **expected_kwargs):
        """Assert that a message was edited with enhanced pattern matching."""
        mock_callback_query.edit_message_text.assert_called()
        
        if text is not None or expected_kwargs:
            call_args = mock_callback_query.edit_message_text.call_args
            if call_args is not None:
                actual_kwargs = call_args.kwargs
                
                if text is not None:
                    actual_text = actual_kwargs.get('text', '')
                    self.assertIn(text, actual_text, 
                                 f"Expected text '{text}' not found in '{actual_text}'")
                
                # Check additional expected kwargs
                for key, expected_value in expected_kwargs.items():
                    self.assertEqual(actual_kwargs.get(key), expected_value, 
                                   f"Expected {key}={expected_value}, got {actual_kwargs.get(key)}")
    
    def assert_telegram_method_called(self, mock_obj, method_name: str, **expected_kwargs):
        """Generic assertion for any Telegram method call."""
        method_mock = getattr(mock_obj, method_name, None)
        if method_mock is None:
            self.fail(f"Method '{method_name}' not found on mock object")
        
        method_mock.assert_called()
        
        if expected_kwargs:
            call_args = method_mock.call_args
            if call_args is not None:
                actual_kwargs = call_args.kwargs
                for key, expected_value in expected_kwargs.items():
                    self.assertEqual(actual_kwargs.get(key), expected_value, 
                                   f"Expected {key}={expected_value}, got {actual_kwargs.get(key)}")


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
# Async Test Pattern Mixins
# ============================================================================

class AsyncTestPatternMixin:
    """Mixin providing standardized async test patterns."""
    
    async def run_async_test_with_timeout(self, coro, timeout=30.0):
        """Run an async test with timeout and proper error handling."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            self.fail(f"Async test timed out after {timeout} seconds")
        except Exception as e:
            self.fail(f"Async test failed: {e}")
    
    async def assert_async_raises(self, exception_class, coro):
        """Assert that an async operation raises a specific exception."""
        with self.assertRaises(exception_class):
            await coro
    
    async def assert_async_no_exception(self, coro):
        """Assert that an async operation completes without raising an exception."""
        try:
            result = await coro
            return result
        except Exception as e:
            self.fail(f"Async operation raised unexpected exception: {e}")
    
    def create_async_context_manager_mock(self, return_value=None):
        """Create a mock async context manager."""
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=return_value)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm
    
    async def wait_for_multiple_async_operations(self, *coroutines, timeout=10.0):
        """Wait for multiple async operations to complete."""
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*coroutines, return_exceptions=True),
                timeout=timeout
            )
            return results
        except asyncio.TimeoutError:
            self.fail(f"Multiple async operations timed out after {timeout} seconds")
    
    def setup_async_mock_chain(self, mock_obj, method_chain, final_return_value=None):
        """Set up a chain of async method calls on a mock object."""
        current_mock = mock_obj
        
        for method_name in method_chain[:-1]:
            next_mock = AsyncMock()
            setattr(current_mock, method_name, next_mock)
            current_mock = next_mock
        
        # Set up the final method in the chain
        final_method = AsyncMock(return_value=final_return_value)
        setattr(current_mock, method_chain[-1], final_method)
        
        return mock_obj
    
    async def assert_async_mock_call_order(self, *async_mocks):
        """Assert that async mocks were called in a specific order."""
        # This is a simplified version - in practice, you might need more sophisticated ordering checks
        for mock in async_mocks:
            mock.assert_called()


class AsyncCoroutineTestMixin:
    """Mixin for testing coroutines and async generators."""
    
    async def assert_coroutine_returns(self, coro, expected_value):
        """Assert that a coroutine returns a specific value."""
        result = await coro
        self.assertEqual(result, expected_value)
    
    async def assert_coroutine_yields(self, async_gen, expected_values):
        """Assert that an async generator yields specific values."""
        actual_values = []
        async for value in async_gen:
            actual_values.append(value)
        
        self.assertEqual(actual_values, expected_values)
    
    def create_async_generator_mock(self, yield_values):
        """Create a mock async generator that yields specific values."""
        async def mock_async_gen():
            for value in yield_values:
                yield value
        
        return mock_async_gen()
    
    async def consume_async_generator(self, async_gen, max_items=None):
        """Consume an async generator and return all yielded values."""
        values = []
        count = 0
        
        async for value in async_gen:
            values.append(value)
            count += 1
            
            if max_items is not None and count >= max_items:
                break
        
        return values


# ============================================================================
# Combined Base Classes
# ============================================================================

class ComprehensiveTestCase(AsyncBaseTestCase, MockTestCase, TelegramTestMixin, 
                          ConfigTestMixin, ErrorTestMixin, AsyncTestPatternMixin):
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