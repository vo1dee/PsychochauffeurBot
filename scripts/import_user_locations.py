"""Import a legacy data/user_locations.csv into the D1 user_locations table.

Copy the old file next to the deployment (its data/ folder is mounted into the
bot container), then run once on the OCI host:

    docker compose -f docker-compose.prod.yml exec bot \
        python scripts/import_user_locations.py data/user_locations_old.csv [--dry-run]

Each user's most recently saved city becomes their home city; rows saved in a
group also become that group's override. Safe to re-run: rows carry their
original timestamps, so they never overwrite a city saved more recently.
"""

import argparse
import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from modules.d1_api_client import D1ApiClient  # noqa: E402

# Rows without a usable timestamp must never win over anything saved later
FALLBACK_TIMESTAMP = datetime(2000, 1, 1)


class Location(NamedTuple):
    user_id: int
    chat_id: int  # 0 = home city
    city: str
    updated_at: datetime


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return FALLBACK_TIMESTAMP


def read_locations(path: Path) -> List[Location]:
    """Return home-city and group-override rows from a legacy CSV.

    Columns are user_id, city, timestamp, chat_id. Header rows and malformed
    rows (including the old bogus "city_name,country_code" header) are skipped.
    """
    latest_home: Dict[int, Location] = {}
    groups: Dict[Tuple[int, int], Location] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                user_id = int(row[0])
            except ValueError:
                continue
            city = row[1].strip()
            if not city:
                continue
            if city.lower() == "kiev":
                city = "Kyiv"
            updated_at = _parse_timestamp(row[2]) if len(row) > 2 else FALLBACK_TIMESTAMP
            raw_chat = row[3].strip() if len(row) > 3 else ""
            chat_id: Optional[int] = int(raw_chat) if raw_chat.lstrip("-").isdigit() else None

            home = Location(user_id, 0, city, updated_at)
            if user_id not in latest_home or updated_at >= latest_home[user_id].updated_at:
                latest_home[user_id] = home
            # A private chat's id equals the user id; only groups get an override
            if chat_id is not None and chat_id not in (0, user_id):
                key = (user_id, chat_id)
                if key not in groups or updated_at >= groups[key].updated_at:
                    groups[key] = Location(user_id, chat_id, city, updated_at)
    return list(latest_home.values()) + list(groups.values())


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="print what would be imported")
    args = parser.parse_args()

    locations = read_locations(args.csv_path)
    homes = sum(1 for loc in locations if loc.chat_id == 0)
    print(f"Found {homes} home city(ies) and {len(locations) - homes} group override(s)")
    if args.dry_run:
        for loc in locations:
            print(f"user {loc.user_id} chat {loc.chat_id or 'home'}: {loc.city} ({loc.updated_at.isoformat()})")
        return

    client = D1ApiClient.from_environment()
    if client is None:
        sys.exit("D1_API_URL and D1_API_TOKEN must be set")
    try:
        for loc in locations:
            await client.set_user_location(loc.user_id, loc.city, chat_id=loc.chat_id, updated_at=loc.updated_at)
        print(f"Imported {len(locations)} row(s) to D1")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
