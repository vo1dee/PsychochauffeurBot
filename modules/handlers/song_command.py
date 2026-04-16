"""
Song command handler.

Supports three modes:
  1. /song artist - song           → search YouTube, download, send
  2. /song (reply to platform URL) → resolve metadata, search YouTube, download, send
  3. /song (reply to YouTube URL)  → download directly (legacy behaviour)
"""

import logging
import os
import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from modules.utils import extract_urls
from modules.const import MusicPlatforms

logger = logging.getLogger(__name__)

_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']


def _escape_md(text: str) -> str:
    for ch in _SPECIAL_CHARS:
        text = text.replace(ch, f'\\{ch}')
    return text


def is_music_platform_url(url: str) -> bool:
    return any(domain in url.lower() for domain in MusicPlatforms.PLATFORM_DOMAINS)


def convert_to_youtube_music_url(url: str) -> Optional[str]:
    """Convert a YouTube URL to a YouTube Music URL."""
    youtube_pattern = r"https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"
    match = re.search(youtube_pattern, url)
    if match:
        return f"https://music.youtube.com/watch?v={match.group(1)}"

    short_pattern = r"https?://youtu\.be/([a-zA-Z0-9_-]+)"
    match = re.search(short_pattern, url)
    if match:
        return f"https://music.youtube.com/watch?v={match.group(1)}"

    shorts_pattern = r"https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)"
    match = re.search(shorts_pattern, url)
    if match:
        return f"https://music.youtube.com/watch?v={match.group(1)}"

    music_pattern = r"https?://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"
    if re.search(music_pattern, url):
        return url

    return None


def find_youtube_url(text: str) -> Optional[str]:
    urls = extract_urls(text)
    for url in urls:
        if any(domain in url.lower() for domain in ["youtube.com", "youtu.be", "music.youtube.com"]):
            return url
    return None


async def _send_audio_reply(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            filename: str, title: Optional[str], source_url: Optional[str]) -> None:
    """Send audio as a reply, then delete the command message."""
    file_size = os.path.getsize(filename)
    if file_size > 50 * 1024 * 1024:
        if update.message:
            await update.message.reply_text("❌ Audio file is too large to send (>50MB).")
        return

    escaped_title = _escape_md(title or "Audio")
    username = "Unknown"
    if update.effective_user:
        username = update.effective_user.username or update.effective_user.first_name or "Unknown"
    escaped_username = _escape_md(username)

    caption = f"🎵 {escaped_title}\n\n👤 Від: @{escaped_username}"
    if source_url:
        escaped_url = _escape_md(source_url)
        caption += f"\n\n🔗 [Посилання]({escaped_url})"

    reply_target = (
        update.message.reply_to_message
        if update.message and update.message.reply_to_message
        else update.message
    )

    with open(filename, "rb") as audio_file:
        if reply_target:
            await reply_target.reply_audio(audio=audio_file, caption=caption, parse_mode="MarkdownV2")
        elif update.effective_chat:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=audio_file,
                caption=caption,
                parse_mode="MarkdownV2",
            )

    try:
        if update.message:
            await update.message.delete()
    except Exception as e:
        logger.debug(f"Could not delete command message: {e}")


