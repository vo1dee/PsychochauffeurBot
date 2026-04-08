"""
SQLite database layer for config storage.

Tables:
  - chats: chat metadata (id, type, name)
  - config_values: all config values (global + per-chat overrides)
  - backups: named snapshots for backup/restore

No caching — always read from DB. SQLite local reads are sub-millisecond.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.getenv(
    "CONFIG_DB_PATH",
    str(Path(__file__).parent.parent / "data" / "config.db"),
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id   TEXT PRIMARY KEY,
    chat_type TEXT NOT NULL DEFAULT 'private',  -- 'global', 'group', 'supergroup', 'private'
    chat_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config_values (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    TEXT    NOT NULL DEFAULT 'global',  -- 'global' for global defaults
    module     TEXT    NOT NULL,
    key        TEXT    NOT NULL,
    value      TEXT    NOT NULL,  -- JSON-encoded value
    updated_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(chat_id, module, key)
);

CREATE TABLE IF NOT EXISTS backups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    chat_id    TEXT    NOT NULL,  -- 'global' or specific chat_id, '__full__' for full DB
    data       TEXT    NOT NULL,  -- JSON blob
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Ensure global "chat" always exists
INSERT OR IGNORE INTO chats (chat_id, chat_type, chat_name)
VALUES ('global', 'global', 'Global Configuration');
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_config_values_chat_module
    ON config_values(chat_id, module);
CREATE INDEX IF NOT EXISTS idx_backups_chat
    ON backups(chat_id);
"""


