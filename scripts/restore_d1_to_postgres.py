"""Restore PostgreSQL (and optionally the config SQLite store) from Cloudflare D1.

This is the reverse of ``scripts/migrate_to_d1.py``: it is used to rebuild a new
bot host's PostgreSQL database when D1 is the only surviving copy of the data.

Sources (pick one per database):
  * ``--export``           run ``wrangler d1 export`` via ``scripts/export_d1_backups.py``
  * ``--data-snapshot``    an existing ``psychochauffeur-data-*.sqlite3`` or ``.sql`` file
  * ``--config-snapshot``  an existing ``psychochauffeur-config-*.sqlite3`` or ``.sql`` file

The PostgreSQL schema is created with the bot's own DDL, rows are inserted with
``ON CONFLICT DO NOTHING`` (safe to re-run), and BIGSERIAL sequences are advanced
past the restored IDs. Neither D1 nor an existing config database is modified
unless ``--overwrite-config`` is given.

Text that was stored in D1 as UTF-8 mis-decoded as Windows-1252 (mojibake such as
``Ñ€ÐµÐ¶Ð¸Ð¼`` for ``режим``) is repaired on the way in; pass ``--no-fix-encoding``
to copy it verbatim.
"""

import argparse
import asyncio
import json
import os
import shutil
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import asyncpg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from scripts.export_d1_backups import export_database  # noqa: E402

BATCH_SIZE = 5000
CONFIG_TABLES = ("chats", "config_values", "backups", "config_audit")


def to_timestamp(value: Any) -> Optional[datetime]:
    """Parse D1 timestamp text (ISO-8601 or SQLite CURRENT_TIMESTAMP, UTC)."""
    if value is None or value == "":
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_bool(value: Any) -> Optional[bool]:
    return None if value is None else bool(int(value))


