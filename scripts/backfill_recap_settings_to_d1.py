"""Copy every existing PostgreSQL chat_recap_settings row to D1.

Dual-write only mirrors rows as they change, so run this once after deploying
the Worker migration that adds the D1 table:

    docker compose -f docker-compose.prod.yml exec bot python scripts/backfill_recap_settings_to_d1.py

Safe to re-run: each row overwrites the D1 copy with the current PostgreSQL state.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from modules.d1_api_client import D1ApiClient  # noqa: E402


async def main() -> None:
    client = D1ApiClient.from_environment()
    if client is None:
        sys.exit("D1_API_URL and D1_API_TOKEN must be set")
    connection = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "telegram_bot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    try:
        rows = await connection.fetch(
            "SELECT chat_id, enabled, send_time, last_sent_date, last_pinned_message_id, updated_at "
            "FROM chat_recap_settings ORDER BY chat_id"
        )
        for row in rows:
            await client.save_recap_settings(dict(row))
            print(f"chat {row['chat_id']}: enabled={row['enabled']} send_time={row['send_time']}")
        print(f"Copied {len(rows)} recap settings row(s) to D1")
    finally:
        await connection.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
