"""
Telegram command menu ("/" button) published by the bot at startup.

This replaces the list maintained by hand in BotFather, so the menu stays in
sync with the handlers registered in code. Admin-only commands are published
under the chat-administrators scope, so regular group members don't see them.
"""

import logging
from typing import List, Tuple

from telegram import Bot, BotCommand, BotCommandScopeAllChatAdministrators, BotCommandScopeDefault

logger = logging.getLogger(__name__)

# Shown to everyone, most-used first.
PUBLIC_COMMANDS: List[Tuple[str, str]] = [
    ("ask", "Ask the AI anything (searches the web if needed)"),
    ("tldr", "Summarize a message or link (reply to it)"),
    ("song", "Download a song by name or by Spotify/Apple/Deezer/YouTube link"),
    ("short", "Download a YouTube Short (reply to a message with the link)"),
    ("analyze", "Summarize today's chat"),
    ("weather", "Current weather: /weather <city>"),
    ("gm", "Geomagnetic storm forecast"),
    ("flares", "Current solar flare activity"),
    ("nasa", "NASA Astronomy Picture of the Day"),
    ("cat", "Random cat picture"),
    ("stats", "Chat activity stats: /stats [days|all]"),
    ("mystats", "Your personal message stats"),
    ("count", "How often a word was used: /count <word>"),
    ("missing", "When a user was last seen: /missing @user"),
    ("report", "Bot usage report: /report [days]"),
    ("ping", "Check if the bot is online"),
    ("help", "All commands and how to use them"),
]

# Shown additionally to chat administrators.
ADMIN_COMMANDS: List[Tuple[str, str]] = [
    ("config", "Chat settings for this bot"),
    ("recap", "Daily chat recap: /recap on|off|time HH:MM"),
    ("speech", "Speech-to-text on/off"),
    ("random", "Random replies on/off"),
    ("reaction", "Emoji reactions on/off"),
    ("mute", "Mute a user: reply with /mute <minutes>"),
    ("unmute", "Unmute a user"),
]


def _to_bot_commands(items: List[Tuple[str, str]]) -> List[BotCommand]:
    return [BotCommand(name, description) for name, description in items]


async def publish_command_menu(bot: Bot) -> None:
    """Publish the command menu. Failures are logged, never raised."""
    try:
        await bot.set_my_commands(
            _to_bot_commands(PUBLIC_COMMANDS), scope=BotCommandScopeDefault()
        )
        await bot.set_my_commands(
            _to_bot_commands(PUBLIC_COMMANDS + ADMIN_COMMANDS),
            scope=BotCommandScopeAllChatAdministrators(),
        )
        logger.info(
            f"Published command menu: {len(PUBLIC_COMMANDS)} public, "
            f"{len(ADMIN_COMMANDS)} admin-only"
        )
    except Exception as e:
        logger.warning(f"Failed to publish command menu: {e}")
