"""
Pytest configuration and shared fixtures for the PsychoChauffeur Bot test suite.
"""

import pytest
import asyncio
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone
import json
import os
from typing import Dict, Any, Optional

# Telegram imports
from telegram import Update, Message, User, Chat, CallbackQuery, Bot
from telegram.ext import CallbackContext, Application

# Local imports
from config.config_manager import ConfigManager
from modules.database import Database
from modules.logger import general_logger, error_logger, chat_logger
from modules.const import KYIV_TZ

# Import base test classes to make them available
from tests.base_test_classes import (
    BaseTestCase, AsyncBaseTestCase, DatabaseTestCase, IntegrationTestCase,
    MockTestCase, ParametrizedTestCase, ComprehensiveTestCase,
    TelegramTestMixin, ConfigTestMixin, ErrorTestMixin
)


# ============================================================================
# Event Loop and Async Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session with performance optimizations."""
    try:
        # Try to get existing loop first
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a new one with optimizations
        policy = asyncio.get_event_loop_policy()
        loop = policy.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Performance optimizations
        if hasattr(loop, 'set_debug'):
            loop.set_debug(False)  # Disable debug mode for performance
    
    yield loop
    
    # Optimized cleanup with timeout
    try:
        # Cancel all pending tasks with timeout
        pending = asyncio.all_tasks(loop)
        if pending:
            for task in pending:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete cancellation with timeout
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=2.0  # Reduced timeout for faster cleanup
                    )
                )
            except asyncio.TimeoutError:
                # Force cleanup if timeout exceeded
                pass
        
        if not loop.is_closed():
            loop.close()
    except Exception:
        pass  # Ignore cleanup errors


