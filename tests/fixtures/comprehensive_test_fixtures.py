"""
Comprehensive test fixtures for isolated testing of all components.
Provides reusable fixtures for unit and integration tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from telegram import Update, Message, User, Chat, CallbackQuery, Voice, VideoNote, Sticker, Location
from telegram.ext import CallbackContext

from modules.service_registry import ServiceRegistry
from modules.message_handler_service import MessageHandlerService
from modules.speech_recognition_service import SpeechRecognitionService
from modules.callback_handler_service import CallbackHandlerService
from modules.command_registry import CommandRegistry
from modules.command_processor import CommandProcessor
from modules.bot_application import BotApplication
from modules.application_bootstrapper import ApplicationBootstrapper
from config.config_manager import ConfigManager


class MockTelegramObjects:
    """Factory for creating mock Telegram objects."""
    
    @staticmethod
    def create_user(user_id=12345, first_name="Test", username="testuser", is_bot=False):
        """Create a mock User object."""
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = first_name
        user.username = username
        user.is_bot = is_bot
        user.language_code = "en"
        return user
    
    @staticmethod
    def create_chat(chat_id=67890, chat_type="private", title=None):
        """Create a mock Chat object."""
        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.type = chat_type
        chat.title = title
        return chat
    
    @staticmethod
    def create_message(text=None, user=None, chat=None, message_id=1, **kwargs):
        """Create a mock Message object."""
        if user is None:
            user = MockTelegramObjects.create_user()
        if chat is None:
            chat = MockTelegramObjects.create_chat()
        
        message = Mock(spec=Message)
        message.message_id = message_id
        message.text = text
        message.from_user = user
        message.chat = chat
        message.date = Mock()
        
        # Add optional attributes
        for attr, value in kwargs.items():
            setattr(message, attr, value)
        
        return message
    
    @staticmethod
    def create_voice_message(file_id="voice_123", duration=10, user=None, chat=None):
        """Create a mock voice message."""
        voice = Mock(spec=Voice)
        voice.file_id = file_id
        voice.duration = duration
        voice.mime_type = "audio/ogg"
        
        message = MockTelegramObjects.create_message(user=user, chat=chat)
        message.voice = voice
        message.text = None
        
        return message
    
    @staticmethod
    def create_video_note_message(file_id="video_note_123", duration=15, user=None, chat=None):
        """Create a mock video note message."""
        video_note = Mock(spec=VideoNote)
        video_note.file_id = file_id
        video_note.duration = duration
        video_note.length = 240
        
        message = MockTelegramObjects.create_message(user=user, chat=chat)
        message.video_note = video_note
        message.text = None
        
        return message
    
    @staticmethod
    def create_sticker_message(file_id="sticker_123", user=None, chat=None):
        """Create a mock sticker message."""
        sticker = Mock(spec=Sticker)
        sticker.file_id = file_id
        sticker.width = 512
        sticker.height = 512
        
        message = MockTelegramObjects.create_message(user=user, chat=chat)
        message.sticker = sticker
        message.text = None
        
        return message
    
    @staticmethod
    def create_location_message(latitude=40.7128, longitude=-74.0060, user=None, chat=None):
        """Create a mock location message."""
        location = Mock(spec=Location)
        location.latitude = latitude
        location.longitude = longitude
        
        message = MockTelegramObjects.create_message(user=user, chat=chat)
        message.location = location
        message.text = None
        
        return message
    
    @staticmethod
    def create_update(message=None, callback_query=None, update_id=1):
        """Create a mock Update object."""
        update = Mock(spec=Update)
        update.update_id = update_id
        update.message = message
        update.callback_query = callback_query
        
        if message:
            update.effective_user = message.from_user
            update.effective_chat = message.chat
        elif callback_query:
            update.effective_user = callback_query.from_user
            update.effective_chat = getattr(callback_query, 'message', Mock()).chat if hasattr(callback_query, 'message') else None
        
        return update
    
    @staticmethod
    def create_callback_query(data="test_callback", user=None, message=None):
        """Create a mock CallbackQuery object."""
        if user is None:
            user = MockTelegramObjects.create_user()
        
        callback_query = Mock(spec=CallbackQuery)
        callback_query.id = "callback_123"
        callback_query.data = data
        callback_query.from_user = user
        callback_query.message = message
        callback_query.answer = AsyncMock()
        
        return callback_query
    
    @staticmethod
    def create_context(bot=None):
        """Create a mock CallbackContext object."""
        if bot is None:
            bot = AsyncMock()
            bot.send_message = AsyncMock()
            bot.edit_message_text = AsyncMock()
            bot.answer_callback_query = AsyncMock()
        
        context = Mock(spec=CallbackContext)
        context.bot = bot
        context.user_data = {}
        context.chat_data = {}
        context.bot_data = {}
        
        return context


class MockServices:
    """Factory for creating mock service objects."""
    
    @staticmethod
    def create_config_manager(default_config=None):
        """Create a mock ConfigManager."""
        if default_config is None:
            default_config = {
                'gpt': {'enabled': True, 'random_response_chance': 0.1},
                'speech': {'enabled': True, 'default_language': 'en'},
                'commands': {'enabled': True},
                'url_processing': {'enabled': True}
            }
        
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config = AsyncMock(return_value=default_config)
        config_manager.save_config = AsyncMock()
        config_manager.initialize = AsyncMock()
        config_manager.ensure_dirs = Mock()
        
        return config_manager
    
    @staticmethod
    def create_gpt_service():
        """Create a mock GPT service."""
        gpt_service = Mock()
        gpt_service.should_respond_randomly = AsyncMock(return_value=False)
        gpt_service.process_message = AsyncMock(return_value="GPT response")
        gpt_service.is_enabled = Mock(return_value=True)
        
        return gpt_service
    
    @staticmethod
    def create_command_processor():
        """Create a mock CommandProcessor."""
        processor = Mock(spec=CommandProcessor)
        processor.process_command = AsyncMock(return_value=True)
        processor.register_command = Mock()
        processor.get_commands = Mock(return_value=[])
        
        return processor
    
    @staticmethod
    def create_service_registry():
        """Create a mock ServiceRegistry."""
        registry = Mock(spec=ServiceRegistry)
        registry.register_service = Mock()
        registry.get_service = Mock()
        registry.initialize_all_services = AsyncMock()
        registry.shutdown_all_services = AsyncMock()
        registry.is_service_registered = Mock(return_value=True)
        
        return registry
    
    @staticmethod
    def create_bot_application():
        """Create a mock BotApplication."""
        app = Mock(spec=BotApplication)
        app.initialize = AsyncMock()
        app.start = AsyncMock()
        app.shutdown = AsyncMock()
        app.is_running = False
        app.telegram_app = Mock()
        app.telegram_bot = Mock()
        
        return app


@pytest.fixture
def mock_user():
    """Fixture for a mock User object."""
    return MockTelegramObjects.create_user()


@pytest.fixture
def mock_chat():
    """Fixture for a mock Chat object."""
    return MockTelegramObjects.create_chat()


@pytest.fixture
def mock_private_chat():
    """Fixture for a mock private Chat object."""
    return MockTelegramObjects.create_chat(chat_type="private")


@pytest.fixture
def mock_group_chat():
    """Fixture for a mock group Chat object."""
    return MockTelegramObjects.create_chat(chat_id=98765, chat_type="group", title="Test Group")


@pytest.fixture
def mock_text_message(mock_user, mock_chat):
    """Fixture for a mock text Message object."""
    return MockTelegramObjects.create_message("Test message", mock_user, mock_chat)


@pytest.fixture
def mock_voice_message(mock_user, mock_chat):
    """Fixture for a mock voice Message object."""
    return MockTelegramObjects.create_voice_message(user=mock_user, chat=mock_chat)


@pytest.fixture
def mock_video_note_message(mock_user, mock_chat):
    """Fixture for a mock video note Message object."""
    return MockTelegramObjects.create_video_note_message(user=mock_user, chat=mock_chat)


@pytest.fixture
def mock_sticker_message(mock_user, mock_chat):
    """Fixture for a mock sticker Message object."""
    return MockTelegramObjects.create_sticker_message(user=mock_user, chat=mock_chat)


@pytest.fixture
def mock_location_message(mock_user, mock_chat):
    """Fixture for a mock location Message object."""
    return MockTelegramObjects.create_location_message(user=mock_user, chat=mock_chat)


@pytest.fixture
def mock_text_update(mock_text_message):
    """Fixture for a mock text Update object."""
    return MockTelegramObjects.create_update(message=mock_text_message)


@pytest.fixture
def mock_voice_update(mock_voice_message):
    """Fixture for a mock voice Update object."""
    return MockTelegramObjects.create_update(message=mock_voice_message)


@pytest.fixture
def mock_callback_query(mock_user):
    """Fixture for a mock CallbackQuery object."""
    return MockTelegramObjects.create_callback_query(user=mock_user)


@pytest.fixture
def mock_callback_update(mock_callback_query):
    """Fixture for a mock callback Update object."""
    return MockTelegramObjects.create_update(callback_query=mock_callback_query)


@pytest.fixture
def mock_context():
    """Fixture for a mock CallbackContext object."""
    return MockTelegramObjects.create_context()


@pytest.fixture
def mock_config_manager():
    """Fixture for a mock ConfigManager."""
    return MockServices.create_config_manager()


@pytest.fixture
def mock_gpt_service():
    """Fixture for a mock GPT service."""
    return MockServices.create_gpt_service()


@pytest.fixture
def mock_command_processor():
    """Fixture for a mock CommandProcessor."""
    return MockServices.create_command_processor()


@pytest.fixture
def mock_service_registry():
    """Fixture for a mock ServiceRegistry."""
    return MockServices.create_service_registry()


@pytest.fixture
def mock_bot_application():
    """Fixture for a mock BotApplication."""
    return MockServices.create_bot_application()


@pytest.fixture
async def message_handler_service(mock_config_manager, mock_gpt_service):
    """Fixture for MessageHandlerService with mocked dependencies."""
    return MessageHandlerService(
        config_manager=mock_config_manager,
        gpt_service=mock_gpt_service
    )


@pytest.fixture
async def speech_recognition_service(mock_config_manager):
    """Fixture for SpeechRecognitionService with mocked dependencies."""
    return SpeechRecognitionService(config_manager=mock_config_manager)


@pytest.fixture
async def callback_handler_service(speech_recognition_service):
    """Fixture for CallbackHandlerService with mocked dependencies."""
    return CallbackHandlerService(speech_service=speech_recognition_service)


@pytest.fixture
async def command_registry(mock_command_processor):
    """Fixture for CommandRegistry with mocked dependencies."""
    return CommandRegistry(command_processor=mock_command_processor)


@pytest.fixture
async def application_bootstrapper():
    """Fixture for ApplicationBootstrapper."""
    return ApplicationBootstrapper()


@pytest.fixture
async def integrated_service_registry():
    """Fixture for a service registry with all services registered."""
    registry = ServiceRegistry()
    
    # Register mock services
    config_manager = MockServices.create_config_manager()
    gpt_service = MockServices.create_gpt_service()
    command_processor = MockServices.create_command_processor()
    
    registry.register_service('config_manager', config_manager)
    registry.register_service('gpt_service', gpt_service)
    registry.register_service('command_processor', command_processor)
    
    # Create and register specialized services
    message_service = MessageHandlerService(
        config_manager=config_manager,
        gpt_service=gpt_service
    )
    registry.register_service('message_handler_service', message_service)
    
    speech_service = SpeechRecognitionService(config_manager=config_manager)
    registry.register_service('speech_recognition_service', speech_service)
    
    callback_service = CallbackHandlerService(speech_service=speech_service)
    registry.register_service('callback_handler_service', callback_service)
    
    command_registry = CommandRegistry(command_processor=command_processor)
    registry.register_service('command_registry', command_registry)
    
    return registry


@pytest.fixture
def sample_configurations():
    """Fixture providing various configuration samples for testing."""
    return {
        'minimal': {
            'gpt': {'enabled': True},
            'speech': {'enabled': True},
            'commands': {'enabled': True}
        },
        'full': {
            'gpt': {
                'enabled': True,
                'random_response_chance': 0.15,
                'model': 'gpt-4',
                'max_tokens': 1000
            },
            'speech': {
                'enabled': True,
                'default_language': 'en',
                'supported_languages': ['en', 'es', 'fr', 'de'],
                'timeout': 30
            },
            'commands': {
                'enabled': True,
                'prefix': '/',
                'case_sensitive': False
            },
            'url_processing': {
                'enabled': True,
                'max_urls_per_message': 5,
                'timeout': 10
            }
        },
        'disabled': {
            'gpt': {'enabled': False},
            'speech': {'enabled': False},
            'commands': {'enabled': False},
            'url_processing': {'enabled': False}
        }
    }


@pytest.fixture
def error_scenarios():
    """Fixture providing various error scenarios for testing."""
    return {
        'network_error': Exception("Network connection failed"),
        'timeout_error': asyncio.TimeoutError("Operation timed out"),
        'permission_error': PermissionError("Access denied"),
        'value_error': ValueError("Invalid value provided"),
        'runtime_error': RuntimeError("Runtime error occurred")
    }


class TestDataGenerator:
    """Utility class for generating test data."""
    
    @staticmethod
    def generate_messages(count=10, prefix="Message"):
        """Generate a list of test messages."""
        return [f"{prefix} {i}" for i in range(count)]
    
    @staticmethod
    def generate_user_ids(count=10, start_id=10000):
        """Generate a list of user IDs."""
        return list(range(start_id, start_id + count))
    
    @staticmethod
    def generate_chat_ids(count=10, start_id=20000):
        """Generate a list of chat IDs."""
        return list(range(start_id, start_id + count))
    
    @staticmethod
    def generate_file_ids(count=10, prefix="file"):
        """Generate a list of file IDs."""
        return [f"{prefix}_{i:03d}" for i in range(count)]
    
    @staticmethod
    def generate_callback_data(count=10, prefix="callback"):
        """Generate a list of callback data strings."""
        return [f"{prefix}_{i}" for i in range(count)]


@pytest.fixture
def test_data_generator():
    """Fixture for TestDataGenerator."""
    return TestDataGenerator()


class AsyncTestHelper:
    """Helper class for async testing utilities."""
    
    @staticmethod
    async def run_with_timeout(coro, timeout=5.0):
        """Run a coroutine with a timeout."""
        return await asyncio.wait_for(coro, timeout=timeout)
    
    @staticmethod
    async def gather_with_exceptions(*coros):
        """Gather coroutines and return results with exceptions."""
        return await asyncio.gather(*coros, return_exceptions=True)
    
    @staticmethod
    def create_async_mock_with_side_effect(side_effect):
        """Create an AsyncMock with side effect."""
        mock = AsyncMock()
        mock.side_effect = side_effect
        return mock


@pytest.fixture
def async_test_helper():
    """Fixture for AsyncTestHelper."""
    return AsyncTestHelper()


class PerformanceTestHelper:
    """Helper class for performance testing utilities."""
    
    @staticmethod
    def measure_execution_time(func):
        """Decorator to measure execution time."""
        import time
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            return result, execution_time
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            return result, execution_time
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    @staticmethod
    def create_load_test_data(message_count=100, user_count=10, chat_count=5):
        """Create test data for load testing."""
        messages = TestDataGenerator.generate_messages(message_count)
        user_ids = TestDataGenerator.generate_user_ids(user_count)
        chat_ids = TestDataGenerator.generate_chat_ids(chat_count)
        
        test_data = []
        for i, message in enumerate(messages):
            user_id = user_ids[i % len(user_ids)]
            chat_id = chat_ids[i % len(chat_ids)]
            
            user = MockTelegramObjects.create_user(user_id=user_id)
            chat = MockTelegramObjects.create_chat(chat_id=chat_id)
            msg = MockTelegramObjects.create_message(text=message, user=user, chat=chat)
            update = MockTelegramObjects.create_update(message=msg)
            
            test_data.append(update)
        
        return test_data


@pytest.fixture
def performance_test_helper():
    """Fixture for PerformanceTestHelper."""
    return PerformanceTestHelper()


# Pytest configuration for comprehensive testing
def pytest_configure(config):
    """Configure pytest for comprehensive testing."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Pytest collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add markers based on test file location
        if "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add slow marker for tests that might take longer
        if any(keyword in item.name.lower() for keyword in ["load", "stress", "concurrent", "memory"]):
            item.add_marker(pytest.mark.slow)