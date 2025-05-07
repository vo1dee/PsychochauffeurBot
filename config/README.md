# Configuration System

This directory contains the configuration system for the Psychochauffeur bot. The system is designed to manage chat-specific configurations with a hierarchical structure and operates asynchronously.

## Directory Structure

- `global/`: Contains default configuration settings applicable to all chats
  - `default_settings.json`: The base configuration file with default values
- `private/`: Contains configuration settings for private chats
  - Files are named as `{chat_id}.json`
- `group/`: Contains configuration settings for group chats
  - Files are named as `{chat_id}.json`

## Configuration Files

### Global Configuration (`global/default_settings.json`)

The global configuration file contains default settings that apply to all chats unless overridden. It includes:

- GPT prompts
- Restriction triggers
- Chat settings
- Response settings
- Safety settings

### Chat-Specific Configuration

Chat-specific configuration files can override any setting from the global configuration. They are stored in either the `private/` or `group/` directory, depending on the chat type.

## Using the ConfigManager

The `ConfigManager` class provides an asynchronous interface for managing configurations. Here's how to use it:

```python
from config.config_manager_async import ConfigManager

# Create an instance
config_manager = ConfigManager()

# Get global configuration
global_config = await config_manager.get_config()

# Get chat-specific configuration
chat_config = await config_manager.get_config(
    chat_id="12345",
    chat_type="private"
)

# Update a setting
await config_manager.update_setting(
    key="response_settings.temperature",
    value=0.9,
    chat_id="12345",
    chat_type="private"
)

# Add to a list setting
await config_manager.add_to_list(
    key="gpt_prompts",
    value={
        "name": "new_prompt",
        "content": "You are a new prompt.",
        "description": "A new prompt"
    },
    chat_id="12345",
    chat_type="private"
)

# Remove from a list setting
await config_manager.remove_from_list(
    key="gpt_prompts",
    value="new_prompt",
    chat_id="12345",
    chat_type="private"
)
```

## Configuration Schema

### Global Configuration Schema

```json
{
  "gpt_prompts": [
    {
      "name": "string",
      "content": "string",
      "description": "string"
    }
  ],
  "restriction_triggers": {
    "keywords": ["string"],
    "patterns": ["string"]
  },
  "chat_settings": {
    "max_message_length": "number",
    "rate_limit": {
      "messages_per_minute": "number",
      "burst_limit": "number"
    },
    "allowed_commands": ["string"]
  },
  "response_settings": {
    "max_tokens": "number",
    "temperature": "number",
    "presence_penalty": "number",
    "frequency_penalty": "number"
  },
  "safety_settings": {
    "content_filter": "boolean",
    "profanity_filter": "boolean",
    "sensitive_content_warning": "boolean"
  }
}
```

## Best Practices

1. Always use the `ConfigManager` class to access and modify configurations
2. Keep the global configuration minimal and use chat-specific overrides for customization
3. Use meaningful names for GPT prompts and other settings
4. Document any custom settings added to chat-specific configurations
5. Regularly backup configuration files
6. Use the async methods to prevent blocking operations

## Error Handling

The `ConfigManager` includes error handling for:
- File not found errors
- JSON parsing errors
- File permission errors
- Concurrent access conflicts

## Dependencies

- Python 3.7+
- aiofiles
- asyncio