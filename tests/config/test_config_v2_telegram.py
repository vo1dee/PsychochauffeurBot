"""Tests for the schema-driven /config Telegram UI, audit ledger, and leaf ops."""

import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from config_v2 import manager as manager_mod
from config_v2.manager import ConfigManager, telegram_actor
from config_v2.schema import (
    MODULE_REGISTRY,
    module_has_advanced_fields,
    telegram_fields,
    telegram_modules,
)


@pytest_asyncio.fixture
async def mgr():
    """Fresh ConfigManager on a temp SQLite DB (also installs the singleton)."""
    path = tempfile.mktemp(suffix=".db")
    instance = await ConfigManager.create(path)
    yield instance
    await instance.close()
    manager_mod._instance = None
    if os.path.exists(path):
        os.unlink(path)


async def _audit_rows(mgr):
    cursor = await mgr.db.db.execute(
        "SELECT chat_id, module, key, old_value, new_value, actor_id, actor_username, source"
        " FROM config_audit ORDER BY id"
    )
    return [tuple(r) for r in await cursor.fetchall()]


class _User:
    id = 42
    username = "tester"
    full_name = "Test User"


# ---------------------------------------------------------------------------
# Schema exposure
# ---------------------------------------------------------------------------
class TestTelegramSchema:
    def test_removed_modules_and_contexts(self):
        assert "video_send" not in MODULE_REGISTRY
        assert "image_analysis" not in MODULE_REGISTRY["gpt"].model_fields

    def test_group_roster(self):
        paths = {
            (f.module, f.path)
            for m in telegram_modules("group")
            for f in telegram_fields(m, "group")
        }
        assert paths == {
            ("gpt", "enabled"),
            ("chat_behavior", "enabled"),
            ("chat_behavior", "restrictions_enabled"),
            ("chat_behavior", "random_response_settings.enabled"),
            ("chat_behavior", "random_response_settings.min_words"),
            ("chat_behavior", "random_response_settings.message_threshold"),
            ("chat_behavior", "random_response_settings.probability"),
            ("safety", "enabled"),
            ("weather", "enabled"),
            ("weather", "units"),
            ("speechmatics", "enabled"),
            ("speechmatics", "allow_all_users"),
        }

    def test_private_roster_hides_group_only(self):
        assert "chat_behavior" not in telegram_modules("private")
        speech_paths = {f.path for f in telegram_fields("speechmatics", "private")}
        assert speech_paths == {"enabled"}  # allow_all_users is group-only

    def test_supergroup_normalized_to_group(self):
        assert telegram_fields("chat_behavior", "supergroup") == telegram_fields(
            "chat_behavior", "group"
        )

    def test_advanced_fields_detection(self):
        assert module_has_advanced_fields("gpt", "group")  # prompts, temperatures…
        assert not module_has_advanced_fields("weather", "group")


# ---------------------------------------------------------------------------
# Manager: leaf ops + audit ledger
# ---------------------------------------------------------------------------
class TestLeafOpsAndAudit:
    @pytest.mark.asyncio
    async def test_set_leaf_nested_and_typed_read(self, mgr):
        actor = telegram_actor(_User())
        await mgr.set_leaf(
            "-1", "chat_behavior", "random_response_settings.probability", 0.07, actor=actor
        )
        from config_v2.schema import ChatBehaviorConfig

        cfg = await mgr.get_typed_config("-1", ChatBehaviorConfig)
        assert cfg.random_response_settings.probability == 0.07
        assert cfg.random_response_settings.min_words == 5  # untouched default

    @pytest.mark.asyncio
    async def test_reset_leaf_restores_default_and_prunes_blob(self, mgr):
        actor = telegram_actor(_User())
        await mgr.set_leaf(
            "-1", "chat_behavior", "random_response_settings.probability", 0.5, actor=actor
        )
        await mgr.reset_leaf(
            "-1", "chat_behavior", "random_response_settings.probability", actor=actor
        )
        assert not await mgr.has_leaf_override(
            "-1", "chat_behavior", "random_response_settings.probability"
        )
        # empty parent blob row is deleted entirely
        assert await mgr.db.get_value("-1", "chat_behavior", "random_response_settings") is None

    @pytest.mark.asyncio
    async def test_audit_records_actor_and_effective_old_value(self, mgr):
        actor = telegram_actor(_User())
        await mgr.set_leaf(
            "-1", "chat_behavior", "random_response_settings.probability", 0.07, actor=actor
        )
        rows = await _audit_rows(mgr)
        assert rows[-1] == (
            "-1",
            "chat_behavior",
            "random_response_settings.probability",
            "0.02",  # effective default before the change
            "0.07",
            "42",
            "tester",
            "telegram",
        )

    @pytest.mark.asyncio
    async def test_audit_reset_records_null_new_value(self, mgr):
        actor = telegram_actor(_User())
        await mgr.set_leaf("-1", "weather", "units", "imperial", actor=actor)
        await mgr.reset_leaf("-1", "weather", "units", actor=actor)
        rows = await _audit_rows(mgr)
        assert rows[-1][2:5] == ("units", '"imperial"', None)

    @pytest.mark.asyncio
    async def test_unattributed_writes_default_to_system(self, mgr):
        await mgr.set_value("-1", "gpt", "enabled", False)
        rows = await _audit_rows(mgr)
        assert rows[-1][5:] == (None, None, "system")

    @pytest.mark.asyncio
    async def test_noop_write_not_audited(self, mgr):
        await mgr.set_value("-1", "gpt", "enabled", False)
        before = len(await _audit_rows(mgr))
        await mgr.set_value("-1", "gpt", "enabled", False)
        assert len(await _audit_rows(mgr)) == before

    @pytest.mark.asyncio
    async def test_cleanup_prunes_removed_settings_only(self, mgr):
        await mgr.db.set_value("-1", "video_send", "send_video_file", True)
        await mgr.db.set_value("-1", "gpt", "image_analysis", {"enabled": True})
        await mgr.db.set_value("-1", "reactions", "enabled", True)  # unknown but kept
        await mgr._cleanup_removed_settings()
        assert await mgr.db.find_rows("video_send") == []
        assert await mgr.db.find_rows("gpt", "image_analysis") == []
        assert len(await mgr.db.find_rows("reactions")) == 1
        sources = {r[7] for r in await _audit_rows(mgr)}
        assert "system" in sources


