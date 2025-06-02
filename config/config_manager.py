"""Asynchronous configuration manager for handling modular configurations."""

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
    """Manages modular configuration for the bot, supporting default and chat-specific JSON settings."""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.GLOBAL_CONFIG_DIR = self.base_dir / 'config' / 'global'
        self.PRIVATE_CONFIG_DIR = self.base_dir / 'config' / 'private'
        self.GROUP_CONFIG_DIR = self.base_dir / 'config' / 'group'
        self.BACKUP_DIR = self.base_dir / 'config' / 'backups'
        self.GLOBAL_CONFIG_FILE = self.GLOBAL_CONFIG_DIR / "global_config.json"
        self._file_locks: Dict[str, asyncio.Lock] = {}
        self._module_cache: Dict[str, Dict[str, Any]] = {}
        logger.debug("ConfigManager initialized")

    async def initialize(self) -> None:
        """Initialize the configuration manager and ensure global config exists."""
        await self.ensure_dirs()
        try:
            global_config = await self._load_global_config()
            if not global_config:
                logger.info("Global config not found or empty, creating new one")
                await self.create_global_config()
        except Exception as e:
            logger.error(f"Error initializing ConfigManager: {e}")
            raise

    async def ensure_dirs(self) -> None:
        """Ensure that base directories for configuration exist."""
        for d in (self.GLOBAL_CONFIG_DIR, self.PRIVATE_CONFIG_DIR, self.GROUP_CONFIG_DIR, self.BACKUP_DIR):
            d.mkdir(parents=True, exist_ok=True)
        logger.debug("Configuration directories verified")

    async def ensure_chat_dir(self, chat_id: str, chat_type: str) -> None:
        """Ensure that the directory for a specific chat exists."""
        base_dir = self.PRIVATE_CONFIG_DIR if chat_type == 'private' else self.GROUP_CONFIG_DIR
        chat_dir = base_dir / chat_id
        chat_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Chat directory verified for {chat_type} chat {chat_id}")

    def _get_chat_config_path(self, chat_id: str, chat_type: str) -> Path:
        """Get the path for a chat's configuration file."""
        base = self.PRIVATE_CONFIG_DIR if chat_type == 'private' else self.GROUP_CONFIG_DIR
        chat_dir = base / chat_id
        return chat_dir / "config.json"

    def _get_lock(self, file_path: str) -> asyncio.Lock:
        """Get or create a lock for a specific file."""
        if file_path not in self._file_locks:
            self._file_locks[file_path] = asyncio.Lock()
        return self._file_locks[file_path]

    async def _load_global_config(self) -> Dict[str, Any]:
        """Load the global configuration file."""
        if not self.GLOBAL_CONFIG_FILE.exists():
            logger.info("Global config file does not exist")
            return {}
            
        async with self._get_lock(str(self.GLOBAL_CONFIG_FILE)):
            try:
                async with aiofiles.open(self.GLOBAL_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if not content.strip():
                        logger.info("Global config file is empty")
                        return {}
                    
                    global_config = json.loads(content)
                    
                    # Handle new format with config_metadata vs old format with chat_metadata
                    if "config_metadata" in global_config:
                        # New format - convert to old format for compatibility
                        converted_config = {
                            "chat_metadata": {
                                "chat_id": "global",
                                "chat_type": "global", 
                                "chat_name": "Global Configuration",
                                "created_at": global_config["config_metadata"].get("created_at", ""),
                                "last_updated": global_config["config_metadata"].get("last_updated", ""),
                                "custom_config_enabled": False
                            },
                            "config_modules": {}
                        }
                        
                        # Convert module_configs to config_modules format
                        for module_name, module_config in global_config.get("module_configs", {}).items():
                            converted_config["config_modules"][module_name] = {
                                "enabled": module_config.get("enabled", True),
                                "overrides": module_config.get("settings", {})
                            }
                        
                        return converted_config
                    
                    return global_config
                    
            except FileNotFoundError:
                logger.info("Global config not found")
                return {}
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in global config: {e}")
                return {}
            except Exception as e:
                logger.error(f"Error loading global config: {e}")
                return {}

    async def create_global_config(self) -> Dict[str, Any]:
        """Create a new global configuration file with default settings."""
        logger.info("Creating new global config")
        try:
            await self.ensure_dirs()
            
            global_config = {
                "chat_metadata": {
                    "chat_id": "global",
                    "chat_type": "global",
                    "chat_name": "Global Configuration",
                    "created_at": str(datetime.datetime.now()),
                    "last_updated": str(datetime.datetime.now()),
                    "custom_config_enabled": False
                },
                "config_modules": {
                    "gpt": {
                        "enabled": True,
                        "overrides": {
                            "command": {
                                "max_tokens": 1500,
                                "temperature": 0.6,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a helpful assistant. Respond to user commands in a clear and concise manner."
                            },
                            "mention": {
                                "max_tokens": 1200,
                                "temperature": 0.5,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a helpful assistant who responds to mentions in group chats. Keep your responses concise and relevant to the conversation."
                            },
                            "private": {
                                "max_tokens": 1000,
                                "temperature": 0.7,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a helpful assistant for private conversations. Keep your responses conversational and engaging."
                            },
                            "random": {
                                "max_tokens": 800,
                                "temperature": 0.7,
                                "presence_penalty": 0.1,
                                "frequency_penalty": 0.1,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a friendly assistant who occasionally joins conversations in group chats. Keep your responses casual and engaging."
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
                                "system_prompt": "Analyze the image and provide a brief description of its contents."
                            },
                            "summary": {
                                "max_tokens": 800,
                                "temperature": 0.3,
                                "presence_penalty": 0.1,
                                "frequency_penalty": 0.1,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "Provide a concise summary of the given text."
                            }
                        }
                    },
                    "chat_behavior": {
                        "enabled": True,
                        "overrides": {
                            "restrictions_enabled": False,
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
                            ],
                            "ban_words": [],
                            "ban_symbols": [],
                            "random_response_settings": {
                                "enabled": True,
                                "min_words": 5,
                                "message_threshold": 50,
                                "probability": 0.02
                            }
                        }
                    },
                    "safety": {
                        "enabled": True,
                        "overrides": {
                            "content_filter_level": "medium",
                            "profanity_filter_enabled": False,
                            "sensitive_content_warning_enabled": False,
                            "restricted_domains": [],
                            "allowed_file_types": [
                                "image/jpeg",
                                "image/png",
                                "image/gif",
                                "video/mp4",
                                "video/quicktime"
                            ]
                        }
                    },
                    "reminders": {
                        "enabled": True,
                        "overrides": {
                            "max_reminders_per_user": 5,
                            "max_reminder_duration_days": 30,
                            "reminder_notification_interval_minutes": 60,
                            "allow_recurring_reminders": True,
                            "max_recurring_reminders": 3
                        }
                    },
                    "weather": {
                        "enabled": True,
                        "overrides": {
                            "default_location": None,
                            "units": "metric",
                            "update_interval_minutes": 30,
                            "forecast_days": 3,
                            "show_alerts": True
                        }
                    },
                    "flares": {
                        "enabled": True,
                        "overrides": {
                            "check_interval_minutes": 15,
                            "notification_threshold": "M5",
                            "auto_notify": False,
                            "include_forecast": True
                        }
                    }
                }
            }

            # Save the global config
            success = await self.save_config(global_config, module_name="global")
            if not success:
                logger.error("Failed to save global config")
                return {}
                
            logger.info("Global config created successfully")
            return global_config
        except Exception as e:
            logger.error(f"Error creating global config: {e}")
            return {}

    async def get_config(
        self,
        chat_id: Optional[str] = None,
        chat_type: Optional[str] = None,
        module_name: Optional[str] = None,
        create_if_missing: bool = True,
        chat_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get configuration for a chat or module."""
        await self.ensure_dirs()

        # Load global config first
        global_config = await self._load_global_config()
        
        if not chat_id or not chat_type:
            if module_name:
                return await self._load_module_config(module_name)
            return global_config

        # Ensure chat directory exists
        await self.ensure_chat_dir(chat_id, chat_type)

        # Load chat config
        chat_config = await self._load_chat_config(chat_id, chat_type)
        if not chat_config:
            if not create_if_missing:
                # Raise FileNotFoundError if config doesn't exist and we shouldn't create it
                raise FileNotFoundError(f"Config not found for {chat_type} chat {chat_id}")
            chat_config = await self.create_new_chat_config(
                chat_id=chat_id,
                chat_type=chat_type,
                chat_name=chat_name or f"{chat_type}_{chat_id}"
            )

        # Always ensure chat_metadata exists
        if "chat_metadata" not in chat_config:
            chat_config["chat_metadata"] = {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_name or f"{chat_type}_{chat_id}",
                "created_at": str(datetime.datetime.now()),
                "last_updated": str(datetime.datetime.now()),
                "custom_config_enabled": False
            }

        # If custom config is disabled, return global config with chat metadata
        if not chat_config.get("chat_metadata", {}).get("custom_config_enabled", False):
            result = global_config.copy()
            result["chat_metadata"] = chat_config["chat_metadata"]
            return result

        # Custom config is enabled - merge global + custom
        if module_name:
            # Get specific module config with inheritance
            global_module = global_config.get("config_modules", {}).get(module_name, {})
            chat_module = chat_config.get("config_modules", {}).get(module_name, {})
            
            if chat_module:
                # Merge global module settings with chat overrides
                merged_overrides = self._deep_merge(
                    global_module.get("overrides", {}),
                    chat_module.get("overrides", {})
                )
                return {
                    "enabled": chat_module.get("enabled", global_module.get("enabled", False)),
                    "overrides": merged_overrides
                }
            
            # No chat override, return global module config
            return global_module

        # Return full merged config (global base + chat overrides)
        merged_config = self._deep_merge(global_config, chat_config)
        return merged_config

    async def _load_module_config(self, module_name: str) -> Dict[str, Any]:
        """Load a module's configuration from the global config."""
        if module_name in self._module_cache:
            return self._module_cache[module_name]

        global_config = await self._load_global_config()
        module_config = global_config.get("config_modules", {}).get(module_name, {})
        self._module_cache[module_name] = module_config
        return module_config

    async def _load_main_config(self) -> Dict[str, Any]:
        """Load the main configuration file."""
        config_path = self.GLOBAL_CONFIG_DIR / "main_config.json"
        async with self._get_lock(str(config_path)):
            try:
                async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                    return json.loads(await f.read())
            except FileNotFoundError:
                logger.error("Main config not found")
                return {}
            except json.JSONDecodeError:
                logger.error("Invalid JSON in main config")
                return {}

    async def _load_chat_config(self, chat_id: str, chat_type: str) -> Dict[str, Any]:
        """Load a chat's configuration file."""
        config_path = self._get_chat_config_path(chat_id, chat_type)
        async with self._get_lock(str(config_path)):
            try:
                async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                    return json.loads(await f.read())
            except FileNotFoundError:
                logger.error(f"Chat config not found: {chat_id}")
                return {}
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in chat config: {chat_id}")
                return {}

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    async def create_new_chat_config(
        self,
        chat_id: str,
        chat_type: Literal['private', 'group'],
        chat_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new configuration file for a chat."""
        logger.info(f"Creating new config for {chat_type} chat {chat_id}")
        await self.ensure_dirs()
        await self.ensure_chat_dir(chat_id, chat_type)
        
        # Get main config
        main_config = await self._load_main_config()
        
        # Create chat config with metadata
        chat_config = {
            "chat_metadata": {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_name or f"{chat_type}_{chat_id}",
                "created_at": str(datetime.datetime.now()),
                "last_updated": str(datetime.datetime.now()),
                "custom_config_enabled": False  # Default to False as per requirements
            },
            "config_modules": {
                "gpt": {
                    "enabled": chat_type == "private",  # Enable by default for private chats
                    "overrides": {
                        "command": {
                            "max_tokens": 1500,
                            "temperature": 0.6,
                            "presence_penalty": 0.0,
                            "frequency_penalty": 0.0,
                            "model": "gpt-4.1-mini",
                            "system_prompt": "You are a helpful assistant. Respond to user commands in a clear and concise manner."
                        },
                        "mention": {
                            "max_tokens": 1200,
                            "temperature": 0.5,
                            "presence_penalty": 0.0,
                            "frequency_penalty": 0.0,
                            "model": "gpt-4.1-mini",
                            "system_prompt": "You are a helpful assistant who responds to mentions in group chats. Keep your responses concise and relevant to the conversation."
                        },
                        "private": {
                            "max_tokens": 1000,
                            "temperature": 0.7,
                            "presence_penalty": 0.0,
                            "frequency_penalty": 0.0,
                            "model": "gpt-4.1-mini",
                            "system_prompt": "You are a helpful assistant for private conversations. Keep your responses conversational and engaging."
                        },
                        "random": {
                            "max_tokens": 800,
                            "temperature": 0.7,
                            "presence_penalty": 0.1,
                            "frequency_penalty": 0.1,
                            "model": "gpt-4.1-mini",
                            "system_prompt": "You are a friendly assistant who occasionally joins conversations in group chats. Keep your responses casual and engaging."
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
                            "system_prompt": "Analyze the image and provide a brief description of its contents."
                        },
                        "summary": {
                            "max_tokens": 800,
                            "temperature": 0.3,
                            "presence_penalty": 0.1,
                            "frequency_penalty": 0.1,
                            "model": "gpt-4.1-mini",
                            "system_prompt": "Provide a concise summary of the given text."
                        }
                    }
                },
                "chat_behavior": {
                    "enabled": chat_type == "private",  # Enable by default for private chats
                    "overrides": {
                        "restrictions_enabled": False,
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
                        ],
                        "ban_words": [],
                        "ban_symbols": [],
                        "random_response_settings": {
                            "enabled": True,
                            "min_words": 5,
                            "message_threshold": 50,
                            "probability": 0.02
                        }
                    }
                },
                "safety": {
                    "enabled": chat_type == "private",  # Enable by default for private chats
                    "overrides": {
                        "content_filter_level": "medium",
                        "profanity_filter_enabled": False,
                        "sensitive_content_warning_enabled": False,
                        "restricted_domains": [],
                        "allowed_file_types": [
                            "image/jpeg",
                            "image/png",
                            "image/gif",
                            "video/mp4",
                            "video/quicktime"
                        ]
                    }
                },
                "reminders": {
                    "enabled": chat_type == "private",  # Enable by default for private chats
                    "overrides": {
                        "max_reminders_per_user": 5,
                        "max_reminder_duration_days": 30,
                        "reminder_notification_interval_minutes": 60,
                        "allow_recurring_reminders": True,
                        "max_recurring_reminders": 3
                    }
                },
                "weather": {
                    "enabled": chat_type == "private",  # Enable by default for private chats
                    "overrides": {
                        "default_location": None,
                        "units": "metric",
                        "update_interval_minutes": 30,
                        "forecast_days": 3,
                        "show_alerts": True
                    }
                },
                "flares": {
                    "enabled": chat_type == "private",  # Enable by default for private chats
                    "overrides": {
                        "check_interval_minutes": 15,
                        "notification_threshold": "M5",
                        "auto_notify": False,
                        "include_forecast": True
                    }
                }
            }
        }

        # Save the new config
        await self.save_config(chat_config, chat_id, chat_type)
        return chat_config

    async def save_config(
        self,
        config_data: Dict[str, Any],
        chat_id: Optional[str] = None,
        chat_type: Optional[str] = None,
        module_name: Optional[str] = None
    ) -> bool:
        """Save configuration data."""
        if not chat_id or not chat_type:
            if module_name == "global":
                config_path = self.GLOBAL_CONFIG_FILE
            elif module_name:
                config_path = self.GLOBAL_CONFIG_DIR / f"{module_name}_config.json"
                self._module_cache[module_name] = config_data
            else:
                config_path = self.GLOBAL_CONFIG_FILE
        else:
            # Ensure the chat directory exists before saving
            await self.ensure_chat_dir(chat_id, chat_type)
            config_path = self._get_chat_config_path(chat_id, chat_type)
            
            # For chat configs, ensure proper structure
            if not isinstance(config_data, dict):
                config_data = {}
            
            # If this is a new config or missing required structure, create it
            if "chat_metadata" not in config_data:
                config_data = {
                    "chat_metadata": {
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "chat_name": f"{chat_type}_{chat_id}",
                        "created_at": str(datetime.datetime.now()),
                        "last_updated": str(datetime.datetime.now()),
                        "custom_config_enabled": False
                    },
                    "config_modules": {}
                }
            
            # Update last_updated timestamp
            config_data["chat_metadata"]["last_updated"] = str(datetime.datetime.now())

        async with self._get_lock(str(config_path)):
            try:
                # Ensure parent directory exists for all config types
                config_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(config_data, indent=2, ensure_ascii=False))
                return True
            except Exception as e:
                logger.error(f"Error saving config: {e}")
                return False

    async def update_module_setting(
        self,
        module_name: str,
        setting_path: str,
        value: Any,
        chat_id: Optional[str] = None,
        chat_type: Optional[str] = None
    ) -> bool:
        """Update a specific setting in a module's configuration."""
        if not chat_id or not chat_type:
            # Update global module config
            module_config = await self._load_module_config(module_name)
            keys = setting_path.split('.')
            current = module_config
            for key in keys[:-1]:
                current = current.setdefault(key, {})
            current[keys[-1]] = value
            return await self.save_config(module_config, module_name=module_name)
        else:
            # Update chat-specific module override
            chat_config = await self.get_config(chat_id, chat_type)
            if module_name not in chat_config.get("config_modules", {}):
                chat_config["config_modules"][module_name] = {"enabled": True, "overrides": {}}
            
            keys = setting_path.split('.')
            current = chat_config["config_modules"][module_name]["overrides"]
            for key in keys[:-1]:
                current = current.setdefault(key, {})
            current[keys[-1]] = value
            
            # Update last_updated timestamp
            chat_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
            
            return await self.save_config(chat_config, chat_id, chat_type)

    async def get_module_setting(
        self,
        module_name: str,
        setting_path: str,
        chat_id: Optional[str] = None,
        chat_type: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Get a specific setting from a module's configuration."""
        # First try to get chat-specific override
        if chat_id and chat_type:
            chat_config = await self.get_config(chat_id, chat_type)
            if module_name in chat_config.get("config_modules", {}):
                module_overrides = chat_config["config_modules"][module_name].get("overrides", {})
                current = module_overrides
                for key in setting_path.split('.'):
                    if key not in current:
                        break
                    current = current[key]
                else:
                    return current

        # If no override or not found, get from global module config
        module_config = await self._load_module_config(module_name)
        current = module_config
        for key in setting_path.split('.'):
            if key not in current:
                return default
            current = current[key]
        return current

    async def backup_config(self, chat_id: str, chat_type: str) -> bool:
        """Create a backup of a chat's configuration."""
        config = await self.get_config(chat_id, chat_type)
        if not config:
            return False

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.BACKUP_DIR / f"{chat_id}_{timestamp}.json"
        
        async with self._get_lock(str(backup_path)):
            try:
                async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(config, indent=2, ensure_ascii=False))
                return True
            except Exception as e:
                logger.error(f"Error creating backup: {e}")
                return False

    async def enable_module(self, chat_id: str, chat_type: str, module_name: str) -> bool:
        """Enable a specific module for a chat."""
        chat_config = await self.get_config(chat_id, chat_type)
        if not chat_config:
            return False

        if module_name not in chat_config.get("config_modules", {}):
            return False

        chat_config["config_modules"][module_name]["enabled"] = True
        chat_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
        
        return await self.save_config(chat_config, chat_id, chat_type)

    async def disable_module(self, chat_id: str, chat_type: str, module_name: str) -> bool:
        """Disable a specific module for a chat."""
        chat_config = await self.get_config(chat_id, chat_type)
        if not chat_config:
            return False

        if module_name not in chat_config.get("config_modules", {}):
            return False

        chat_config["config_modules"][module_name]["enabled"] = False
        chat_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
        
        return await self.save_config(chat_config, chat_id, chat_type)

    async def enable_custom_config(self, chat_id: str, chat_type: str) -> bool:
        """Enable custom configuration for a chat."""
        # Load chat config directly to preserve existing settings
        chat_config = await self._load_chat_config(chat_id, chat_type)
        if not chat_config:
            # If no config exists, create a new one
            chat_config = await self.create_new_chat_config(chat_id, chat_type)

        chat_config["chat_metadata"]["custom_config_enabled"] = True
        chat_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
        
        return await self.save_config(chat_config, chat_id, chat_type)

    async def disable_custom_config(self, chat_id: str, chat_type: str) -> bool:
        """Disable custom configuration for a chat."""
        chat_config = await self.get_config(chat_id, chat_type)
        if not chat_config:
            return False

        chat_config["chat_metadata"]["custom_config_enabled"] = False
        chat_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())
        
        return await self.save_config(chat_config, chat_id, chat_type)

    async def migrate_to_modular_config(self, chat_id: str, chat_type: str) -> bool:
        """Migrate an existing configuration to the new modular structure."""
        logger.info(f"Migrating config for {chat_type} chat {chat_id} to modular structure")
        
        try:
            # Load the old config
            old_config = await self._load_chat_config(chat_id, chat_type)
            if not old_config:
                logger.error(f"No config found for {chat_type} chat {chat_id}")
                return False

            # Create new modular config structure
            new_config = {
                "chat_metadata": old_config.get("chat_metadata", {}),
                "config_modules": {}
            }

            # Migrate GPT settings
            if "gpt_settings" in old_config:
                new_config["config_modules"]["gpt"] = {
                    "enabled": True,
                    "overrides": old_config["gpt_settings"]
                }

            # Migrate chat settings
            if "chat_settings" in old_config:
                new_config["config_modules"]["chat"] = {
                    "enabled": True,
                    "overrides": old_config["chat_settings"]
                }

            # Migrate safety settings
            if "safety_settings" in old_config:
                new_config["config_modules"]["safety"] = {
                    "enabled": True,
                    "overrides": old_config["safety_settings"]
                }

            # Update timestamps
            new_config["chat_metadata"]["last_updated"] = str(datetime.datetime.now())

            # Ensure chat directory exists
            await self.ensure_chat_dir(chat_id, chat_type)

            # Save the new config
            return await self.save_config(new_config, chat_id, chat_type)

        except Exception as e:
            logger.error(f"Error migrating config for {chat_type} chat {chat_id}: {e}")
            return False

    async def migrate_all_to_modular(self) -> Dict[str, bool]:
        """Migrate all existing configurations to the new modular structure."""
        logger.info("Starting migration to modular configuration structure")
        results = {}

        # Migrate private chats
        for config_file in self.PRIVATE_CONFIG_DIR.glob("*.json"):
            chat_id = config_file.stem
            try:
                success = await self.migrate_to_modular_config(chat_id, "private")
                results[f"private_{chat_id}"] = success
            except Exception as e:
                logger.error(f"Error migrating private chat {chat_id}: {e}")
                results[f"private_{chat_id}"] = False

        # Migrate group chats
        for config_file in self.GROUP_CONFIG_DIR.glob("*.json"):
            chat_id = config_file.stem
            try:
                success = await self.migrate_to_modular_config(chat_id, "group")
                results[f"group_{chat_id}"] = success
            except Exception as e:
                logger.error(f"Error migrating group chat {chat_id}: {e}")
                results[f"group_{chat_id}"] = False

        logger.info(f"Migration completed: {sum(results.values())} successful, {len(results) - sum(results.values())} failed")
        return results

    async def migrate_existing_configs(self) -> Dict[str, bool]:
        """Migrate existing config files to the new directory structure."""
        logger.info("Starting migration of existing config files to new directory structure")
        results = {}

        # Get default module configurations
        default_config = await self.create_new_chat_config("default", "private")
        default_modules = default_config["config_modules"]

        # Migrate private chat configs
        for config_file in self.PRIVATE_CONFIG_DIR.glob("*.json"):
            if config_file.name == "main_config.json":
                continue
            chat_id = config_file.stem
            try:
                # Read existing config
                async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.loads(await f.read())
                
                # Create chat directory
                await self.ensure_chat_dir(chat_id, "private")
                
                # Merge with default module configurations
                if "config_modules" not in config_data or not config_data["config_modules"]:
                    config_data["config_modules"] = default_modules
                else:
                    # Merge existing modules with defaults
                    for module_name, default_module in default_modules.items():
                        if module_name not in config_data["config_modules"]:
                            config_data["config_modules"][module_name] = default_module
                        else:
                            # Merge overrides
                            existing_module = config_data["config_modules"][module_name]
                            if "overrides" not in existing_module:
                                existing_module["overrides"] = default_module["overrides"]
                            else:
                                # Deep merge overrides
                                for key, value in default_module["overrides"].items():
                                    if key not in existing_module["overrides"]:
                                        existing_module["overrides"][key] = value
                
                # Save to new location
                new_path = self._get_chat_config_path(chat_id, "private")
                async with aiofiles.open(new_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(config_data, indent=2, ensure_ascii=False))
                
                # Remove old file
                config_file.unlink()
                results[f"private_{chat_id}"] = True
                logger.info(f"Migrated private chat config: {chat_id}")
            except Exception as e:
                logger.error(f"Error migrating private chat config {chat_id}: {e}")
                results[f"private_{chat_id}"] = False

        # Migrate group chat configs
        for config_file in self.GROUP_CONFIG_DIR.glob("*.json"):
            if config_file.name == "main_config.json":
                continue
            chat_id = config_file.stem
            try:
                # Read existing config
                async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.loads(await f.read())
                
                # Create chat directory
                await self.ensure_chat_dir(chat_id, "group")
                
                # Merge with default module configurations
                if "config_modules" not in config_data or not config_data["config_modules"]:
                    config_data["config_modules"] = default_modules
                else:
                    # Merge existing modules with defaults
                    for module_name, default_module in default_modules.items():
                        if module_name not in config_data["config_modules"]:
                            config_data["config_modules"][module_name] = default_module
                        else:
                            # Merge overrides
                            existing_module = config_data["config_modules"][module_name]
                            if "overrides" not in existing_module:
                                existing_module["overrides"] = default_module["overrides"]
                            else:
                                # Deep merge overrides
                                for key, value in default_module["overrides"].items():
                                    if key not in existing_module["overrides"]:
                                        existing_module["overrides"][key] = value
                
                # Save to new location
                new_path = self._get_chat_config_path(chat_id, "group")
                async with aiofiles.open(new_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(config_data, indent=2, ensure_ascii=False))
                
                # Remove old file
                config_file.unlink()
                results[f"group_{chat_id}"] = True
                logger.info(f"Migrated group chat config: {chat_id}")
            except Exception as e:
                logger.error(f"Error migrating group chat config {chat_id}: {e}")
                results[f"group_{chat_id}"] = False

        logger.info(f"Migration completed: {sum(results.values())} successful, {len(results) - sum(results.values())} failed")
        return results 