"""
Handler for MessageReactionUpdated updates.

Tracks when users add emoji reactions to messages.
Requires python-telegram-bot >= 21.0.
"""

import asyncio
import os

from telegram import Update, ReactionTypeEmoji
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from modules.chat_action import chat_action_for as _chat_action_for
from modules.logger import general_logger, error_logger


async def handle_reaction_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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

    asyncio.ensure_future(record_bot_event("reaction", chat_id, user_id))

    # ⚡ reaction triggers YouTube Shorts download
    new_emojis = [
        r.emoji for r in reaction.new_reaction if isinstance(r, ReactionTypeEmoji)
    ]
    old_emojis = [
        r.emoji
        for r in (reaction.old_reaction or [])
        if isinstance(r, ReactionTypeEmoji)
    ]
    if "⚡" in new_emojis and "⚡" not in old_emojis:
        shorts_cache = context.bot_data.get("shorts_url_cache", {})
        shorts_url = shorts_cache.get((chat_id, reaction.message_id))
        if shorts_url:
            await _handle_shorts_download(
                context, chat_id, reaction.message_id, shorts_url, reaction.user
            )


async def _handle_shorts_download(context, chat_id, message_id, shorts_url, user):
    """Download and send a YouTube Short triggered by ⚡ reaction."""
    in_progress = context.bot_data.setdefault("shorts_in_progress", set())
    key = (chat_id, message_id)
    if key in in_progress:
        general_logger.debug(
            f"Shorts download already in progress for message {message_id}, skipping duplicate"
        )
        return
    in_progress.add(key)

    from modules.handlers.song_command import (
        build_shorts_caption,
        convert_shorts_to_regular,
    )

    watch_url = convert_shorts_to_regular(shorts_url)
    if not watch_url:
        in_progress.discard(key)
        return

    video_downloader = context.bot_data.get("video_downloader")
    if not video_downloader:
        error_logger.error("Video downloader not available for ⚡ reaction")
        in_progress.discard(key)
        return

    processing_msg = None
    filename = None
    try:
        cached = video_downloader.video_cache.get(watch_url)
        if cached and cached.get("media_kind") == "video":
            username = (
                user.username or user.first_name or "Unknown" if user else "Unknown"
            )
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=cached["file_id"],
                    caption=build_shorts_caption(
                        cached.get("title"), username, watch_url
                    ),
                    parse_mode="MarkdownV2",
                    reply_to_message_id=message_id,
                )
                return
            except BadRequest:
                video_downloader.video_cache.evict(watch_url)
        processing_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⚡ Downloading Shorts...",
            reply_to_message_id=message_id,
        )
        async with _chat_action_for(context.bot, chat_id, ChatAction.UPLOAD_VIDEO):
            filename, title = await asyncio.wait_for(
                video_downloader.download_video(watch_url), timeout=60
            )

            if not filename or not os.path.exists(filename):
                await processing_msg.edit_text("Failed to download Shorts.")
                return

            file_size = os.path.getsize(filename)
            if file_size > 50 * 1024 * 1024:
                await processing_msg.edit_text(
                    "Video file is too large to send (>50MB)."
                )
                return

            try:
                await processing_msg.delete()
            except Exception as del_err:
                general_logger.warning(
                    f"Failed to delete processing message: {del_err}"
                )

            username = "Unknown"
            if user:
                username = user.username or user.first_name or "Unknown"
            caption = build_shorts_caption(title, username, watch_url)

            with open(filename, "rb") as video_file:
                sent = await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=caption,
                    parse_mode="MarkdownV2",
                    reply_to_message_id=message_id,
                )
            if sent.video:
                video_downloader.video_cache.set(
                    watch_url, sent.video.file_id, title, "video"
                )

            general_logger.info(f"Successfully sent Shorts via ⚡ reaction: {title}")

    except Exception as e:
        error_logger.error(f"Error in ⚡ shorts download: {e}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.edit_text(
                    f"Error downloading Shorts: {str(e)[:100]}"
                )
            except Exception as edit_err:
                general_logger.warning(
                    f"Failed to edit processing message after error: {edit_err}"
                )

    finally:
        in_progress.discard(key)
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass  # cleanup
