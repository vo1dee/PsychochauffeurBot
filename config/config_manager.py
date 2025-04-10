"""Configuration manager for handling default and chat-specific configurations."""

import os
import importlib.util
from typing import Dict, Any, Optional, Literal


class ConfigManager:
    """Manages configuration for the bot, supporting default and chat-specific settings."""

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DEFAULT_CONFIG_DIR = os.path.join(base_dir, 'config/default')
    PRIVATE_CONFIG_DIR = os.path.join(base_dir, 'config/private_chats')
    GROUP_CONFIG_DIR = os.path.join(base_dir, 'config/group_chats')

    @classmethod
    def load_module(cls, module_path: str, module_name: str) -> Any:
        """Load a Python module from file path."""
        if not os.path.exists(module_path):
            return None

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @classmethod
    def get_chat_config_dir(cls, chat_id: str, chat_type: str) -> str:
        """Get the appropriate config directory based on chat type."""
        if chat_type == 'private':
            return os.path.join(cls.PRIVATE_CONFIG_DIR, str(chat_id))
        else:
            return os.path.join(cls.GROUP_CONFIG_DIR, str(chat_id))

    @classmethod
    def get_config(
        cls, config_name: str, chat_id: Optional[str] = None, 
        chat_type: Optional[Literal['private', 'group']] = None
    ) -> Dict[str, Any]:
        """Get configuration, prioritizing chat-specific config if available."""
        # Try to load chat-specific config first
        chat_config = None
        if chat_id and chat_type:
            chat_config_dir = cls.get_chat_config_dir(chat_id, chat_type)
            if os.path.exists(chat_config_dir):
                config_path = os.path.join(chat_config_dir, f"{config_name}.py")
                prefix = 'private' if chat_type == 'private' else 'group'
                chat_config = cls.load_module(
                    config_path, f"{prefix}_{chat_id}_{config_name}"
                )

        # Load default config
        default_config_path = os.path.join(cls.DEFAULT_CONFIG_DIR, f"{config_name}.py")
        default_config = cls.load_module(default_config_path, f"default_{config_name}")

        # Create chat-specific config if it doesn't exist but chat_id is provided
        if chat_id and chat_type and not chat_config and default_config:
            default_config_data = getattr(default_config, config_name.upper(), {})
            cls.save_chat_config(config_name, default_config_data, chat_id, chat_type)

        # Return the appropriate config
        if chat_config:
            return getattr(chat_config, config_name.upper(), {})
        elif default_config:
            return getattr(default_config, config_name.upper(), {})
        return {}

    @classmethod
    def save_chat_config(
        cls, config_name: str, config_data: Dict[str, Any], 
        chat_id: str, chat_type: Literal['private', 'group']
    ) -> bool:
        """Save chat-specific configuration."""
        try:
            # Get the appropriate directory based on chat type
            chat_config_dir = cls.get_chat_config_dir(chat_id, chat_type)
            os.makedirs(chat_config_dir, exist_ok=True)

            # Create the config file content
            chat_type_str = 'private chat' if chat_type == 'private' else 'group chat'
            config_content = (
                f"\"\"\"{config_name} configuration for {chat_type_str} {chat_id}\"\"\"\n"
                f"{config_name.upper()} = {config_data}\n"
            )

            # Write the config file
            config_path = os.path.join(chat_config_dir, f"{config_name}.py")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            return True
        except Exception as e:
            print(f"Error saving chat config: {e}")
            return False