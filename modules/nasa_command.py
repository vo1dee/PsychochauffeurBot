"""
NASA Astronomy Picture of the Day command.

First call per chat returns today's APOD, subsequent calls return random APODs.
"""

import logging
from datetime import date

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from modules.const import Config

logger = logging.getLogger(__name__)

NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"


async def nasa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /nasa command - NASA Astronomy Picture of the Day."""
    if not update.message:
        return

    api_key = Config.NASA_API_KEY or "DEMO_KEY"
    chat_data = context.chat_data or {}

    # Check if we've already attempted today's APOD in this chat.
    today = date.today().isoformat()
    shown_today = chat_data.get("nasa_apod_shown_date") == today

    try:
        params = {"api_key": api_key, "thumbs": "true"}
        if shown_today:
            params["count"] = "1"
        # else: no extra params = today's picture

        async with aiohttp.ClientSession() as session:
            async with session.get(NASA_APOD_URL, params=params) as response:
                if response.status != 200 and not shown_today:
                    # Today's APOD may not be available yet (timezone mismatch);
                    # fall back to a random picture
                    logger.info(
                        "NASA APOD returned %s for today, falling back to random",
                        response.status,
                    )
                    params["count"] = "1"
                    async with session.get(NASA_APOD_URL, params=params) as fallback:
                        if fallback.status != 200:
                            await update.message.reply_text(
                                f"NASA API error: {fallback.status}"
                            )
                            return
                        data = await fallback.json()
                elif response.status != 200:
                    await update.message.reply_text(
                        f"NASA API error: {response.status}"
                    )
                    return
                else:
                    data = await response.json()

        # count=1 returns a list, default returns a single object
        if isinstance(data, list):
            apod = data[0]
        else:
            apod = data

        title = apod.get("title", "Unknown")
        explanation = apod.get("explanation", "")
        media_type = apod.get("media_type", "image")
        apod_date = apod.get("date", "")
        hd_url = apod.get("hdurl")
        url = apod.get("url", "")
        thumbnail = apod.get("thumbnail_url")

        # Truncate explanation for caption (Telegram limit ~1024 for photos)
        max_explanation = 600
        if len(explanation) > max_explanation:
            explanation = explanation[:max_explanation].rsplit(" ", 1)[0] + "..."

        source_link = f"https://apod.nasa.gov/apod/ap{apod_date.replace('-', '')[2:]}.html"

        caption = (
            f"<b>{title}</b>\n"
            f"<i>{apod_date}</i>\n\n"
            f"{explanation}\n\n"
            f"<a href=\"{source_link}\">APOD Source</a>"
        )

        if media_type == "image":
            # Send HD version if available, fallback to regular
            image_url = hd_url or url
            try:
                await update.message.reply_photo(
                    photo=image_url,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                # HD image might be too large for Telegram, try regular
                if hd_url and url != hd_url:
                    await update.message.reply_photo(
                        photo=url,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    raise
        elif media_type == "video":
            # For videos, send thumbnail with link
            video_caption = (
                f"<b>{title}</b>\n"
                f"<i>{apod_date}</i>\n\n"
                f"{explanation}\n\n"
                f"<a href=\"{url}\">Watch Video</a> | "
                f"<a href=\"{source_link}\">APOD Source</a>"
            )
            if thumbnail:
                await update.message.reply_photo(
                    photo=thumbnail,
                    caption=video_caption,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text(
                    video_caption,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                )
        else:
            await update.message.reply_text(
                caption,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )

        # Mark as shown only after successfully sending to chat
        if not shown_today and context.chat_data is not None:
            context.chat_data["nasa_apod_shown_date"] = today

    except Exception as e:
        logger.error(f"Error fetching NASA APOD: {e}", exc_info=True)
        await update.message.reply_text(
            "An error occurred while fetching NASA's Astronomy Picture of the Day."
        )
