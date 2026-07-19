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
from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Type

from pydantic import BaseModel

from config_v2.database import ConfigDB
from config_v2.schema import MODULE_REGISTRY

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class AuditActor:
    """Who is responsible for a config change (recorded in the audit ledger)."""

    source: str  # 'telegram' | 'web' | 'system'
    id: Optional[str] = None
    username: Optional[str] = None


SYSTEM_ACTOR = AuditActor("system")
WEB_ACTOR = AuditActor("web")


def telegram_actor(user: Any) -> AuditActor:
    """Build an AuditActor from a telegram.User (system actor if user is missing)."""
    if user is None:
        return SYSTEM_ACTOR
    username = getattr(user, "username", None) or getattr(user, "full_name", None)
    return AuditActor("telegram", str(user.id), username)


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

        # Prune rows for settings that were removed from the schema
        await _instance._cleanup_removed_settings()

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
    # Write operations (all audited — see docs/adr/0002)
    # ------------------------------------------------------------------
    async def set_value(
        self,
        chat_id: str,
        module: str,
        key: str,
        value: Any,
        actor: AuditActor = SYSTEM_ACTOR,
    ) -> None:
        """Set a single config value for a chat (or 'global')."""
        chat_id = str(chat_id)
        old = await self.db.get_value(chat_id, module, key)
        await self.db.set_value(chat_id, module, key, value)
        if old != value:
            await self._audit(chat_id, module, key, old, value, actor)

    async def set_module_config(
        self,
        chat_id: str,
        module: str,
        data: dict[str, Any],
        actor: AuditActor = SYSTEM_ACTOR,
    ) -> None:
        """Replace all config values for a module in a chat."""
        chat_id = str(chat_id)
        old_data = await self.db.get_module_config(chat_id, module)
        await self.db.set_module_config(chat_id, module, data)
        for key in old_data.keys() | data.keys():
            old, new = old_data.get(key), data.get(key)
            if old != new:
                await self._audit(chat_id, module, key, old, new, actor)

    async def delete_override(
        self,
        chat_id: str,
        module: str,
        key: str,
        actor: AuditActor = SYSTEM_ACTOR,
    ) -> None:
        """Delete a per-chat override (reverts to global default)."""
        chat_id = str(chat_id)
        old = await self.db.get_value(chat_id, module, key)
        await self.db.delete_value(chat_id, module, key)
        if old is not None:
            await self._audit(chat_id, module, key, old, None, actor)

    async def delete_module_overrides(
        self, chat_id: str, module: str, actor: AuditActor = SYSTEM_ACTOR
    ) -> None:
        """Delete all overrides for a specific module (reverts to global)."""
        chat_id = str(chat_id)
        old_data = await self.db.get_module_config(chat_id, module)
        await self.db.delete_module_config(chat_id, module)
        for key, old in old_data.items():
            await self._audit(chat_id, module, key, old, None, actor)

    async def delete_chat_overrides(
        self, chat_id: str, actor: AuditActor = SYSTEM_ACTOR
    ) -> None:
        """Delete all overrides for a chat (reverts entirely to global)."""
        chat_id = str(chat_id)
        await self.db.delete_chat_config(chat_id)
        await self._audit(chat_id, "*", "*", None, None, actor)

    # ------------------------------------------------------------------
    # Leaf-level access (dotted paths inside a module, used by /config UI)
    # ------------------------------------------------------------------
    async def get_effective_leaf(self, chat_id: str, module: str, path: str) -> Any:
        """Resolved (defaults + global + chat) value of one dotted-path setting."""
        resolved = await self.get_resolved_raw(str(chat_id), module)
        return _walk_path(resolved, path)

    async def has_leaf_override(self, chat_id: str, module: str, path: str) -> bool:
        """True if the chat has its own override for this dotted-path setting."""
        head, _, rest = path.partition(".")
        raw = await self.db.get_value(str(chat_id), module, head)
        if raw is None:
            return False
        return not rest or _walk_path(raw, rest, missing_ok=True) is not _MISSING

    async def set_leaf(
        self,
        chat_id: str,
        module: str,
        path: str,
        value: Any,
        actor: AuditActor = SYSTEM_ACTOR,
    ) -> None:
        """Set one setting by dotted path, creating a per-chat override."""
        chat_id = str(chat_id)
        old = await self.get_effective_leaf(chat_id, module, path)
        head, _, rest = path.partition(".")
        if not rest:
            await self.db.set_value(chat_id, module, head, value)
        else:
            blob = await self.db.get_value(chat_id, module, head) or {}
            if not isinstance(blob, dict):
                blob = {}
            _set_nested(blob, rest, value)
            await self.db.set_value(chat_id, module, head, blob)
        if old != value:
            await self._audit(chat_id, module, path, old, value, actor)

    async def reset_leaf(
        self,
        chat_id: str,
        module: str,
        path: str,
        actor: AuditActor = SYSTEM_ACTOR,
    ) -> None:
        """Remove a per-chat override so the setting follows the global default again."""
        chat_id = str(chat_id)
        head, _, rest = path.partition(".")
        old = await self.db.get_value(chat_id, module, head)
        if old is None:
            return
        if not rest:
            await self.db.delete_value(chat_id, module, head)
            await self._audit(chat_id, module, path, old, None, actor)
            return
        old_leaf = _pop_nested(old, rest)
        if old_leaf is _MISSING:
            return
        if old:
            await self.db.set_value(chat_id, module, head, old)
        else:
            await self.db.delete_value(chat_id, module, head)
        await self._audit(chat_id, module, path, old_leaf, None, actor)

    async def _audit(
        self,
        chat_id: str,
        module: str,
        key: str,
        old: Any,
        new: Any,
        actor: AuditActor,
    ) -> None:
        await self.db.add_audit_entry(
            chat_id, module, key, old, new,
            actor_id=actor.id, actor_username=actor.username, source=actor.source,
        )

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

    async def restore_backup(
        self, backup_id: int, actor: AuditActor = SYSTEM_ACTOR
    ) -> bool:
        ok = await self.db.restore_backup(backup_id)
        if ok:
            await self._audit("*", "*", "*", None, {"restored_backup": backup_id}, actor)
        return ok

    async def delete_backup(self, backup_id: int) -> None:
        await self.db.delete_backup(backup_id)

    async def export_chat(self, chat_id: str) -> dict[str, Any]:
        return await self.db.export_chat_json(chat_id)

    async def import_chat(
        self, chat_id: str, data: dict[str, Any], actor: AuditActor = SYSTEM_ACTOR
    ) -> None:
        await self.db.import_chat_json(chat_id, data)
        await self._audit(str(chat_id), "*", "*", None, {"imported": True}, actor)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _model_to_key(self, model_class: Type[BaseModel]) -> str:
        """Find the module key for a Pydantic model class."""
        for key, cls in MODULE_REGISTRY.items():
            if cls is model_class:
                return key
        raise ValueError(f"Unknown config model: {model_class.__name__}")

    # Modules / keys deleted from the schema whose DB rows should be pruned.
    # Deliberately explicit (not "everything unknown") so rows belonging to
    # broken-but-fixable features (e.g. 'reactions') are left alone.
    _REMOVED_MODULES = ("video_send",)
    _REMOVED_KEYS = (
        ("gpt", "image_analysis"),
        # Inert dotted-key rows written by the old /random command bug
        ("gpt", "random_response_settings.enabled"),
    )

    async def _cleanup_removed_settings(self) -> None:
        """Delete (and audit) config rows orphaned by schema removals. Idempotent."""
        for module in self._REMOVED_MODULES:
            for row in await self.db.find_rows(module):
                await self.delete_override(row["chat_id"], module, row["key"])
        for module, key in self._REMOVED_KEYS:
            for row in await self.db.find_rows(module, key):
                await self.delete_override(row["chat_id"], module, key)

    async def _ensure_global_defaults(self) -> None:
        """Populate global defaults for any module that has no values yet."""
        for module_key, model_class in MODULE_REGISTRY.items():
            existing = await self.db.get_module_config("global", module_key)
            if not existing:
                defaults = model_class().model_dump()
                flat = _flatten_dict(defaults)
                await self.db.set_module_config("global", module_key, flat)
                logger.info("Populated global defaults for module: %s", module_key)


