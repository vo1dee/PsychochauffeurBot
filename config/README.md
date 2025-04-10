# Configuration System for PsychochauffeurBot

This directory contains configurations for the PsychochauffeurBot, supporting both default settings and chat-specific overrides.

## Directory Structure

- `default/` - Default configurations used when no chat-specific config exists
- `private_chats/` - Private chat-specific configurations (organized by user ID)
- `group_chats/` - Group chat-specific configurations (organized by chat ID)
- `config_manager.py` - Configuration management system
- `default/examples/` - Example configuration files

## Configuration Types

### GPT Prompts (`gpt_prompts.py`)
Contains system prompts used for different GPT interactions:
- `gpt_response` - Regular GPT responses
- `gpt_response_return_text` - Direct text-only responses
- `gpt_summary` - Chat message summarization
- `get_word_from_gpt` - Word game responses

### Weather Configuration (`weather_config.py`)
Contains weather-related settings:
- `CITY_TRANSLATIONS` - Map of Ukrainian city names to English equivalents
- `CONDITION_EMOJIS` - Weather condition ID ranges mapped to emojis
- `FEELS_LIKE_EMOJIS` - Temperature ranges mapped to appropriate emojis

## Creating Chat-Specific Configurations

1. Create a directory with the chat ID under the appropriate directory:
   ```
   # For private chats:
   mkdir -p config/private_chats/{user_id}
   
   # For group chats:
   mkdir -p config/group_chats/{chat_id}
   ```

2. Create a configuration file matching one of the default configs:
   ```
   # Example for custom GPT prompts in a private chat:
   vim config/private_chats/{user_id}/gpt_prompts.py
   
   # Example for custom GPT prompts in a group chat:
   vim config/group_chats/{chat_id}/gpt_prompts.py
   ```

3. Add your custom configuration following the standard format (see examples in `default/examples/`).

Note: The system will automatically create these configuration files for new chats, copying the default settings.

## Usage

The configuration system automatically merges default and chat-specific settings, prioritizing chat-specific values when available.

In code, access configurations using:

```python
from config.config_manager import ConfigManager

# Get configuration (automatically uses chat-specific if available)
# chat_type should be 'private' or 'group'
prompts = ConfigManager.get_config("gpt_prompts", chat_id, chat_type)

# Access a specific prompt
system_prompt = prompts["gpt_response"]
```