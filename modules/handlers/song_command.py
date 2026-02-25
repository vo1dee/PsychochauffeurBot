"""
Song command handler.

Downloads YouTube videos as MP3 audio files when used as a reply.
"""

import logging
import os
import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from modules.utils import extract_urls

logger = logging.getLogger(__name__)


def convert_to_youtube_music_url(url: str) -> Optional[str]:
    """
    Convert a YouTube URL to a YouTube Music URL.

    Converts:
    - https://www.youtube.com/watch?v=xxx -> https://music.youtube.com/watch?v=xxx
    - https://youtube.com/watch?v=xxx -> https://music.youtube.com/watch?v=xxx
    - https://youtu.be/xxx -> https://music.youtube.com/watch?v=xxx

    Args:
        url: YouTube URL to convert

    Returns:
        YouTube Music URL or None if not a valid YouTube URL
    """
    # Pattern for standard YouTube URLs
    youtube_pattern = r"https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"
    match = re.search(youtube_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://music.youtube.com/watch?v={video_id}"

    # Pattern for short YouTube URLs (youtu.be)
    short_pattern = r"https?://youtu\.be/([a-zA-Z0-9_-]+)"
    match = re.search(short_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://music.youtube.com/watch?v={video_id}"

    # Pattern for YouTube shorts
    shorts_pattern = r"https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)"
    match = re.search(shorts_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://music.youtube.com/watch?v={video_id}"

    # If already a YouTube Music URL, return as-is
    music_pattern = r"https?://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"
    if re.search(music_pattern, url):
        return url

    return None


def find_youtube_url(text: str) -> Optional[str]:
    """
    Find and extract a YouTube URL from text.

    Args:
        text: Text to search for YouTube URLs

    Returns:
        First YouTube URL found or None
    """
    urls = extract_urls(text)
    for url in urls:
        if any(
            domain in url.lower()
            for domain in ["youtube.com", "youtu.be", "music.youtube.com"]
        ):
            return url
    return None


async def song_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /song command.

    When used as a reply to a message containing a YouTube link,
    downloads the audio as MP3 and sends it.
    """
    if not update.message:
        return

    # Check if command is a reply to another message
    reply_message = update.message.reply_to_message
    if not reply_message:
        await update.message.reply_text(
            "Please use /song as a reply to a message containing a YouTube link."
        )
        return

    # Get text from the replied message
    reply_text = reply_message.text or reply_message.caption or ""

    # Find YouTube URL in the replied message
    youtube_url = find_youtube_url(reply_text)
    if not youtube_url:
        await update.message.reply_text("No YouTube link found in the replied message.")
        return

    # Convert to YouTube Music URL
    music_url = convert_to_youtube_music_url(youtube_url)
    if not music_url:
        await update.message.reply_text(
            "Could not convert the link to a YouTube Music URL."
        )
        return

    # Get video downloader from bot_data
    video_downloader = context.bot_data.get("video_downloader")
    if not video_downloader:
        logger.error("Video downloader not available in bot_data")
        await update.message.reply_text("Audio download service is not available.")
        return

    # Send initial processing message
    processing_msg = await update.message.reply_text("Downloading audio...")

    filename = None
    try:
        # Download the audio
        filename, title = await video_downloader.download_youtube_music(music_url)

        if not filename or not os.path.exists(filename):
            await processing_msg.edit_text("Failed to download audio.")
            return

        # Check file size (50MB Telegram limit)
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await processing_msg.edit_text("Audio file is too large to send (>50MB).")
            try:
                os.remove(filename)
            except Exception:
                pass
            return

        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Prepare caption with Markdown V2 escaping
        special_chars = [
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
        escaped_title = title or "Audio"
        for char in special_chars:
            escaped_title = escaped_title.replace(char, f"\\{char}")

        username = "Unknown"
        if update.effective_user:
            username = (
                update.effective_user.username
                or update.effective_user.first_name
                or "Unknown"
            )
        escaped_username = username
        for char in special_chars:
            escaped_username = escaped_username.replace(char, f"\\{char}")

        escaped_url = music_url
        for char in special_chars:
            escaped_url = escaped_url.replace(char, f"\\{char}")

        caption = f"🎵 {escaped_title}\n\n👤 Від: @{escaped_username}\n\n🔗 [Посилання]({escaped_url})"

        # Send audio as reply to the original message containing the YouTube link
        with open(filename, "rb") as audio_file:
            await reply_message.reply_audio(
                audio=audio_file, caption=caption, parse_mode="MarkdownV2"
            )

        # Delete the /song command message
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete command message: {e}")

        logger.info(f"Successfully sent audio: {title}")

    except Exception as e:
        logger.error(f"Error in song command: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(f"Error downloading audio: {str(e)[:100]}")
        except Exception:
            pass

    finally:
        # Cleanup downloaded file
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                logger.warning(f"Could not remove temporary file {filename}: {e}")


def find_youtube_shorts_url(text: str) -> Optional[str]:
    """
    Find and extract a YouTube Shorts URL from text.

    Args:
        text: Text to search for YouTube Shorts URLs

    Returns:
        YouTube Shorts URL found or None
    """
    urls = extract_urls(text)
    for url in urls:
        if "youtube.com/shorts" in url.lower() or "youtu.be/shorts" in url.lower():
            return url
    return None


def convert_shorts_to_regular(url: str) -> Optional[str]:
    """
    Convert a YouTube Shorts URL to a regular YouTube watch URL.

    Args:
        url: YouTube Shorts URL

    Returns:
        Regular YouTube watch URL or None if not valid
    """
    shorts_pattern = r"https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)"
    match = re.search(shorts_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"

    short_be_pattern = r"https?://youtu\.be/shorts/([a-zA-Z0-9_-]+)"
    match = re.search(short_be_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"

    return None


async def short_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /short command.

    When used as a reply to a message containing a YouTube Shorts link,
    downloads the video and sends it.
    """
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

        special_chars = [
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
        escaped_title = title or "Shorts"
        for char in special_chars:
            escaped_title = escaped_title.replace(char, f"\\{char}")

        username = "Unknown"
        if update.effective_user:
            username = (
                update.effective_user.username
                or update.effective_user.first_name
                or "Unknown"
            )
        escaped_username = username
        for char in special_chars:
            escaped_username = escaped_username.replace(char, f"\\{char}")

        escaped_url = watch_url
        for char in special_chars:
            escaped_url = escaped_url.replace(char, f"\\{char}")

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