# ---------------------------------------------------------------------------
# /config UI
# ---------------------------------------------------------------------------
class TestConfigMenu:
    @pytest.mark.asyncio
    async def test_callback_data_fits_telegram_limit(self, mgr):
        from modules.handlers.config_commands import _build_category, _build_root

        for chat_type in ("group", "private"):
            _, markup = _build_root(chat_type)
            for module in telegram_modules(chat_type):
                _, cat_markup = await _build_category("-1", chat_type, module)
                for row in list(markup.inline_keyboard) + list(cat_markup.inline_keyboard):
                    for button in row:
                        assert len(button.callback_data.encode()) <= 64

    @pytest.mark.asyncio
    async def test_override_shows_marker_and_reset_button(self, mgr):
        from modules.handlers.config_commands import _build_category

        actor = telegram_actor(_User())
        await mgr.set_leaf("-1", "weather", "units", "imperial", actor=actor)
        text, markup = await _build_category("-1", "group", "weather")
        assert "✏️" in text
        reset_buttons = [
            b
            for row in markup.inline_keyboard
            for b in row
            if b.callback_data.startswith("cfg:r:")
        ]
        assert len(reset_buttons) == 1

    def test_parse_value_clamps_and_validates(self):
        from modules.handlers.config_commands import _fields_by_hash, _parse_value

        fields = _fields_by_hash("group").values()
        prob = next(f for f in fields if f.path.endswith("probability"))
        assert _parse_value(prob, "5") == 1.0  # clamped to le
        assert _parse_value(prob, "-1") == 0.0  # clamped to ge
        units = next(f for f in fields if f.path == "units")
        with pytest.raises(ValueError):
            _parse_value(units, "kelvin")

    def test_field_hashes_stable(self):
        from modules.handlers.config_commands import _field_hash

        # Stable identity — a changed hash silently breaks deployed menus
        assert _field_hash("weather", "units") == _field_hash("weather", "units")
        assert _field_hash("gpt", "enabled") != _field_hash("weather", "enabled")


def _make_callback_update(data: str, chat_type: str = "supergroup", status: str = "member"):
    """Fake Update/context pair for a callback press."""
    update = MagicMock()
    update.effective_chat.id = -100123
    update.effective_chat.type = chat_type
    update.effective_user = _User()
    query = update.callback_query
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.delete = AsyncMock()
    context = MagicMock()
    member = MagicMock()
    member.status = status
    context.bot.get_chat_member = AsyncMock(return_value=member)
    return update, context


class TestConfigCallbacks:
    @pytest.mark.asyncio
    async def test_non_admin_press_denied_in_group(self, mgr):
        from modules.handlers.config_commands import MSG_ADMINS_ONLY, handle_config_callback

        update, context = _make_callback_update("cfg:m", status="member")
        await handle_config_callback(update, context)
        update.callback_query.answer.assert_awaited_once_with(MSG_ADMINS_ONLY)
        update.callback_query.edit_message_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_toggle_writes_value_and_audit(self, mgr):
        from modules.handlers.config_commands import _field_hash, handle_config_callback

        fhash = _field_hash("gpt", "enabled")
        update, context = _make_callback_update(f"cfg:s:{fhash}:0", status="administrator")
        await handle_config_callback(update, context)

        assert await mgr.get_effective_leaf("-100123", "gpt", "enabled") is False
        rows = await _audit_rows(mgr)
        assert rows[-1][0] == "-100123"
        assert rows[-1][5:] == ("42", "tester", "telegram")
        update.callback_query.edit_message_text.assert_awaited()  # menu re-rendered

    @pytest.mark.asyncio
    async def test_stale_field_hash_answers_outdated(self, mgr):
        from modules.handlers.config_commands import MSG_STALE_MENU, handle_config_callback

        update, context = _make_callback_update("cfg:s:deadbeef:1", status="creator")
        await handle_config_callback(update, context)
        update.callback_query.answer.assert_awaited_once_with(MSG_STALE_MENU, show_alert=True)

    @pytest.mark.asyncio
    async def test_private_chat_needs_no_admin_check(self, mgr):
        from modules.handlers.config_commands import handle_config_callback

        update, context = _make_callback_update("cfg:m", chat_type="private")
        context.bot.get_chat_member = AsyncMock(side_effect=AssertionError("must not be called"))
        await handle_config_callback(update, context)
        update.callback_query.edit_message_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_group_only_module_rejected_in_private(self, mgr):
        from modules.handlers.config_commands import MSG_STALE_MENU, handle_config_callback

        update, context = _make_callback_update("cfg:c:chat_behavior", chat_type="private")
        await handle_config_callback(update, context)
        update.callback_query.answer.assert_awaited_once_with(MSG_STALE_MENU, show_alert=True)
