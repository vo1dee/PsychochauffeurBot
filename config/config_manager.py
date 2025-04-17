"""Configuration manager for handling default and chat-specific configurations."""

import os
import json
from typing import Dict, Any, Optional, Literal


class ConfigManager:
    """Manages configuration for the bot, supporting default and chat-specific JSON settings."""

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DEFAULT_CONFIG_DIR = os.path.join(base_dir, 'config', 'default')
    GLOBAL_CONFIG_DIR = os.path.join(base_dir, 'config', 'global')
    PRIVATE_CONFIG_DIR = os.path.join(base_dir, 'config', 'private_chats')
    GROUP_CONFIG_DIR = os.path.join(base_dir, 'config', 'group_chats')

    @classmethod
    def ensure_dirs(cls) -> None:
        """Ensure that base directories for configuration exist."""
        for d in (
            cls.DEFAULT_CONFIG_DIR,
            os.path.join(cls.DEFAULT_CONFIG_DIR, 'examples'),
            cls.GLOBAL_CONFIG_DIR,
            cls.PRIVATE_CONFIG_DIR,
            cls.GROUP_CONFIG_DIR,
        ):
            os.makedirs(d, exist_ok=True)

    @classmethod
    def get_chat_config_dir(cls, chat_id: str, chat_type: str) -> str:
        """Get the directory path for a chat's configurations."""
        base = cls.PRIVATE_CONFIG_DIR if chat_type == 'private' else cls.GROUP_CONFIG_DIR
        return os.path.join(base, str(chat_id))

    @classmethod
    def get_config(
        cls, config_name: str, chat_id: Optional[str] = None,
        chat_type: Optional[Literal['private', 'group']] = None
    ) -> Dict[str, Any]:
        """Retrieve configuration data, checking chat-specific, then global, then default JSON files."""
        cls.ensure_dirs()
        # 1. Chat-specific override
        if chat_type in ('private', 'group') and chat_id:
            chat_dir = cls.get_chat_config_dir(chat_id, chat_type)
            os.makedirs(chat_dir, exist_ok=True)
            path = os.path.join(chat_dir, f"{config_name}.json")
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except json.JSONDecodeError:
                    pass
        # 2. Global override
        cls.ensure_dirs()
        global_path = os.path.join(cls.GLOBAL_CONFIG_DIR, f"{config_name}.json")
        if os.path.exists(global_path):
            try:
                with open(global_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        # 3. Default
        default_path = os.path.join(cls.DEFAULT_CONFIG_DIR, f"{config_name}.json")
        if os.path.exists(default_path):
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}


    @classmethod
    def save_chat_config(
        cls, config_name: str, config_data: Dict[str, Any],
        chat_id: Optional[str] = None,
        chat_type: Literal['private', 'group', 'global'] = 'global'
    ) -> bool:
        """Save configuration data to chat-specific, global, or default override JSON file."""
        try:
            cls.ensure_dirs()
            # Determine target directory
            if chat_type == 'global':
                target_dir = cls.GLOBAL_CONFIG_DIR
            elif chat_type in ('private', 'group') and chat_id:
                target_dir = cls.get_chat_config_dir(chat_id, chat_type)
            else:
                return False
            os.makedirs(target_dir, exist_ok=True)
            path = os.path.join(target_dir, f"{config_name}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving chat config: {e}")
            return False