"""
New ConfigManager with typed accessor.

Usage:
    from config_v2.manager import get_config, config_manager

    # Get resolved config (global defaults + per-chat overrides merged)
    gpt = await get_config(chat_id, GPTConfig)
    gpt.command.temperature  # float, type-checked

    # Set a per-chat override
    await config_manager().set_value(chat_id, "gpt", "command", {...})

    # Set a global default
    await config_manager().set_value("global", "gpt", "command", {...})
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TypeVar, Type

from pydantic import BaseModel

from config_v2.database import ConfigDB
from config_v2.schema import MODULE_REGISTRY

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Singleton
_instance: Optional[ConfigManager] = None


def config_manager() -> ConfigManager:
    """Get the singleton ConfigManager."""
    assert _instance is not None, "ConfigManager not initialized — call await ConfigManager.create() first"
    return _instance


async def get_config(chat_id: str | int, model_class: Type[T]) -> T:
    """
    Get resolved config for a chat.

    Merges global defaults → per-chat overrides → Pydantic defaults (for missing keys).
    Returns a fully populated Pydantic model instance.
    """
    return await config_manager().get_typed_config(str(chat_id), model_class)


class ConfigManager:
    """Manages config reads/writes through SQLite."""

    def __init__(self, db: ConfigDB) -> None:
        self.db = db

    @classmethod
    async def create(cls, db_path: str | None = None) -> ConfigManager:
        """Create and initialize the singleton ConfigManager."""
        global _instance
        from config_v2.database import DB_PATH

        db = ConfigDB(db_path or DB_PATH)
        await db.initialize()
        _instance = cls(db)

        # Ensure global defaults exist for all registered modules
        await _instance._ensure_global_defaults()

        logger.info("ConfigManager v2 initialized")
        return _instance

    async def close(self) -> None:
        await self.db.close()

    # ------------------------------------------------------------------
    # Typed config access (the main API)
    # ------------------------------------------------------------------
    async def get_typed_config(self, chat_id: str, model_class: Type[T]) -> T:
        """
        Resolve config for a chat by merging:
        1. Pydantic defaults (from the model class)
        2. Global DB values (chat_id='global')
        3. Per-chat DB overrides (if chat_id != 'global')

        Returns a fully populated Pydantic model.
        """
        # Find which module key maps to this model class
        module_key = self._model_to_key(model_class)

        # Start with Pydantic defaults
        defaults = model_class().model_dump()

        # Layer global values on top
        global_values = await self.db.get_module_config("global", module_key)
        merged = _deep_merge(defaults, global_values)

        # Layer per-chat overrides on top (if not requesting global itself)
        if chat_id != "global":
            chat_values = await self.db.get_module_config(str(chat_id), module_key)
            merged = _deep_merge(merged, chat_values)

        return model_class.model_validate(merged)

    async def get_raw_config(
        self, chat_id: str, module: str
    ) -> dict[str, Any]:
        """Get raw (unmerged) config values for a module in a chat."""
        return await self.db.get_module_config(chat_id, module)

    async def get_resolved_raw(
        self, chat_id: str, module: str
    ) -> dict[str, Any]:
        """Get merged config as a dict (global + per-chat)."""
        model_class = MODULE_REGISTRY.get(module)
        if not model_class:
            return {}
        obj = await self.get_typed_config(chat_id, model_class)
        return obj.model_dump()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    async def set_value(
        self, chat_id: str, module: str, key: str, value: Any
    ) -> None:
        """Set a single config value for a chat (or 'global')."""
        await self.db.set_value(str(chat_id), module, key, value)

    async def set_module_config(
        self, chat_id: str, module: str, data: dict[str, Any]
    ) -> None:
        """Replace all config values for a module in a chat."""
        await self.db.set_module_config(str(chat_id), module, data)

    async def delete_override(
        self, chat_id: str, module: str, key: str
    ) -> None:
        """Delete a per-chat override (reverts to global default)."""
        await self.db.delete_value(str(chat_id), module, key)

    async def delete_chat_overrides(self, chat_id: str) -> None:
        """Delete all overrides for a chat (reverts entirely to global)."""
        await self.db.delete_chat_config(str(chat_id))

    async def ensure_chat(
        self, chat_id: str | int, chat_type: str, chat_name: str = ""
    ) -> None:
        """Ensure a chat exists in the DB."""
        await self.db.upsert_chat(str(chat_id), chat_type, chat_name)

    # ------------------------------------------------------------------
    # Backup / restore / export
    # ------------------------------------------------------------------
    async def create_backup(self, name: str, chat_id: str = "__full__") -> int:
        return await self.db.create_backup(name, chat_id)

    async def list_backups(self, chat_id: Optional[str] = None) -> list[dict]:
        return await self.db.list_backups(chat_id)

    async def restore_backup(self, backup_id: int) -> bool:
        return await self.db.restore_backup(backup_id)

    async def delete_backup(self, backup_id: int) -> None:
        await self.db.delete_backup(backup_id)

    async def export_chat(self, chat_id: str) -> dict[str, Any]:
        return await self.db.export_chat_json(chat_id)

    async def import_chat(self, chat_id: str, data: dict[str, Any]) -> None:
        await self.db.import_chat_json(chat_id, data)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _model_to_key(self, model_class: Type[BaseModel]) -> str:
        """Find the module key for a Pydantic model class."""
        for key, cls in MODULE_REGISTRY.items():
            if cls is model_class:
                return key
        raise ValueError(f"Unknown config model: {model_class.__name__}")

    async def _ensure_global_defaults(self) -> None:
        """Populate global defaults for any module that has no values yet."""
        for module_key, model_class in MODULE_REGISTRY.items():
            existing = await self.db.get_module_config("global", module_key)
            if not existing:
                defaults = model_class().model_dump()
                flat = _flatten_dict(defaults)
                await self.db.set_module_config("global", module_key, flat)
                logger.info("Populated global defaults for module: %s", module_key)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten nested dict: {'a': {'b': 1}} → {'a': {'b': 1}} (keep top-level nested)."""
    # For config storage, we keep the top-level keys as-is but store nested dicts as JSON
    # This preserves the structure for sub-models like GPTContextConfig
    return d
