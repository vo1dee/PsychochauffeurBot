"""Export both production D1 databases into local SQL and SQLite snapshots."""

import argparse
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DATABASES = ("psychochauffeur-data", "psychochauffeur-config")


def export_database(name: str, backup_dir: Path, timestamp: str) -> None:
    """Export one remote D1 database and create a locally queryable snapshot."""
    sql_file = backup_dir / f"{name}-{timestamp}.sql"
    sqlite_file = backup_dir / f"{name}-{timestamp}.sqlite3"
    temporary_sqlite_file = sqlite_file.with_suffix(".sqlite3.tmp")
    command = [
        "npx",
        "wrangler",
        "d1",
        "export",
        name,
        "--remote",
        "--output",
        str(sql_file.resolve()),
        "--skip-confirmation",
    ]
    subprocess.run(command, check=True, cwd="worker")
    print(f"Building local SQLite snapshot {sqlite_file.name}...")
    try:
        with sqlite3.connect(temporary_sqlite_file) as connection:
            connection.executescript(sql_file.read_text(encoding="utf-8"))
        temporary_sqlite_file.replace(sqlite_file)
    except BaseException:
        temporary_sqlite_file.unlink(missing_ok=True)
        raise
    print(f"Created {sqlite_file}")


def main() -> None:
    """Create dated backups, retaining a bounded number of complete backup sets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/d1-backups"))
    parser.add_argument("--keep", type=int, default=30)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for database in DATABASES:
        export_database(database, args.output_dir, timestamp)

    snapshots = sorted(args.output_dir.glob("*.sqlite3"), reverse=True)
    for snapshot in snapshots[args.keep * len(DATABASES) :]:
        snapshot.unlink()
        sql_file = snapshot.with_suffix(".sql")
        if sql_file.exists():
            sql_file.unlink()


if __name__ == "__main__":
    main()