def to_json_text(value: Any) -> Optional[str]:
    """Pass JSON through as text; asyncpg's default jsonb codec accepts str."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    json.loads(value)  # Fail loudly on corrupt JSON rather than inserting it.
    return str(value)


def to_date(value: Any) -> Optional[date]:
    return None if value in (None, "") else date.fromisoformat(str(value)[:10])


def identity(value: Any) -> Any:
    return value


# Bytes 0x80-0x9F that Windows-1252 leaves undefined survive mis-decoding as U+0080-U+009F.
_MOJIBAKE_MARKERS = ("Ð", "Ñ", "Ò", "Ó", "Ã", "â€", "ðŸ")


def fix_mojibake(value: Any) -> Any:
    """Undo UTF-8 text that was decoded as Windows-1252 (e.g. 'Ñ€ÐµÐ¶Ð¸Ð¼' -> 'режим').

    Strings that do not round-trip cleanly (already-correct Cyrillic, plain ASCII,
    genuinely Latin text) are returned unchanged.
    """
    if not isinstance(value, str) or value.isascii() or not any(m in value for m in _MOJIBAKE_MARKERS):
        return value
    raw = bytearray()
    for char in value:
        try:
            raw += char.encode("cp1252")
        except UnicodeEncodeError:
            if ord(char) > 0xFF:
                return value
            raw.append(ord(char))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return value


FIX_ENCODING = True
FIXED_COUNTS: dict[str, int] = {}


# Column -> converter, in PostgreSQL insert order (parents before children).
TABLES: dict[str, dict[str, Callable[[Any], Any]]] = {
    "chats": {"chat_id": identity, "chat_type": identity, "title": identity, "created_at": to_timestamp},
    "users": {
        "user_id": identity,
        "first_name": identity,
        "last_name": identity,
        "username": identity,
        "is_bot": to_bool,
        "created_at": to_timestamp,
    },
    "messages": {
        "internal_message_id": identity,
        "message_id": identity,
        "chat_id": identity,
        "user_id": identity,
        "timestamp": to_timestamp,
        "text": identity,
        "is_command": to_bool,
        "command_name": identity,
        "is_gpt_reply": to_bool,
        "replied_to_message_id": identity,
        "gpt_context_message_ids": to_json_text,
        "raw_telegram_message": to_json_text,
    },
    "analysis_cache": {
        "chat_id": identity,
        "time_period": identity,
        "message_content_hash": identity,
        "result": identity,
        "created_at": to_timestamp,
    },
    "bot_events": {
        "id": identity,
        "event_type": identity,
        "chat_id": identity,
        "user_id": identity,
        "timestamp": to_timestamp,
    },
    "chat_recap_settings": {
        "chat_id": identity,
        "enabled": to_bool,
        "send_time": identity,
        "last_sent_date": to_date,
        "last_pinned_message_id": identity,
        "updated_at": to_timestamp,
    },
}
SEQUENCES = {"messages": "internal_message_id", "bot_events": "id"}


def open_snapshot(path: Path) -> Path:
    """Return a SQLite file for ``path``, building one next to a ``.sql`` export if needed.

    The export is replayed one statement at a time so memory stays flat even for
    multi-hundred-megabyte dumps on small hosts.
    """
    if path.suffix != ".sql":
        return path
    sqlite_path = path.with_suffix(".sqlite3")
    if sqlite_path.exists():
        print(f"Using existing {sqlite_path}")
        return sqlite_path
    temporary = sqlite_path.with_suffix(".sqlite3.tmp")
    temporary.unlink(missing_ok=True)
    print(f"Building {sqlite_path} from {path} ...")
    try:
        with sqlite3.connect(temporary) as connection, path.open(encoding="utf-8") as dump:
            connection.execute("PRAGMA journal_mode = OFF")
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute("BEGIN")
            statement = ""
            count = 0
            for line in dump:
                statement += line
                if sqlite3.complete_statement(statement):
                    stripped = statement.strip().rstrip(";").strip().upper()
                    # The export manages its own transaction/pragma state; we wrap everything in one.
                    if stripped not in {"BEGIN TRANSACTION", "COMMIT", "PRAGMA DEFER_FOREIGN_KEYS = ON",
                                        "PRAGMA DEFER_FOREIGN_KEYS = OFF"}:
                        connection.execute(statement)
                    statement = ""
                    count += 1
                    if count % 50000 == 0:
                        print(f"  {count:,} statements")
            connection.execute("COMMIT")
        temporary.replace(sqlite_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return sqlite_path


def iter_batches(connection: sqlite3.Connection, table: str, columns: list[str]) -> Iterator[list[tuple]]:
    converters = [TABLES[table][column] for column in columns]
    cursor = connection.execute(f"SELECT {', '.join(columns)} FROM {table}")
    while rows := cursor.fetchmany(BATCH_SIZE):
        if FIX_ENCODING:
            repaired = []
            for row in rows:
                fixed = tuple(fix_mojibake(value) for value in row)
                if fixed != row:
                    FIXED_COUNTS[table] = FIXED_COUNTS.get(table, 0) + 1
                repaired.append(fixed)
            rows = repaired
        yield [tuple(convert(value) for convert, value in zip(converters, row)) for row in rows]


async def restore_data(snapshot: Path, schema_sql: str) -> dict[str, dict[str, int]]:
    """Copy every data table from the D1 snapshot into PostgreSQL."""
    pg = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "telegram_bot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    report: dict[str, dict[str, int]] = {}
    try:
        await pg.execute(schema_sql)
        with sqlite3.connect(snapshot) as source:
            for table, spec in TABLES.items():
                available = {row[1] for row in source.execute(f"PRAGMA table_info({table})")}
                if not available:
                    print(f"{table:15} not in this D1 export; skipped")
                    continue
                columns = [column for column in spec if column in available]
                d1_count = source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                staging = f"restore_{table}"
                async with pg.transaction():
                    await pg.execute(
                        f"CREATE TEMP TABLE {staging} (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP"
                    )
                    for batch in iter_batches(source, table, columns):
                        await pg.copy_records_to_table(staging, records=batch, columns=columns)
                    column_list = ", ".join(columns)
                    status = await pg.execute(
                        f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {staging} "
                        "ON CONFLICT DO NOTHING"
                    )
                inserted = int(status.split()[-1])
                pg_count = await pg.fetchval(f"SELECT COUNT(*) FROM {table}")
                fixed = FIXED_COUNTS.get(table, 0)
                report[table] = {"d1": d1_count, "inserted": inserted, "postgres": pg_count, "encoding_fixed": fixed}
                print(
                    f"{table:15} d1={d1_count:>9,} inserted={inserted:>9,} postgres={pg_count:>9,} "
                    f"encoding_fixed={fixed:>9,}"
                )

        for table, column in SEQUENCES.items():
            await pg.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                f"COALESCE((SELECT MAX({column}) FROM {table}), 0) + 1, false)"
            )
    finally:
        await pg.close()
    return report


def restore_config(snapshot: Path, target: Path, overwrite: bool) -> None:
    """Restore the config_v2 SQLite store from the D1 config snapshot."""
    if target.exists() and not overwrite:
        print(f"Config database {target} already exists; skipping (use --overwrite-config).")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(f".db.bak-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
        shutil.copy2(target, backup)
        print(f"Backed up existing config database to {backup}")
        target.unlink()
    with sqlite3.connect(snapshot) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
        if FIX_ENCODING:
            for table in CONFIG_TABLES:
                columns = [row[1] for row in destination.execute(f"PRAGMA table_info({table})")]
                fixed = 0
                for row in destination.execute(f"SELECT rowid, {', '.join(columns)} FROM {table}").fetchall():
                    repaired = tuple(fix_mojibake(value) for value in row[1:])
                    if repaired != tuple(row[1:]):
                        assignments = ", ".join(f"{column} = ?" for column in columns)
                        destination.execute(f"UPDATE {table} SET {assignments} WHERE rowid = ?", (*repaired, row[0]))
                        fixed += 1
                if fixed:
                    print(f"config.{table:13} encoding_fixed={fixed:,}")
        for table in CONFIG_TABLES:
            count = destination.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"config.{table:13} rows={count:,}")
    print(f"Restored config database to {target}")


def default_serializer(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(type(value))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", action="store_true", help="Export both D1 databases with Wrangler first")
    parser.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "data" / "d1-backups")
    parser.add_argument("--data-snapshot", type=Path, help="psychochauffeur-data .sqlite3 or .sql export")
    parser.add_argument("--config-snapshot", type=Path, help="psychochauffeur-config .sqlite3 or .sql export")
    parser.add_argument(
        "--config-db",
        type=Path,
        default=Path(os.getenv("CONFIG_DB_PATH", str(PROJECT_ROOT / "data" / "config.db"))),
    )
    parser.add_argument("--overwrite-config", action="store_true")
    parser.add_argument("--skip-data", action="store_true")
    parser.add_argument(
        "--no-fix-encoding",
        action="store_true",
        help="Do not repair UTF-8 text that was mis-decoded as Windows-1252 in D1",
    )
    args = parser.parse_args()
    global FIX_ENCODING
    FIX_ENCODING = not args.no_fix_encoding

    if args.export:
        args.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for database in ("psychochauffeur-data", "psychochauffeur-config"):
            export_database(database, args.backup_dir, timestamp)
        args.data_snapshot = args.data_snapshot or args.backup_dir / f"psychochauffeur-data-{timestamp}.sqlite3"
        args.config_snapshot = (
            args.config_snapshot or args.backup_dir / f"psychochauffeur-config-{timestamp}.sqlite3"
        )

    if not args.data_snapshot and not args.config_snapshot:
        parser.error("pass --export, --data-snapshot and/or --config-snapshot")

    if args.data_snapshot and not args.skip_data:
        from modules.database import CREATE_TABLES_SQL

        report = await restore_data(open_snapshot(args.data_snapshot), CREATE_TABLES_SQL)
        mismatched = [table for table, counts in report.items() if counts["postgres"] < counts["d1"]]
        manifest = args.backup_dir / "restore-manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(report, indent=2, default=default_serializer) + "\n", encoding="utf-8"
        )
        print(f"Wrote {manifest}")
        if mismatched:
            print(f"WARNING: PostgreSQL has fewer rows than D1 for: {', '.join(mismatched)}")
            sys.exit(1)
    if args.config_snapshot:
        restore_config(open_snapshot(args.config_snapshot), args.config_db, args.overwrite_config)


if __name__ == "__main__":
    asyncio.run(main())
