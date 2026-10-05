"""Recap settings writes are mirrored to D1 with the full row PostgreSQL returned."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules import database
from modules.d1_api_client import D1ApiClient
from modules.database import Database

ROW = {
    "chat_id": -100123,
    "enabled": True,
    "send_time": "09:30",
    "last_sent_date": date(2026, 10, 5),
    "last_pinned_message_id": 42,
    "updated_at": datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc),
}


def _pool_returning(row: Optional[dict[str, Any]]) -> tuple[MagicMock, AsyncMock]:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)

    @asynccontextmanager
    async def acquire():  # type: ignore[no-untyped-def]
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn.fetchrow


@pytest.fixture
def d1_client() -> MagicMock:
    client = MagicMock()
    client.save_recap_settings = AsyncMock()
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        lambda: Database.upsert_recap_settings(ROW["chat_id"], enabled=True),
        lambda: Database.set_recap_pinned_message(ROW["chat_id"], 42),
        lambda: Database.mark_recap_sent(ROW["chat_id"], date(2026, 10, 5)),
    ],
    ids=["upsert", "pin", "mark_sent"],
)
async def test_recap_writes_mirror_returned_row(call, d1_client: MagicMock) -> None:  # type: ignore[no-untyped-def]
    pool, fetchrow = _pool_returning(ROW)
    with patch.object(Database, "get_pool", new=AsyncMock(return_value=pool)), \
         patch.object(database, "get_d1_api_client", new=AsyncMock(return_value=d1_client)):
        await call()
    assert "RETURNING chat_id, enabled, send_time" in fetchrow.call_args.args[0]
    d1_client.save_recap_settings.assert_awaited_once_with(ROW)


@pytest.mark.asyncio
async def test_mark_recap_sent_lost_race_does_not_mirror(d1_client: MagicMock) -> None:
    pool, _ = _pool_returning(None)
    with patch.object(Database, "get_pool", new=AsyncMock(return_value=pool)), \
         patch.object(database, "get_d1_api_client", new=AsyncMock(return_value=d1_client)):
        claimed = await Database.mark_recap_sent(ROW["chat_id"], date(2026, 10, 5))
    assert claimed is False
    d1_client.save_recap_settings.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_recap_sent_claims_without_d1() -> None:
    pool, _ = _pool_returning(ROW)
    with patch.object(Database, "get_pool", new=AsyncMock(return_value=pool)), \
         patch.object(database, "get_d1_api_client", new=AsyncMock(return_value=None)):
        assert await Database.mark_recap_sent(ROW["chat_id"], date(2026, 10, 5)) is True


@pytest.mark.asyncio
async def test_client_serializes_recap_row() -> None:
    client = D1ApiClient("https://d1.example", "token")
    with patch.object(client, "_post", new=AsyncMock(return_value={"ok": True})) as post:
        await client.save_recap_settings(ROW)
    await client.close()
    post.assert_awaited_once_with(
        "/v1/data/recap/upsert",
        {
            "chat_id": -100123,
            "enabled": True,
            "send_time": "09:30",
            "last_sent_date": "2026-10-05",
            "last_pinned_message_id": 42,
            "updated_at": "2026-10-05T07:00:00+00:00",
        },
    )
