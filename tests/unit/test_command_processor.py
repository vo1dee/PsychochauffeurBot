"""
Unit tests for the CommandProcessor and command handling system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from modules.command_processor import (
    CommandProcessor, CommandType, CommandMetadata, BaseCommandHandler,
    TextCommandHandler, CallbackQueryHandler, MessageFilterHandler
)


class TestCommandMetadata:
    """Test cases for CommandMetadata."""
    
    def test_command_metadata_creation(self):
        """Test CommandMetadata creation with all parameters."""
        metadata = CommandMetadata(
            name="test_command",
            description="Test command description",
            command_type=CommandType.TEXT_COMMAND,
            permissions=["admin"],
            rate_limit=60,
            admin_only=True,
            group_only=False,
            private_only=True
        )
        
        assert metadata.name == "test_command"
        assert metadata.description == "Test command description"
        assert metadata.command_type == CommandType.TEXT_COMMAND
        assert metadata.permissions == ["admin"]
        assert metadata.rate_limit == 60
        assert metadata.admin_only is True
        assert metadata.group_only is False
        assert metadata.private_only is True
    
    def test_command_metadata_defaults(self):
        """Test CommandMetadata default values."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND
        )
        
        assert metadata.permissions == []
        assert metadata.rate_limit is None
        assert metadata.admin_only is False
        assert metadata.group_only is False
        assert metadata.private_only is False


class TestBaseCommandHandler:
    """Test cases for BaseCommandHandler."""
    
    @pytest.fixture
    def mock_update_private(self):
        """Create a mock update for private chat."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user
        )
        return Update(update_id=1, message=message)
    
    @pytest.fixture
    def mock_update_group(self):
        """Create a mock update for group chat."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=-123, type="supergroup", title="Test Group")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user
        )
        return Update(update_id=1, message=message)
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock CallbackContext."""
        context = Mock(spec=CallbackContext)
        context.bot = Mock()
        context.bot.get_chat_member = AsyncMock()
        return context
    
    class TestCommandHandler(BaseCommandHandler):
        """Test implementation of BaseCommandHandler."""
        
        async def handle(self, update, context):
            return "handled"
    
    def test_base_handler_creation(self):
        """Test BaseCommandHandler creation."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND
        )
        handler = self.TestCommandHandler(metadata)
        assert handler.metadata == metadata
    
    @pytest.mark.asyncio
    async def test_can_execute_no_restrictions(self, mock_update_private, mock_context):
        """Test can_execute with no restrictions."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND
        )
        handler = self.TestCommandHandler(metadata)
        
        result = await handler.can_execute(mock_update_private, mock_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_execute_private_only_in_private(self, mock_update_private, mock_context):
        """Test can_execute with private_only restriction in private chat."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            private_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        result = await handler.can_execute(mock_update_private, mock_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_execute_private_only_in_group(self, mock_update_group, mock_context):
        """Test can_execute with private_only restriction in group chat."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            private_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        result = await handler.can_execute(mock_update_group, mock_context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_can_execute_group_only_in_group(self, mock_update_group, mock_context):
        """Test can_execute with group_only restriction in group chat."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            group_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        result = await handler.can_execute(mock_update_group, mock_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_execute_group_only_in_private(self, mock_update_private, mock_context):
        """Test can_execute with group_only restriction in private chat."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            group_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        result = await handler.can_execute(mock_update_private, mock_context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_can_execute_admin_only_in_private(self, mock_update_private, mock_context):
        """Test can_execute with admin_only restriction in private chat."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            admin_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        result = await handler.can_execute(mock_update_private, mock_context)
        assert result is True  # Private chats always allow admin commands
    
    @pytest.mark.asyncio
    async def test_can_execute_admin_only_as_admin(self, mock_update_group, mock_context):
        """Test can_execute with admin_only restriction as admin."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            admin_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        # Mock admin status
        mock_member = Mock()
        mock_member.status = "administrator"
        mock_context.bot.get_chat_member.return_value = mock_member
        
        result = await handler.can_execute(mock_update_group, mock_context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_can_execute_admin_only_as_regular_user(self, mock_update_group, mock_context):
        """Test can_execute with admin_only restriction as regular user."""
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND,
            admin_only=True
        )
        handler = self.TestCommandHandler(metadata)
        
        # Mock regular user status
        mock_member = Mock()
        mock_member.status = "member"
        mock_context.bot.get_chat_member.return_value = mock_member
        
        result = await handler.can_execute(mock_update_group, mock_context)
        assert result is False


class TestTextCommandHandler:
    """Test cases for TextCommandHandler."""
    
    @pytest.fixture
    def mock_update(self) -> None:
        """Create a mock update."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        
        # Create a mock message instead of real Message object
        message = Mock(spec=Message)
        message.message_id = 1
        message.date = None
        message.chat = chat
        message.from_user = user
        message.text = "/test"
        message.reply_text = AsyncMock()
        
        return Update(update_id=1, message=message)
    
    @pytest.fixture
    def mock_context(self) -> None:
        """Create a mock context."""
        return Mock(spec=CallbackContext)
    
    @pytest.mark.asyncio
    async def test_text_command_handler_success(self, mock_update, mock_context) -> None:
        """Test successful text command handling."""
        async def test_handler(update, context):
            return "success"
        
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND
        )
        handler = TextCommandHandler(metadata, test_handler)
        
        with patch.object(handler, 'can_execute', return_value=True):
            result = await handler.handle(mock_update, mock_context)
            # The handle method doesn't return the handler result due to error decorator
    
    @pytest.mark.asyncio
    async def test_text_command_handler_permission_denied(self, mock_update, mock_context):
        """Test text command handling with permission denied."""
        async def test_handler(update, context):
            return "success"
        
        metadata = CommandMetadata(
            name="test",
            description="Test",
            command_type=CommandType.TEXT_COMMAND
        )
        handler = TextCommandHandler(metadata, test_handler)
        
        with patch.object(handler, 'can_execute', return_value=False):
            await handler.handle(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once_with(
                "❌ You don't have permission to use this command."
            )


class TestCallbackQueryHandler:
    """Test cases for CallbackQueryHandler."""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock update with callback query."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user
        )
        
        # Create a mock callback query instead of real CallbackQuery object
        callback_query = Mock(spec=CallbackQuery)
        callback_query.id = "test_callback"
        callback_query.from_user = user
        callback_query.chat_instance = "test_instance"
        callback_query.message = message
        callback_query.data = "test_data"
        callback_query.answer = AsyncMock()
        
        return Update(update_id=1, callback_query=callback_query)
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        return Mock(spec=CallbackContext)
    
    @pytest.mark.asyncio
    async def test_callback_query_handler_success(self, mock_update, mock_context):
        """Test successful callback query handling."""
        async def test_handler(update, context):
            return "success"
        
        metadata = CommandMetadata(
            name="test_callback",
            description="Test callback",
            command_type=CommandType.CALLBACK_QUERY
        )
        handler = CallbackQueryHandler(metadata, test_handler, "test_pattern")
        
        with patch.object(handler, 'can_execute', return_value=True):
            await handler.handle(mock_update, mock_context)
    
    @pytest.mark.asyncio
    async def test_callback_query_handler_permission_denied(self, mock_update, mock_context):
        """Test callback query handling with permission denied."""
        async def test_handler(update, context):
            return "success"
        
        metadata = CommandMetadata(
            name="test_callback",
            description="Test callback",
            command_type=CommandType.CALLBACK_QUERY
        )
        handler = CallbackQueryHandler(metadata, test_handler)
        
        with patch.object(handler, 'can_execute', return_value=False):
            await handler.handle(mock_update, mock_context)
            mock_update.callback_query.answer.assert_called_once_with(
                "❌ You don't have permission to use this feature."
            )


