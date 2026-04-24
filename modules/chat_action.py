"""Reusable typing / chat-action indicator with automatic keepalive."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_KEEPALIVE_INTERVAL = 4.5  # seconds — Telegram indicator expires after ~5 s


async def _keepalive(bot, chat_id: int, action: ChatAction) -> None:
    """Resend chat action every interval until cancelled."""
    try:
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL)
            try:
                await bot.send_chat_action(chat_id=chat_id, action=action)
            except Exception as exc:
                logger.debug("chat_action keepalive error (ignored): %s", exc)
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def chat_action_for(bot, chat_id: int, action: ChatAction = ChatAction.TYPING):
    """Context manager that emits a chat action and keeps it alive until exit."""
    task = None
    try:
        await bot.send_chat_action(chat_id=chat_id, action=action)
        task = asyncio.create_task(_keepalive(bot, chat_id, action))
        yield
    except Exception:
        raise
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@asynccontextmanager
async def chat_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: ChatAction = ChatAction.TYPING,
):
    """Convenience wrapper that resolves chat_id from update.effective_chat."""
    chat = update.effective_chat
    if chat is None:
        yield
        return
    async with chat_action_for(context.bot, chat.id, action):
        yield
