# Psychochauffeur Bot Configuration System

This directory contains the configuration system for the Psychochauffeur bot. The system is designed to manage chat-specific configurations with a hierarchical structure and operates asynchronously.

## Directory Structure

- `global/`: Contains default configuration settings applicable to all chats
  - `main_config.json`: The base configuration file with default values
  - `{module_name}_config.json`: Module-specific default configurations
- `private/`: Contains configuration settings for private chats
  - Files are named as `{chat_id}.json`
- `group/`: Contains configuration settings for group chats
  - Files are named as `{chat_id}.json`
- `backups/`: Contains backup files of chat configurations
  - Files are named as `{chat_id}_{timestamp}.json`

## Configuration Files

### Chat Configuration Structure

Each chat configuration file follows this structure:

```json
{
  "chat_metadata": {
    "chat_id": "string",
    "chat_type": "private|group",
    "chat_name": "string",
    "created_at": "YYYY-MM-DD HH:MM:SS.ffffff",
    "last_updated": "YYYY-MM-DD HH:MM:SS.ffffff",
    "custom_config_enabled": false
  },
  "config_modules": {
    "gpt": {
      "enabled": false,
      "overrides": {
        "command": {
          "max_tokens": 1500,
          "temperature": 0.6,
          "presence_penalty": 0.0,
          "frequency_penalty": 0.0,
          "model": "gpt-4.1-mini",
          "system_prompt": "string"
        },
        "mention": { ... },
        "random": { ... },
        "weather": { ... },
        "analyze": { ... },
        "image_analysis": { ... },
        "summary": { ... }
      }
    },
    "chat_behavior": {
      "enabled": false,
      "overrides": {
        "restrictions_enabled": false,
        "max_message_length": 2048,
        "rate_limit": {
          "messages_per_minute": 20,
          "burst_limit": 5
        },
        "allowed_commands": ["string"],
        "ban_words": ["string"],
        "ban_symbols": ["string"]
      }
    },
    "safety": {
      "enabled": false,
      "overrides": {
        "content_filter_level": "medium",
        "profanity_filter_enabled": false,
        "sensitive_content_warning_enabled": false
      }
    }
  }
}
```

## Using the ConfigManager

The `ConfigManager` class provides an asynchronous interface for managing configurations. Here's how to use it:

```python
from config.config_manager import ConfigManager

# Create an instance
config_manager = ConfigManager()

# Get chat configuration
chat_config = await config_manager.get_config(
    chat_id="12345",
    chat_type="private"
)

# Enable/disable custom configuration
await config_manager.enable_custom_config(chat_id, chat_type)
await config_manager.disable_custom_config(chat_id, chat_type)

# Enable/disable specific modules
await config_manager.enable_module(chat_id, chat_type, "gpt")
await config_manager.disable_module(chat_id, chat_type, "gpt")

# Update module settings
await config_manager.update_module_setting(
    module_name="gpt",
    setting_path="command.temperature",
    value=0.8,
    chat_id=chat_id,
    chat_type=chat_type
)

# Get module setting
temperature = await config_manager.get_module_setting(
    module_name="gpt",
    setting_path="command.temperature",
    chat_id=chat_id,
    chat_type=chat_type,
    default=0.7
)

# Create backup
await config_manager.backup_config(chat_id, chat_type)
```

## Bot Commands

The bot provides the following commands for managing configurations:

- `/config` - Show current configuration status and available commands
- `/config enable` - Enable custom configuration for the chat
- `/config disable` - Disable custom configuration (use global settings)
- `/config enable_module <module>` - Enable a specific module
- `/config disable_module <module>` - Disable a specific module
- `/config modules` - List available modules and their status
- `/config backup` - Create a backup of current configuration
- `/config restore [timestamp]` - Restore from backup (most recent if no timestamp)
- `/config list` - List available backups

## Best Practices

1. Always use the `ConfigManager` class to access and modify configurations
2. Keep the global configuration minimal and use chat-specific overrides for customization
3. Use meaningful names for GPT prompts and other settings
4. Document any custom settings added to chat-specific configurations
5. Regularly backup configuration files
6. Use the async methods to prevent blocking operations
7. Set `custom_config_enabled` to `false` by default for new chats
8. Enable modules only when needed to maintain performance

## Error Handling

The `ConfigManager` includes error handling for:
- File not found errors
- JSON parsing errors
- File permission errors
- Concurrent access conflicts
- Invalid module names
- Invalid setting paths

## Dependencies

- Python 3.7+
- aiofiles
- asyncio
- pathlib
- typing

## Security Considerations

1. Only administrators can modify group chat configurations
2. Private chat configurations can only be modified by the chat owner
3. All file operations are performed with proper locking to prevent race conditions
4. Configuration files are stored with proper permissions
5. Sensitive settings should be stored in environment variables, not in configuration files

## Performance Considerations

1. Module configurations are cached to reduce file I/O
2. File operations are performed asynchronously
3. Configuration files are loaded only when needed
4. Backups are created before major changes
5. The system uses file locking to prevent concurrent modifications