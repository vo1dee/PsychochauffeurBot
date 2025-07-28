"""
Additional test fixtures and utilities for specific testing scenarios.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import tempfile
import json

from telegram import Update, Message, User, Chat, Document, PhotoSize, Voice, VideoNote
from telegram.ext import CallbackContext

from modules.const import KYIV_TZ
from modules.error_handler import StandardError, ErrorSeverity, ErrorCategory


class TelegramObjectFactory:
    """Factory for creating Telegram objects for testing."""
    
    @staticmethod
    def create_user(
        user_id: int = 12345,
        username: str = "testuser",
        first_name: str = "Test",
        last_name: str = "User",
        is_bot: bool = False
    ) -> User:
        """Create a Telegram User object."""
        return User(
            id=user_id,
            is_bot=is_bot,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code="en"
        )
    
    @staticmethod
    def create_chat(
        chat_id: int = 12345,
        chat_type: str = "private",
        title: Optional[str] = None,
        username: Optional[str] = None
    ) -> Chat:
        """Create a Telegram Chat object."""
        if chat_type == "private":
            return Chat(
                id=chat_id,
                type=Chat.PRIVATE,
                username=username or "testuser",
                first_name="Test",
                last_name="User"
            )
        else:
            return Chat(
                id=chat_id,
                type=Chat.SUPERGROUP if chat_type == "supergroup" else Chat.GROUP,
                title=title or "Test Group",
                description="A test group chat"
            )
    
    @staticmethod
    def create_message(
        message_id: int = 1,
        user: Optional[User] = None,
        chat: Optional[Chat] = None,
        text: Optional[str] = "Test message",
        date: Optional[datetime] = None,
        reply_to_message: Optional[Message] = None
    ) -> Message:
        """Create a Telegram Message object."""
        if user is None:
            user = TelegramObjectFactory.create_user()
        if chat is None:
            chat = TelegramObjectFactory.create_chat()
        if date is None:
            date = datetime.now(KYIV_TZ)
        
        return Message(
            message_id=message_id,
            date=date,
            chat=chat,
            from_user=user,
            text=text,
            reply_to_message=reply_to_message
        )
    
    @staticmethod
    def create_update(
        update_id: int = 1,
        message: Optional[Message] = None,
        callback_query: Optional[Any] = None
    ) -> Update:
        """Create a Telegram Update object."""
        if message is None and callback_query is None:
            message = TelegramObjectFactory.create_message()
        
        return Update(
            update_id=update_id,
            message=message,
            callback_query=callback_query
        )
    
    @staticmethod
    def create_document(
        file_id: str = "test_file_id",
        file_unique_id: str = "test_unique_id",
        file_name: str = "test.txt",
        mime_type: str = "text/plain",
        file_size: int = 1024
    ) -> Document:
        """Create a Telegram Document object."""
        return Document(
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_name=file_name,
            mime_type=mime_type,
            file_size=file_size
        )
    
    @staticmethod
    def create_photo(
        file_id: str = "test_photo_id",
        file_unique_id: str = "test_photo_unique_id",
        width: int = 800,
        height: int = 600,
        file_size: int = 50000
    ) -> PhotoSize:
        """Create a Telegram PhotoSize object."""
        return PhotoSize(
            file_id=file_id,
            file_unique_id=file_unique_id,
            width=width,
            height=height,
            file_size=file_size
        )
    
    @staticmethod
    def create_voice(
        file_id: str = "test_voice_id",
        file_unique_id: str = "test_voice_unique_id",
        duration: int = 30,
        mime_type: str = "audio/ogg",
        file_size: int = 15000
    ) -> Voice:
        """Create a Telegram Voice object."""
        return Voice(
            file_id=file_id,
            file_unique_id=file_unique_id,
            duration=duration,
            mime_type=mime_type,
            file_size=file_size
        )


class MockServiceFactory:
    """Factory for creating mock services."""
    
    @staticmethod
    def create_database_mock():
        """Create a mock database with common methods."""
        mock_db = Mock()
        mock_db.initialize = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])
        mock_db.fetchrow = AsyncMock(return_value=None)
        mock_db.fetchval = AsyncMock(return_value=None)
        return mock_db
    
    @staticmethod
    def create_config_manager_mock():
        """Create a mock configuration manager."""
        mock_config = Mock()
        mock_config.initialize = AsyncMock()
        mock_config.get_config = AsyncMock(return_value={})
        mock_config.save_config = AsyncMock(return_value=True)
        mock_config.update_module_setting = AsyncMock()
        return mock_config
    
    @staticmethod
    def create_logger_mock():
        """Create a mock logger."""
        mock_logger = Mock()
        mock_logger.info = Mock()
        mock_logger.warning = Mock()
        mock_logger.error = Mock()
        mock_logger.debug = Mock()
        mock_logger.critical = Mock()
        return mock_logger
    
    @staticmethod
    def create_error_handler_mock():
        """Create a mock error handler."""
        mock_handler = Mock()
        mock_handler.handle_error = AsyncMock()
        mock_handler.create_error = Mock(return_value=StandardError("Test error"))
        mock_handler.format_error_message = Mock(return_value="Formatted error")
        return mock_handler


class TestDataGenerator:
    """Generator for test data scenarios."""
    
    @staticmethod
    def generate_chat_messages(count: int = 10, chat_id: int = 12345) -> List[Dict[str, Any]]:
        """Generate a list of chat messages for testing."""
        messages = []
        base_time = datetime.now(KYIV_TZ)
        
        for i in range(count):
            messages.append({
                "message_id": i + 1,
                "chat_id": chat_id,
                "user_id": 12345 + (i % 3),  # Rotate between 3 users
                "username": f"user{i % 3 + 1}",
                "text": f"Test message {i + 1}",
                "timestamp": base_time + timedelta(minutes=i),
                "is_user": True
            })
        
        return messages
    
    @staticmethod
    def generate_error_scenarios() -> List[Dict[str, Any]]:
        """Generate various error scenarios for testing."""
        return [
            {
                "error_type": ConnectionError,
                "message": "Network connection failed",
                "expected_category": ErrorCategory.NETWORK,
                "expected_severity": ErrorSeverity.MEDIUM
            },
            {
                "error_type": ValueError,
                "message": "Invalid input value",
                "expected_category": ErrorCategory.INPUT,
                "expected_severity": ErrorSeverity.MEDIUM
            },
            {
                "error_type": FileNotFoundError,
                "message": "File not found",
                "expected_category": ErrorCategory.RESOURCE,
                "expected_severity": ErrorSeverity.MEDIUM
            },
            {
                "error_type": PermissionError,
                "message": "Permission denied",
                "expected_category": ErrorCategory.PERMISSION,
                "expected_severity": ErrorSeverity.MEDIUM
            }
        ]
    
    @staticmethod
    def generate_config_scenarios() -> List[Dict[str, Any]]:
        """Generate configuration test scenarios."""
        return [
            {
                "name": "minimal_config",
                "config": {
                    "chat_metadata": {
                        "chat_id": "test",
                        "chat_type": "private",
                        "custom_config_enabled": False
                    }
                }
            },
            {
                "name": "full_config",
                "config": {
                    "chat_metadata": {
                        "chat_id": "test",
                        "chat_type": "group",
                        "chat_name": "Test Group",
                        "custom_config_enabled": True
                    },
                    "config_modules": {
                        "gpt": {
                            "enabled": True,
                            "overrides": {
                                "temperature": 0.7,
                                "max_tokens": 1000
                            }
                        }
                    }
                }
            }
        ]


class AsyncTestHelpers:
    """Helpers for async testing scenarios."""
    
    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run a coroutine with timeout."""
        return await asyncio.wait_for(coro, timeout=timeout)
    
    @staticmethod
    async def simulate_delay(delay: float = 0.1):
        """Simulate async delay."""
        await asyncio.sleep(delay)
    
    @staticmethod
    def create_async_context_manager(return_value=None) -> None:
        """Create a mock async context manager."""
        class AsyncContextManager:
            async def __aenter__(self):
                return return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        return AsyncContextManager()


