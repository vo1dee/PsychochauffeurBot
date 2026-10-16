"""Tests for saved /weather locations (D1 with CSV fallback) and the CSV importer."""

import importlib.util
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from modules import user_locations
from modules.d1_api_client import D1ApiError

USER = 42
GROUP = -100123


def _client() -> MagicMock:
    client = MagicMock()
    client.set_user_location = AsyncMock()
    client.get_user_location = AsyncMock(return_value="Lviv")
    return client


@pytest.mark.asyncio
async def test_private_chat_saves_home_city_only() -> None:
    client = _client()
    with patch.object(user_locations, "get_d1_api_client", AsyncMock(return_value=client)):
        await user_locations.save_user_location(USER, " kiev ", USER)
    client.set_user_location.assert_awaited_once_with(USER, "Kyiv")


@pytest.mark.asyncio
async def test_group_saves_home_city_and_override() -> None:
    client = _client()
    with patch.object(user_locations, "get_d1_api_client", AsyncMock(return_value=client)):
        await user_locations.save_user_location(USER, "Lviv", GROUP)
    assert client.set_user_location.await_args_list == [
        call(USER, "Lviv"),
        call(USER, "Lviv", chat_id=GROUP),
    ]


@pytest.mark.asyncio
async def test_lookup_passes_group_only_for_groups() -> None:
    client = _client()
    with patch.object(user_locations, "get_d1_api_client", AsyncMock(return_value=client)):
        assert await user_locations.get_last_used_city(USER, GROUP) == "Lviv"
        assert await user_locations.get_last_used_city(USER, USER) == "Lviv"
    assert client.get_user_location.await_args_list == [call(USER, GROUP), call(USER, None)]


@pytest.mark.asyncio
async def test_falls_back_to_csv_when_d1_fails() -> None:
    client = _client()
    client.set_user_location.side_effect = D1ApiError("down")
    client.get_user_location.side_effect = D1ApiError("down")
    with patch.object(user_locations, "get_d1_api_client", AsyncMock(return_value=client)), \
            patch.object(user_locations.file_manager, "save_user_location") as csv_save, \
            patch.object(user_locations.utils, "get_last_used_city", return_value="Odesa") as csv_get:
        await user_locations.save_user_location(USER, "Odesa", GROUP)
        assert await user_locations.get_last_used_city(USER, GROUP) == "Odesa"
    assert csv_save.call_args_list == [call(USER, "Odesa"), call(USER, "Odesa", GROUP)]
    csv_get.assert_called_once_with(USER, GROUP)


@pytest.mark.asyncio
async def test_uses_csv_when_d1_not_configured() -> None:
    with patch.object(user_locations, "get_d1_api_client", AsyncMock(return_value=None)), \
            patch.object(user_locations.file_manager, "save_user_location") as csv_save:
        await user_locations.save_user_location(USER, "Kharkiv", USER)
    csv_save.assert_called_once_with(USER, "Kharkiv")


def _load_import_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "import_user_locations.py"
    spec = importlib.util.spec_from_file_location("import_user_locations", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_import_reads_legacy_csv(tmp_path: Path) -> None:
    script = _load_import_script()
    csv_path = tmp_path / "user_locations.csv"
    csv_path.write_text(
        "user_id,city,timestamp,chat_id\n"
        "city_name,country_code\n"
        "42,Kiev,2024-01-05T10:00:00,\n"
        "42,Lviv,2024-03-01T09:00:00,-1001\n"
        "42,Odesa,2024-02-01T09:00:00,42\n"
        "7,Kharkiv,not-a-date,\n"
        "8,,2024-01-01T00:00:00,\n",
        encoding="utf-8",
    )
    rows = {(loc.user_id, loc.chat_id): loc for loc in script.read_locations(csv_path)}

    assert set(rows) == {(42, 0), (42, -1001), (7, 0)}
    assert rows[(42, 0)].city == "Lviv"  # most recent save becomes the home city
    assert rows[(42, -1001)].city == "Lviv"
    assert rows[(7, 0)].updated_at == datetime(2000, 1, 1)  # never beats newer data