class AsyncTestManager:
    """Centralized async test configuration and event loop management with enhanced patterns."""
    
    @staticmethod
    def setup_event_loop():
        """Set up event loop for async tests with proper isolation."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    
    @staticmethod
    def cleanup_event_loop():
        """Clean up event loop after async tests with comprehensive task cancellation."""
        try:
            loop = asyncio.get_running_loop()
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete cancellation with timeout
            if pending:
                try:
                    loop.run_until_complete(
                        asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=5.0
                        )
                    )
                except asyncio.TimeoutError:
                    logging.warning("Some async tasks did not complete cancellation within timeout")
        except RuntimeError:
            pass  # No running loop to clean up
    
    @staticmethod
    async def run_async_test(coro, timeout=30.0):
        """Run an async test with proper error handling and timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logging.error(f"Async test timed out after {timeout} seconds")
            raise
        except Exception as e:
            # Log the error for debugging
            logging.error(f"Async test failed: {e}")
            raise
    
    @staticmethod
    def create_async_mock_with_return(return_value):
        """Create an AsyncMock that returns a specific value."""
        async_mock = AsyncMock()
        async_mock.return_value = return_value
        return async_mock
    
    @staticmethod
    def create_async_mock_with_side_effect(side_effect):
        """Create an AsyncMock with a side effect."""
        async_mock = AsyncMock()
        async_mock.side_effect = side_effect
        return async_mock
    
    @staticmethod
    async def wait_for_async_operations(*awaitables, timeout=5.0):
        """Wait for multiple async operations with timeout."""
        try:
            return await asyncio.wait_for(
                asyncio.gather(*awaitables, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logging.error(f"Async operations timed out after {timeout} seconds")
            raise
    
    @staticmethod
    def assert_async_mock_called_correctly(async_mock, expected_call_count=1, expected_args=None, expected_kwargs=None):
        """Assert that an async mock was called correctly."""
        assert async_mock.call_count == expected_call_count, f"Expected {expected_call_count} calls, got {async_mock.call_count}"
        
        if expected_args is not None or expected_kwargs is not None:
            if expected_args is None:
                expected_args = ()
            if expected_kwargs is None:
                expected_kwargs = {}
            
            async_mock.assert_called_with(*expected_args, **expected_kwargs)


@pytest.fixture
def async_test_manager():
    """Provide access to async test manager."""
    return AsyncTestManager()


@pytest.fixture
async def async_test_environment():
    """Set up and tear down async test environment."""
    # Setup
    loop = AsyncTestManager.setup_event_loop()
    
    yield loop
    
    # Cleanup
    AsyncTestManager.cleanup_event_loop()


@pytest.fixture(autouse=True)
def ensure_event_loop():
    """Automatically ensure event loop is available for all tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    yield loop
    
    # Cleanup
    AsyncTestManager.cleanup_event_loop()


@pytest.fixture
def async_mock_factory():
    """Factory for creating properly configured async mocks."""
    created_mocks = []
    
    def create_mock(return_value=None, side_effect=None, **kwargs):
        if side_effect is not None:
            mock = AsyncMock(side_effect=side_effect, **kwargs)
        else:
            mock = AsyncMock(return_value=return_value, **kwargs)
        created_mocks.append(mock)
        return mock
    
    yield create_mock
    
    # Cleanup - reset all created mocks
    for mock in created_mocks:
        mock.reset_mock()


@pytest.fixture
async def async_database_mock():
    """Provide a mock database with async methods."""
    db_mock = AsyncMock()
    
    # Common database operations
    db_mock.initialize = AsyncMock()
    db_mock.close = AsyncMock()
    db_mock.execute = AsyncMock()
    db_mock.fetch_one = AsyncMock()
    db_mock.fetch_all = AsyncMock()
    db_mock.save_chat_info = AsyncMock()
    db_mock.save_user_info = AsyncMock()
    db_mock.get_message_count = AsyncMock(return_value=0)
    db_mock.get_recent_messages = AsyncMock(return_value=[])
    
    yield db_mock
    
    # Cleanup
    db_mock.reset_mock()


@pytest.fixture
async def async_config_manager_mock():
    """Provide a mock config manager with async methods."""
    config_mock = AsyncMock()
    
    # Common config operations
    config_mock.initialize = AsyncMock()
    config_mock.get_config = AsyncMock(return_value={})
    config_mock.set_config = AsyncMock()
    config_mock.update_config = AsyncMock()
    config_mock.delete_config = AsyncMock()
    config_mock.list_configs = AsyncMock(return_value=[])
    
    yield config_mock
    
    # Cleanup
    config_mock.reset_mock()


# ============================================================================
# Temporary Directory and File System Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_config_dir(temp_dir):
    """Create a temporary configuration directory structure."""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    
    # Create subdirectories
    (config_dir / "global").mkdir()
    (config_dir / "private").mkdir()
    (config_dir / "group").mkdir()
    (config_dir / "backups").mkdir()
    
    return config_dir


@pytest.fixture
def temp_log_dir(temp_dir):
    """Create a temporary log directory structure."""
    log_dir = temp_dir / "logs"
    log_dir.mkdir()
    
    # Create subdirectories
    (log_dir / "analytics").mkdir()
    
    return log_dir


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
async def test_database():
    """Create a test database instance with proper cleanup."""
    # Use in-memory SQLite for testing
    original_db_url = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    try:
        await Database.initialize()
        yield Database
    finally:
        await Database.close()
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        elif 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']


# ============================================================================
# Configuration Manager Fixtures
# ============================================================================

@pytest.fixture
async def test_config_manager(temp_config_dir):
    """Create a test configuration manager with temporary directories."""
    config_manager = ConfigManager()
    
    # Override paths to use temporary directories
    config_manager.base_dir = temp_config_dir.parent
    config_manager.GLOBAL_CONFIG_DIR = temp_config_dir / "global"
    config_manager.PRIVATE_CONFIG_DIR = temp_config_dir / "private"
    config_manager.GROUP_CONFIG_DIR = temp_config_dir / "group"
    config_manager.BACKUP_DIR = temp_config_dir / "backups"
    config_manager.GLOBAL_CONFIG_FILE = config_manager.GLOBAL_CONFIG_DIR / "global_config.json"
    
    await config_manager.initialize()
    return config_manager


@pytest.fixture
def sample_global_config():
    """Sample global configuration for testing."""
    return {
        "chat_metadata": {
            "chat_id": "global",
            "chat_type": "global",
            "chat_name": "Global Configuration",
            "created_at": "2025-07-15T10:00:00",
            "last_updated": "2025-07-15T10:00:00",
            "custom_config_enabled": False
        },
        "config_modules": {
            "gpt": {
                "enabled": True,
                "overrides": {
                    "command": {
                        "max_tokens": 1500,
                        "temperature": 0.6,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "Test system prompt"
                    }
                }
            },
            "chat_behavior": {
                "enabled": True,
                "overrides": {
                    "restrictions_enabled": False,
                    "max_message_length": 2048
                }
            }
        }
    }


# ============================================================================
# Performance-Optimized Session Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def session_mock_bot():
    """Create a session-scoped mock bot for expensive setup operations."""
    bot = Mock(spec=Bot)
    bot.token = "test_token"
    bot.id = 123456789
    bot.username = "test_bot"
    bot.first_name = "Test Bot"
    bot.is_bot = True
    
    # Pre-configure common async methods to avoid repeated setup
    async_methods = [
        'get_me', 'send_message', 'send_photo', 'send_document', 'edit_message_text',
        'delete_message', 'answer_callback_query', 'set_my_commands'
    ]
    
    for method_name in async_methods:
        setattr(bot, method_name, AsyncMock())
    
    return bot


@pytest.fixture(scope="session")
def session_test_config():
    """Create a session-scoped test configuration to avoid repeated setup."""
    return {
        "test_mode": True,
        "database_url": "sqlite:///:memory:",
        "log_level": "ERROR",  # Reduce logging overhead in tests
        "timeout_settings": {
            "default": 5.0,
            "network": 2.0,
            "database": 1.0
        }
    }


# ============================================================================
# Telegram Mock Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_bot(session_mock_bot):
    """Create a mock Telegram Bot instance with optimized setup using session fixture."""
    # Create a fresh mock based on the session fixture to avoid cross-test contamination
    bot = Mock(spec=Bot)
    
    # Copy basic attributes from session fixture
    bot.token = session_mock_bot.token
    bot.id = session_mock_bot.id
    bot.username = session_mock_bot.username
    bot.first_name = session_mock_bot.first_name
    bot.is_bot = session_mock_bot.is_bot
    bot.can_join_groups = True
    bot.can_read_all_group_messages = True
    bot.supports_inline_queries = False
    
    # Only configure commonly used async methods to reduce setup overhead
    essential_methods = {
        'get_me': AsyncMock(return_value=Mock(
            id=bot.id,
            username=bot.username,
            first_name=bot.first_name,
            is_bot=bot.is_bot
        )),
        'send_message': AsyncMock(),
        'send_photo': AsyncMock(),
        'send_document': AsyncMock(),
        'edit_message_text': AsyncMock(),
        'delete_message': AsyncMock(),
        'answer_callback_query': AsyncMock(),
        'set_my_commands': AsyncMock(),
        'get_chat': AsyncMock(),
        'get_chat_member': AsyncMock(),
        'send_chat_action': AsyncMock()
    }
    
    # Configure essential methods
    for method_name, mock_method in essential_methods.items():
        setattr(bot, method_name, mock_method)
    
    # Use __getattr__ to lazily create other methods when accessed
    def lazy_async_mock(name):
        if not hasattr(bot, name):
            setattr(bot, name, AsyncMock())
        return getattr(bot, name)
    
    bot.__getattr__ = lazy_async_mock
    
    return bot


@pytest.fixture(scope="function")
def mock_user():
    """Create a mock Telegram User with function scope for proper isolation."""
    return User(
        id=12345,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="en"
    )


@pytest.fixture(scope="function")
def mock_private_chat():
    """Create a mock private Telegram Chat with function scope for proper isolation."""
    return Chat(
        id=12345,
        type=Chat.PRIVATE,
        username="testuser",
        first_name="Test",
        last_name="User"
    )


@pytest.fixture(scope="function")
def mock_group_chat():
    """Create a mock group Telegram Chat with function scope for proper isolation."""
    return Chat(
        id=-1001234567890,
        type=Chat.SUPERGROUP,
        title="Test Group",
        description="A test group chat"
    )


@pytest.fixture(scope="function")
def mock_message(mock_user, mock_private_chat):
    """Create a mock Telegram Message with proper attribute configuration and function scope for isolation."""
    message = Mock(spec=Message)
    
    # Core message attributes - ensure all required attributes are set
    message.message_id = 1
    message.date = datetime.now(timezone.utc)
    message.chat = mock_private_chat
    message.from_user = mock_user
    message.text = "Test message"
    message.chat_id = mock_private_chat.id
    message.id = 1  # Alias for message_id
    
    # Ensure message can be modified by tests without affecting other tests
    message.configure_mock = Mock(side_effect=lambda **kwargs: setattr(message, list(kwargs.keys())[0], list(kwargs.values())[0]) if kwargs else None)
    
    # Message content attributes
    message.reply_markup = None
    message.entities = []
    message.caption = None
    message.caption_entities = []
    message.photo = None
    message.document = None
    message.video = None
    message.audio = None
    message.voice = None
    message.sticker = None
    message.animation = None
    message.contact = None
    message.location = None
    message.venue = None
    message.poll = None
    message.dice = None
    message.game = None
    message.invoice = None
    message.successful_payment = None
    message.passport_data = None
    message.web_app_data = None
    
    # Message metadata
    message.edit_date = None
    message.media_group_id = None
    message.author_signature = None
    message.forward_from = None
    message.forward_from_chat = None
    message.forward_from_message_id = None
    message.forward_signature = None
    message.forward_sender_name = None
    message.forward_date = None
    message.is_automatic_forward = False
    message.reply_to_message = None
    message.via_bot = None
    message.sender_chat = None
    message.is_topic_message = False
    message.message_thread_id = None
    message.has_protected_content = False
    message.has_media_spoiler = False
    
    # Group/channel specific attributes
    message.new_chat_members = []
    message.left_chat_member = None
    message.new_chat_title = None
    message.new_chat_photo = []
    message.delete_chat_photo = False
    message.group_chat_created = False
    message.supergroup_chat_created = False
    message.channel_chat_created = False
    message.migrate_to_chat_id = None
    message.migrate_from_chat_id = None
    message.pinned_message = None
    
    # Forum topic attributes
    message.forum_topic_created = None
    message.forum_topic_edited = None
    message.forum_topic_closed = None
    message.forum_topic_reopened = None
    message.general_forum_topic_hidden = None
    message.general_forum_topic_unhidden = None
    
    # Video chat attributes
    message.video_chat_scheduled = None
    message.video_chat_started = None
    message.video_chat_ended = None
    message.video_chat_participants_invited = None
    
    # Other attributes
    message.connected_website = None
    message.write_access_allowed = None
    message.proximity_alert_triggered = None
    message.chat_shared = None
    message.user_shared = None
    message.story = None
    message.message_auto_delete_timer_changed = None
    
    # Async methods
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    message.reply_document = AsyncMock()
    message.reply_audio = AsyncMock()
    message.reply_video = AsyncMock()
    message.reply_voice = AsyncMock()
    message.reply_sticker = AsyncMock()
    message.reply_animation = AsyncMock()
    message.reply_contact = AsyncMock()
    message.reply_location = AsyncMock()
    message.reply_venue = AsyncMock()
    message.reply_poll = AsyncMock()
    message.reply_dice = AsyncMock()
    message.reply_game = AsyncMock()
    message.reply_invoice = AsyncMock()
    message.reply_media_group = AsyncMock()
    message.reply_html = AsyncMock()
    message.reply_markdown = AsyncMock()
    message.reply_markdown_v2 = AsyncMock()
    message.reply_copy = AsyncMock()
    message.reply_chat_action = AsyncMock()
    
    message.edit_text = AsyncMock()
    message.edit_caption = AsyncMock()
    message.edit_media = AsyncMock()
    message.edit_reply_markup = AsyncMock()
    message.edit_live_location = AsyncMock()
    message.stop_live_location = AsyncMock()
    
    message.delete = AsyncMock()
    message.forward = AsyncMock()
    message.copy = AsyncMock()
    message.pin = AsyncMock()
    message.unpin = AsyncMock()
    message.stop_poll = AsyncMock()
    
    # Properties that return formatted text
    message.text_html = message.text
    message.text_markdown = message.text
    message.text_markdown_v2 = message.text
    message.caption_html = message.caption
    message.caption_markdown = message.caption
    message.caption_markdown_v2 = message.caption
    
    # Utility methods
    message.parse_entities = Mock(return_value={})
    message.parse_entity = Mock(return_value="")
    message.parse_caption_entities = Mock(return_value={})
    message.parse_caption_entity = Mock(return_value="")
    
    # Link property
    message.link = f"https://t.me/c/{abs(mock_private_chat.id)}/{message.message_id}"
    
    return message


@pytest.fixture(scope="function")
def mock_update(mock_message):
    """Create a mock Telegram Update."""
    return Update(
        update_id=1,
        message=mock_message
    )


@pytest.fixture(scope="function")
def mock_callback_query(mock_user, mock_private_chat):
    """Create a mock Telegram CallbackQuery with proper attribute configuration and function scope for isolation."""
    # Create mock message for the callback query using the same pattern as mock_message
    message = Mock(spec=Message)
    message.message_id = 1
    message.date = datetime.now(timezone.utc)
    message.chat = mock_private_chat
    message.from_user = mock_user
    message.text = "Original message"
    message.chat_id = mock_private_chat.id
    message.id = 1
    
    # Ensure message can be modified by tests without affecting other tests
    message.configure_mock = Mock(side_effect=lambda **kwargs: setattr(message, list(kwargs.keys())[0], list(kwargs.values())[0]) if kwargs else None)
    
    # Essential message attributes for callback queries
    message.reply_markup = None
    message.entities = []
    message.caption = None
    message.photo = None
    message.document = None
    message.video = None
    message.audio = None
    message.voice = None
    message.sticker = None
    
    # Message methods
    message.reply_text = AsyncMock()
    message.edit_text = AsyncMock()
    message.edit_caption = AsyncMock()
    message.edit_media = AsyncMock()
    message.edit_reply_markup = AsyncMock()
    message.delete = AsyncMock()
    message.pin = AsyncMock()
    message.unpin = AsyncMock()
    
    # Create mock callback query
    callback_query = Mock(spec=CallbackQuery)
    callback_query.id = "test_callback_query"
    callback_query.from_user = mock_user
    callback_query.chat_instance = "test_chat_instance"
    callback_query.message = message
    callback_query.data = "test_callback_data"
    callback_query.inline_message_id = None
    callback_query.game_short_name = None
    
    # CallbackQuery methods
    callback_query.answer = AsyncMock()
    callback_query.edit_message_text = AsyncMock()
    callback_query.edit_message_reply_markup = AsyncMock()
    callback_query.edit_message_caption = AsyncMock()
    callback_query.edit_message_media = AsyncMock()
    callback_query.edit_message_live_location = AsyncMock()
    callback_query.stop_message_live_location = AsyncMock()
    callback_query.delete_message = AsyncMock()
    callback_query.copy_message = AsyncMock()
    callback_query.pin_message = AsyncMock()
    callback_query.unpin_message = AsyncMock()
    callback_query.set_game_score = AsyncMock()
    callback_query.get_game_high_scores = AsyncMock()
    
    # Utility methods
    callback_query.to_dict = Mock(return_value={
        'id': callback_query.id,
        'from': mock_user.to_dict(),
        'chat_instance': callback_query.chat_instance,
        'data': callback_query.data
    })
    callback_query.to_json = Mock(return_value='{"id": "test_callback_query"}')
    
    return callback_query


@pytest.fixture
def mock_context(mock_bot):
    """Create a mock CallbackContext."""
    context = Mock(spec=CallbackContext)
    context.bot = mock_bot
    context.args = []
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    return context


@pytest.fixture
def mock_application(mock_bot):
    """Create a mock Telegram Application."""
    app = Mock(spec=Application)
    app.bot = mock_bot
    app.add_handler = Mock()
    app.run_polling = AsyncMock()
    return app


# ============================================================================
# Mock Object Factories for Better Test Isolation
# ============================================================================

class MockTelegramObjectFactory:
    """Factory for creating properly configured Telegram mock objects."""
    
    @staticmethod
    def create_message(
        message_id: int = 1,
        text: str = "Test message",
        user_id: int = 12345,
        chat_id: int = 12345,
        chat_type: str = "private",
        **kwargs
    ) -> Mock:
        """Create a mock Message with proper attribute configuration."""
        # Create user and chat
        user = User(
            id=user_id,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
            language_code="en"
        )
        
        if chat_type == "private":
            chat = Chat(
                id=chat_id,
                type=Chat.PRIVATE,
                username="testuser",
                first_name="Test",
                last_name="User"
            )
        else:
            chat = Chat(
                id=chat_id,
                type=Chat.SUPERGROUP,
                title="Test Group",
                description="A test group chat"
            )
        
        message = Mock(spec=Message)
        
        # Core attributes
        message.message_id = message_id
        message.date = datetime.now(timezone.utc)
        message.chat = chat
        message.from_user = user
        message.text = text
        message.chat_id = chat.id
        message.id = message_id
        
        # Apply any additional kwargs
        for key, value in kwargs.items():
            setattr(message, key, value)
        
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
        
        for attr, default_value in default_attrs.items():
            if not hasattr(message, attr):
                setattr(message, attr, default_value)
        
        # Async methods
        message.reply_text = AsyncMock()
        message.reply_photo = AsyncMock()
        message.reply_document = AsyncMock()
        message.edit_text = AsyncMock()
        message.delete = AsyncMock()
        message.pin = AsyncMock()
        message.unpin = AsyncMock()
        
        return message
    
    @staticmethod
    def create_callback_query(
        callback_id: str = "test_callback",
        data: str = "test_data",
        user_id: int = 12345,
        chat_id: int = 12345,
        **kwargs
    ) -> Mock:
        """Create a mock CallbackQuery with proper attribute configuration."""
        # Create associated message
        message = MockTelegramObjectFactory.create_message(
            user_id=user_id,
            chat_id=chat_id,
            text="Original message"
        )
        
        callback_query = Mock(spec=CallbackQuery)
        callback_query.id = callback_id
        callback_query.from_user = message.from_user
        callback_query.chat_instance = "test_chat_instance"
        callback_query.message = message
        callback_query.data = data
        callback_query.inline_message_id = None
        callback_query.game_short_name = None
        
        # Apply any additional kwargs
        for key, value in kwargs.items():
            setattr(callback_query, key, value)
        
        # CallbackQuery methods
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        callback_query.edit_message_reply_markup = AsyncMock()
        callback_query.delete_message = AsyncMock()
        
        return callback_query


@pytest.fixture
def mock_telegram_factory():
    """Provide access to Telegram mock object factory."""
    return MockTelegramObjectFactory()


# ============================================================================
# External Service Mock Factories
# ============================================================================

class MockExternalServices:
    """Factory for creating mocks of external services."""
    
    @staticmethod
    def create_openai_mock():
        """Create a mock OpenAI client."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test AI response"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        return mock_client
    
    @staticmethod
    def create_weather_api_mock():
        """Create a mock weather API client."""
        mock_client = Mock()
        mock_client.get_current_weather = AsyncMock(return_value={
            "temperature": 20.5,
            "description": "Clear sky",
            "humidity": 65,
            "wind_speed": 3.2
        })
        return mock_client
    
    @staticmethod
    def create_video_downloader_mock():
        """Create a mock video downloader."""
        mock_downloader = Mock()
        mock_downloader.download = AsyncMock(return_value={
            "success": True,
            "file_path": "/tmp/test_video.mp4",
            "title": "Test Video",
            "duration": 120
        })
        return mock_downloader


@pytest.fixture
def mock_external_services():
    """Provide access to external service mocks."""
    return MockExternalServices()


# ============================================================================
# Test Data Factories
# ============================================================================

class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_reminder_data():
        """Create test reminder data."""
        return {
            "task": "Test reminder",
            "frequency": "daily",
            "delay": 3600,  # 1 hour
            "date_modifier": None,
            "next_execution": datetime.now(KYIV_TZ),
            "user_id": 12345,
            "chat_id": 12345,
            "user_mention_md": "@testuser"
        }
    
    @staticmethod
    def create_error_data():
        """Create test error data."""
        return {
            "message": "Test error message",
            "severity": "medium",
            "category": "general",
            "context": {"test_key": "test_value"},
            "timestamp": datetime.now(KYIV_TZ)
        }
    
    @staticmethod
    def create_chat_config_data():
        """Create test chat configuration data."""
        return {
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


@pytest.fixture
def test_data_factory():
    """Provide access to test data factory."""
    return TestDataFactory()


# ============================================================================
# Standardized Mock Usage Patterns
# ============================================================================

class StandardMockPatterns:
    """Standardized patterns for mock setup and teardown."""
    
    @staticmethod
    def setup_telegram_mocks():
        """Set up standard Telegram API mocks with consistent patterns."""
        mocks = {}
        
        # Bot mock with all essential methods
        bot_mock = Mock(spec=Bot)
        bot_mock.token = "test_token"
        bot_mock.id = 123456789
        bot_mock.username = "test_bot"
        bot_mock.first_name = "Test Bot"
        bot_mock.is_bot = True
        
        # Essential async methods
        essential_methods = [
            'get_me', 'send_message', 'send_photo', 'send_document', 'send_audio',
            'send_video', 'send_voice', 'send_sticker', 'send_animation', 'send_location',
            'send_contact', 'send_poll', 'send_dice', 'send_chat_action', 'send_media_group',
            'edit_message_text', 'edit_message_caption', 'edit_message_media', 
            'edit_message_reply_markup', 'delete_message', 'forward_message', 'copy_message',
            'pin_chat_message', 'unpin_chat_message', 'get_file', 'get_chat', 
            'get_chat_member', 'answer_callback_query'
        ]
        
        for method_name in essential_methods:
            setattr(bot_mock, method_name, AsyncMock())
        
        # Special return values for common methods
        bot_mock.get_me.return_value = Mock(
            id=bot_mock.id,
            username=bot_mock.username,
            first_name=bot_mock.first_name,
            is_bot=bot_mock.is_bot
        )
        
        mocks['bot'] = bot_mock
        
        # Application mock
        app_mock = Mock(spec=Application)
        app_mock.bot = bot_mock
        app_mock.add_handler = Mock()
        app_mock.run_polling = AsyncMock()
        app_mock.stop = AsyncMock()
        mocks['application'] = app_mock
        
        return mocks
    
    @staticmethod
    def setup_external_service_mocks():
        """Set up standard external service mocks."""
        mocks = {}
        
        # OpenAI mock
        openai_mock = Mock()
        openai_response = Mock()
        openai_response.choices = [Mock()]
        openai_response.choices[0].message = Mock()
        openai_response.choices[0].message.content = "Test AI response"
        openai_mock.chat.completions.create = AsyncMock(return_value=openai_response)
        mocks['openai'] = openai_mock
        
        # Weather API mock
        weather_mock = Mock()
        weather_mock.get_current_weather = AsyncMock(return_value={
            "temperature": 20.5,
            "description": "Clear sky",
            "humidity": 65,
            "wind_speed": 3.2
        })
        mocks['weather'] = weather_mock
        
        # Video downloader mock
        video_mock = Mock()
        video_mock.download = AsyncMock(return_value={
            "success": True,
            "file_path": "/tmp/test_video.mp4",
            "title": "Test Video",
            "duration": 120
        })
        mocks['video_downloader'] = video_mock
        
        return mocks
    
    @staticmethod
    def cleanup_mocks(mock_dict):
        """Clean up mocks with standard teardown pattern."""
        for mock_name, mock_obj in mock_dict.items():
            if hasattr(mock_obj, 'reset_mock'):
                mock_obj.reset_mock()
            elif hasattr(mock_obj, 'stop'):
                try:
                    mock_obj.stop()
                except (RuntimeError, AttributeError):
                    pass  # Mock was already stopped or doesn't support stopping
    
    @staticmethod
    def configure_telegram_message_mock(message_mock, **overrides):
        """Configure a Telegram message mock with standard attributes."""
        # Standard configuration
        standard_config = {
            'message_id': 1,
            'text': 'Test message',
            'chat_id': 12345,
            'from_user': Mock(id=12345, first_name='Test', username='testuser'),
            'date': datetime.now(timezone.utc),
            'reply_markup': None,
            'entities': [],
            'photo': None,
            'document': None,
            'video': None,
            'audio': None,
            'voice': None,
            'sticker': None
        }
        
        # Apply overrides
        standard_config.update(overrides)
        
        # Configure the mock
        for attr, value in standard_config.items():
            setattr(message_mock, attr, value)
        
        # Ensure essential methods are available
        essential_methods = [
            'reply_text', 'reply_photo', 'reply_document', 'edit_text', 
            'delete', 'pin', 'unpin', 'forward', 'copy'
        ]
        
        for method_name in essential_methods:
            if not hasattr(message_mock, method_name):
                setattr(message_mock, method_name, AsyncMock())
        
        return message_mock
    
    @staticmethod
    def configure_callback_query_mock(callback_mock, **overrides):
        """Configure a CallbackQuery mock with standard attributes."""
        # Standard configuration
        standard_config = {
            'id': 'test_callback',
            'data': 'test_data',
            'chat_instance': 'test_chat_instance',
            'from_user': Mock(id=12345, first_name='Test', username='testuser'),
            'inline_message_id': None,
            'game_short_name': None
        }
        
        # Apply overrides
        standard_config.update(overrides)
        
        # Configure the mock
        for attr, value in standard_config.items():
            setattr(callback_mock, attr, value)
        
        # Ensure essential methods are available
        essential_methods = [
            'answer', 'edit_message_text', 'edit_message_reply_markup',
            'delete_message', 'copy_message'
        ]
        
        for method_name in essential_methods:
            if not hasattr(callback_mock, method_name):
                setattr(callback_mock, method_name, AsyncMock())
        
        return callback_mock


@pytest.fixture
def standard_mocks():
    """Provide access to standardized mock patterns."""
    return StandardMockPatterns()


@pytest.fixture
def telegram_mocks():
    """Provide pre-configured Telegram mocks."""
    mocks = StandardMockPatterns.setup_telegram_mocks()
    yield mocks
    StandardMockPatterns.cleanup_mocks(mocks)


@pytest.fixture
def external_service_mocks():
    """Provide pre-configured external service mocks."""
    mocks = StandardMockPatterns.setup_external_service_mocks()
    yield mocks
    StandardMockPatterns.cleanup_mocks(mocks)


# ============================================================================
# Test Utilities
# ============================================================================

class TestHelpers:
    """Helper utilities for tests."""
    
    @staticmethod
    async def create_test_file(path: Path, content: str = "test content"):
        """Create a test file with specified content."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path
    
    @staticmethod
    async def create_test_json_file(path: Path, data: Dict[str, Any]):
        """Create a test JSON file with specified data."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return path
    
    @staticmethod
    def assert_dict_contains(actual: Dict[str, Any], expected: Dict[str, Any]):
        """Assert that actual dictionary contains all key-value pairs from expected."""
        for key, value in expected.items():
            assert key in actual, f"Key '{key}' not found in actual dictionary"
            if isinstance(value, dict) and isinstance(actual[key], dict):
                TestHelpers.assert_dict_contains(actual[key], value)
            else:
                assert actual[key] == value, f"Value mismatch for key '{key}': expected {value}, got {actual[key]}"
    
    @staticmethod
    async def wait_for_async_operation(coro, timeout: float = 5.0):
        """Wait for an async operation with timeout."""
        return await asyncio.wait_for(coro, timeout=timeout)


@pytest.fixture
def test_helpers():
    """Provide access to test helper utilities."""
    return TestHelpers()


# ============================================================================
# Environment and Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables and cleanup."""
    # Set test environment variables
    test_env_vars = {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'OPENAI_API_KEY': 'test_openai_key',
        'OPENWEATHER_API_KEY': 'test_weather_key',
        'DATABASE_URL': 'sqlite:///:memory:',
        'ERROR_CHANNEL_ID': 'test_error_channel'
    }
    
    for key, value in test_env_vars.items():
        monkeypatch.setenv(key, value)
    
    yield
    
    # Cleanup is handled automatically by monkeypatch


@pytest.fixture
def isolated_test():
    """Ensure test isolation by clearing global state."""
    # Store original state
    original_state = {}
    
    yield
    
    # Restore original state if needed
    # This can be expanded based on specific global state that needs cleanup


# ============================================================================
# Performance and Timing Fixtures
# ============================================================================

@pytest.fixture
def performance_timer():
    """Provide a simple performance timer for tests."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.perf_counter()
        
        def stop(self):
            self.end_time = time.perf_counter()
        
        @property
        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time
    
    return Timer()


# ============================================================================
# Logging Test Fixtures
# ============================================================================

@pytest.fixture
def capture_logs(caplog):
    """Capture logs for testing."""
    with caplog.at_level(logging.INFO):
        yield caplog


# ============================================================================
# Parametrized Test Data
# ============================================================================

@pytest.fixture(params=[
    {"chat_type": "private", "chat_id": "12345"},
    {"chat_type": "group", "chat_id": "-1001234567890"},
    {"chat_type": "supergroup", "chat_id": "-1001234567891"}
])
def chat_types(request):
    """Parametrized fixture for different chat types."""
    return request.param


@pytest.fixture(params=[
    {"severity": "low", "category": "general"},
    {"severity": "medium", "category": "network"},
    {"severity": "high", "category": "database"},
    {"severity": "critical", "category": "api"}
])
def error_types(request):
    """Parametrized fixture for different error types."""
    return request.param