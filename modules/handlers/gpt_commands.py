"""
GPT-related command handlers.

Contains handlers for AI/GPT functionality including ask, analyze, and stats commands.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import existing GPT functions
from modules.gpt import ask_gpt_command as _ask_gpt, analyze_command as _analyze, mystats_command as _mystats

logger = logging.getLogger(__name__)


async def ask_gpt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ask command for GPT queries."""
    await _ask_gpt(update, context)


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /analyze command for GPT analysis."""
    await _analyze(update, context)


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /mystats command for user statistics."""
    await _mystats(update, context)