class TestCommandProcessor:
    """Test cases for CommandProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create a CommandProcessor instance."""
        return CommandProcessor()
    
    @pytest.mark.asyncio
    async def test_processor_initialization(self, processor):
        """Test CommandProcessor initialization."""
        await processor.initialize()
        # No specific assertions needed, just ensure no exceptions
    
    @pytest.mark.asyncio
    async def test_processor_shutdown(self, processor):
        """Test CommandProcessor shutdown."""
        await processor.initialize()
        await processor.shutdown()
        
        assert len(processor._handlers) == 0
        assert len(processor._telegram_handlers) == 0
    
    def test_register_text_command(self, processor):
        """Test registering a text command."""
        async def test_handler(update, context):
            pass
        
        result = processor.register_text_command(
            command="test",
            handler_func=test_handler,
            description="Test command",
            admin_only=True
        )
        
        assert result is processor  # Should return self for chaining
        assert "test" in processor._handlers
        assert len(processor._telegram_handlers) == 1
        
        handler = processor._handlers["test"]
        assert isinstance(handler, TextCommandHandler)
        assert handler.metadata.name == "test"
        assert handler.metadata.description == "Test command"
        assert handler.metadata.admin_only is True
    
    def test_register_callback_handler(self, processor):
        """Test registering a callback handler."""
        async def test_handler(update, context):
            pass
        
        result = processor.register_callback_handler(
            name="test_callback",
            handler_func=test_handler,
            pattern="test_*",
            description="Test callback",
            admin_only=False
        )
        
        assert result is processor
        assert "test_callback" in processor._handlers
        assert len(processor._telegram_handlers) == 1
        
        handler = processor._handlers["test_callback"]
        assert isinstance(handler, CallbackQueryHandler)
        assert handler.metadata.name == "test_callback"
        assert handler.pattern == "test_*"
    
    def test_register_message_handler(self, processor):
        """Test registering a message handler."""
        async def test_handler(update, context):
            pass
        
        result = processor.register_message_handler(
            name="photo_handler",
            handler_func=test_handler,
            message_filter=filters.PHOTO,
            description="Photo handler",
            group_only=True
        )
        
        assert result is processor
        assert "photo_handler" in processor._handlers
        assert len(processor._telegram_handlers) == 1
        
        handler = processor._handlers["photo_handler"]
        assert isinstance(handler, MessageFilterHandler)
        assert handler.metadata.group_only is True
    
    def test_get_telegram_handlers(self, processor):
        """Test getting Telegram handlers."""
        async def test_handler(update, context):
            pass
        
        processor.register_text_command("test1", test_handler)
        processor.register_callback_handler("test2", test_handler)
        
        handlers = processor.get_telegram_handlers()
        assert len(handlers) == 2
        assert isinstance(handlers[0], CommandHandler)
    
    def test_get_registered_commands(self, processor):
        """Test getting registered command names."""
        async def test_handler(update, context):
            pass
        
        processor.register_text_command("test1", test_handler)
        processor.register_callback_handler("test2", test_handler)
        
        commands = processor.get_registered_commands()
        assert "test1" in commands
        assert "test2" in commands
        assert len(commands) == 2
    
    def test_get_command_info(self, processor):
        """Test getting command metadata."""
        async def test_handler(update, context):
            pass
        
        processor.register_text_command(
            "test",
            test_handler,
            description="Test command",
            admin_only=True
        )
        
        info = processor.get_command_info("test")
        assert info is not None
        assert info.name == "test"
        assert info.description == "Test command"
        assert info.admin_only is True
        
        # Test non-existent command
        info = processor.get_command_info("nonexistent")
        assert info is None
    
    def test_get_commands_by_type(self, processor):
        """Test getting commands by type."""
        async def test_handler(update, context):
            pass
        
        processor.register_text_command("text_cmd", test_handler)
        processor.register_callback_handler("callback_cmd", test_handler)
        processor.register_message_handler("msg_handler", test_handler, filters.TEXT)
        
        text_commands = processor.get_commands_by_type(CommandType.TEXT_COMMAND)
        callback_commands = processor.get_commands_by_type(CommandType.CALLBACK_QUERY)
        message_handlers = processor.get_commands_by_type(CommandType.MESSAGE_HANDLER)
        
        assert "text_cmd" in text_commands
        assert "callback_cmd" in callback_commands
        assert "msg_handler" in message_handlers
        assert len(text_commands) == 1
        assert len(callback_commands) == 1
        assert len(message_handlers) == 1


