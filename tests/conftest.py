"""
Pytest configuration and shared fixtures for the PsychoChauffeur Bot test suite.
"""

import pytest
import asyncio
import tempfile
import shutil
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


# ============================================================================
# Event Loop and Async Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
# Telegram Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_bot():
    """Create a mock Telegram Bot instance."""
    bot = Mock(spec=Bot)
    bot.token = "test_token"
    bot.get_me = AsyncMock(return_value=Mock(username="test_bot"))
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_sticker = AsyncMock()
    bot.send_document = AsyncMock()
    bot.get_file = AsyncMock()
    bot.get_chat_member = AsyncMock()
    return bot


@pytest.fixture
def mock_user():
    """Create a mock Telegram User."""
    return User(
        id=12345,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="en"
    )


@pytest.fixture
def mock_private_chat():
    """Create a mock private Telegram Chat."""
    return Chat(
        id=12345,
        type=Chat.PRIVATE,
        username="testuser",
        first_name="Test",
        last_name="User"
    )


@pytest.fixture
def mock_group_chat():
    """Create a mock group Telegram Chat."""
    return Chat(
        id=-1001234567890,
        type=Chat.SUPERGROUP,
        title="Test Group",
        description="A test group chat"
    )


@pytest.fixture
def mock_message(mock_user, mock_private_chat):
    """Create a mock Telegram Message."""
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=mock_private_chat,
        from_user=mock_user,
        text="Test message"
    )


@pytest.fixture
def mock_update(mock_message):
    """Create a mock Telegram Update."""
    return Update(
        update_id=1,
        message=mock_message
    )


@pytest.fixture
def mock_callback_query(mock_user, mock_private_chat):
    """Create a mock Telegram CallbackQuery."""
    message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=mock_private_chat,
        from_user=mock_user,
        text="Original message"
    )
    
    return CallbackQuery(
        id="test_callback_query",
        from_user=mock_user,
        chat_instance="test_chat_instance",
        message=message,
        data="test_callback_data"
    )


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