class ConfigDB:
    """Async SQLite wrapper for config storage."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create DB file, tables, and indexes."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA_SQL)
        await self._db.executescript(CREATE_INDEX_SQL)
        await self._db.commit()
        logger.info("Config DB initialized at %s", self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "ConfigDB not initialized"
        return self._db

    # ------------------------------------------------------------------
    # Chat management
    # ------------------------------------------------------------------
    async def upsert_chat(
        self, chat_id: str, chat_type: str, chat_name: str = ""
    ) -> None:
        await self.db.execute(
            """INSERT INTO chats (chat_id, chat_type, chat_name, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(chat_id) DO UPDATE SET
                   chat_type = excluded.chat_type,
                   chat_name = CASE WHEN excluded.chat_name != '' THEN excluded.chat_name ELSE chats.chat_name END,
                   updated_at = datetime('now')
            """,
            (chat_id, chat_type, chat_name),
        )
        await self.db.commit()

    async def get_chats(self) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM chats WHERE chat_id != 'global' ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_chat(self, chat_id: str) -> Optional[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM chats WHERE chat_id = ?", (chat_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Config values — flat key/value per module per chat
    # ------------------------------------------------------------------
    async def get_module_config(
        self, chat_id: str, module: str
    ) -> dict[str, Any]:
        """Get all key/value pairs for a module in a chat."""
        cursor = await self.db.execute(
            "SELECT key, value FROM config_values WHERE chat_id = ? AND module = ?",
            (chat_id, module),
        )
        rows = await cursor.fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}

    async def get_all_modules_config(self, chat_id: str) -> dict[str, dict[str, Any]]:
        """Get all modules' config for a chat, keyed by module name."""
        cursor = await self.db.execute(
            "SELECT module, key, value FROM config_values WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            mod = row["module"]
            if mod not in result:
                result[mod] = {}
            result[mod][row["key"]] = json.loads(row["value"])
        return result

    async def set_value(
        self, chat_id: str, module: str, key: str, value: Any
    ) -> None:
        """Set a single config value."""
        await self.db.execute(
            """INSERT INTO config_values (chat_id, module, key, value, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(chat_id, module, key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = datetime('now')
            """,
            (chat_id, module, key, json.dumps(value)),
        )
        await self.db.commit()

    async def set_module_config(
        self, chat_id: str, module: str, data: dict[str, Any]
    ) -> None:
        """Set all values for a module at once (replaces existing)."""
        await self.db.execute(
            "DELETE FROM config_values WHERE chat_id = ? AND module = ?",
            (chat_id, module),
        )
        for key, value in data.items():
            await self.db.execute(
                """INSERT INTO config_values (chat_id, module, key, value, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (chat_id, module, key, json.dumps(value)),
            )
        await self.db.commit()

    async def delete_chat_config(self, chat_id: str) -> None:
        """Delete all config overrides for a chat."""
        await self.db.execute(
            "DELETE FROM config_values WHERE chat_id = ?", (chat_id,)
        )
        await self.db.commit()

    async def delete_value(self, chat_id: str, module: str, key: str) -> None:
        """Delete a single override (reverts to global default)."""
        await self.db.execute(
            "DELETE FROM config_values WHERE chat_id = ? AND module = ? AND key = ?",
            (chat_id, module, key),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------
    async def create_backup(self, name: str, chat_id: str = "__full__") -> int:
        """Create a backup. Returns backup ID."""
        if chat_id == "__full__":
            # Full DB backup — all config values
            cursor = await self.db.execute(
                "SELECT chat_id, module, key, value FROM config_values"
            )
            rows = await cursor.fetchall()
            data = [dict(r) for r in rows]
        else:
            # Per-chat backup
            cursor = await self.db.execute(
                "SELECT module, key, value FROM config_values WHERE chat_id = ?",
                (chat_id,),
            )
            rows = await cursor.fetchall()
            data = [dict(r) for r in rows]

        cursor = await self.db.execute(
            "INSERT INTO backups (name, chat_id, data) VALUES (?, ?, ?)",
            (name, chat_id, json.dumps(data)),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def list_backups(
        self, chat_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        if chat_id:
            cursor = await self.db.execute(
                "SELECT id, name, chat_id, created_at FROM backups WHERE chat_id = ? ORDER BY created_at DESC",
                (chat_id,),
            )
        else:
            cursor = await self.db.execute(
                "SELECT id, name, chat_id, created_at FROM backups ORDER BY created_at DESC"
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def restore_backup(self, backup_id: int) -> bool:
        """Restore a backup by ID."""
        cursor = await self.db.execute(
            "SELECT chat_id, data FROM backups WHERE id = ?", (backup_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False

        data = json.loads(row["data"])
        target_chat = row["chat_id"]

        if target_chat == "__full__":
            # Full restore — clear all, re-insert
            await self.db.execute("DELETE FROM config_values")
            for item in data:
                await self.db.execute(
                    """INSERT INTO config_values (chat_id, module, key, value, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'))""",
                    (item["chat_id"], item["module"], item["key"], item["value"]),
                )
        else:
            # Per-chat restore
            await self.db.execute(
                "DELETE FROM config_values WHERE chat_id = ?", (target_chat,)
            )
            for item in data:
                await self.db.execute(
                    """INSERT INTO config_values (chat_id, module, key, value, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'))""",
                    (target_chat, item["module"], item["key"], item["value"]),
                )

        await self.db.commit()
        return True

    async def delete_backup(self, backup_id: int) -> None:
        await self.db.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
        await self.db.commit()

    async def export_chat_json(self, chat_id: str) -> dict[str, Any]:
        """Export a chat's config as a JSON-serializable dict."""
        chat = await self.get_chat(chat_id)
        modules = await self.get_all_modules_config(chat_id)
        return {"chat": chat, "modules": modules}

    async def import_chat_json(self, chat_id: str, data: dict[str, Any]) -> None:
        """Import a chat's config from exported JSON."""
        if "chat" in data and data["chat"]:
            chat = data["chat"]
            await self.upsert_chat(
                chat_id,
                chat.get("chat_type", "private"),
                chat.get("chat_name", ""),
            )
        for module, values in data.get("modules", {}).items():
            await self.set_module_config(chat_id, module, values)