async def song_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /song command (3 modes)."""
    if not update.message:
        return

    video_downloader = context.bot_data.get("video_downloader")
    if not video_downloader:
        logger.error("Video downloader not available in bot_data")
        await update.message.reply_text("❌ Audio download service is not available.")
        return

    # ── Mode A: /song artist - song ──────────────────────────────────────────
    if context.args:
        query = " ".join(context.args)
        processing_msg = await update.message.reply_text(f"🔎 Searching for: {query}…")
        filename = None
        try:
            filename, title = await video_downloader.search_and_download_track(query)
            if not filename or not os.path.exists(filename):
                await processing_msg.edit_text("❌ Track not found.")
                return
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await _send_audio_reply(update, context, filename, title, source_url=None)
        except Exception as e:
            logger.error(f"song_command search error: {e}", exc_info=True)
            try:
                await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")
            except Exception:
                pass
        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
        return

    # ── Modes B & C: reply to a message ──────────────────────────────────────
    reply_message = update.message.reply_to_message
    if not reply_message:
        await update.message.reply_text(
            "Usage:\n"
            "• `/song Artist \\- Song Name` — search for a track\n"
            "• Reply to a Spotify/Deezer/Apple Music/SoundCloud link with `/song`\n"
            "• Reply to a YouTube link with `/song`",
            parse_mode="MarkdownV2",
        )
        return

    reply_text = reply_message.text or reply_message.caption or ""
    urls = extract_urls(reply_text)

    # Mode B: streaming platform URL
    platform_url = next((u for u in urls if is_music_platform_url(u)), None)
    if platform_url:
        processing_msg = await update.message.reply_text("⏳ Resolving track…")
        filename = None
        try:
            filename, title = await video_downloader.download_music_platform_url(platform_url)
            if not filename or not os.path.exists(filename):
                await processing_msg.edit_text("❌ Failed to download track.")
                return
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await _send_audio_reply(update, context, filename, title, source_url=platform_url)
        except Exception as e:
            logger.error(f"song_command platform error: {e}", exc_info=True)
            try:
                await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")
            except Exception:
                pass
        finally:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
        return

    # Mode C: YouTube URL (existing behaviour)
    youtube_url = find_youtube_url(reply_text)
    if not youtube_url:
        await update.message.reply_text("❌ No supported link found in the replied message.")
        return

    music_url = convert_to_youtube_music_url(youtube_url)
    if not music_url:
        await update.message.reply_text("❌ Could not convert the link to a YouTube Music URL.")
        return

    processing_msg = await update.message.reply_text("⏳ Downloading audio…")
    filename = None
    try:
        filename, title = await video_downloader.download_youtube_music(music_url)
        if not filename or not os.path.exists(filename):
            await processing_msg.edit_text("❌ Failed to download audio.")
            return
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await _send_audio_reply(update, context, filename, title, source_url=music_url)
    except Exception as e:
        logger.error(f"song_command youtube error: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")
        except Exception:
            pass
    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


def find_youtube_shorts_url(text: str) -> Optional[str]:
    urls = extract_urls(text)
    for url in urls:
        if "youtube.com/shorts" in url.lower() or "youtu.be/shorts" in url.lower():
            return url
    return None


def convert_shorts_to_regular(url: str) -> Optional[str]:
    shorts_pattern = r"https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)"
    match = re.search(shorts_pattern, url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"

    short_be_pattern = r"https?://youtu\.be/shorts/([a-zA-Z0-9_-]+)"
    match = re.search(short_be_pattern, url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"

    return None


async def short_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /short command — download YouTube Shorts as video."""
    if not update.message:
        return

    reply_message = update.message.reply_to_message
    if not reply_message:
        await update.message.reply_text(
            "Please use /short as a reply to a message containing a YouTube Shorts link."
        )
        return

    reply_text = reply_message.text or reply_message.caption or ""

    shorts_url = find_youtube_shorts_url(reply_text)
    if not shorts_url:
        await update.message.reply_text(
            "No YouTube Shorts link found in the replied message."
        )
        return

    watch_url = convert_shorts_to_regular(shorts_url)
    if not watch_url:
        await update.message.reply_text(
            "Could not convert the Shorts link to a watchable format."
        )
        return

    video_downloader = context.bot_data.get("video_downloader")
    if not video_downloader:
        logger.error("Video downloader not available in bot_data")
        await update.message.reply_text("Video download service is not available.")
        return

    processing_msg = await update.message.reply_text("Downloading Shorts...")

    filename = None
    try:
        filename, title = await video_downloader.download_video(watch_url)

        if not filename or not os.path.exists(filename):
            await processing_msg.edit_text("Failed to download Shorts.")
            return

        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await processing_msg.edit_text("Video file is too large to send (>50MB).")
            try:
                os.remove(filename)
            except Exception:
                pass
            return

        try:
            await processing_msg.delete()
        except Exception:
            pass

        escaped_title = _escape_md(title or "Shorts")
        username = "Unknown"
        if update.effective_user:
            username = (
                update.effective_user.username
                or update.effective_user.first_name
                or "Unknown"
            )
        escaped_username = _escape_md(username)
        escaped_url = _escape_md(watch_url)

        caption = f"🎬 {escaped_title}\n\n👤 Від: @{escaped_username}\n\n🔗 [Посилання]({escaped_url})"

        with open(filename, "rb") as video_file:
            await reply_message.reply_video(
                video=video_file, caption=caption, parse_mode="MarkdownV2"
            )

        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete command message: {e}")

        logger.info(f"Successfully sent Shorts: {title}")

    except Exception as e:
        logger.error(f"Error in short command: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(f"Error downloading Shorts: {str(e)[:100]}")
        except Exception:
            pass

    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                logger.warning(f"Could not remove temporary file {filename}: {e}")
