"""
Unit tests for application models.

This module contains comprehensive unit tests for the data models used
throughout the refactored application architecture.
"""

import pytest
from unittest.mock import Mock
from typing import Any

from modules.application_models import (
    ServiceConfiguration,
    MessageContext,
    HandlerMetadata,
    CommandMetadata,
    ServiceHealth
)


class TestServiceConfiguration:
    """Test cases for ServiceConfiguration data model."""
    
    def test_valid_configuration(self) -> None:
        """Test creating a valid service configuration."""
        config = ServiceConfiguration(
            telegram_token="test_token_123",
            error_channel_id="test_channel_456"
        )
        
        assert config.telegram_token == "test_token_123"
        assert config.error_channel_id == "test_channel_456"
        assert config.database_url is None
        assert config.redis_url is None
        assert config.debug_mode is False
    
    def test_configuration_with_optional_fields(self) -> None:
        """Test creating configuration with optional fields."""
        config = ServiceConfiguration(
            telegram_token="test_token",
            error_channel_id="test_channel",
            database_url="postgresql://localhost/test",
            redis_url="redis://localhost:6379",
            debug_mode=True
        )
        
        assert config.telegram_token == "test_token"
        assert config.error_channel_id == "test_channel"
        assert config.database_url == "postgresql://localhost/test"
        assert config.redis_url == "redis://localhost:6379"
        assert config.debug_mode is True
    
    def test_empty_telegram_token(self) -> None:
        """Test configuration with empty telegram token."""
        with pytest.raises(ValueError, match="telegram_token is required"):
            ServiceConfiguration(
                telegram_token="",
                error_channel_id="test_channel"
            )
    
    def test_empty_error_channel_id(self) -> None:
        """Test configuration with empty error channel ID."""
        with pytest.raises(ValueError, match="error_channel_id is required"):
            ServiceConfiguration(
                telegram_token="test_token",
                error_channel_id=""
            )
    
    def test_none_telegram_token(self) -> None:
        """Test configuration with None telegram token."""
        with pytest.raises(ValueError, match="telegram_token is required"):
            ServiceConfiguration(
                telegram_token=None,  # type: ignore
                error_channel_id="test_channel"
            )
    
    def test_none_error_channel_id(self) -> None:
        """Test configuration with None error channel ID."""
        with pytest.raises(ValueError, match="error_channel_id is required"):
            ServiceConfiguration(
                telegram_token="test_token",
                error_channel_id=None  # type: ignore
            )


