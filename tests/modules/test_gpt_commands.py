import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.handlers import gpt_commands

@pytest.mark.asyncio
async def test_ask_gpt_command_calls_ask_gpt() -> None:
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.gpt_commands._ask_gpt", new=AsyncMock()) as mock_ask_gpt:
        await gpt_commands.ask_gpt_command(update, context)
        mock_ask_gpt.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_analyze_command_calls_analyze() -> None:
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.gpt_commands._analyze", new=AsyncMock()) as mock_analyze:
        await gpt_commands.analyze_command(update, context)
        mock_analyze.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_mystats_command_calls_mystats() -> None:
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.gpt_commands._mystats", new=AsyncMock()) as mock_mystats:
        await gpt_commands.mystats_command(update, context)
        mock_mystats.assert_awaited_once_with(update, context) 