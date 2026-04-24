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
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from modules.utils import extract_urls
from modules.const import MusicPlatforms

logger = logging.getLogger(__name__)

_SPECIAL_CHARS = [
    "_",
    "*",
    "[",
    "]",
    "(",
    ")",
    "~",
    "`",
    ">",
    "#",
    "+",
    "-",
    "=",
    "|",
    "{",
    "}",
    ".",
    "!",
]


def _escape_md(text: str) -> str:
    for ch in _SPECIAL_CHARS:
        text = text.replace(ch, f"\\{ch}")
    return text


def is_music_platform_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    if not hostname:
        return False
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in MusicPlatforms.PLATFORM_DOMAINS
    )


def platform_label_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "spotify" in host:
        return "Spotify"
    if "deezer" in host:
        return "Deezer"
    if "apple" in host:
        return "Apple Music"
    if "soundcloud" in host:
        return "SoundCloud"
    return "Original"


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
        if any(
            domain in url.lower()
            for domain in ["youtube.com", "youtu.be", "music.youtube.com"]
        ):
            return url
    return None


def normalize_telegram_audio_metadata(
    title: Optional[str], performer: Optional[str]
) -> tuple[str, Optional[str]]:
    """Ensure Telegram audio card doesn't duplicate performer in title."""
    normalized_title = (title or "Audio").strip() or "Audio"
    normalized_performer = (
        performer.strip() if isinstance(performer, str) else performer
    )
    if normalized_performer:
        pattern = rf"^\s*{re.escape(normalized_performer)}\s*[-–—:]\s*(.+)$"
        match = re.match(pattern, normalized_title, flags=re.IGNORECASE)
        if match:
            normalized_title = match.group(1).strip() or normalized_title
    return normalized_title, normalized_performer


async def _send_audio_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filename: str,
    title: Optional[str],
    performer: Optional[str] = None,
    youtube_url: Optional[str] = None,
    platform_url: Optional[str] = None,
    video_id: Optional[str] = None,
) -> None:
    """Send audio as a reply, then delete the command message."""
    file_size = os.path.getsize(filename)
    if file_size > 50 * 1024 * 1024:
        if update.message:
            await update.message.reply_text(
                "❌ Audio file is too large to send (>50MB)."
            )
        return

    tg_title, tg_performer = normalize_telegram_audio_metadata(title, performer)
    display_title = (
        f"{tg_performer} - {tg_title}" if tg_performer else tg_title
    )  # for caption text
    escaped_title = _escape_md(display_title or "Audio")
    username = "Unknown"
    if update.effective_user:
        username = (
            update.effective_user.username
            or update.effective_user.first_name
            or "Unknown"
        )
    escaped_username = _escape_md(username)

    caption = f"🎵 {escaped_title}\n\n👤 Від: @{escaped_username}"
    if platform_url:
        source_label = platform_label_from_url(platform_url)
        caption += f"\n\n🔗 [{_escape_md(source_label)}]({_escape_md(platform_url)})"
    if youtube_url:
        caption += f"\n\n🔗 [YouTube]({_escape_md(youtube_url)})"

    reply_markup = None
    buttons = []
    if youtube_url:
        buttons.append(InlineKeyboardButton("🔗 YouTube", url=youtube_url))
    if platform_url and platform_url != youtube_url:
        source_label = platform_label_from_url(platform_url)
        buttons.append(InlineKeyboardButton(f"🎵 {source_label}", url=platform_url))
    if buttons:
        reply_markup = InlineKeyboardMarkup([buttons])

    reply_target = (
        update.message.reply_to_message
        if update.message and update.message.reply_to_message
        else update.message
    )

    sent_msg = None
    with open(filename, "rb") as audio_file:
        send_kwargs = dict(
            audio=audio_file,
            title=tg_title,
            performer=tg_performer,
            caption=caption,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup,
        )
        if reply_target:
            sent_msg = await reply_target.reply_audio(**send_kwargs)
        elif update.effective_chat:
            sent_msg = await context.bot.send_audio(
                chat_id=update.effective_chat.id, **send_kwargs
            )

    # Populate song cache if we have a file_id and video_id
    if sent_msg and sent_msg.audio and video_id:
        video_downloader = context.bot_data.get("video_downloader")
        if video_downloader and hasattr(video_downloader, "song_cache"):
            video_downloader.song_cache.set(
                video_id=video_id,
                file_id=sent_msg.audio.file_id,
                title=display_title or "Audio",
                performer=tg_performer,
                webpage_url=youtube_url or "",
            )

    if update.effective_chat:
        from modules.event_tracker import record_bot_event

        user_id = update.effective_user.id if update.effective_user else None
        await record_bot_event("song_sent", update.effective_chat.id, user_id)

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
            filename, title, performer, youtube_url, video_id = (
                await video_downloader.search_and_download_track(query)
            )
            if not filename or not os.path.exists(filename):
                await processing_msg.edit_text("❌ Track not found.")
                return
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await _send_audio_reply(
                update,
                context,
                filename,
                title,
                performer=performer,
                youtube_url=youtube_url,
                video_id=video_id,
            )
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
    if not platform_url:
        for candidate_url in urls:
            try:
                normalized_url = await video_downloader.normalize_music_platform_url(
                    candidate_url
                )
            except Exception as e:
                logger.debug(f"Could not normalize music URL '{candidate_url}': {e}")
                continue

            if is_music_platform_url(normalized_url):
                platform_url = normalized_url
                break

    if platform_url:
        processing_msg = await update.message.reply_text("⏳ Resolving track…")
        filename = None
        try:
            filename, title, performer, youtube_url, video_id = (
                await video_downloader.download_music_platform_url(platform_url)
            )
            if not filename or not os.path.exists(filename):
                await processing_msg.edit_text("❌ Failed to download track.")
                return
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await _send_audio_reply(
                update,
                context,
                filename,
                title,
                performer=performer,
                youtube_url=youtube_url,
                platform_url=platform_url,
                video_id=video_id,
            )
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
        await update.message.reply_text(
            "❌ No supported link found in the replied message."
        )
        return

    music_url = convert_to_youtube_music_url(youtube_url)
    if not music_url:
        await update.message.reply_text(
            "❌ Could not convert the link to a YouTube Music URL."
        )
        return

    processing_msg = await update.message.reply_text("⏳ Downloading audio…")
    filename = None
    try:
        filename, title, performer, youtube_url, video_id = (
            await video_downloader.download_youtube_music(music_url)
        )
        if not filename or not os.path.exists(filename):
            await processing_msg.edit_text("❌ Failed to download audio.")
            return
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await _send_audio_reply(
            update,
            context,
            filename,
            title,
            performer=performer,
            youtube_url=youtube_url or music_url,
            video_id=video_id,
        )
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