class TestMessageContext:
    """Test cases for MessageContext data model."""
    
    @pytest.fixture
    def mock_update(self) -> Mock:
        """Create a mock Telegram update."""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_chat = Mock()
        update.effective_chat.id = 67890
        update.effective_chat.type = "private"
        update.message = Mock()
        update.message.text = "Hello world"
        return update
    
    @pytest.fixture
    def mock_context(self) -> Mock:
        """Create a mock Telegram callback context."""
        return Mock()
    
    def test_manual_creation(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test manual creation of MessageContext."""
        context = MessageContext(
            update=mock_update,
            context=mock_context,
            user_id=12345,
            chat_id=67890,
            chat_type="private",
            message_text="Hello world"
        )
        
        assert context.update == mock_update
        assert context.context == mock_context
        assert context.user_id == 12345
        assert context.chat_id == 67890
        assert context.chat_type == "private"
        assert context.message_text == "Hello world"
        assert context.urls == []
        assert context.is_command is False
        assert context.requires_gpt_response is False
    
    def test_from_update_text_message(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test creating MessageContext from update with text message."""
        context = MessageContext.from_update(mock_update, mock_context)
        
        assert context.update == mock_update
        assert context.context == mock_context
        assert context.user_id == 12345
        assert context.chat_id == 67890
        assert context.chat_type == "private"
        assert context.message_text == "Hello world"
        assert context.is_command is False
    
    def test_from_update_command_message(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test creating MessageContext from update with command message."""
        mock_update.message.text = "/start hello"
        
        context = MessageContext.from_update(mock_update, mock_context)
        
        assert context.message_text == "/start hello"
        assert context.is_command is True
    
    def test_from_update_no_message_text(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test creating MessageContext from update without message text."""
        mock_update.message.text = None
        
        context = MessageContext.from_update(mock_update, mock_context)
        
        assert context.message_text is None
        assert context.is_command is False
    
    def test_from_update_no_message(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test creating MessageContext from update without message."""
        mock_update.message = None
        
        context = MessageContext.from_update(mock_update, mock_context)
        
        assert context.message_text is None
        assert context.is_command is False
    
    def test_from_update_no_effective_user(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test creating MessageContext from update without effective user."""
        mock_update.effective_user = None
        
        with pytest.raises(ValueError, match="Update must have an effective user"):
            MessageContext.from_update(mock_update, mock_context)
    
    def test_from_update_no_effective_chat(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test creating MessageContext from update without effective chat."""
        mock_update.effective_chat = None
        
        with pytest.raises(ValueError, match="Update must have an effective chat"):
            MessageContext.from_update(mock_update, mock_context)
    
    def test_with_urls(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test MessageContext with URLs."""
        context = MessageContext(
            update=mock_update,
            context=mock_context,
            user_id=12345,
            chat_id=67890,
            chat_type="private",
            urls=["https://example.com", "https://test.com"]
        )
        
        assert context.urls == ["https://example.com", "https://test.com"]
    
    def test_requires_gpt_response(self, mock_update: Mock, mock_context: Mock) -> None:
        """Test MessageContext with GPT response requirement."""
        context = MessageContext(
            update=mock_update,
            context=mock_context,
            user_id=12345,
            chat_id=67890,
            chat_type="private",
            requires_gpt_response=True
        )
        
        assert context.requires_gpt_response is True


class TestHandlerMetadata:
    """Test cases for HandlerMetadata data model."""
    
    def test_valid_metadata(self) -> None:
        """Test creating valid handler metadata."""
        metadata = HandlerMetadata(
            name="text_handler",
            description="Handles text messages",
            message_types=["text", "command"]
        )
        
        assert metadata.name == "text_handler"
        assert metadata.description == "Handles text messages"
        assert metadata.message_types == ["text", "command"]
        assert metadata.priority == 0
        assert metadata.enabled is True
        assert metadata.dependencies == []
    
    def test_metadata_with_optional_fields(self) -> None:
        """Test creating metadata with optional fields."""
        metadata = HandlerMetadata(
            name="advanced_handler",
            description="Advanced message handler",
            message_types=["photo", "video"],
            priority=10,
            enabled=False,
            dependencies=["config_manager", "database"]
        )
        
        assert metadata.name == "advanced_handler"
        assert metadata.description == "Advanced message handler"
        assert metadata.message_types == ["photo", "video"]
        assert metadata.priority == 10
        assert metadata.enabled is False
        assert metadata.dependencies == ["config_manager", "database"]
    
    def test_empty_name(self) -> None:
        """Test metadata with empty name."""
        with pytest.raises(ValueError, match="Handler name is required"):
            HandlerMetadata(
                name="",
                description="Test handler",
                message_types=["text"]
            )
    
    def test_empty_description(self) -> None:
        """Test metadata with empty description."""
        with pytest.raises(ValueError, match="Handler description is required"):
            HandlerMetadata(
                name="test_handler",
                description="",
                message_types=["text"]
            )
    
    def test_empty_message_types(self) -> None:
        """Test metadata with empty message types."""
        with pytest.raises(ValueError, match="At least one message type must be specified"):
            HandlerMetadata(
                name="test_handler",
                description="Test handler",
                message_types=[]
            )


class TestCommandMetadata:
    """Test cases for CommandMetadata data model."""
    
    def test_valid_metadata(self) -> None:
        """Test creating valid command metadata."""
        metadata = CommandMetadata(
            name="start",
            description="Start the bot"
        )
        
        assert metadata.name == "start"
        assert metadata.description == "Start the bot"
        assert metadata.category == "basic"
        assert metadata.admin_only is False
        assert metadata.enabled is True
        assert metadata.aliases == []
        assert metadata.usage is None
    
    def test_metadata_with_optional_fields(self) -> None:
        """Test creating metadata with optional fields."""
        metadata = CommandMetadata(
            name="admin_command",
            description="Admin only command",
            category="admin",
            admin_only=True,
            enabled=False,
            aliases=["adm", "admin"],
            usage="/admin_command [options]"
        )
        
        assert metadata.name == "admin_command"
        assert metadata.description == "Admin only command"
        assert metadata.category == "admin"
        assert metadata.admin_only is True
        assert metadata.enabled is False
        assert metadata.aliases == ["adm", "admin"]
        assert metadata.usage == "/admin_command [options]"
    
    def test_empty_name(self) -> None:
        """Test metadata with empty name."""
        with pytest.raises(ValueError, match="Command name is required"):
            CommandMetadata(
                name="",
                description="Test command"
            )
    
    def test_empty_description(self) -> None:
        """Test metadata with empty description."""
        with pytest.raises(ValueError, match="Command description is required"):
            CommandMetadata(
                name="test_command",
                description=""
            )
    
    def test_invalid_category(self) -> None:
        """Test metadata with invalid category."""
        with pytest.raises(ValueError, match="Invalid command category: invalid"):
            CommandMetadata(
                name="test_command",
                description="Test command",
                category="invalid"
            )
    
    def test_valid_categories(self) -> None:
        """Test all valid command categories."""
        valid_categories = ["basic", "gpt", "utility", "speech", "admin"]
        
        for category in valid_categories:
            metadata = CommandMetadata(
                name="test_command",
                description="Test command",
                category=category
            )
            assert metadata.category == category


class TestServiceHealth:
    """Test cases for ServiceHealth data model."""
    
    def test_healthy_service(self) -> None:
        """Test creating healthy service status."""
        health = ServiceHealth(
            service_name="database",
            is_healthy=True,
            status="Running normally"
        )
        
        assert health.service_name == "database"
        assert health.is_healthy is True
        assert health.status == "Running normally"
        assert health.last_check is None
        assert health.error_message is None
        assert health.metrics == {}
    
    def test_unhealthy_service(self) -> None:
        """Test creating unhealthy service status."""
        health = ServiceHealth(
            service_name="redis",
            is_healthy=False,
            status="Connection failed",
            error_message="Connection timeout after 5 seconds"
        )
        
        assert health.service_name == "redis"
        assert health.is_healthy is False
        assert health.status == "Connection failed"
        assert health.error_message == "Connection timeout after 5 seconds"
    
    def test_service_with_metrics(self) -> None:
        """Test creating service status with metrics."""
        health = ServiceHealth(
            service_name="api",
            is_healthy=True,
            status="Running",
            last_check="2024-01-01T12:00:00Z",
            metrics={
                "response_time": 150,
                "requests_per_second": 25,
                "memory_usage": "128MB"
            }
        )
        
        assert health.service_name == "api"
        assert health.is_healthy is True
        assert health.status == "Running"
        assert health.last_check == "2024-01-01T12:00:00Z"
        assert health.metrics["response_time"] == 150
        assert health.metrics["requests_per_second"] == 25
        assert health.metrics["memory_usage"] == "128MB"
    
    def test_default_metrics(self) -> None:
        """Test that metrics defaults to empty dict."""
        health = ServiceHealth(
            service_name="test",
            is_healthy=True,
            status="OK"
        )
        
        assert health.metrics == {}
        
        # Verify we can add to metrics
        health.metrics["test_metric"] = "test_value"
        assert health.metrics["test_metric"] == "test_value"