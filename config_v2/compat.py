"""
Compatibility layer: makes the new config_v2 system accessible
through the old get_shared_config_manager().get_config() API.

This lets existing bot modules work without changes while we migrate
them to the new typed API one by one.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config_v2.manager import config_manager
from config_v2.schema import MODULE_REGISTRY

logger = logging.getLogger(__name__)


class CompatConfigManager:
    """
    Drop-in replacement for the old config.config_manager.ConfigManager.

    Translates old-style calls like:
        get_config(chat_id, chat_type, module_name="gpt")
    into new-style SQLite reads and returns dicts in the old format.
    """

    async def initialize(self) -> None:
        """No-op — the real init happens in ConfigManager.create()."""
        pass

    async def get_config(
        self,
        chat_id: Optional[str] = None,
        chat_type: Optional[str] = None,
        module_name: Optional[str] = None,
        create_if_missing: bool = True,
        chat_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compatibility wrapper for the old get_config() API.

        Returns data in the old format:
          - Full config: {"chat_metadata": {...}, "config_modules": {"gpt": {"enabled": ..., "overrides": {...}}, ...}}
          - Module config: {"enabled": ..., "overrides": {...}}
          - Global config: {"chat_metadata": {...}, "config_modules": {...}}
        """
        mgr = config_manager()

        # Ensure chat exists in DB if we have info
        if chat_id and chat_type and chat_id != "global":
            await mgr.ensure_chat(chat_id, chat_type, chat_name or "")

        effective_chat = str(chat_id) if chat_id else "global"

        if module_name:
            # Return single module in old format: {"enabled": ..., "overrides": {...}}
            resolved = await mgr.get_resolved_raw(effective_chat, module_name)
            enabled = resolved.pop("enabled", True)
            return {"enabled": enabled, "overrides": resolved}

        # Return full config in old format
        config_modules: Dict[str, Any] = {}
        for mod_key in MODULE_REGISTRY:
            resolved = await mgr.get_resolved_raw(effective_chat, mod_key)
            enabled = resolved.pop("enabled", True)
            config_modules[mod_key] = {"enabled": enabled, "overrides": resolved}

        result: Dict[str, Any] = {"config_modules": config_modules}

        # Add chat_metadata for compatibility
        if effective_chat != "global":
            chat_info = await mgr.db.get_chat(effective_chat)
            result["chat_metadata"] = {
                "chat_id": effective_chat,
                "chat_type": chat_type or (chat_info["chat_type"] if chat_info else "private"),
                "chat_name": chat_name or (chat_info["chat_name"] if chat_info else ""),
                "custom_config_enabled": True,  # Always true in new system (overrides are explicit)
            }
        else:
            result["chat_metadata"] = {
                "chat_id": "global",
                "chat_type": "global",
                "chat_name": "Global Configuration",
                "custom_config_enabled": False,
            }

        return result

    async def save_config(self, *args: Any, **kwargs: Any) -> None:
        """No-op — old save_config is not needed, writes happen via set_value."""
        pass

    async def enable_custom_config(self, *args: Any, **kwargs: Any) -> None:
        """No-op — custom config is always enabled in v2."""
        pass

    async def disable_custom_config(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def enable_module(
        self, chat_id: str, chat_type: str, module_name: str
    ) -> None:
        mgr = config_manager()
        await mgr.set_value(str(chat_id), module_name, "enabled", True)

    async def disable_module(
        self, chat_id: str, chat_type: str, module_name: str
    ) -> None:
        mgr = config_manager()
        await mgr.set_value(str(chat_id), module_name, "enabled", False)

    def get_analysis_cache_config(self) -> Dict[str, Any]:
        """Return default analysis cache config for compatibility."""
        return {
            "max_size": 100,
            "ttl_seconds": 3600,
        }

    async def ensure_chat_dir(self, *args: Any, **kwargs: Any) -> None:
        """No-op — no directories in v2."""
        pass

    async def ensure_dirs(self) -> None:
        """No-op."""
        pass

    async def create_new_chat_config(
        self,
        chat_id: str,
        chat_type: str,
        chat_name: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create chat in DB and return config in old format."""
        mgr = config_manager()
        await mgr.ensure_chat(chat_id, chat_type, chat_name)
        return await self.get_config(chat_id, chat_type, chat_name=chat_name)


# Singleton
_compat_instance: Optional[CompatConfigManager] = None


def get_shared_config_manager() -> CompatConfigManager:
    """Drop-in replacement for config.config_manager.get_shared_config_manager()."""
    global _compat_instance
    if _compat_instance is None:
        _compat_instance = CompatConfigManager()
    return _compat_instance


def set_singleton(manager: Any) -> None:
    """Compatibility shim — accepts but ignores the old ConfigManager."""
    pass
