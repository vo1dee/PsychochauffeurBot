"""
Handler for MessageReactionUpdated updates.

Tracks when users add emoji reactions to messages.
Requires python-telegram-bot >= 21.0.
"""

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from modules.logger import general_logger


async def handle_reaction_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Record user-added reactions to the bot_events table."""
    reaction = update.message_reaction
    if not reaction:
        return

    old_count = len(reaction.old_reaction) if reaction.old_reaction else 0
    new_count = len(reaction.new_reaction) if reaction.new_reaction else 0

    # Only track when a reaction is being added (net positive change)
    if new_count <= old_count:
        return

    user_id = reaction.user.id if reaction.user else None
    chat_id = reaction.chat.id

    general_logger.debug(f"Reaction added in chat {chat_id} by user {user_id}")

    from modules.event_tracker import record_bot_event
    asyncio.ensure_future(record_bot_event('reaction', chat_id, user_id))
