"""
Command Registry for centralized command management.

This module provides a centralized registry for managing bot commands,
including registration, categorization, and metadata management.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from telegram import Update
from telegram.ext import CallbackContext

from modules.command_processor import CommandProcessor, CommandMetadata, CommandType
from modules.service_registry import ServiceInterface

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Categories for organizing commands."""
    BASIC = "basic"
    GPT = "gpt"
    UTILITY = "utility"
    SPEECH = "speech"
    ADMIN = "admin"


@dataclass
class CommandInfo:
    """Extended command information with categorization."""
    name: str
    description: str
    category: CommandCategory
    handler_func: Callable[..., Any]
    admin_only: bool = False
    group_only: bool = False
    private_only: bool = False
    rate_limit: Optional[int] = None
    aliases: List[str] = field(default_factory=list)
    usage: Optional[str] = None
    examples: List[str] = field(default_factory=list)


class CommandRegistry(ServiceInterface):
    """
    Centralized command registry for managing bot commands.
    
    Provides command registration, categorization, discovery, and help generation.
    Integrates with the existing CommandProcessor for actual command handling.
    """
    
    def __init__(self, command_processor: CommandProcessor) -> None:
        """Initialize the command registry."""
        self.command_processor = command_processor
        self._commands: Dict[str, CommandInfo] = {}
        self._categories: Dict[CommandCategory, Set[str]] = {
            category: set() for category in CommandCategory
        }
        self._aliases: Dict[str, str] = {}  # alias -> command_name mapping
        
    async def initialize(self) -> None:
        """Initialize the command registry."""
        logger.info("Command Registry initialized")
        
    async def shutdown(self) -> None:
        """Shutdown the command registry."""
        self._commands.clear()
        self._categories.clear()
        self._aliases.clear()
        logger.info("Command Registry shutdown")
    
    def register_command(self, command_info: CommandInfo) -> 'CommandRegistry':
        """Register a single command with the registry."""
        command_name = command_info.name
        
        # Check for duplicate registration
        if command_name in self._commands:
            logger.warning(f"Command '{command_name}' is already registered, overwriting")
        
        # Store command info
        self._commands[command_name] = command_info
        self._categories[command_info.category].add(command_name)
        
        # Register aliases
        for alias in command_info.aliases:
            if alias in self._aliases:
                logger.warning(f"Alias '{alias}' is already registered for command '{self._aliases[alias]}', overwriting")
            self._aliases[alias] = command_name
        
        # Register with CommandProcessor
        self.command_processor.register_text_command(
            command=command_name,
            handler_func=command_info.handler_func,
            description=command_info.description,
            admin_only=command_info.admin_only,
            group_only=command_info.group_only,
            private_only=command_info.private_only,
            rate_limit=command_info.rate_limit
        )
        
        # Register aliases with CommandProcessor
        for alias in command_info.aliases:
            self.command_processor.register_text_command(
                command=alias,
                handler_func=command_info.handler_func,
                description=f"Alias for /{command_name}",
                admin_only=command_info.admin_only,
                group_only=command_info.group_only,
                private_only=command_info.private_only,
                rate_limit=command_info.rate_limit
            )
        
        logger.info(f"Registered command: /{command_name} (category: {command_info.category.value})")
        if command_info.aliases:
            logger.info(f"  Aliases: {', '.join(f'/{alias}' for alias in command_info.aliases)}")
        
        return self
    
    async def register_all_commands(self) -> None:
        """Register all bot commands organized by category."""
        await self.register_basic_commands()
        await self.register_gpt_commands()
        await self.register_utility_commands()
        await self.register_speech_commands()
        
        logger.info(f"Registered {len(self._commands)} commands across {len(CommandCategory)} categories")
    
    async def register_basic_commands(self) -> None:
        """Register basic bot commands."""
        from modules.handlers.basic_commands import start_command, help_command, ping_command
        
        # Start command
        self.register_command(CommandInfo(
            name="start",
            description="Start the bot and show welcome message",
            category=CommandCategory.BASIC,
            handler_func=start_command,
            usage="/start",
            examples=["/start"]
        ))
        
        # Help command (alias for start)
        self.register_command(CommandInfo(
            name="help",
            description="Show help information",
            category=CommandCategory.BASIC,
            handler_func=help_command,
            usage="/help",
            examples=["/help"]
        ))
        
        # Ping command
        self.register_command(CommandInfo(
            name="ping",
            description="Check if the bot is responsive",
            category=CommandCategory.BASIC,
            handler_func=ping_command,
            usage="/ping",
            examples=["/ping"]
        ))
        
        logger.info("Registered basic commands")
    
    async def register_gpt_commands(self) -> None:
        """Register GPT-related commands."""
        from modules.handlers.gpt_commands import ask_gpt_command, analyze_command, mystats_command
        
        # Ask GPT command
        self.register_command(CommandInfo(
            name="ask",
            description="Ask GPT a question",
            category=CommandCategory.GPT,
            handler_func=ask_gpt_command,
            usage="/ask <question>",
            examples=["/ask What is the weather like?", "/ask Explain quantum physics"]
        ))
        
        # Analyze command
        self.register_command(CommandInfo(
            name="analyze",
            description="Analyze content with GPT",
            category=CommandCategory.GPT,
            handler_func=analyze_command,
            usage="/analyze <content>",
            examples=["/analyze This is some text to analyze"]
        ))
        
        # My stats command
        self.register_command(CommandInfo(
            name="mystats",
            description="Show your usage statistics",
            category=CommandCategory.GPT,
            handler_func=mystats_command,
            usage="/mystats",
            examples=["/mystats"]
        ))
        
        logger.info("Registered GPT commands")
    
    async def register_utility_commands(self) -> None:
        """Register utility commands."""
        from modules.handlers.utility_commands import (
            cat_command, screenshot_command, count_command, 
            missing_command, error_report_command
        )
        from modules.weather import WeatherCommandHandler
        from modules.geomagnetic import GeomagneticCommandHandler
        from modules.reminders.reminders import ReminderManager
        
        # Cat command
        self.register_command(CommandInfo(
            name="cat",
            description="Get a random cat photo",
            category=CommandCategory.UTILITY,
            handler_func=cat_command,
            usage="/cat",
            examples=["/cat"]
        ))
        
        # Screenshot/flares command
        self.register_command(CommandInfo(
            name="flares",
            description="Get solar flares screenshot",
            category=CommandCategory.UTILITY,
            handler_func=screenshot_command,
            usage="/flares",
            examples=["/flares"]
        ))
        
        # Count command
        self.register_command(CommandInfo(
            name="count",
            description="Count messages in the chat",
            category=CommandCategory.UTILITY,
            handler_func=count_command,
            usage="/count",
            examples=["/count"]
        ))
        
        # Missing command
        self.register_command(CommandInfo(
            name="missing",
            description="Show missing features",
            category=CommandCategory.UTILITY,
            handler_func=missing_command,
            usage="/missing",
            examples=["/missing"]
        ))
        
        # Weather command (class-based handler)
        weather_handler = WeatherCommandHandler()
        self.register_command(CommandInfo(
            name="weather",
            description="Get weather information for a city",
            category=CommandCategory.UTILITY,
            handler_func=weather_handler,
            usage="/weather <city>",
            examples=["/weather London", "/weather New York"]
        ))
        
        # Geomagnetic command (class-based handler)
        geomagnetic_handler = GeomagneticCommandHandler()
        self.register_command(CommandInfo(
            name="gm",
            description="Get geomagnetic activity information",
            category=CommandCategory.UTILITY,
            handler_func=geomagnetic_handler,
            usage="/gm",
            examples=["/gm"]
        ))
        
        # Reminder command (class-based handler)
        reminder_manager = ReminderManager()
        self.register_command(CommandInfo(
            name="remind",
            description="Set a reminder",
            category=CommandCategory.UTILITY,
            handler_func=reminder_manager.remind,
            usage="/remind <time> <message>",
            examples=["/remind 10m Take a break", "/remind tomorrow 9am Meeting"]
        ))
        
        # Error report command
        self.register_command(CommandInfo(
            name="error_report",
            description="Generate error report",
            category=CommandCategory.ADMIN,
            handler_func=error_report_command,
            admin_only=True,
            usage="/error_report",
            examples=["/error_report"]
        ))
        
        logger.info("Registered utility commands")
    
    async def register_speech_commands(self) -> None:
        """Register speech recognition commands."""
        from modules.handlers.speech_commands import speech_command
        
        # Speech command
        self.register_command(CommandInfo(
            name="speech",
            description="Toggle speech recognition on/off",
            category=CommandCategory.SPEECH,
            handler_func=speech_command,
            admin_only=True,
            usage="/speech <on|off>",
            examples=["/speech on", "/speech off"]
        ))
        
        logger.info("Registered speech commands")
    
    def get_command_list(self) -> List[CommandInfo]:
        """Get list of all registered commands."""
        return list(self._commands.values())
    
    def get_commands_by_category(self, category: CommandCategory) -> List[CommandInfo]:
        """Get all commands in a specific category."""
        command_names = self._categories.get(category, set())
        return [self._commands[name] for name in command_names if name in self._commands]
    
    def get_command_info(self, command_name: str) -> Optional[CommandInfo]:
        """Get information about a specific command."""
        # Check if it's an alias first
        if command_name in self._aliases:
            command_name = self._aliases[command_name]
        
        return self._commands.get(command_name)
    
    def get_command_names(self) -> List[str]:
        """Get list of all command names."""
        return list(self._commands.keys())
    
    def get_command_names_by_category(self, category: CommandCategory) -> List[str]:
        """Get command names for a specific category."""
        return list(self._categories.get(category, set()))
    
    def get_help_text(self, category: Optional[CommandCategory] = None) -> str:
        """Generate help text for commands."""
        if category:
            commands = self.get_commands_by_category(category)
            title = f"{category.value.title()} Commands"
        else:
            commands = self.get_command_list()
            title = "All Commands"
        
        if not commands:
            return f"No commands found for {title.lower()}."
        
        help_lines = [f"📋 {title}:\n"]
        
        # Group by category if showing all commands
        if not category:
            for cat in CommandCategory:
                cat_commands = self.get_commands_by_category(cat)
                if cat_commands:
                    help_lines.append(f"\n🔹 {cat.value.title()}:")
                    for cmd in sorted(cat_commands, key=lambda x: x.name):
                        help_lines.append(f"  /{cmd.name} - {cmd.description}")
        else:
            # Show detailed info for single category
            for cmd in sorted(commands, key=lambda x: x.name):
                cmd_line = f"/{cmd.name}"
                if cmd.aliases:
                    cmd_line += f" ({', '.join(f'/{alias}' for alias in cmd.aliases)})"
                cmd_line += f" - {cmd.description}"
                
                if cmd.admin_only:
                    cmd_line += " [Admin Only]"
                if cmd.group_only:
                    cmd_line += " [Groups Only]"
                if cmd.private_only:
                    cmd_line += " [Private Only]"
                
                help_lines.append(cmd_line)
                
                if cmd.usage:
                    help_lines.append(f"  Usage: {cmd.usage}")
                if cmd.examples:
                    help_lines.append(f"  Examples: {', '.join(cmd.examples)}")
                help_lines.append("")  # Empty line between commands
        
        return "\n".join(help_lines)
    
    def get_categories(self) -> List[CommandCategory]:
        """Get list of all command categories."""
        return list(CommandCategory)
    
    def get_category_stats(self) -> Dict[CommandCategory, int]:
        """Get statistics about commands per category."""
        return {
            category: len(command_names) 
            for category, command_names in self._categories.items()
        }
    
    def search_commands(self, query: str) -> List[CommandInfo]:
        """Search for commands by name or description."""
        query_lower = query.lower()
        results = []
        
        for command_info in self._commands.values():
            # Search in name
            if query_lower in command_info.name.lower():
                results.append(command_info)
                continue
            
            # Search in description
            if query_lower in command_info.description.lower():
                results.append(command_info)
                continue
            
            # Search in aliases
            if any(query_lower in alias.lower() for alias in command_info.aliases):
                results.append(command_info)
                continue
        
        return results
    
    def validate_command_registration(self) -> List[str]:
        """Validate command registration and return any issues found."""
        issues = []
        
        # Check for commands without handlers
        for name, command_info in self._commands.items():
            if not callable(command_info.handler_func):
                issues.append(f"Command '{name}' has invalid handler function")
        
        # Check for orphaned aliases
        for alias, command_name in self._aliases.items():
            if command_name not in self._commands:
                issues.append(f"Alias '{alias}' points to non-existent command '{command_name}'")
        
        # Check category consistency
        for category, command_names in self._categories.items():
            for command_name in command_names:
                if command_name not in self._commands:
                    issues.append(f"Category '{category.value}' contains non-existent command '{command_name}'")
                elif self._commands[command_name].category != category:
                    issues.append(f"Command '{command_name}' category mismatch")
        
        return issues