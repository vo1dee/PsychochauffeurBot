"""Export the existing PostgreSQL and config SQLite data as D1 import SQL.

Apply Worker migrations first, inspect the generated manifest, then import each
file with ``npm --prefix worker exec wrangler -- d1 execute ... --remote --file``.
The script does not contact Cloudflare and never changes either source database.
"""

import argparse
import asyncio
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, TextIO

import asyncpg
from dotenv import load_dotenv


DATA_TABLES = ("chats", "users", "messages", "analysis_cache", "bot_events")
CONFIG_TABLES = ("chats", "config_values", "backups", "config_audit")

# Match the production bot's connection behavior regardless of the caller's
# current working directory.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def sql_literal(value: Any) -> str:
    """Encode a Python value as a portable SQLite SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (datetime, date)):
        return sql_literal(value.isoformat())
    if isinstance(value, (dict, list)):
        return sql_literal(json.dumps(value, separators=(",", ":")))
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def write_insert(output: TextIO, table: str, row: dict[str, Any]) -> None:
    """Write one idempotent D1 insert statement."""
    columns = ", ".join(row.keys())
    values = ", ".join(sql_literal(value) for value in row.values())
    output.write(f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({values});\n")


async def export_postgres(output_path: Path) -> dict[str, int]:
    """Stream PostgreSQL tables into D1-compatible SQL without loading all history."""
    connection = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "telegram_bot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    counts: dict[str, int] = {}
    try:
        with output_path.open("w", encoding="utf-8") as output:
            output.write("PRAGMA defer_foreign_keys = on;\n")
            async with connection.transaction():
                for table in DATA_TABLES:
                    count = 0
                    async for record in connection.cursor(f"SELECT * FROM {table}"):
                        row = dict(record)
                        for key in ("gpt_context_message_ids", "raw_telegram_message"):
                            if (
                                key in row
                                and row[key] is not None
                                and not isinstance(row[key], str)
                            ):
                                row[key] = json.dumps(row[key], separators=(",", ":"))
                        write_insert(output, table, row)
                        count += 1
                    counts[table] = count
    finally:
        await connection.close()
    return counts


def export_config(database_path: Path, output_path: Path) -> dict[str, int]:
    """Export the existing local configuration SQLite database as D1 SQL."""
    counts: dict[str, int] = {}
    with sqlite3.connect(database_path) as connection, output_path.open(
        "w", encoding="utf-8"
    ) as output:
        output.write("PRAGMA defer_foreign_keys = on;\n")
        connection.row_factory = sqlite3.Row
        for table in CONFIG_TABLES:
            rows = connection.execute(f"SELECT * FROM {table}")
            count = 0
            for row in rows:
                write_insert(output, table, dict(row))
                count += 1
            counts[table] = count
    return counts


async def main() -> None:
    """Generate SQL imports and a count manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/d1-migration"))
    parser.add_argument("--config-db", type=Path, default=Path("data/config.db"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data_file = args.output_dir / "data.sql"
    config_file = args.output_dir / "config.sql"
    counts = {
        "data": await export_postgres(data_file),
        "config": export_config(args.config_db, config_file),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(counts, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {data_file}, {config_file}, and {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    asyncio.run(main())