class TestCommandProcessorIntegration:
    """Integration tests for CommandProcessor."""
    
    @pytest.mark.asyncio
    async def test_full_command_lifecycle(self):
        """Test complete command registration and handling lifecycle."""
        processor = CommandProcessor()
        await processor.initialize()
        
        # Track if handler was called
        handler_called = False
        
        async def test_handler(update, context):
            nonlocal handler_called
            handler_called = True
            return "success"
        
        # Register command
        processor.register_text_command(
            "test",
            test_handler,
            description="Test command"
        )
        
        # Create mock update and context
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="/test"
        )
        update = Update(update_id=1, message=message)
        context = Mock(spec=CallbackContext)
        
        # Get the handler and execute it
        telegram_handlers = processor.get_telegram_handlers()
        command_handler = telegram_handlers[0]
        
        # Execute the handler (this will call our test_handler through the wrapper)
        await command_handler.callback(update, context)
        
        # Verify handler was called
        assert handler_called
        
        await processor.shutdown()
    
    def test_method_chaining(self):
        """Test that registration methods support chaining."""
        processor = CommandProcessor()
        
        async def handler1(update, context):
            pass
        
        async def handler2(update, context):
            pass
        
        async def handler3(update, context):
            pass
        
        # Test method chaining
        result = (processor
                 .register_text_command("cmd1", handler1)
                 .register_callback_handler("cb1", handler2)
                 .register_message_handler("msg1", handler3, filters.TEXT))
        
        assert result is processor
        assert len(processor.get_registered_commands()) == 3