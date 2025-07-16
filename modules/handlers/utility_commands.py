"""
Utility command handlers.

Contains handlers for utility commands like cat, screenshot, count, etc.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import existing utility functions
from modules.utils import cat_command as _cat, screenshot_command as _screenshot
from modules.count_command import count_command as _count, missing_command as _missing
from modules.error_analytics import error_report_command as _error_report

logger = logging.getLogger(__name__)


async def cat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cat command for random cat photos."""
    await _cat(update, context)


async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /flares command for solar flares screenshot."""
    await _screenshot(update, context)


async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /count command for message counting."""
    await _count(update, context)


async def missing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /missing command for missing features."""
    await _missing(update, context)


async def error_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /error_report command for error reporting."""
    await _error_report(update, context)