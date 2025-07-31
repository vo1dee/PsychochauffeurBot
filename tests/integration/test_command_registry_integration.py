"""
Integration tests for CommandRegistry.

Tests integration between CommandRegistry and CommandProcessor.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch

from modules.command_registry import CommandRegistry, CommandInfo, CommandCategory
from modules.command_processor import CommandProcessor


class TestCommandRegistryIntegration:
    """Integration tests for CommandRegistry with CommandProcessor."""
    
    @pytest.fixture
    def command_processor(self):
        """Create a real CommandProcessor instance."""
        return CommandProcessor()
    
    @pytest.fixture
    def command_registry(self, command_processor):
        """Create a CommandRegistry with real CommandProcessor."""
        return CommandRegistry(command_processor)
    
    @pytest.mark.asyncio
    async def test_command_registration_integration(self, command_registry, command_processor):
        """Test that commands are properly registered with CommandProcessor."""
        async def test_handler(update, context):
            pass
        
        # Register a command
        command_info = CommandInfo(
            name="integration_test",
            description="Integration test command",
            category=CommandCategory.BASIC,
            handler_func=test_handler,
            aliases=["itest"]
        )
        
        command_registry.register_command(command_info)
        
        # Verify command is registered in CommandProcessor
        registered_commands = command_processor.get_registered_commands()
        assert "integration_test" in registered_commands
        assert "itest" in registered_commands  # alias should also be registered
        
        # Verify command metadata
        cmd_info = command_processor.get_command_info("integration_test")
        assert cmd_info is not None
        assert cmd_info.name == "integration_test"
        assert cmd_info.description == "Integration test command"
    
    @pytest.mark.asyncio
    async def test_telegram_handlers_integration(self, command_registry, command_processor):
        """Test that Telegram handlers are created properly."""
        async def test_handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="telegram_test",
            description="Telegram handler test",
            category=CommandCategory.UTILITY,
            handler_func=test_handler
        )
        
        command_registry.register_command(command_info)
        
        # Get Telegram handlers
        telegram_handlers = command_processor.get_telegram_handlers()
        
        # Should have at least one handler for our command
        assert len(telegram_handlers) >= 1
        
        # Verify handler type
        from telegram.ext import CommandHandler
        command_handlers = [h for h in telegram_handlers if isinstance(h, CommandHandler)]
        assert len(command_handlers) >= 1
    
    @pytest.mark.asyncio
    async def test_full_command_registration_flow(self, command_registry):
        """Test the complete command registration flow."""
        # Mock the command handlers to avoid import issues
        with patch('modules.handlers.basic_commands.start_command') as mock_start, \
             patch('modules.handlers.basic_commands.help_command') as mock_help, \
             patch('modules.handlers.basic_commands.ping_command') as mock_ping:
            
            # Register basic commands
            await command_registry.register_basic_commands()
            
            # Verify commands are registered
            basic_commands = command_registry.get_commands_by_category(CommandCategory.BASIC)
            assert len(basic_commands) == 3
            
            # Verify CommandProcessor has the commands
            processor_commands = command_registry.command_processor.get_registered_commands()
            assert "start" in processor_commands
            assert "help" in processor_commands
            assert "ping" in processor_commands
    
    @pytest.mark.asyncio
    async def test_command_permissions_integration(self, command_registry, command_processor):
        """Test that command permissions are properly passed to CommandProcessor."""
        async def admin_handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="admin_command",
            description="Admin only command",
            category=CommandCategory.ADMIN,
            handler_func=admin_handler,
            admin_only=True,
            group_only=True,
            rate_limit=60
        )
        
        command_registry.register_command(command_info)
        
        # Verify permissions are set in CommandProcessor
        cmd_metadata = command_processor.get_command_info("admin_command")
        assert cmd_metadata is not None
        assert cmd_metadata.admin_only is True
        assert cmd_metadata.group_only is True
        assert cmd_metadata.rate_limit == 60
    
    @pytest.mark.asyncio
    async def test_service_lifecycle_integration(self, command_registry, command_processor):
        """Test service initialization and shutdown."""
        # Initialize both services
        await command_processor.initialize()
        await command_registry.initialize()
        
        # Register a command
        async def lifecycle_handler(update, context):
            pass
        
        command_info = CommandInfo(
            name="lifecycle_test",
            description="Lifecycle test command",
            category=CommandCategory.BASIC,
            handler_func=lifecycle_handler
        )
        
        command_registry.register_command(command_info)
        
        # Verify command is registered
        assert "lifecycle_test" in command_processor.get_registered_commands()
        
        # Shutdown services
        await command_registry.shutdown()
        await command_processor.shutdown()
        
        # Verify cleanup
        assert len(command_registry._commands) == 0
        assert len(command_processor._handlers) == 0