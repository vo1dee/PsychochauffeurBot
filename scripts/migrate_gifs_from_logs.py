#!/usr/bin/env python3
"""
One-time migration: parse chat log files for [ANIMATION] entries and insert them
into the messages table so GIF counts work in /stats, /mystats, /report.

Inserts rows with:
  - negative message_id (below current minimum) to avoid conflicts with real IDs
  - raw_telegram_message = '{"animation": {}}' so the existing queries match
  - text = NULL, is_command = false
  - user_id looked up from the users table by username

Run once: python scripts/migrate_gifs_from_logs.py
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import asyncpg
import pytz
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "telegram_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

LOGS_DIR = Path(__file__).parent.parent / "logs"
KYIV_TZ = pytz.timezone("Europe/Kyiv")

# Matches lines like:
# 2026-02-19 11:38:33,998 +0200 - chat - INFO - Ctx:[-1002096701815][supergroup][Psychochauffeur Club][vo1dee] - [ANIMATION]
LOG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) ([+-]\d{4}) - chat - INFO - "
    r"Ctx:\[(-?\d+)\]\[[^\]]+\]\[[^\]]*\]\[([^\]]+)\] - \[ANIMATION\]"
)


def parse_log_files():
    """Yield (timestamp_utc, chat_id, username) for every [ANIMATION] line in all logs."""
    for log_file in sorted(LOGS_DIR.rglob("*.log")):
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = LOG_RE.match(line)
                    if not m:
                        continue
                    ts_str, tz_str, chat_id_str, username = m.groups()
                    dt_str = f"{ts_str} {tz_str}"
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S,%f %z")
                    ts_utc = dt.astimezone(pytz.UTC)
                    yield ts_utc, int(chat_id_str), username
        except Exception as e:
            print(f"  Warning: could not read {log_file}: {e}", file=sys.stderr)


async def main():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )

    # Find the current lowest negative message_id; we'll go below it
    min_id = await conn.fetchval("SELECT MIN(message_id) FROM messages")
    min_id = min_id or 0
    next_id = min(min_id, 0) - 1

    # Build username -> user_id map from DB
    rows = await conn.fetch("SELECT user_id, username FROM users WHERE username IS NOT NULL")
    username_to_id = {r["username"].lower(): r["user_id"] for r in rows}
    print(f"Loaded {len(username_to_id)} usernames from DB")

    # Collect all animation entries, deduplicate by (chat_id, timestamp, username)
    entries = list(parse_log_files())
    seen = set()
    deduped = []
    for ts, chat_id, username in entries:
        key = (chat_id, ts, username.lower())
        if key not in seen:
            seen.add(key)
            deduped.append((ts, chat_id, username.lower()))
    print(f"Found {len(entries)} animation log lines → {len(deduped)} unique entries")

    # Check which (chat_id, timestamp, username) are already in the DB as animations
    existing = await conn.fetch(
        "SELECT chat_id, timestamp, u.username "
        "FROM messages m JOIN users u ON m.user_id = u.user_id "
        "WHERE raw_telegram_message ? 'animation'"
    )
    already = {(r["chat_id"], r["timestamp"].replace(tzinfo=pytz.UTC), r["username"].lower() if r["username"] else "") for r in existing}
    print(f"Already have {len(already)} animation rows in DB")

    skipped_no_user = 0
    skipped_exists = 0
    inserted = 0
    raw_animation = json.dumps({"animation": {}})

    async with conn.transaction():
        for ts, chat_id, username in deduped:
            key = (chat_id, ts, username)
            if key in already:
                skipped_exists += 1
                continue
            user_id = username_to_id.get(username)
            if user_id is None:
                skipped_no_user += 1
                continue
            await conn.execute("""
                INSERT INTO messages (
                    message_id, chat_id, user_id, timestamp,
                    text, is_command, is_gpt_reply, raw_telegram_message
                ) VALUES ($1, $2, $3, $4, NULL, false, false, $5)
                ON CONFLICT (chat_id, message_id) DO NOTHING
            """, next_id, chat_id, user_id, ts, raw_animation)
            next_id -= 1
            inserted += 1

    await conn.close()

    print(f"\nDone.")
    print(f"  Inserted:           {inserted}")
    print(f"  Skipped (exists):   {skipped_exists}")
    print(f"  Skipped (no user):  {skipped_no_user}")


if __name__ == "__main__":
    asyncio.run(main())