_MISSING = object()


def _walk_path(data: Any, path: str, missing_ok: bool = False) -> Any:
    """Follow a dotted path into nested dicts. Returns _MISSING/None when absent."""
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING if missing_ok else None
        current = current[part]
    return current


def _set_nested(data: dict, path: str, value: Any) -> None:
    """Set a value at a dotted path, creating intermediate dicts."""
    parts = path.split(".")
    for part in parts[:-1]:
        nxt = data.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            data[part] = nxt
        data = nxt
    data[parts[-1]] = value


def _pop_nested(data: dict, path: str) -> Any:
    """Remove and return the value at a dotted path, pruning empty parents.

    Returns _MISSING if the path is absent.
    """
    parts = path.split(".")
    parents: list[dict] = []
    current = data
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            return _MISSING
        parents.append(current)
        current = nxt
    if parts[-1] not in current:
        return _MISSING
    value = current.pop(parts[-1])
    for parent, part in zip(reversed(parents), reversed(parts[:-1])):
        if not parent[part]:
            del parent[part]
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and value == "":
            # Empty string stored in DB for a list field — treat as empty list
            result[key] = []
        else:
            result[key] = value
    return result


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten nested dict: {'a': {'b': 1}} → {'a': {'b': 1}} (keep top-level nested)."""
    # For config storage, we keep the top-level keys as-is but store nested dicts as JSON
    # This preserves the structure for sub-models like GPTContextConfig
    return d
