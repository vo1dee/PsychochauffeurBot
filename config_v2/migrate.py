"""
One-time migration: read existing JSON configs → populate SQLite.

Usage:
    python -m config_v2.migrate
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from config_v2.database import ConfigDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OLD_CONFIG_DIR = Path(__file__).parent.parent / "config"


def _parse_old_config(path: Path) -> dict | None:
    """Read and parse an old JSON config file."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to read %s: %s", path, e)
        return None


def _extract_module_values(module_data: dict) -> dict:
    """
    Convert old module format:
        {"enabled": true, "overrides": {"key": "val"}}
    Into flat dict:
        {"enabled": true, "key": "val"}
    """
    result: dict = {}

    enabled = module_data.get("enabled")
    if enabled is not None:
        result["enabled"] = enabled

    overrides = module_data.get("overrides", {})
    for key, value in overrides.items():
        result[key] = value

    return result


async def migrate(db_path: str | None = None) -> None:
    """Run the migration."""
    db = ConfigDB(db_path or os.getenv("CONFIG_DB_PATH", str(Path(__file__).parent.parent / "data" / "config.db")))
    await db.initialize()

    migrated = 0

    # 1. Migrate global config
    global_path = OLD_CONFIG_DIR / "global" / "global_config.json"
    if global_path.exists():
        data = _parse_old_config(global_path)
        if data:
            modules = data.get("config_modules", {})
            for module_name, module_data in modules.items():
                values = _extract_module_values(module_data)
                await db.set_module_config("global", module_name, values)
                logger.info("  Global module '%s': %d values", module_name, len(values))
            migrated += 1
            logger.info("Migrated global config")

    # 2. Migrate group configs
    group_dir = OLD_CONFIG_DIR / "group"
    if group_dir.exists():
        for chat_dir in sorted(group_dir.iterdir()):
            config_file = chat_dir / "config.json"
            if not config_file.exists():
                continue

            data = _parse_old_config(config_file)
            if not data:
                continue

            chat_id = str(chat_dir.name)
            meta = data.get("chat_metadata", {})
            chat_type = meta.get("chat_type", "supergroup")
            chat_name = meta.get("chat_name", "")

            # Only migrate if custom config was enabled (otherwise it's just a copy of global)
            custom_enabled = meta.get("custom_config_enabled", False)

            await db.upsert_chat(chat_id, chat_type, chat_name)

            if custom_enabled:
                modules = data.get("config_modules", {})
                for module_name, module_data in modules.items():
                    values = _extract_module_values(module_data)
                    await db.set_module_config(chat_id, module_name, values)
                logger.info(
                    "Migrated group %s (%s) — %d modules",
                    chat_id, chat_name, len(modules),
                )
            else:
                logger.info(
                    "Registered group %s (%s) — using global defaults",
                    chat_id, chat_name,
                )
            migrated += 1

    # 3. Migrate private configs
    private_dir = OLD_CONFIG_DIR / "private"
    if private_dir.exists():
        for chat_dir in sorted(private_dir.iterdir()):
            config_file = chat_dir / "config.json"
            if not config_file.exists():
                continue

            data = _parse_old_config(config_file)
            if not data:
                continue

            chat_id = str(chat_dir.name)
            meta = data.get("chat_metadata", {})
            chat_type = "private"
            chat_name = meta.get("chat_name", f"private_{chat_id}")

            custom_enabled = meta.get("custom_config_enabled", False)

            await db.upsert_chat(chat_id, chat_type, chat_name)

            if custom_enabled:
                modules = data.get("config_modules", {})
                for module_name, module_data in modules.items():
                    values = _extract_module_values(module_data)
                    await db.set_module_config(chat_id, module_name, values)
                logger.info(
                    "Migrated private %s (%s) — %d modules",
                    chat_id, chat_name, len(modules),
                )
            else:
                logger.info(
                    "Registered private %s (%s) — using global defaults",
                    chat_id, chat_name,
                )
            migrated += 1

    await db.close()
    logger.info("Migration complete: %d configs processed", migrated)


if __name__ == "__main__":
    asyncio.run(migrate())
