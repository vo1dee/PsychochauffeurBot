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
        missing_dirs = []
        for d in (self.GLOBAL_CONFIG_DIR, self.PRIVATE_CONFIG_DIR, self.GROUP_CONFIG_DIR, self.BACKUP_DIR):
            try:
                # First check if directory exists
                if d.exists():
                    logger.debug(f"Directory already exists: {d}")
                    continue
                    
                # Try to create directory
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {d}")
                except PermissionError:
                    logger.warning(f"Could not create directory {d}, checking if it exists")
                    if not d.exists():
                        logger.warning(f"Directory {d} does not exist and could not be created")
                        missing_dirs.append(str(d))
                        continue
                    logger.info(f"Directory {d} exists but could not be created by us")
                
                try:
                    # Get the current user's uid and gid
                    uid = os.getuid()
                    gid = os.getgid()
                    
                    # Try to set ownership, but don't fail if we can't
                    try:
                        os.chown(d, uid, gid)
                    except PermissionError:
                        logger.warning(f"Could not set ownership for {d}, continuing without ownership change")
                    
                    # Try to set permissions, but don't fail if we can't
                    try:
                        os.chmod(d, 0o750)
                    except PermissionError:
                        logger.warning(f"Could not set permissions for {d}, continuing without permission change")
                    
                    logger.debug(f"Directory created and permissions set: {d}")
                except Exception as e:
                    logger.warning(f"Could not set permissions for {d}: {e}, continuing without permission change")
                    
            except Exception as e:
                logger.error(f"Error with directory {d}: {e}")
                missing_dirs.append(str(d))
                
        if missing_dirs:
            logger.warning(f"Some directories could not be created: {', '.join(missing_dirs)}")
            logger.warning("The bot will continue but some features may not work correctly")
        else:
            logger.debug("All configuration directories verified")

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
            except PermissionError:
                logger.warning(f"Permission denied when accessing global config file: {self.GLOBAL_CONFIG_FILE}")
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
                                "system_prompt": "You are a helpful assistant. Respond to user commands in a clear and concise manner. If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You answer like a helpfull assistant and stick to the point of the conversation. Keep your responses concise and relevant to the conversation."
                            },
                            "mention": {
                                "max_tokens": 1200,
                                "temperature": 0.5,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a helpful assistant who responds to mentions in group chats. Keep your responses concise and relevant to the conversation. If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance."
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
                                "system_prompt": "You are a friendly assistant who occasionally joins conversations in group chats. Keep your responses casual and engaging. "
                            },
                            "weather": {
                                "max_tokens": 400,
                                "temperature": 0.2,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a weather information assistant. Provide concise weather updates and forecasts."
                            },
                            "image_analysis": {
                                "max_tokens": 250,
                                "temperature": 0.2,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are an image analysis assistant. Provide detailed descriptions and analysis of images. Describe the main elements in 2-3 concise sentences. Focus on objects, people, settings, actions, and context. Do not speculate beyond what is clearly visible. Keep descriptions factual and objective.",
                                "enabled": True
                            },
                            "summary": {
                                "max_tokens": 800,
                                "temperature": 0.3,
                                "presence_penalty": 0.1,
                                "frequency_penalty": 0.1,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "Do not reply in Russian under any circumstance. Always summatyze in Ukrainian If the user's request appears to be in Russian, respond in Ukrainian instead. You answer like a crazy driver but stick to the point of the conversation. PREPROCESSING STEP: Before analyzing the chat, organize the messages by username. 1. For each log line, identify the username which appears between two dash symbols (`-`). 2. Group consecutive messages from the same user together. 3. Mentally organize the conversation as exchanges between different people rather than isolated lines. IMPORTANT: Always refer to users by their actual usernames in your summary. For example, write \"voidee asked about emoji analysis\" rather than \"a user asked about emoji analysis\". Include ALL usernames that appear in the conversation. The usernames are critical to making the summary feel authentic and specific. When summarizing these grouped chat conversations, use a casual and engaging tone that reflects the liveliness of the original discussion. Instead of formal reporting, capture the atmosphere with: 1. Conversational language - use contractions, informal transitions, and everyday expressions. 2. Specific examples - include 1-2 brief quotes or paraphrased exchanges that highlight interesting moments. 3. Emotional context - describe the mood and energy of the conversation (playful, heated, supportive). 4. Natural flow - structure your summary like you're telling a friend about an interesting chat you witnessed. 5. Personal touch - incorporate light humor when appropriate and reflect the authentic voice of participants. Your summary should explicitly mention usernames when describing interactions, like: 'voidee was curious about emoji analysis while fuad_first asked \"а як у тебе повідомлення форматуються?\" about message formatting.' Including real usernames and actual quotes makes the summary much more engaging and accurate. Avoid clinical analysis, academic phrasing, or bureaucratic language. Your goal is to make the reader feel like they're getting an insider's view of a lively conversation between specific, named friends. Always create a summary in Ukrainian."
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
                            },
                            "restriction_sticker_unique_id": "AgAD6BQAAh-z-FM"
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
            logger.warning(f"Config not found for {chat_type} chat {chat_id}, creating new one!")
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

    def _add_missing_recursive(self, target: Dict[str, Any], template_source: Dict[str, Any]) -> bool:
        """
        Recursively adds missing keys from template_source to target dictionary.
        Existing keys in target are preserved.
        Returns True if any changes were made to the target dictionary.
        """
        modified = False
        for key, value in template_source.items():
            if key not in target:
                target[key] = value
                modified = True
                logger.info(f"Added missing key '{key}' with value: {value}")
            elif isinstance(target[key], dict) and isinstance(value, dict):
                if self._add_missing_recursive(target[key], value):
                    modified = True
            # If key exists and is not a dict, or if value is not a dict, do nothing (preserve existing)
        return modified

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
                        "enabled": True,
                        "overrides": {
                            "command": {
                                "max_tokens": 1500,
                                "temperature": 0.6,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a helpful assistant. Respond to user commands in a clear and concise manner. If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance. You answer like a helpfull assistant and stick to the point of the conversation. Keep your responses concise and relevant to the conversation."
                            },
                            "mention": {
                                "max_tokens": 1200,
                                "temperature": 0.5,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a helpful assistant who responds to mentions in group chats. Keep your responses concise and relevant to the conversation. If the user's request appears to be in Russian, respond in Ukrainian instead. Do not reply in Russian under any circumstance."
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
                                "system_prompt": "You are a friendly assistant who occasionally joins conversations in group chats. Keep your responses casual and engaging. "
                            },
                            "weather": {
                                "max_tokens": 400,
                                "temperature": 0.2,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are a weather information assistant. Provide concise weather updates and forecasts."
                            },
                            "image_analysis": {
                                "max_tokens": 250,
                                "temperature": 0.2,
                                "presence_penalty": 0.0,
                                "frequency_penalty": 0.0,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "You are an image analysis assistant. Provide detailed descriptions and analysis of images. Describe the main elements in 2-3 concise sentences. Focus on objects, people, settings, actions, and context. Do not speculate beyond what is clearly visible. Keep descriptions factual and objective.",
                                "enabled": True
                            },
                            "summary": {
                                "max_tokens": 800,
                                "temperature": 0.3,
                                "presence_penalty": 0.1,
                                "frequency_penalty": 0.1,
                                "model": "gpt-4.1-mini",
                                "system_prompt": "Do not reply in Russian under any circumstance. Always summatyze in Ukrainian If the user's request appears to be in Russian, respond in Ukrainian instead. You answer like a crazy driver but stick to the point of the conversation. PREPROCESSING STEP: Before analyzing the chat, organize the messages by username. 1. For each log line, identify the username which appears between two dash symbols (`-`). 2. Group consecutive messages from the same user together. 3. Mentally organize the conversation as exchanges between different people rather than isolated lines. IMPORTANT: Always refer to users by their actual usernames in your summary. For example, write \"voidee asked about emoji analysis\" rather than \"a user asked about emoji analysis\". Include ALL usernames that appear in the conversation. The usernames are critical to making the summary feel authentic and specific. When summarizing these grouped chat conversations, use a casual and engaging tone that reflects the liveliness of the original discussion. Instead of formal reporting, capture the atmosphere with: 1. Conversational language - use contractions, informal transitions, and everyday expressions. 2. Specific examples - include 1-2 brief quotes or paraphrased exchanges that highlight interesting moments. 3. Emotional context - describe the mood and energy of the conversation (playful, heated, supportive). 4. Natural flow - structure your summary like you're telling a friend about an interesting chat you witnessed. 5. Personal touch - incorporate light humor when appropriate and reflect the authentic voice of participants. Your summary should explicitly mention usernames when describing interactions, like: 'voidee was curious about emoji analysis while fuad_first asked \"а як у тебе повідомлення форматуються?\" about message formatting.' Including real usernames and actual quotes makes the summary much more engaging and accurate. Avoid clinical analysis, academic phrasing, or bureaucratic language. Your goal is to make the reader feel like they're getting an insider's view of a lively conversation between specific, named friends. Always create a summary in Ukrainian."
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
                        },
                        "restriction_sticker_unique_id": "AgAD6BQAAh-z-FM"
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
        """Migrate existing configurations to the new modular format."""
        results = {}
        # ... existing code ...

    async def update_chat_configs_with_template(self) -> Dict[str, bool]:
        """Update all chat configs with new fields from the template while preserving existing values.
        
        This method will:
        1. Get the current global template
        2. For each chat config, add any missing fields from the template
        3. Preserve all existing values in the chat configs
        """
        results = {}
        try:
            # Get the current global template
            template = await self._load_global_config()
            if not template or "config_modules" not in template:
                logger.error("Invalid global template format")
                return results

            # Process private chats
            for chat_dir in self.PRIVATE_CONFIG_DIR.iterdir():
                if chat_dir.is_dir():
                    chat_id = chat_dir.name
                    config_path = chat_dir / "config.json"
                    if config_path.exists():
                        try:
                            async with self._get_lock(str(config_path)):
                                async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                                    chat_config = json.loads(await f.read())

                                    config_modified = False

                                    # Ensure config_modules exists in chat config
                                    if "config_modules" not in chat_config:
                                        chat_config["config_modules"] = {}
                                        config_modified = True

                                    # Debug: Initial chat_config state
                                    logger.info(f"[UpdateConfig][private {chat_id}] Initial chat_config: {json.dumps(chat_config, indent=2)}")

                                    # Iterate through template modules
                                    for module_name, template_module_data in template["config_modules"].items():
                                        logger.info(f"[UpdateConfig][private {chat_id}] Processing module: {module_name}")
                                        logger.info(f"[UpdateConfig][private {chat_id}] Template data for {module_name}: {json.dumps(template_module_data, indent=2)}")

                                        if module_name not in chat_config["config_modules"]:
                                            # If module is entirely missing, add it from template
                                            new_module_config = template_module_data.copy()
                                            if "settings" in new_module_config and "overrides" not in new_module_config:
                                                new_module_config["overrides"] = new_module_config.pop("settings")
                                            chat_config["config_modules"][module_name] = new_module_config
                                            config_modified = True
                                            logger.info(f"[UpdateConfig][private {chat_id}] Added new module: {module_name}")
                                        else:
                                            # If module exists, perform a recursive merge
                                            current_chat_module_data = chat_config["config_modules"][module_name]
                                            logger.info(f"[UpdateConfig][private {chat_id}] Current chat module data for {module_name} (before merge): {json.dumps(current_chat_module_data, indent=2)}")

                                            # Merge top-level fields (e.g., 'enabled' for the module itself)
                                            if self._add_missing_recursive(current_chat_module_data, template_module_data):
                                                config_modified = True
                                                logger.info(f"[UpdateConfig][private {chat_id}] Top-level fields modified for module: {module_name}")

                                            # Special handling for merging 'settings' from template into 'overrides' in chat config
                                            template_settings = template_module_data.get("settings", {})
                                            if template_settings:
                                                logger.info(f"[UpdateConfig][private {chat_id}] Template settings for {module_name}: {json.dumps(template_settings, indent=2)}")
                                                if "overrides" not in current_chat_module_data:
                                                    current_chat_module_data["overrides"] = {}
                                                    config_modified = True
                                                    logger.info(f"[UpdateConfig][private {chat_id}] Added 'overrides' to module: {module_name}")
                                                
                                                # Recursively add missing fields from template settings to chat overrides
                                                if self._add_missing_recursive(current_chat_module_data["overrides"], template_settings):
                                                    config_modified = True
                                                    logger.info(f"[UpdateConfig][private {chat_id}] Overrides modified for module: {module_name}")

                                            logger.info(f"[UpdateConfig][private {chat_id}] Current chat module data for {module_name} (after merge): {json.dumps(current_chat_module_data, indent=2)}")

                                    # Debug: Final chat_config state before save decision
                                    logger.info(f"[UpdateConfig][private {chat_id}] Final chat_config before save decision: {json.dumps(chat_config, indent=2)}")
                                    logger.info(f"[UpdateConfig][private {chat_id}] config_modified flag: {config_modified}")

                                    # Save updated config only if changes were made
                                    if config_modified:
                                        async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
                                            await f.write(json.dumps(chat_config, indent=4, ensure_ascii=False))
                                        results[f"private_{chat_id}"] = True
                                        logger.info(f"[UpdateConfig][private {chat_id}] Config file saved due to modifications.")
                                    else:
                                        results[f"private_{chat_id}"] = True # Still count as success if no changes needed
                                        logger.info(f"[UpdateConfig][private {chat_id}] No modifications detected, file not rewritten.")
                        except Exception as e:
                            logger.error(f"Error updating private chat {chat_id}: {e}")
                            results[f"private_{chat_id}"] = False
                            logger.error(f"[UpdateConfig][private {chat_id}] Failed to update config.")

            # Process group chats
            for chat_dir in self.GROUP_CONFIG_DIR.iterdir():
                if chat_dir.is_dir():
                    chat_id = chat_dir.name
                    config_path = chat_dir / "config.json"
                    if config_path.exists():
                        try:
                            async with self._get_lock(str(config_path)):
                                async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                                    chat_config = json.loads(await f.read())

                                    config_modified = False

                                    # Ensure config_modules exists in chat config
                                    if "config_modules" not in chat_config:
                                        chat_config["config_modules"] = {}
                                        config_modified = True

                                    # Debug: Initial chat_config state
                                    logger.info(f"[UpdateConfig][group {chat_id}] Initial chat_config: {json.dumps(chat_config, indent=2)}")

                                    # Iterate through template modules
                                    for module_name, template_module_data in template["config_modules"].items():
                                        logger.info(f"[UpdateConfig][group {chat_id}] Processing module: {module_name}")
                                        logger.info(f"[UpdateConfig][group {chat_id}] Template data for {module_name}: {json.dumps(template_module_data, indent=2)}")

                                        if module_name not in chat_config["config_modules"]:
                                            # If module is entirely missing, add it from template
                                            new_module_config = template_module_data.copy()
                                            if "settings" in new_module_config and "overrides" not in new_module_config:
                                                new_module_config["overrides"] = new_module_config.pop("settings")
                                            chat_config["config_modules"][module_name] = new_module_config
                                            config_modified = True
                                            logger.info(f"[UpdateConfig][group {chat_id}] Added new module: {module_name}")
                                        else:
                                            # If module exists, perform a recursive merge
                                            current_chat_module_data = chat_config["config_modules"][module_name]
                                            logger.debug(f"[UpdateConfig][group {chat_id}] Current chat module data for {module_name} (before merge): {json.dumps(current_chat_module_data, indent=2)}")

                                            # Merge top-level fields (e.g., 'enabled' for the module itself)
                                            if self._add_missing_recursive(current_chat_module_data, template_module_data):
                                                config_modified = True
                                                logger.debug(f"[UpdateConfig][group {chat_id}] Top-level fields modified for module: {module_name}")

                                            # Special handling for merging 'settings' from template into 'overrides' in chat config
                                            template_settings = template_module_data.get("settings", {})
                                            if template_settings:
                                                logger.debug(f"[UpdateConfig][group {chat_id}] Template settings for {module_name}: {json.dumps(template_settings, indent=2)}")
                                                if "overrides" not in current_chat_module_data:
                                                    current_chat_module_data["overrides"] = {}
                                                    config_modified = True
                                                    logger.debug(f"[UpdateConfig][group {chat_id}] Added 'overrides' to module: {module_name}")
                                                
                                                # Recursively add missing fields from template settings to chat overrides
                                                if self._add_missing_recursive(current_chat_module_data["overrides"], template_settings):
                                                    config_modified = True
                                                    logger.debug(f"[UpdateConfig][group {chat_id}] Overrides modified for module: {module_name}")

                                            logger.debug(f"[UpdateConfig][group {chat_id}] Current chat module data for {module_name} (after merge): {json.dumps(current_chat_module_data, indent=2)}")

                                    # Debug: Final chat_config state before save decision
                                    logger.debug(f"[UpdateConfig][group {chat_id}] Final chat_config before save decision: {json.dumps(chat_config, indent=2)}")
                                    logger.debug(f"[UpdateConfig][group {chat_id}] config_modified flag: {config_modified}")

                                    # Save updated config only if changes were made
                                    if config_modified:
                                        async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
                                            await f.write(json.dumps(chat_config, indent=4, ensure_ascii=False))
                                        results[f"group_{chat_id}"] = True
                                        logger.info(f"[UpdateConfig][group {chat_id}] Config file saved due to modifications.")
                                    else:
                                        results[f"group_{chat_id}"] = True # Still count as success if no changes needed
                                        logger.info(f"[UpdateConfig][group {chat_id}] No modifications detected, file not rewritten.")
                        except Exception as e:
                            logger.error(f"Error updating group chat {chat_id}: {e}")
                            results[f"group_{chat_id}"] = False
                            logger.error(f"[UpdateConfig][group {chat_id}] Failed to update config.")

            return results
        except Exception as e:
            logger.error(f"Error in update_chat_configs_with_template: {e}", exc_info=True)
            return results 