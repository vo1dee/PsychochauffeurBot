"""
Handler for MessageReactionUpdated updates.

Tracks when users add emoji reactions to messages.
Requires python-telegram-bot >= 21.0.
"""

import asyncio
import os

from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes

from modules.logger import general_logger, error_logger


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

    # ⚡ reaction triggers YouTube Shorts download
    new_emojis = [r.emoji for r in reaction.new_reaction if isinstance(r, ReactionTypeEmoji)]
    old_emojis = [r.emoji for r in (reaction.old_reaction or []) if isinstance(r, ReactionTypeEmoji)]
    if "⚡" in new_emojis and "⚡" not in old_emojis:
        shorts_cache = context.bot_data.get("shorts_url_cache", {})
        shorts_url = shorts_cache.get((chat_id, reaction.message_id))
        if shorts_url:
            await _handle_shorts_download(context, chat_id, reaction.message_id, shorts_url, reaction.user)


async def _handle_shorts_download(context, chat_id, message_id, shorts_url, user):
    """Download and send a YouTube Short triggered by ⚡ reaction."""
    from modules.handlers.song_command import convert_shorts_to_regular

    watch_url = convert_shorts_to_regular(shorts_url)
    if not watch_url:
        return

    video_downloader = context.bot_data.get("video_downloader")
    if not video_downloader:
        error_logger.error("Video downloader not available for ⚡ reaction")
        return

    processing_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="⚡ Downloading Shorts...",
        reply_to_message_id=message_id,
    )

    filename = None
    try:
        filename, title = await video_downloader.download_video(watch_url)

        if not filename or not os.path.exists(filename):
            await processing_msg.edit_text("Failed to download Shorts.")
            return

        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await processing_msg.edit_text("Video file is too large to send (>50MB).")
            return

        try:
            await processing_msg.delete()
        except Exception as del_err:
            error_logger.warning(f"Failed to delete processing message: {del_err}")

        special_chars = [
            "_", "*", "[", "]", "(", ")", "~", "`", ">",
            "#", "+", "-", "=", "|", "{", "}", ".", "!",
        ]
        escaped_title = title or "Shorts"
        for char in special_chars:
            escaped_title = escaped_title.replace(char, f"\\{char}")

        username = "Unknown"
        if user:
            username = user.username or user.first_name or "Unknown"
        escaped_username = username
        for char in special_chars:
            escaped_username = escaped_username.replace(char, f"\\{char}")

        escaped_url = watch_url
        for char in special_chars:
            escaped_url = escaped_url.replace(char, f"\\{char}")

        caption = f"🎬 {escaped_title}\n\n👤 Від: @{escaped_username}\n\n🔗 [Посилання]({escaped_url})"

        with open(filename, "rb") as video_file:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption=caption,
                parse_mode="MarkdownV2",
                reply_to_message_id=message_id,
            )

        general_logger.info(f"Successfully sent Shorts via ⚡ reaction: {title}")

    except Exception as e:
        error_logger.error(f"Error in ⚡ shorts download: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(f"Error downloading Shorts: {str(e)[:100]}")
        except Exception as edit_err:
            error_logger.warning(f"Failed to edit processing message after error: {edit_err}")

    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass  # cleanup
