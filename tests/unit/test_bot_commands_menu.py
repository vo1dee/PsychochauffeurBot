"""Tests for the startup-published Telegram command menu."""

import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from telegram import BotCommandScopeAllChatAdministrators, BotCommandScopeDefault

from modules.bot_commands_menu import ADMIN_COMMANDS, PUBLIC_COMMANDS, publish_command_menu

MODULES = Path(__file__).resolve().parents[2] / "modules"


def _registered_command_names() -> set:
    """Command names registered in either registry (parsed from source)."""
    names = set()
    handler_src = (MODULES / "handler_registry.py").read_text()
    names |= set(re.findall(r'register_text_command\(\s*"([a-z_]+)"', handler_src))
    command_src = (MODULES / "command_registry.py").read_text()
    names |= set(re.findall(r'CommandInfo\(\s*name="([a-z_]+)"', command_src))
    return names


def test_every_menu_command_has_a_handler():
    registered = _registered_command_names()
    menu = {name for name, _ in PUBLIC_COMMANDS + ADMIN_COMMANDS}
    assert menu - registered == set()


def test_menu_entries_follow_telegram_rules():
    names = [name for name, _ in PUBLIC_COMMANDS + ADMIN_COMMANDS]
    assert len(names) == len(set(names)), "duplicate command in menu"
    assert len(names) <= 100
    for name, description in PUBLIC_COMMANDS + ADMIN_COMMANDS:
        assert re.fullmatch(r"[a-z0-9_]{1,32}", name)
        assert 1 <= len(description) <= 256


@pytest.mark.asyncio
async def test_publish_sets_default_and_admin_scopes():
    bot = AsyncMock()
    await publish_command_menu(bot)

    assert bot.set_my_commands.await_count == 2
    default_call, admin_call = bot.set_my_commands.await_args_list
    assert isinstance(default_call.kwargs["scope"], BotCommandScopeDefault)
    assert len(default_call.args[0]) == len(PUBLIC_COMMANDS)
    assert isinstance(admin_call.kwargs["scope"], BotCommandScopeAllChatAdministrators)
    assert len(admin_call.args[0]) == len(PUBLIC_COMMANDS) + len(ADMIN_COMMANDS)


@pytest.mark.asyncio
async def test_publish_swallows_errors():
    bot = AsyncMock()
    bot.set_my_commands.side_effect = RuntimeError("network down")
    await publish_command_menu(bot)  # must not raise
