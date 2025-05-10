"""Asynchronous configuration manager for handling default and chat-specific configurations."""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, Literal, List, Union
import aiofiles
from pathlib import Path
import datetime

from modules.logger import general_logger, error_logger

# Set up logging with a more concise format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Try to import GPT_PROMPTS, use empty dict if not available
try:
    from modules.prompts import GPT_PROMPTS
except ImportError:
    logger.warning("Could not import GPT_PROMPTS, using empty dict")
    GPT_PROMPTS = {
        'image_analysis': 'Default image analysis prompt',
        'gpt_summary': 'Default summary prompt'
    }


class ConfigManager:
    """Manages configuration for the bot, supporting default and chat-specific JSON settings."""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.GLOBAL_CONFIG_DIR = self.base_dir / 'config' / 'global'
        self.PRIVATE_CONFIG_DIR = self.base_dir / 'config' / 'private'
        self.GROUP_CONFIG_DIR = self.base_dir / 'config' / 'group'
        self.BACKUP_DIR = self.base_dir / 'config' / 'backups'
        self._file_locks: Dict[str, asyncio.Lock] = {}
        logger.debug("ConfigManager initialized")

    async def ensure_dirs(self) -> None:
        """Ensure that base directories for configuration exist."""
        for d in (self.GLOBAL_CONFIG_DIR, self.PRIVATE_CONFIG_DIR, self.GROUP_CONFIG_DIR, self.BACKUP_DIR):
            d.mkdir(parents=True, exist_ok=True)
        logger.debug("Configuration directories verified")

    def _get_chat_config_path(self, chat_id: str, chat_type: str) -> Path:
        """Get the path for a chat's configuration file."""
        base = self.PRIVATE_CONFIG_DIR if chat_type == 'private' else self.GROUP_CONFIG_DIR
        return base / f"{chat_id}.json"

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
        logger.info(f"Creating new config for {chat_type} chat {chat_id}")
        await self.ensure_dirs()
        
        # Get global config as base
        global_config = await self.get_config()
        
        # Add chat-specific metadata
        chat_config = {
            "chat_metadata": {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_name or chat_type,
                "created_at": str(datetime.datetime.now()),
                "last_updated": str(datetime.datetime.now()),
                "custom_config_enabled": True  # Enable custom config by default for new chats
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
                    "command": {
                        "max_tokens": 2000,
                        "temperature": 0.7,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You answer like a passionate QA tester who loves finding bugs and edge cases. You have a special testing toolkit that you occasionally mention, but don't overdo it. You're detail-oriented and thorough, always thinking about potential issues and edge cases. Occasionally use emojis. Sometimes use technical terms in English, but keep them contextual and helpful. Keep your responses accurate, helpful, and focused on quality assurance. You have a particular fondness for automated testing and occasionally mention your favorite testing frameworks."
                    },
                    "mention": {
                        "max_tokens": 1500,
                        "temperature": 0.6,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You are a helpful assistant who responds to mentions in group chats. Keep your responses concise and relevant to the conversation. Use emojis occasionally to make responses more engaging. Focus on being helpful while maintaining a friendly tone."
                    },
                    "random": {
                        "max_tokens": 1000,
                        "temperature": 0.8,
                        "presence_penalty": 0.1,
                        "frequency_penalty": 0.1,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You are a friendly assistant who occasionally joins conversations in private chats. Keep your responses casual and engaging. Use emojis to make responses more lively. Focus on being helpful while maintaining a conversational tone."
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
                    "command": {
                        "max_tokens": 1500,
                        "temperature": 0.6,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You answer like a passionate QA tester who loves finding bugs and edge cases. You have a special testing toolkit that you occasionally mention, but don't overdo it. You're detail-oriented and thorough, always thinking about potential issues and edge cases. Occasionally use emojis. Sometimes use technical terms in English, but keep them contextual and helpful. Keep your responses accurate, helpful, and focused on quality assurance. You have a particular fondness for automated testing and occasionally mention your favorite testing frameworks."
                    },
                    "mention": {
                        "max_tokens": 1200,
                        "temperature": 0.5,
                        "presence_penalty": 0.0,
                        "frequency_penalty": 0.0,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You are a helpful assistant who responds to mentions in group chats. Keep your responses concise and relevant to the conversation. Use emojis occasionally to make responses more engaging. Focus on being helpful while maintaining a friendly tone."
                    },
                    "random": {
                        "max_tokens": 800,
                        "temperature": 0.7,
                        "presence_penalty": 0.1,
                        "frequency_penalty": 0.1,
                        "model": "gpt-4.1-mini",
                        "system_prompt": "If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You are a friendly assistant who occasionally joins conversations in group chats. Keep your responses casual and engaging. Use emojis to make responses more lively. Focus on being helpful while maintaining a conversational tone."
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
        
        # Save the new config
        chat_path = self._get_chat_config_path(chat_id, chat_type)
        try:
            async with self._get_lock(str(chat_path)):
                async with aiofiles.open(chat_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(merged_config, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Error creating chat config: {e}")
            raise
        
        return merged_config

    async def get_config(
        self,
        chat_id: Optional[str] = None,
        chat_type: Optional[str] = None,
        config_name: Optional[str] = None,
        create_if_missing: bool = True
    ) -> Dict[str, Any]:
        """Get configuration for a chat, falling back to global settings."""
        await self.ensure_dirs()
        
        if config_name:
            config_path = self.get_config_path(config_name, chat_id, chat_type)
            if os.path.exists(config_path):
                async with aiofiles.open(config_path, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
            elif create_if_missing:
                # Create a new config file with default settings
                default_config = await self._load_global_config()
                await self.save_config(default_config, chat_id, chat_type)
                return default_config
            else:
                raise FileNotFoundError(f"Config {config_name} not found")
        
        # If no config_name is provided, get the default config for the chat
        if chat_type == "global":
            return await self._load_global_config()
        
        # Get chat-specific config
        chat_config = await self._load_chat_config(chat_id)
        if chat_config:
            return chat_config
        
        # If no chat config exists and create_if_missing is True, create one
        if create_if_missing:
            return await self.create_new_chat_config(chat_id, chat_type)
        
        # Return empty dict if no config exists and create_if_missing is False
        return {}

    def _validate_config_structure(self, config: Dict[str, Any]) -> bool:
        """Validate the structure of a configuration."""
        try:
            # Check required top-level keys
            if not isinstance(config, dict):
                return False

            # Check chat metadata
            metadata = config.get("chat_metadata", {})
            if not isinstance(metadata, dict):
                return False

            # Check chat settings
            settings = config.get("chat_settings", {})
            if not isinstance(settings, dict):
                return False

            # Check GPT settings
            gpt_settings = config.get("gpt_settings", {})
            if not isinstance(gpt_settings, dict):
                return False

            # Validate each GPT setting
            for setting_type, setting in gpt_settings.items():
                if not isinstance(setting, dict):
                    return False
                required_keys = ["max_tokens", "temperature", "presence_penalty", "frequency_penalty", "model", "system_prompt"]
                if not all(key in setting for key in required_keys):
                    return False
                if not isinstance(setting["system_prompt"], str) or len(setting["system_prompt"]) < 10:
                    return False

            return True
        except Exception as e:
            logger.error(f"Error validating config structure: {e}")
            return False

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
        chat_type: Optional[str] = None,
        config_name: Optional[str] = None
    ) -> bool:
        """Save configuration data."""
        await self.ensure_dirs()
        
        if not self._validate_config_structure(config_data):
            error_logger.error("Invalid config structure")
            return False
        
        try:
            if config_name:
                config_path = self.get_config_path(config_name, chat_id, chat_type)
                # Create backup if file exists
                if os.path.exists(config_path):
                    backup_path = self.BACKUP_DIR / f"{config_path.name}.bak"
                    async with aiofiles.open(config_path, 'r') as src, aiofiles.open(backup_path, 'w') as dst:
                        await dst.write(await src.read())
                
                # Add metadata if it doesn't exist
                if "chat_metadata" not in config_data and chat_id and chat_type:
                    config_data["chat_metadata"] = {
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "chat_name": chat_type,
                        "created_at": str(datetime.datetime.now()),
                        "last_updated": str(datetime.datetime.now()),
                        "custom_config_enabled": True
                    }
                
                # Write new config
                async with aiofiles.open(config_path, 'w') as f:
                    await f.write(json.dumps(config_data, indent=2))
                return True
            
            # If no config_name is provided, save to the default chat config
            if chat_type == "global":
                config_path = self.GLOBAL_CONFIG_DIR / "default_settings.json"
            else:
                config_path = self._get_chat_config_path(chat_id, chat_type)
            
            # Create backup if file exists
            if os.path.exists(config_path):
                backup_path = self.BACKUP_DIR / f"{config_path.name}.bak"
                async with aiofiles.open(config_path, 'r') as src, aiofiles.open(backup_path, 'w') as dst:
                    await dst.write(await src.read())
            
            # Add metadata if it doesn't exist
            if "chat_metadata" not in config_data and chat_id and chat_type:
                config_data["chat_metadata"] = {
                    "chat_id": chat_id,
                    "chat_type": chat_type,
                    "chat_name": chat_type,
                    "created_at": str(datetime.datetime.now()),
                    "last_updated": str(datetime.datetime.now()),
                    "custom_config_enabled": True
                }
            
            # Write new config
            async with aiofiles.open(config_path, 'w') as f:
                await f.write(json.dumps(config_data, indent=2))
            return True
            
        except Exception as e:
            error_logger.error(f"Error saving config: {e}")
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
        
        # Get current config
        current_config = await self.get_config(chat_id=chat_id, chat_type=chat_type)
        
        # Handle nested keys (e.g., "chat_metadata.custom_config_enabled")
        if "." in key:
            parts = key.split(".")
            target = current_config
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value
        else:
            current_config[key] = value
            
        # Save the updated config
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
        """Migrate an existing configuration to the new version with gpt_settings."""
        logger.info(f"Migrating config for {chat_type} chat {chat_id}")
        try:
            # Get the chat config path
            chat_path = self._get_chat_config_path(chat_id, chat_type)
            
            # Load existing config if it exists
            existing_config = {}
            if chat_path.exists():
                async with self._get_lock(str(chat_path)):
                    async with aiofiles.open(chat_path, 'r', encoding='utf-8') as f:
                        try:
                            existing_config = json.loads(await f.read())
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in config for chat {chat_id}, will create new config")
                            existing_config = {}
            
            # Get the new default config for this chat type
            new_config = await self.create_new_chat_config(chat_id, chat_type, existing_config.get("chat_metadata", {}).get("chat_name"))
            
            # Preserve existing settings if they exist
            if "chat_metadata" in existing_config:
                new_config["chat_metadata"] = existing_config["chat_metadata"]
                new_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
            
            if "chat_settings" in existing_config:
                # Deep merge chat settings to preserve any custom values
                new_config["chat_settings"] = self._deep_merge(
                    new_config["chat_settings"],
                    existing_config["chat_settings"]
                )
                
                # Only add random_response_settings if it doesn't exist
                if "random_response_settings" not in new_config["chat_settings"]:
                    logger.info(f"Adding random_response_settings to chat {chat_id}")
                    new_config["chat_settings"]["random_response_settings"] = {
                        "enabled": True,
                        "min_words": 5,
                        "message_threshold": 50,
                        "probability": 0.02,
                        "cooldown_minutes": 30
                    }
            
            if "safety_settings" in existing_config:
                new_config["safety_settings"] = self._deep_merge(
                    new_config["safety_settings"],
                    existing_config["safety_settings"]
                )

            # Migrate old gpt_prompts if they exist
            if "gpt_prompts" in existing_config:
                for prompt in existing_config["gpt_prompts"]:
                    if prompt["name"] == "default":
                        # Only update response types that don't have a system prompt
                        for response_type in ["command", "mention", "random"]:
                            if (response_type in new_config["gpt_settings"] and 
                                "system_prompt" not in new_config["gpt_settings"][response_type]):
                                new_config["gpt_settings"][response_type]["system_prompt"] = prompt["content"]
                    elif prompt["name"] == "psychologist":
                        # Store as a custom prompt that can be used later
                        if "custom_prompts" not in new_config:
                            new_config["custom_prompts"] = {}
                        new_config["custom_prompts"]["psychologist"] = prompt["content"]

            # Migrate old response_settings if they exist
            if "response_settings" in existing_config:
                old_settings = existing_config["response_settings"]
                # Only add missing settings to each response type
                for response_type in ["command", "mention", "random"]:
                    if response_type in new_config["gpt_settings"]:
                        for setting in ["max_tokens", "temperature", "presence_penalty", "frequency_penalty"]:
                            if setting not in new_config["gpt_settings"][response_type]:
                                new_config["gpt_settings"][response_type][setting] = old_settings.get(setting)

            # Ensure all required response types exist
            required_response_types = ["command", "mention", "random", "weather", "analyze", "image_analysis", "summary"]
            for response_type in required_response_types:
                if response_type not in new_config["gpt_settings"]:
                    logger.warning(f"Missing response type {response_type} in config, adding default settings")
                    # Copy settings from a similar response type or use defaults
                    template_type = "command" if response_type in ["command", "mention"] else "random"
                    new_config["gpt_settings"][response_type] = new_config["gpt_settings"][template_type].copy()

            # Save the migrated config
            async with self._get_lock(str(chat_path)):
                async with aiofiles.open(chat_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(new_config, ensure_ascii=False, indent=2))
            
            logger.info(f"Successfully migrated config for {chat_type} chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error migrating config for {chat_type} chat {chat_id}: {e}")
            return False

    async def migrate_all_configs(self) -> Dict[str, bool]:
        """Migrate all existing configurations to the new version."""
        logger.info("Starting configuration migration")
        results = {}
        
        # Ensure directories exist
        await self.ensure_dirs()
        
        # Migrate private chats
        for config_file in self.PRIVATE_CONFIG_DIR.glob("*.json"):
            chat_id = config_file.stem
            # Only migrate if the config needs migration
            try:
                async with aiofiles.open(config_file, 'r') as f:
                    content = await f.read()
                    config = json.loads(content)
                    # Check if config needs migration (missing required fields)
                    if not self._validate_config_structure(config):
                        success = await self.migrate_config(chat_id, "private")
                        results[f"private_{chat_id}"] = success
                    else:
                        results[f"private_{chat_id}"] = True  # Already up to date
            except Exception as e:
                logger.error(f"Error checking config for private chat {chat_id}: {e}")
                results[f"private_{chat_id}"] = False
        
        # Migrate group chats
        for config_file in self.GROUP_CONFIG_DIR.glob("*.json"):
            chat_id = config_file.stem
            # Only migrate if the config needs migration
            try:
                async with aiofiles.open(config_file, 'r') as f:
                    content = await f.read()
                    config = json.loads(content)
                    # Check if config needs migration (missing required fields)
                    if not self._validate_config_structure(config):
                        success = await self.migrate_config(chat_id, "group")
                        results[f"group_{chat_id}"] = success
                    else:
                        results[f"group_{chat_id}"] = True  # Already up to date
            except Exception as e:
                logger.error(f"Error checking config for group chat {chat_id}: {e}")
                results[f"group_{chat_id}"] = False
        
        logger.info(f"Migration completed: {sum(results.values())} successful, {len(results) - sum(results.values())} failed")
        return results

    async def backup_config(self, chat_id: str, chat_type: str) -> bool:
        """Create a backup of a chat's configuration."""
        try:
            source_path = self._get_chat_config_path(chat_id, chat_type)
            if not source_path.exists():
                return False

            # Create backup filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.BACKUP_DIR / f"{chat_type}_{chat_id}_{timestamp}.json"

            # Copy the file
            async with aiofiles.open(source_path, 'r') as src:
                content = await src.read()
                async with aiofiles.open(backup_path, 'w') as dst:
                    await dst.write(content)

            logger.info(f"Created backup of {chat_type} chat {chat_id} config at {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup config for {chat_type} chat {chat_id}: {e}")
            return False

    async def restore_config(self, chat_id: str, chat_type: str, backup_timestamp: Optional[str] = None) -> bool:
        """Restore a chat's configuration from backup."""
        try:
            # Find the most recent backup if timestamp not specified
            if not backup_timestamp:
                backups = list(self.BACKUP_DIR.glob(f"{chat_type}_{chat_id}_*.json"))
                if not backups:
                    return False
                backup_path = max(backups, key=lambda p: p.stat().st_mtime)
            else:
                backup_path = self.BACKUP_DIR / f"{chat_type}_{chat_id}_{backup_timestamp}.json"
                if not backup_path.exists():
                    return False

            # Restore the backup
            target_path = self._get_chat_config_path(chat_id, chat_type)
            async with aiofiles.open(backup_path, 'r') as src:
                content = await src.read()
                async with aiofiles.open(target_path, 'w') as dst:
                    await dst.write(content)

            logger.info(f"Restored config for {chat_type} chat {chat_id} from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore config for {chat_type} chat {chat_id}: {e}")
            return False

    async def list_backups(self, chat_id: str, chat_type: str) -> List[str]:
        """List available backups for a chat."""
        try:
            backups = list(self.BACKUP_DIR.glob(f"{chat_type}_{chat_id}_*.json"))
            return [b.stem.split('_')[-1] for b in sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)]
        except Exception as e:
            logger.error(f"Failed to list backups for {chat_type} chat {chat_id}: {e}")
            return []

    async def _load_global_config(self) -> Dict[str, Any]:
        """Load the global configuration file."""
        try:
            config_path = self.GLOBAL_CONFIG_DIR / 'default_settings.json'
            if not config_path.exists():
                # Create default global config if it doesn't exist
                default_config = {
                    "chat_settings": {
                        "restrictions_enabled": True,
                        "max_message_length": 4096,
                        "rate_limit": {
                            "messages_per_minute": 30,
                            "burst_limit": 10
                        }
                    },
                    "gpt_settings": {
                        "command": {
                            "max_tokens": 2000,
                            "temperature": 0.7,
                            "presence_penalty": 0.0,
                            "frequency_penalty": 0.0,
                            "model": "gpt-4.1-mini",
                            "system_prompt": "You are a helpful assistant."
                        }
                    }
                }
                await self.save_config(default_config)
                return default_config

            async with self._get_lock(str(config_path)):
                async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                    return json.loads(await f.read())
        except Exception as e:
            error_logger.error(f"Error loading global config: {e}")
            return {}

    async def _load_chat_config(self, chat_id: str) -> Dict[str, Any]:
        """Load a chat-specific configuration file."""
        try:
            # Try both private and group configs
            for chat_type in ['private', 'group']:
                config_path = self._get_chat_config_path(chat_id, chat_type)
                if config_path.exists():
                    async with self._get_lock(str(config_path)):
                        async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                            return json.loads(await f.read())
            
            # If no config found, raise FileNotFoundError
            raise FileNotFoundError(f"No config found for chat {chat_id}")
        except Exception as e:
            error_logger.error(f"Error loading chat config for {chat_id}: {e}")
            raise

    async def _save_chat_config(self, chat_id: str, config: Dict[str, Any]) -> None:
        """Save a chat-specific configuration file."""
        try:
            chat_type = config.get("chat_metadata", {}).get("chat_type", "private")
            config_path = self._get_chat_config_path(chat_id, chat_type)
            
            # Create backup before saving
            if config_path.exists():
                await self.backup_config(chat_id, chat_type)
            
            async with self._get_lock(str(config_path)):
                async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(config, ensure_ascii=False, indent=2))
        except Exception as e:
            error_logger.error(f"Error saving chat config for {chat_id}: {e}")
            raise

    def _create_new_chat_config(self, chat_id: str, chat_type: str, chat_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat configuration dictionary."""
        return {
            "chat_metadata": {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_name or chat_type,
                "created_at": str(datetime.datetime.now()),
                "last_updated": str(datetime.datetime.now()),
                "custom_config_enabled": True
            },
            "chat_settings": {
                "restrictions_enabled": True,
                "max_message_length": 4096,
                "rate_limit": {
                    "messages_per_minute": 30,
                    "burst_limit": 10
                }
            },
            "gpt_settings": {
                "command": {
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "presence_penalty": 0.0,
                    "frequency_penalty": 0.0,
                    "model": "gpt-4.1-mini",
                    "system_prompt": "You are a helpful assistant."
                }
            }
        }

    def get_config_path(self, config_name: str, chat_id: Optional[str] = None, chat_type: Optional[str] = None) -> Path:
        """Get the path for a specific configuration file."""
        if chat_type == "global":
            return self.GLOBAL_CONFIG_DIR / f"{config_name}.json"
        elif chat_type == "private":
            return self.PRIVATE_CONFIG_DIR / f"{chat_id}_{config_name}.json"
        elif chat_type == "group":
            return self.GROUP_CONFIG_DIR / f"{chat_id}_{config_name}.json"
        else:
            raise ValueError(f"Invalid chat type: {chat_type}") 