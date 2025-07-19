import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.handlers import utility_commands

@pytest.mark.asyncio
async def test_cat_command_calls_cat():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._cat", new=AsyncMock()) as mock_cat:
        await utility_commands.cat_command(update, context)
        mock_cat.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_screenshot_command_calls_screenshot():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._screenshot", new=AsyncMock()) as mock_screenshot:
        await utility_commands.screenshot_command(update, context)
        mock_screenshot.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_count_command_calls_count():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._count", new=AsyncMock()) as mock_count:
        await utility_commands.count_command(update, context)
        mock_count.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_missing_command_calls_missing():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._missing", new=AsyncMock()) as mock_missing:
        await utility_commands.missing_command(update, context)
        mock_missing.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_error_report_command_calls_error_report():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._error_report", new=AsyncMock()) as mock_error_report:
        await utility_commands.error_report_command(update, context)
        mock_error_report.assert_awaited_once_with(update, context) 