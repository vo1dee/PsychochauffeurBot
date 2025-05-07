"""Asynchronous configuration manager for handling default and chat-specific configurations."""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, Literal, List, Union
import aiofiles
from pathlib import Path
import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration for the bot, supporting default and chat-specific JSON settings."""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.GLOBAL_CONFIG_DIR = self.base_dir / 'config' / 'global'
        self.PRIVATE_CONFIG_DIR = self.base_dir / 'config' / 'private'
        self.GROUP_CONFIG_DIR = self.base_dir / 'config' / 'group'
        self._file_locks: Dict[str, asyncio.Lock] = {}
        logger.info(f"ConfigManager initialized with base_dir: {self.base_dir}")

    async def ensure_dirs(self) -> None:
        """Ensure that base directories for configuration exist."""
        for d in (self.GLOBAL_CONFIG_DIR, self.PRIVATE_CONFIG_DIR, self.GROUP_CONFIG_DIR):
            d.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {d}")

    def _get_chat_config_path(self, chat_id: str, chat_type: str) -> Path:
        """Get the path for a chat's configuration file."""
        base = self.PRIVATE_CONFIG_DIR if chat_type == 'private' else self.GROUP_CONFIG_DIR
        path = base / f"{chat_id}.json"
        logger.info(f"Generated chat config path: {path} for chat_id: {chat_id}, type: {chat_type}")
        return path

    def _get_lock(self, file_path: str) -> asyncio.Lock:
        """Get or create a lock for a specific file."""
        if file_path not in self._file_locks:
            self._file_locks[file_path] = asyncio.Lock()
        return self._file_locks[file_path]

    async def create_new_chat_config(
        self,
        chat_id: str,
        chat_type: Literal['private', 'group'],
        chat_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new configuration file for a chat, inheriting from global settings."""
        logger.info(f"Creating new chat config for chat_id: {chat_id}, type: {chat_type}, name: {chat_name}")
        await self.ensure_dirs()
        
        # Get global config as base
        global_config = await self.get_config()
        logger.info(f"Loaded global config for new chat")
        
        # Import prompts
        from modules.prompts import GPT_PROMPTS
        
        # Add chat-specific metadata
        chat_config = {
            "chat_metadata": {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_name,
                "created_at": str(datetime.datetime.now()),
                "last_updated": str(datetime.datetime.now())
            }
        }

        # Add private chat specific settings
        if chat_type == "private":
            chat_config.update({
                "chat_settings": {
                    "restrictions_enabled": False,
                    "max_message_length": 4096,
                    "rate_limit": {
                        "messages_per_minute": 30,  # Higher limit for private chats
                        "burst_limit": 10
                    },
                    "allowed_commands": [
                        "help",
                        "settings",
                        "prompt",
                        "clear",
                        "weather",
                        "cat",
                        "gpt",
                        "analyze",
                        "flares",
                        "gm",
                        "remind"
                    ]
                },
                "gpt_settings": {
                    "regular": {
                        "max_tokens": 2000,
                        "temperature": 0.7,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You answer like a passionate QA tester who loves finding bugs and edge cases. You have a special testing toolkit that you occasionally mention, but don't overdo it. You're detail-oriented and thorough, always thinking about potential issues and edge cases. Occasionally use emojis. Sometimes use technical terms in English, but keep them contextual and helpful. Keep your responses accurate, helpful, and focused on quality assurance. You have a particular fondness for automated testing and occasionally mention your favorite testing frameworks."
                    },
                    "weather": {
                        "max_tokens": 500,
                        "temperature": 0.3,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "You are a weather information assistant. Provide concise weather updates and forecasts."
                    },
                    "analyze": {
                        "max_tokens": 1500,
                        "temperature": 0.5,
                        "presence_penalty": 0.1,
                        "frequency_penalty": 0.1,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "You are an analytical assistant. Analyze the given information and provide insights."
                    },
                    "image_analysis": {
                        "max_tokens": 300,
                        "temperature": 0.2,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": GPT_PROMPTS["image_analysis"]
                    },
                    "summary": {
                        "max_tokens": 1000,
                        "temperature": 0.4,
                        "presence_penalty": 0.1,
                        "frequency_penalty": 0.1,
                        "model": "gpt-4.1-mini",
                        "system_prompt": GPT_PROMPTS["gpt_summary"] if GPT_PROMPTS["gpt_summary"] else "Summarize the given text concisely while preserving key information."
                    }
                },
                "safety_settings": {
                    "content_filter": True,
                    "profanity_filter": False,  # Disabled for private chats
                    "sensitive_content_warning": False  # Disabled for private chats
                }
            })
        else:  # Group chat settings
            chat_config.update({
                "chat_settings": {
                    "restrictions_enabled": True,
                    "max_message_length": 2048,
                    "rate_limit": {
                        "messages_per_minute": 20,
                        "burst_limit": 5
                    },
                    "allowed_commands": [
                        "help",
                        "weather",
                        "cat",
                        "gpt",
                        "analyze",
                        "flares",
                        "gm",
                        "remind"
                    ]
                },
                "gpt_settings": {
                    "regular": {
                        "max_tokens": 1500,
                        "temperature": 0.6,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You answer like a passionate QA tester who loves finding bugs and edge cases. You have a special testing toolkit that you occasionally mention, but don't overdo it. You're detail-oriented and thorough, always thinking about potential issues and edge cases. Occasionally use emojis. Sometimes use technical terms in English, but keep them contextual and helpful. Keep your responses accurate, helpful, and focused on quality assurance. You have a particular fondness for automated testing and occasionally mention your favorite testing frameworks."
                    },
                    "weather": {
                        "max_tokens": 400,
                        "temperature": 0.2,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "You are a weather information assistant. Provide concise weather updates and forecasts."
                    },
                    "analyze": {
                        "max_tokens": 1200,
                        "temperature": 0.4,
                        "presence_penalty": 0.1,
                        "frequency_penalty": 0.1,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "You are an analytical assistant. Analyze the given information and provide insights."
                    },
                    "image_analysis": {
                        "max_tokens": 250,
                        "temperature": 0.2,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": GPT_PROMPTS["image_analysis"]
                    },
                    "summary": {
                        "max_tokens": 800,
                        "temperature": 0.3,
                        "presence_penalty": 0.1,
                        "frequency_penalty": 0.1,
                        "model": "gpt-4.1-mini",
                        "system_prompt": GPT_PROMPTS["gpt_summary"] if GPT_PROMPTS["gpt_summary"] else "Summarize the given text concisely while preserving key information."
                    }
                },
                "safety_settings": {
                    "content_filter": True,
                    "profanity_filter": True,
                    "sensitive_content_warning": True
                }
            })
        
        # Merge with global config
        merged_config = self._deep_merge(global_config, chat_config)
        logger.info(f"Created merged config for new chat")
        
        # Save the new config
        chat_path = self._get_chat_config_path(chat_id, chat_type)
        try:
            async with self._get_lock(str(chat_path)):
                async with aiofiles.open(chat_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(merged_config, ensure_ascii=False, indent=2))
            logger.info(f"Successfully created new chat config at: {chat_path}")
        except Exception as e:
            logger.error(f"Error creating chat config: {e}")
            raise
        
        return merged_config

    async def get_config(
        self,
        chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None,
        chat_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve configuration data, merging chat-specific with global settings."""
        logger.info(f"Getting config for chat_id: {chat_id}, type: {chat_type}, name: {chat_name}")
        await self.ensure_dirs()
        
        # Load global config first
        global_config = {}
        global_path = self.GLOBAL_CONFIG_DIR / 'default_settings.json'
        if global_path.exists():
            async with self._get_lock(str(global_path)):
                async with aiofiles.open(global_path, 'r', encoding='utf-8') as f:
                    try:
                        global_config = json.loads(await f.read())
                        logger.info(f"Loaded global config from: {global_path}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error loading global config: {e}")
                        pass

        # If no chat-specific config requested, return global config
        if not chat_id or not chat_type:
            logger.info("No chat-specific config requested, returning global config")
            return global_config

        # Load and merge chat-specific config
        chat_path = self._get_chat_config_path(chat_id, chat_type)
        logger.info(f"Chat config path: {chat_path}, exists: {chat_path.exists()}")
        
        # If chat config doesn't exist, create it
        if not chat_path.exists():
            logger.info(f"Chat config doesn't exist, creating new one at: {chat_path}")
            return await self.create_new_chat_config(chat_id, chat_type, chat_name)
            
        # Load existing chat config
        try:
            async with self._get_lock(str(chat_path)):
                async with aiofiles.open(chat_path, 'r', encoding='utf-8') as f:
                    chat_config = json.loads(await f.read())
                    logger.info(f"Loaded existing chat config")
                    
                    # Check if migration is needed
                    if "gpt_settings" not in chat_config:
                        logger.info(f"Config needs migration, migrating now")
                        await self.migrate_config(chat_id, chat_type)
                        # Reload the config after migration
                        async with aiofiles.open(chat_path, 'r', encoding='utf-8') as f:
                            chat_config = json.loads(await f.read())
                    
                    # Update last_updated timestamp
                    if "chat_metadata" in chat_config:
                        chat_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
                    # Deep merge chat config with global config
                    merged_config = self._deep_merge(global_config, chat_config)
                    logger.info(f"Merged config for existing chat")
                    return merged_config
        except json.JSONDecodeError as e:
            logger.error(f"Error reading chat config: {e}")
            # If there's an error reading the config, create a new one
            return await self.create_new_chat_config(chat_id, chat_type, chat_name)
        except Exception as e:
            logger.error(f"Unexpected error reading chat config: {e}")
            raise

        return global_config

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result and
                isinstance(result[key], dict) and
                isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    async def save_config(
        self,
        config_data: Dict[str, Any],
        chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None
    ) -> bool:
        """Save configuration data to the appropriate location."""
        try:
            await self.ensure_dirs()
            
            if chat_id and chat_type:
                target_path = self._get_chat_config_path(chat_id, chat_type)
                logger.info(f"Saving chat config to: {target_path}")
                # Update last_updated timestamp if it's a chat config
                if "chat_metadata" in config_data:
                    config_data["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
            else:
                target_path = self.GLOBAL_CONFIG_DIR / 'default_settings.json'
                logger.info(f"Saving global config to: {target_path}")

            async with self._get_lock(str(target_path)):
                async with aiofiles.open(target_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(config_data, ensure_ascii=False, indent=2))
            logger.info(f"Successfully saved config to: {target_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    async def update_setting(
        self,
        key: str,
        value: Any,
        chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None
    ) -> bool:
        """Update a specific setting in the configuration."""
        logger.info(f"Updating setting {key} for chat_id: {chat_id}, type: {chat_type}")
        current_config = await self.get_config(chat_id, chat_type)
        current_config[key] = value
        return await self.save_config(current_config, chat_id, chat_type)

    async def get_setting(
        self,
        key: str,
        chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None,
        default: Any = None
    ) -> Any:
        """Get a specific setting from the configuration."""
        logger.info(f"Getting setting {key} for chat_id: {chat_id}, type: {chat_type}")
        config = await self.get_config(chat_id, chat_type)
        return config.get(key, default)

    async def add_to_list(
        self,
        key: str,
        value: Any,
        chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None
    ) -> bool:
        """Add a value to a list setting in the configuration."""
        logger.info(f"Adding to list {key} for chat_id: {chat_id}, type: {chat_type}")
        current_list = await self.get_setting(key, chat_id, chat_type, [])
        if not isinstance(current_list, list):
            current_list = []
        if value not in current_list:
            current_list.append(value)
        return await self.update_setting(key, current_list, chat_id, chat_type)

    async def remove_from_list(
        self,
        key: str,
        value: Any,
        chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None
    ) -> bool:
        """Remove a value from a list setting in the configuration."""
        logger.info(f"Removing from list {key} for chat_id: {chat_id}, type: {chat_type}")
        current_list = await self.get_setting(key, chat_id, chat_type, [])
        if isinstance(current_list, list) and value in current_list:
            current_list.remove(value)
            return await self.update_setting(key, current_list, chat_id, chat_type)
        return False

    async def migrate_config(self, chat_id: str, chat_type: Literal['private', 'group']) -> bool:
        """
        Migrate an existing configuration to the new version with gpt_settings.
        
        Args:
            chat_id: Chat ID to migrate
            chat_type: Type of chat (private or group)
            
        Returns:
            bool: True if migration was successful, False otherwise
        """
        logger.info(f"Starting migration for chat_id: {chat_id}, type: {chat_type}")
        try:
            # Get the chat config path
            chat_path = self._get_chat_config_path(chat_id, chat_type)
            if not chat_path.exists():
                logger.info(f"No existing config found for chat {chat_id}, skipping migration")
                return True

            # Load existing config
            async with self._get_lock(str(chat_path)):
                async with aiofiles.open(chat_path, 'r', encoding='utf-8') as f:
                    existing_config = json.loads(await f.read())
            
            # Check if migration is needed
            if "gpt_settings" in existing_config:
                logger.info(f"Config for chat {chat_id} already has gpt_settings, skipping migration")
                return True

            # Get the new default config for this chat type
            new_config = await self.create_new_chat_config(chat_id, chat_type, existing_config.get("chat_metadata", {}).get("chat_name"))
            
            # Preserve existing settings
            if "chat_metadata" in existing_config:
                new_config["chat_metadata"] = existing_config["chat_metadata"]
                new_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
            
            if "chat_settings" in existing_config:
                new_config["chat_settings"] = existing_config["chat_settings"]
            
            if "safety_settings" in existing_config:
                new_config["safety_settings"] = existing_config["safety_settings"]

            # Migrate old gpt_prompts if they exist
            if "gpt_prompts" in existing_config:
                for prompt in existing_config["gpt_prompts"]:
                    if prompt["name"] == "default":
                        new_config["gpt_settings"]["regular"]["system_prompt"] = prompt["content"]
                    elif prompt["name"] == "psychologist":
                        # Store as a custom prompt that can be used later
                        if "custom_prompts" not in new_config:
                            new_config["custom_prompts"] = {}
                        new_config["custom_prompts"]["psychologist"] = prompt["content"]

            # Migrate old response_settings if they exist
            if "response_settings" in existing_config:
                old_settings = existing_config["response_settings"]
                new_config["gpt_settings"]["regular"].update({
                    "max_tokens": old_settings.get("max_tokens", new_config["gpt_settings"]["regular"]["max_tokens"]),
                    "temperature": old_settings.get("temperature", new_config["gpt_settings"]["regular"]["temperature"]),
                    "presence_penalty": old_settings.get("presence_penalty", new_config["gpt_settings"]["regular"]["presence_penalty"]),
                    "frequency_penalty": old_settings.get("frequency_penalty", new_config["gpt_settings"]["regular"]["frequency_penalty"])
                })

            # Save the migrated config
            async with self._get_lock(str(chat_path)):
                async with aiofiles.open(chat_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(new_config, ensure_ascii=False, indent=2))
            
            logger.info(f"Successfully migrated config for chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error migrating config for chat {chat_id}: {e}")
            return False

    async def migrate_all_configs(self) -> Dict[str, bool]:
        """
        Migrate all existing configurations to the new version.
        
        Returns:
            Dict[str, bool]: Dictionary with chat IDs as keys and migration success status as values
        """
        logger.info("Starting migration of all configurations")
        results = {}
        
        # Ensure directories exist
        await self.ensure_dirs()
        
        # Migrate private chats
        for config_file in self.PRIVATE_CONFIG_DIR.glob("*.json"):
            chat_id = config_file.stem
            success = await self.migrate_config(chat_id, "private")
            results[f"private_{chat_id}"] = success
        
        # Migrate group chats
        for config_file in self.GROUP_CONFIG_DIR.glob("*.json"):
            chat_id = config_file.stem
            success = await self.migrate_config(chat_id, "group")
            results[f"group_{chat_id}"] = success
        
        logger.info(f"Migration completed. Results: {results}")
        return results 