class FileTestHelpers:
    """Helpers for file-related testing."""
    
    @staticmethod
    def create_temp_file(content: str = "test content", suffix: str = ".txt") -> str:
        """Create a temporary file with content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name
    
    @staticmethod
    def create_temp_json_file(data: Dict[str, Any], suffix: str = ".json") -> str:
        """Create a temporary JSON file with data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            json.dump(data, f, indent=2)
            return f.name
    
    @staticmethod
    def create_temp_directory() -> str:
        """Create a temporary directory."""
        return tempfile.mkdtemp()


# Pytest fixtures using the factories above

@pytest.fixture
def telegram_factory():
    """Provide access to Telegram object factory."""
    return TelegramObjectFactory()


@pytest.fixture
def mock_service_factory():
    """Provide access to mock service factory."""
    return MockServiceFactory()


@pytest.fixture
def test_data_generator():
    """Provide access to test data generator."""
    return TestDataGenerator()


@pytest.fixture
def async_helpers():
    """Provide access to async test helpers."""
    return AsyncTestHelpers()


@pytest.fixture
def file_helpers():
    """Provide access to file test helpers."""
    return FileTestHelpers()


@pytest.fixture
def mock_time():
    """Mock time-related functions for consistent testing."""
    with patch('time.time', return_value=1642694400.0):  # Fixed timestamp
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2022, 1, 20, 12, 0, 0, tzinfo=KYIV_TZ)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            yield mock_datetime


@pytest.fixture
def mock_external_apis():
    """Mock external API calls."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": "test"}
        mock_response.text = "test response"
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        
        yield mock_client


@pytest.fixture
def isolated_event_loop():
    """Create an isolated event loop for tests that need complete isolation."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture
def performance_benchmark():
    """Benchmark performance of operations."""
    import time
    
    class Benchmark:
        def __init__(self):
            self.measurements = {}
        
        def measure(self, name: str):
            class Timer:
                def __init__(self, benchmark, name):
                    self.benchmark = benchmark
                    self.name = name
                    self.start_time = None
                
                def __enter__(self):
                    self.start_time = time.perf_counter()
                    return self
                
                def __exit__(self, exc_type, exc_val, exc_tb):
                    end_time = time.perf_counter()
                    self.benchmark.measurements[self.name] = end_time - self.start_time
            
            return Timer(self, name)
        
        def get_measurement(self, name: str) -> float:
            return self.measurements.get(name, 0.0)
        
        def assert_faster_than(self, name: str, threshold: float):
            measurement = self.get_measurement(name)
            assert measurement < threshold, f"Operation '{name}' took {measurement:.4f}s, expected < {threshold}s"
    
    return Benchmark()