"""
Unit tests for CommandRegistry.

Tests command registration, categorization, discovery, and help generation.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Any, List

from modules.command_registry import CommandRegistry, CommandInfo, CommandCategory
from modules.command_processor import CommandProcessor


class TestCommandRegistry:
    """Test cases for CommandRegistry class."""
    
    @pytest.fixture
    def mock_command_processor(self):
        """Create a mock CommandProcessor."""
        processor = Mock(spec=CommandProcessor)
        processor.register_text_command = Mock(return_value=processor)
        return processor
    
    @pytest.fixture
    def command_registry(self, mock_command_processor):
        """Create a CommandRegistry instance for testing."""
        return CommandRegistry(mock_command_processor)
    
    @pytest.fixture
    def sample_command_info(self):
        """Create sample command info for testing."""
        async def sample_handler(update, context):
            pass
        
        return CommandInfo(
            name="test",
            description="Test command",
            category=CommandCategory.BASIC,
            handler_func=sample_handler,
            usage="/test",
            examples=["/test"]
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, command_registry):
        """Test CommandRegistry initialization."""
        await command_registry.initialize()
        
        assert command_registry._commands == {}
        assert all(len(commands) == 0 for commands in command_registry._categories.values())
        assert command_registry._aliases == {}
    
    @pytest.mark.asyncio
    async def test_shutdown(self, command_registry):
        """Test CommandRegistry shutdown."""
        # Add some test data
        command_registry._commands["test"] = Mock()
        command_registry._categories[CommandCategory.BASIC].add("test")
        command_registry._aliases["t"] = "test"
        
        await command_registry.shutdown()
        
        assert command_registry._commands == {}
        assert all(len(commands) == 0 for commands in command_registry._categories.values())
        assert command_registry._aliases == {}
    
    def test_register_command_basic(self, command_registry, sample_command_info, mock_command_processor):
        """Test basic command registration."""
        result = command_registry.register_command(sample_command_info)
        
        # Should return self for chaining
        assert result is command_registry
        
        # Command should be stored
        assert "test" in command_registry._commands
        assert command_registry._commands["test"] == sample_command_info
        
        # Category should be updated
        assert "test" in command_registry._categories[CommandCategory.BASIC]
        
        # Should register with CommandProcessor
        mock_command_processor.register_text_command.assert_called_once_with(
            command="test",
            handler_func=sample_command_info.handler_func,
            description="Test command",
            admin_only=False,
            group_only=False,
            private_only=False,
            rate_limit=None
        )
    
    def test_register_command_with_aliases(self, command_registry, mock_command_processor):
        """Test command registration with aliases."""
        async def handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="test",
            description="Test command",
            category=CommandCategory.BASIC,
            handler_func=handler,
            aliases=["t", "tst"]
        )
        
        command_registry.register_command(command_info)
        
        # Aliases should be stored
        assert command_registry._aliases["t"] == "test"
        assert command_registry._aliases["tst"] == "test"
        
        # Should register aliases with CommandProcessor
        assert mock_command_processor.register_text_command.call_count == 3  # main + 2 aliases
    
    def test_register_command_with_permissions(self, command_registry, mock_command_processor):
        """Test command registration with permission settings."""
        async def handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="admin_test",
            description="Admin test command",
            category=CommandCategory.ADMIN,
            handler_func=handler,
            admin_only=True,
            group_only=True,
            rate_limit=60
        )
        
        command_registry.register_command(command_info)
        
        # Should register with correct permissions
        mock_command_processor.register_text_command.assert_called_once_with(
            command="admin_test",
            handler_func=handler,
            description="Admin test command",
            admin_only=True,
            group_only=True,
            private_only=False,
            rate_limit=60
        )
    
    def test_register_duplicate_command(self, command_registry, sample_command_info):
        """Test registering a duplicate command (should overwrite)."""
        # Register first time
        command_registry.register_command(sample_command_info)
        
        # Register again with different description
        duplicate_info = CommandInfo(
            name="test",
            description="Updated test command",
            category=CommandCategory.UTILITY,
            handler_func=sample_command_info.handler_func
        )
        
        with patch('modules.command_registry.logger') as mock_logger:
            command_registry.register_command(duplicate_info)
            mock_logger.warning.assert_called_once()
        
        # Should be updated
        assert command_registry._commands["test"].description == "Updated test command"
        assert command_registry._commands["test"].category == CommandCategory.UTILITY
    
    @pytest.mark.asyncio
    @patch('modules.command_registry.logger')
    async def test_register_basic_commands(self, mock_logger, command_registry):
        """Test registration of basic commands."""
        with patch('modules.handlers.basic_commands.start_command') as mock_start, \
             patch('modules.handlers.basic_commands.help_command') as mock_help, \
             patch('modules.handlers.basic_commands.ping_command') as mock_ping:
            
            await command_registry.register_basic_commands()
            
            # Should register 3 basic commands
            basic_commands = command_registry.get_commands_by_category(CommandCategory.BASIC)
            assert len(basic_commands) == 3
            
            command_names = [cmd.name for cmd in basic_commands]
            assert "start" in command_names
            assert "help" in command_names
            assert "ping" in command_names
    
    @pytest.mark.asyncio
    @patch('modules.command_registry.logger')
    async def test_register_gpt_commands(self, mock_logger, command_registry):
        """Test registration of GPT commands."""
        with patch('modules.handlers.gpt_commands.ask_gpt_command') as mock_ask, \
             patch('modules.handlers.gpt_commands.analyze_command') as mock_analyze, \
             patch('modules.handlers.gpt_commands.mystats_command') as mock_stats:
            
            await command_registry.register_gpt_commands()
            
            # Should register 3 GPT commands
            gpt_commands = command_registry.get_commands_by_category(CommandCategory.GPT)
            assert len(gpt_commands) == 3
            
            command_names = [cmd.name for cmd in gpt_commands]
            assert "ask" in command_names
            assert "analyze" in command_names
            assert "mystats" in command_names
    
    @pytest.mark.asyncio
    @patch('modules.command_registry.logger')
    async def test_register_utility_commands(self, mock_logger, command_registry):
        """Test registration of utility commands."""
        with patch('modules.handlers.utility_commands.cat_command'), \
             patch('modules.handlers.utility_commands.screenshot_command'), \
             patch('modules.handlers.utility_commands.count_command'), \
             patch('modules.handlers.utility_commands.missing_command'), \
             patch('modules.handlers.utility_commands.error_report_command'):
            
            await command_registry.register_utility_commands()
            
            # Should register utility commands
            utility_commands = command_registry.get_commands_by_category(CommandCategory.UTILITY)
            admin_commands = command_registry.get_commands_by_category(CommandCategory.ADMIN)
            
            assert len(utility_commands) >= 4  # cat, flares, count, missing
            assert len(admin_commands) >= 1   # error_report
    
    @pytest.mark.asyncio
    @patch('modules.command_registry.logger')
    async def test_register_speech_commands(self, mock_logger, command_registry):
        """Test registration of speech commands."""
        with patch('modules.handlers.speech_commands.speech_command'):
            await command_registry.register_speech_commands()
            
            # Should register speech commands
            speech_commands = command_registry.get_commands_by_category(CommandCategory.SPEECH)
            assert len(speech_commands) == 1
            assert speech_commands[0].name == "speech"
            assert speech_commands[0].admin_only is True
    
    @pytest.mark.asyncio
    @patch('modules.command_registry.logger')
    async def test_register_all_commands(self, mock_logger, command_registry):
        """Test registration of all commands."""
        with patch.object(command_registry, 'register_basic_commands') as mock_basic, \
             patch.object(command_registry, 'register_gpt_commands') as mock_gpt, \
             patch.object(command_registry, 'register_utility_commands') as mock_utility, \
             patch.object(command_registry, 'register_speech_commands') as mock_speech:
            
            await command_registry.register_all_commands()
            
            # Should call all registration methods
            mock_basic.assert_called_once()
            mock_gpt.assert_called_once()
            mock_utility.assert_called_once()
            mock_speech.assert_called_once()
    
    def test_get_command_list(self, command_registry, sample_command_info):
        """Test getting list of all commands."""
        command_registry.register_command(sample_command_info)
        
        commands = command_registry.get_command_list()
        assert len(commands) == 1
        assert commands[0] == sample_command_info
    
    def test_get_commands_by_category(self, command_registry):
        """Test getting commands by category."""
        async def handler1(update, context):
            pass
        async def handler2(update, context):
            pass
        
        basic_cmd = CommandInfo("basic", "Basic command", CommandCategory.BASIC, handler1)
        gpt_cmd = CommandInfo("gpt", "GPT command", CommandCategory.GPT, handler2)
        
        command_registry.register_command(basic_cmd)
        command_registry.register_command(gpt_cmd)
        
        basic_commands = command_registry.get_commands_by_category(CommandCategory.BASIC)
        gpt_commands = command_registry.get_commands_by_category(CommandCategory.GPT)
        
        assert len(basic_commands) == 1
        assert len(gpt_commands) == 1
        assert basic_commands[0].name == "basic"
        assert gpt_commands[0].name == "gpt"
    
    def test_get_command_info(self, command_registry, sample_command_info):
        """Test getting command information."""
        command_registry.register_command(sample_command_info)
        
        # Test getting by name
        info = command_registry.get_command_info("test")
        assert info == sample_command_info
        
        # Test non-existent command
        info = command_registry.get_command_info("nonexistent")
        assert info is None
    
    def test_get_command_info_by_alias(self, command_registry):
        """Test getting command information by alias."""
        async def handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="test",
            description="Test command",
            category=CommandCategory.BASIC,
            handler_func=handler,
            aliases=["t"]
        )
        
        command_registry.register_command(command_info)
        
        # Should work with alias
        info = command_registry.get_command_info("t")
        assert info is not None
        assert info.name == "test"
    
    def test_get_command_names(self, command_registry, sample_command_info):
        """Test getting command names."""
        command_registry.register_command(sample_command_info)
        
        names = command_registry.get_command_names()
        assert "test" in names
        assert len(names) == 1
    
    def test_get_command_names_by_category(self, command_registry, sample_command_info):
        """Test getting command names by category."""
        command_registry.register_command(sample_command_info)
        
        basic_names = command_registry.get_command_names_by_category(CommandCategory.BASIC)
        gpt_names = command_registry.get_command_names_by_category(CommandCategory.GPT)
        
        assert "test" in basic_names
        assert len(basic_names) == 1
        assert len(gpt_names) == 0
    
    def test_get_help_text_all_commands(self, command_registry):
        """Test generating help text for all commands."""
        async def handler(update, context):
            pass
        
        basic_cmd = CommandInfo("basic", "Basic command", CommandCategory.BASIC, handler)
        gpt_cmd = CommandInfo("gpt", "GPT command", CommandCategory.GPT, handler)
        
        command_registry.register_command(basic_cmd)
        command_registry.register_command(gpt_cmd)
        
        help_text = command_registry.get_help_text()
        
        assert "All Commands" in help_text
        assert "Basic:" in help_text
        assert "Gpt:" in help_text
        assert "/basic - Basic command" in help_text
        assert "/gpt - GPT command" in help_text
    
    def test_get_help_text_single_category(self, command_registry):
        """Test generating help text for a single category."""
        async def handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="test",
            description="Test command",
            category=CommandCategory.BASIC,
            handler_func=handler,
            aliases=["t"],
            usage="/test <arg>",
            examples=["/test hello"],
            admin_only=True
        )
        
        command_registry.register_command(command_info)
        
        help_text = command_registry.get_help_text(CommandCategory.BASIC)
        
        assert "Basic Commands" in help_text
        assert "/test (/t) - Test command [Admin Only]" in help_text
        assert "Usage: /test <arg>" in help_text
        assert "Examples: /test hello" in help_text
    
    def test_get_help_text_empty_category(self, command_registry):
        """Test generating help text for empty category."""
        help_text = command_registry.get_help_text(CommandCategory.BASIC)
        assert "No commands found" in help_text
    
    def test_get_categories(self, command_registry):
        """Test getting list of categories."""
        categories = command_registry.get_categories()
        assert CommandCategory.BASIC in categories
        assert CommandCategory.GPT in categories
        assert CommandCategory.UTILITY in categories
        assert CommandCategory.SPEECH in categories
        assert CommandCategory.ADMIN in categories
    
    def test_get_category_stats(self, command_registry, sample_command_info):
        """Test getting category statistics."""
        command_registry.register_command(sample_command_info)
        
        stats = command_registry.get_category_stats()
        
        assert stats[CommandCategory.BASIC] == 1
        assert stats[CommandCategory.GPT] == 0
        assert stats[CommandCategory.UTILITY] == 0
        assert stats[CommandCategory.SPEECH] == 0
        assert stats[CommandCategory.ADMIN] == 0
    
    def test_search_commands(self, command_registry):
        """Test searching for commands."""
        async def handler(update, context):
            pass
        
        cmd1 = CommandInfo("test", "Test command", CommandCategory.BASIC, handler)
        cmd2 = CommandInfo("help", "Help with testing", CommandCategory.BASIC, handler)
        cmd3 = CommandInfo("other", "Other command", CommandCategory.UTILITY, handler, aliases=["test_alias"])
        
        command_registry.register_command(cmd1)
        command_registry.register_command(cmd2)
        command_registry.register_command(cmd3)
        
        # Search by name - should find "test" command, "help" (contains "test" in description), and "other" (has "test_alias")
        results = command_registry.search_commands("test")
        assert len(results) == 3  # "test" command, "help" with "testing" in description, and "other" with "test_alias"
        
        # Search by description
        results = command_registry.search_commands("help")
        assert len(results) == 1
        assert results[0].name == "help"
        
        # Search with no results
        results = command_registry.search_commands("nonexistent")
        assert len(results) == 0
    
    def test_validate_command_registration(self, command_registry):
        """Test command registration validation."""
        async def valid_handler(update, context):
            pass
        
        # Add valid command
        valid_cmd = CommandInfo("valid", "Valid command", CommandCategory.BASIC, valid_handler)
        command_registry.register_command(valid_cmd)
        
        # Add command with invalid handler
        invalid_cmd = CommandInfo("invalid", "Invalid command", CommandCategory.BASIC, "not_a_function")
        command_registry._commands["invalid"] = invalid_cmd
        command_registry._categories[CommandCategory.BASIC].add("invalid")
        
        # Add orphaned alias
        command_registry._aliases["orphan"] = "nonexistent"
        
        # Add orphaned category entry
        command_registry._categories[CommandCategory.GPT].add("missing_command")
        
        issues = command_registry.validate_command_registration()
        
        assert len(issues) >= 3
        assert any("invalid handler function" in issue for issue in issues)
        assert any("points to non-existent command" in issue for issue in issues)
        assert any("non-existent command" in issue for issue in issues)
    
    def test_validate_command_registration_clean(self, command_registry, sample_command_info):
        """Test validation with clean registration."""
        command_registry.register_command(sample_command_info)
        
        issues = command_registry.validate_command_registration()
        assert len(issues) == 0


class TestCommandInfo:
    """Test cases for CommandInfo dataclass."""
    
    def test_command_info_creation(self):
        """Test CommandInfo creation with minimal parameters."""
        async def handler(update, context):
            pass
        
        cmd_info = CommandInfo(
            name="test",
            description="Test command",
            category=CommandCategory.BASIC,
            handler_func=handler
        )
        
        assert cmd_info.name == "test"
        assert cmd_info.description == "Test command"
        assert cmd_info.category == CommandCategory.BASIC
        assert cmd_info.handler_func == handler
        assert cmd_info.admin_only is False
        assert cmd_info.group_only is False
        assert cmd_info.private_only is False
        assert cmd_info.rate_limit is None
        assert cmd_info.aliases == []
        assert cmd_info.usage is None
        assert cmd_info.examples == []
    
    def test_command_info_with_all_parameters(self):
        """Test CommandInfo creation with all parameters."""
        async def handler(update, context):
            pass
        
        cmd_info = CommandInfo(
            name="test",
            description="Test command",
            category=CommandCategory.ADMIN,
            handler_func=handler,
            admin_only=True,
            group_only=True,
            private_only=False,
            rate_limit=60,
            aliases=["t", "tst"],
            usage="/test <arg>",
            examples=["/test hello", "/test world"]
        )
        
        assert cmd_info.admin_only is True
        assert cmd_info.group_only is True
        assert cmd_info.private_only is False
        assert cmd_info.rate_limit == 60
        assert cmd_info.aliases == ["t", "tst"]
        assert cmd_info.usage == "/test <arg>"
        assert cmd_info.examples == ["/test hello", "/test world"]


class TestCommandCategory:
    """Test cases for CommandCategory enum."""
    
    def test_command_categories(self):
        """Test that all expected categories exist."""
        assert CommandCategory.BASIC.value == "basic"
        assert CommandCategory.GPT.value == "gpt"
        assert CommandCategory.UTILITY.value == "utility"
        assert CommandCategory.SPEECH.value == "speech"
        assert CommandCategory.ADMIN.value == "admin"
    
    def test_category_enumeration(self):
        """Test that we can enumerate all categories."""
        categories = list(CommandCategory)
        assert len(categories) == 5
        assert CommandCategory.BASIC in categories
        assert CommandCategory.GPT in categories
        assert CommandCategory.UTILITY in categories
        assert CommandCategory.SPEECH in categories
        assert CommandCategory.ADMIN in categories