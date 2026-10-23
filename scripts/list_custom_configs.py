#!/usr/bin/env python3
"""
List which chats have custom (per-chat) config overrides in the config_v2 SQLite DB.

Read-only. On the OCI host run it inside the bot container:

    docker compose -f docker-compose.prod.yml exec bot python scripts/list_custom_configs.py

Options:
    --global   also print global values stored in the DB (they override the code defaults
               from config_v2/schema.py for every chat)
    --values   print the overridden values, not just the keys
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "config.db"


def _short(value: str, limit: int = 100) -> str:
    text = json.dumps(json.loads(value), ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=os.getenv("CONFIG_DB_PATH", str(DEFAULT_DB)))
    parser.add_argument("--global", dest="show_global", action="store_true")
    parser.add_argument("--values", action="store_true")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Config DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute(
        """
        SELECT v.chat_id, COALESCE(c.chat_type, '?'), COALESCE(c.chat_name, ''),
               v.module, v.key, v.value, v.updated_at
        FROM config_values v LEFT JOIN chats c ON c.chat_id = v.chat_id
        ORDER BY v.chat_id = 'global' DESC, c.chat_type, v.chat_id, v.module, v.key
        """
    ).fetchall()
    total_chats = conn.execute("SELECT COUNT(*) FROM chats WHERE chat_id != 'global'").fetchone()[0]
    conn.close()

    chats: dict = {}
    for chat_id, chat_type, chat_name, module, key, value, updated_at in rows:
        if chat_id == "global" and not args.show_global:
            continue
        chat = chats.setdefault(chat_id, {"type": chat_type, "name": chat_name, "modules": {}})
        chat["modules"].setdefault(module, []).append((key, value, updated_at))

    custom = [cid for cid in chats if cid != "global"]
    print(f"Known chats: {total_chats}, with custom overrides: {len(custom)}\n")

    for chat_id, chat in chats.items():
        print(f"{chat_id}  [{chat['type']}]  {chat['name']}")
        for module, entries in chat["modules"].items():
            if args.values:
                print(f"  {module}:")
                for key, value, updated_at in entries:
                    print(f"    {key} = {_short(value)}  ({updated_at})")
            else:
                print(f"  {module}: {', '.join(key for key, _, _ in entries)}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
