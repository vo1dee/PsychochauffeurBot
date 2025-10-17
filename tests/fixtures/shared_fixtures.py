"""
Enhanced shared test fixtures for common data structures and mock services.
This module provides comprehensive fixtures that can be reused across all test modules.
"""

import pytest
import asyncio
import tempfile
import shutil
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock, MagicMock

# Telegram imports
from telegram import Update, Message, User, Chat, CallbackQuery, Bot, Document, PhotoSize, Voice
from telegram.ext import CallbackContext, Application

# Local imports
from modules.const import KYIV_TZ


# ============================================================================
# Core Data Structure Fixtures
# ============================================================================

@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Sample user data for testing."""
    return {
        "user_id": 12345,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "language_code": "en",
        "is_bot": False,
        "created_at": datetime.now(timezone.utc),
        "permissions": ["read", "write"],
        "preferences": {
            "language": "en",
            "timezone": "UTC",
            "notifications": True
        }
    }


@pytest.fixture
def sample_chat_data() -> Dict[str, Any]:
    """Sample chat data for testing."""
    return {
        "chat_id": -1001234567890,
        "chat_type": "supergroup",
        "title": "Test Group",
        "description": "A test group for testing purposes",
        "member_count": 50,
        "created_at": datetime.now(timezone.utc),
        "settings": {
            "allow_bots": True,
            "restrict_messages": False,
            "auto_delete_timer": None
        }
    }


@pytest.fixture
def sample_message_data() -> Dict[str, Any]:
    """Sample message data for testing."""
    return {
        "message_id": 1,
        "text": "Test message content",
        "timestamp": datetime.now(timezone.utc),
        "chat_id": 12345,
        "user_id": 12345,
        "reply_to_message_id": None,
        "entities": [],
        "media_type": None,
        "edited": False
    }


@pytest.fixture
def sample_config_data() -> Dict[str, Any]:
    """Sample configuration data for testing."""
    return {
        "chat_metadata": {
            "chat_id": "test_chat",
            "chat_type": "private",
            "chat_name": "Test Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "custom_config_enabled": True
        },
        "config_modules": {
            "gpt": {
                "enabled": True,
                "overrides": {
                    "command": {
                        "max_tokens": 1500,
                        "temperature": 0.7,
                        "model": "gpt-4o-mini",
                        "system_prompt": "Test system prompt"
                    }
                }
            },
            "chat_behavior": {
                "enabled": True,
                "overrides": {
                    "restrictions_enabled": False,
                    "max_message_length": 2048,
                    "auto_responses": True
                }
            },
            "security": {
                "enabled": True,
                "overrides": {
                    "input_validation": True,
                    "rate_limiting": True,
                    "allowed_file_types": [".txt", ".pdf", ".jpg", ".png"]
                }
            }
        }
    }


@pytest.fixture
def sample_error_data() -> Dict[str, Any]:
    """Sample error data for testing."""
    return {
        "error_id": "test_error_001",
        "error_type": "ValidationError",
        "message": "Test validation error",
        "severity": "medium",
        "category": "input",
        "context": {
            "user_id": 12345,
            "chat_id": -1001234567890,
            "command": "/test",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        "stack_trace": "Test stack trace",
        "resolved": False,
        "created_at": datetime.now(timezone.utc)
    }


@pytest.fixture
def sample_api_response_data() -> Dict[str, Any]:
    """Sample API response data for testing."""
    return {
        "openai": {
            "choices": [
                {
                    "message": {
                        "content": "Test AI response content",
                        "role": "assistant"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 25,
                "total_tokens": 75
            },
            "model": "gpt-4o-mini"
        },
        "weather": {
            "name": "Kyiv",
            "main": {
                "temp": 20.5,
                "feels_like": 22.0,
                "humidity": 65,
                "pressure": 1013
            },
            "weather": [
                {
                    "main": "Clear",
                    "description": "clear sky",
                    "icon": "01d"
                }
            ],
            "wind": {
                "speed": 3.2,
                "deg": 180
            }
        },
        "video_info": {
            "title": "Test Video",
            "duration": 120,
            "uploader": "Test Channel",
            "view_count": 1000,
            "upload_date": "20240101",
            "formats": [
                {
                    "format_id": "720p",
                    "ext": "mp4",
                    "filesize": 1024000
                }
            ]
        }
    }


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_config_directory(temp_directory: Path) -> Path:
    """Create a temporary configuration directory structure."""
    config_dir = temp_directory / "config"
    config_dir.mkdir()
    
    # Create subdirectories
    (config_dir / "global").mkdir()
    (config_dir / "private").mkdir()
    (config_dir / "group").mkdir()
    (config_dir / "backups").mkdir()
    (config_dir / "schemas").mkdir()
    (config_dir / "modules").mkdir()
    
    return config_dir


@pytest.fixture
def temp_log_directory(temp_directory: Path) -> Path:
    """Create a temporary log directory structure."""
    log_dir = temp_directory / "logs"
    log_dir.mkdir()
    
    # Create subdirectories
    (log_dir / "analytics").mkdir()
    (log_dir / "errors").mkdir()
    (log_dir / "chat_logs").mkdir()
    
    return log_dir


@pytest.fixture
def temp_data_directory(temp_directory: Path) -> Path:
    """Create a temporary data directory structure."""
    data_dir = temp_directory / "data"
    data_dir.mkdir()
    
    # Create subdirectories
    (data_dir / "downloads").mkdir()
    (data_dir / "uploads").mkdir()
    (data_dir / "cache").mkdir()
    (data_dir / "exports").mkdir()
    
    return data_dir


@pytest.fixture
def sample_config_files(temp_config_directory: Path, sample_config_data: Dict[str, Any]) -> Dict[str, Path]:
    """Create sample configuration files for testing."""
    files = {}
    
    # Global config file
    global_config_file = temp_config_directory / "global" / "global_config.json"
    with open(global_config_file, 'w') as f:
        json.dump(sample_config_data, f, indent=2, default=str)
    files["global"] = global_config_file
    
    # Private config file
    private_config_file = temp_config_directory / "private" / "12345.json"
    private_config = sample_config_data.copy()
    private_config["chat_metadata"]["chat_id"] = "12345"
    private_config["chat_metadata"]["chat_type"] = "private"
    with open(private_config_file, 'w') as f:
        json.dump(private_config, f, indent=2, default=str)
    files["private"] = private_config_file
    
    # Group config file
    group_config_file = temp_config_directory / "group" / "-1001234567890.json"
    group_config = sample_config_data.copy()
    group_config["chat_metadata"]["chat_id"] = "-1001234567890"
    group_config["chat_metadata"]["chat_type"] = "supergroup"
    with open(group_config_file, 'w') as f:
        json.dump(group_config, f, indent=2, default=str)
    files["group"] = group_config_file
    
    return files


@pytest.fixture
def sample_log_files(temp_log_directory: Path) -> Dict[str, Path]:
    """Create sample log files for testing."""
    files = {}
    
    # General log file
    general_log = temp_log_directory / "general.log"
    with open(general_log, 'w') as f:
        f.write("2024-01-01 12:00:00 - INFO - Test log entry\n")
        f.write("2024-01-01 12:01:00 - WARNING - Test warning\n")
        f.write("2024-01-01 12:02:00 - ERROR - Test error\n")
    files["general"] = general_log
    
    # Error log file
    error_log = temp_log_directory / "errors" / "error.log"
    with open(error_log, 'w') as f:
        f.write("2024-01-01 12:02:00 - ERROR - Test error message\n")
        f.write("2024-01-01 12:03:00 - CRITICAL - Test critical error\n")
    files["error"] = error_log
    
    # Chat log file
    chat_log = temp_log_directory / "chat_logs" / "12345.log"
    with open(chat_log, 'w') as f:
        f.write("2024-01-01 12:00:00 - USER - testuser: Hello\n")
        f.write("2024-01-01 12:00:30 - BOT - Test Bot: Hi there!\n")
    files["chat"] = chat_log
    
    return files


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def sample_database_records() -> Dict[str, List[Dict[str, Any]]]:
    """Sample database records for testing."""
    return {
        "users": [
            {
                "id": 12345,
                "username": "testuser1",
                "first_name": "Test1",
                "last_name": "User",
                "created_at": datetime.now(timezone.utc)
            },
            {
                "id": 12346,
                "username": "testuser2",
                "first_name": "Test2",
                "last_name": "User",
                "created_at": datetime.now(timezone.utc)
            }
        ],
        "chats": [
            {
                "id": 12345,
                "type": "private",
                "title": None,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "id": -1001234567890,
                "type": "supergroup",
                "title": "Test Group",
                "created_at": datetime.now(timezone.utc)
            }
        ],
        "messages": [
            {
                "id": 1,
                "chat_id": 12345,
                "user_id": 12345,
                "text": "Hello",
                "timestamp": datetime.now(timezone.utc)
            },
            {
                "id": 2,
                "chat_id": 12345,
                "user_id": 12345,
                "text": "How are you?",
                "timestamp": datetime.now(timezone.utc) + timedelta(minutes=1)
            }
        ],
        "errors": [
            {
                "id": 1,
                "error_type": "ValidationError",
                "message": "Test error",
                "severity": "medium",
                "category": "input",
                "context": json.dumps({"test": "data"}),
                "timestamp": datetime.now(timezone.utc)
            }
        ]
    }


# ============================================================================
# Test Scenario Fixtures
# ============================================================================

@pytest.fixture
def test_scenarios() -> Dict[str, List[Dict[str, Any]]]:
    """Common test scenarios for various testing needs."""
    return {
        "input_validation": [
            {"input": "", "expected": False, "error": "Empty input"},
            {"input": "valid_input", "expected": True, "error": None},
            {"input": "a" * 5000, "expected": False, "error": "Input too long"},
            {"input": "<script>alert('xss')</script>", "expected": False, "error": "Invalid characters"},
            {"input": "SELECT * FROM users", "expected": False, "error": "SQL injection attempt"}
        ],
        "file_types": [
            {"filename": "test.txt", "allowed": True, "mime_type": "text/plain"},
            {"filename": "test.pdf", "allowed": True, "mime_type": "application/pdf"},
            {"filename": "test.jpg", "allowed": True, "mime_type": "image/jpeg"},
            {"filename": "test.exe", "allowed": False, "mime_type": "application/x-executable"},
            {"filename": "test.bat", "allowed": False, "mime_type": "application/x-bat"}
        ],
        "api_responses": [
            {"status_code": 200, "success": True, "data": {"result": "success"}},
            {"status_code": 400, "success": False, "error": "Bad request"},
            {"status_code": 401, "success": False, "error": "Unauthorized"},
            {"status_code": 404, "success": False, "error": "Not found"},
            {"status_code": 500, "success": False, "error": "Internal server error"}
        ],
        "rate_limiting": [
            {"requests": 1, "time_window": 60, "allowed": True},
            {"requests": 10, "time_window": 60, "allowed": True},
            {"requests": 100, "time_window": 60, "allowed": False},
            {"requests": 5, "time_window": 1, "allowed": False}
        ]
    }


@pytest.fixture
def error_scenarios() -> List[Dict[str, Any]]:
    """Common error scenarios for testing error handling."""
    return [
        {
            "exception": ConnectionError("Network connection failed"),
            "expected_category": "network",
            "expected_severity": "medium",
            "should_retry": True
        },
        {
            "exception": ValueError("Invalid input value"),
            "expected_category": "input",
            "expected_severity": "low",
            "should_retry": False
        },
        {
            "exception": FileNotFoundError("File not found"),
            "expected_category": "resource",
            "expected_severity": "medium",
            "should_retry": False
        },
        {
            "exception": PermissionError("Permission denied"),
            "expected_category": "permission",
            "expected_severity": "high",
            "should_retry": False
        },
        {
            "exception": TimeoutError("Operation timed out"),
            "expected_category": "network",
            "expected_severity": "medium",
            "should_retry": True
        }
    ]


# ============================================================================
# Performance and Load Testing Fixtures
# ============================================================================

@pytest.fixture
def performance_thresholds() -> Dict[str, float]:
    """Performance thresholds for various operations."""
    return {
        "database_query": 0.1,  # 100ms
        "api_call": 2.0,        # 2 seconds
        "file_operation": 0.5,  # 500ms
        "config_load": 0.05,    # 50ms
        "message_process": 0.1, # 100ms
        "image_process": 5.0,   # 5 seconds
        "video_process": 30.0   # 30 seconds
    }


@pytest.fixture
def load_test_data() -> Dict[str, Any]:
    """Data for load testing scenarios."""
    return {
        "concurrent_users": [1, 5, 10, 25, 50],
        "message_volumes": [10, 100, 1000, 5000],
        "file_sizes": [1024, 10240, 102400, 1048576],  # 1KB to 1MB
        "duration_seconds": [10, 30, 60, 300]
    }