import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.handlers import utility_commands
import typing

@pytest.mark.asyncio
async def test_cat_command_calls_cat(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._cat", new=AsyncMock()) as mock_cat:
        await utility_commands.cat_command(mock_update, mock_context)
        mock_cat.assert_awaited_once_with(mock_update, mock_context)

@pytest.mark.asyncio
async def test_screenshot_command_calls_screenshot(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._screenshot", new=AsyncMock()) as mock_screenshot:
        await utility_commands.screenshot_command(mock_update, mock_context)
        mock_screenshot.assert_awaited_once_with(mock_update, mock_context)

@pytest.mark.asyncio
async def test_count_command_calls_count(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._count", new=AsyncMock()) as mock_count:
        await utility_commands.count_command(mock_update, mock_context)
        mock_count.assert_awaited_once_with(mock_update, mock_context)

@pytest.mark.asyncio
async def test_missing_command_calls_missing() -> None:
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.utility_commands._missing", new=AsyncMock()) as mock_missing:
        await utility_commands.missing_command(update, context)
        mock_missing.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_error_report_command_calls_error_report(mock_update: typing.Any, mock_context: typing.Any) -> None:
    with patch("modules.handlers.utility_commands._error_report", new=AsyncMock()) as mock_error_report:
        await utility_commands.error_report_command(mock_update, mock_context)
        mock_error_report.assert_awaited_once_with(mock_update, mock_context) 