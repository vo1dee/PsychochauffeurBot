"""NASA Astronomy Picture of the Day command.

First successful call per chat per day returns today's APOD; subsequent calls
return a random APOD. If today's fetch fails, a random picture is sent as a
consolation (shown flag stays unset so the next call retries today's).

NASA API calls are retried on transient failures. All failures are silent in
chat and reported to the error channel via error_logger.
"""

import asyncio
import logging
from datetime import date
from io import BytesIO
from typing import Any

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from modules.const import Config
from modules.logger import error_logger

logger = logging.getLogger(__name__)

NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.5


async def _fetch_apod(session: aiohttp.ClientSession, params: dict) -> Any:
    """Fetch APOD JSON with retries. Returns parsed JSON or raises on final failure."""
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with session.get(NASA_APOD_URL, params=params) as response:
                if response.status == 200:
                    return await response.json()
                last_error = f"HTTP {response.status}"
                logger.warning(
                    "NASA APOD attempt %d/%d returned %s",
                    attempt,
                    MAX_ATTEMPTS,
                    response.status,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(
                "NASA APOD attempt %d/%d failed: %s",
                attempt,
                MAX_ATTEMPTS,
                last_error,
            )
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"NASA APOD failed after {MAX_ATTEMPTS} attempts: {last_error}")


async def nasa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /nasa command - NASA Astronomy Picture of the Day."""
    if not update.message:
        return

    api_key = Config.NASA_API_KEY or "DEMO_KEY"
    chat_data = context.chat_data or {}

    today = date.today().isoformat()
    shown_today = chat_data.get("nasa_apod_shown_date") == today

    params = {"api_key": api_key, "thumbs": "true"}
    if shown_today:
        params["count"] = "1"
    # else: no extra params = today's picture (per NASA Eastern time)

    timeout = aiohttp.ClientTimeout(total=15)
    fetched_todays = False

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                data = await _fetch_apod(session, params)
                fetched_todays = not shown_today
            except RuntimeError as e:
                if shown_today:
                    # Random fetch failed after retries. Silent to chat, notify channel.
                    error_logger.error("NASA APOD random fetch failed: %s", e)
                    return
                # Today's fetch failed — fall back to random as a consolation.
                # Leave shown_today unset so the next call retries today's.
                error_logger.error(
                    "NASA APOD today's fetch failed, sending random fallback: %s", e
                )
                params["count"] = "1"
                try:
                    data = await _fetch_apod(session, params)
                except RuntimeError as e2:
                    error_logger.error(
                        "NASA APOD random fallback also failed: %s", e2
                    )
                    return

            apod = data[0] if isinstance(data, list) else data

            title = apod.get("title", "Unknown")
            explanation = apod.get("explanation", "")
            media_type = apod.get("media_type", "image")
            apod_date = apod.get("date", "")
            url = apod.get("url", "")
            thumbnail = apod.get("thumbnail_url")

            max_explanation = 850
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
                async with session.get(url) as img_response:
                    if img_response.status != 200:
                        error_logger.error(
                            "NASA APOD image download failed: HTTP %s for %s",
                            img_response.status,
                            url,
                        )
                        return
                    image_bytes = await img_response.read()
                await update.message.reply_photo(
                    photo=BytesIO(image_bytes),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
            elif media_type == "video":
                video_caption = (
                    f"<b>{title}</b>\n"
                    f"<i>{apod_date}</i>\n\n"
                    f"{explanation}\n\n"
                    f"<a href=\"{url}\">Watch Video</a> | "
                    f"<a href=\"{source_link}\">APOD Source</a>"
                )
                sent_thumb = False
                if thumbnail:
                    async with session.get(thumbnail) as thumb_response:
                        if thumb_response.status == 200:
                            thumb_bytes = await thumb_response.read()
                            await update.message.reply_photo(
                                photo=BytesIO(thumb_bytes),
                                caption=video_caption,
                                parse_mode=ParseMode.HTML,
                            )
                            sent_thumb = True
                if not sent_thumb:
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

            if fetched_todays and context.chat_data is not None:
                context.chat_data["nasa_apod_shown_date"] = today

    except Exception as e:
        error_logger.error(
            "Unexpected error in NASA APOD command: %s", e, exc_info=True
        )
