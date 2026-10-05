"""NASA Astronomy Picture of the Day command.

First successful call per chat per day returns today's APOD; subsequent calls
return a random APOD. If today's fetch fails, a random picture is sent as a
consolation (shown flag stays unset so the next call retries today's).

NASA API calls are retried on transient failures. All failures are silent in
chat and reported to the error channel via error_logger.
"""

import asyncio
import html
import logging
import random
import re
from datetime import date, timedelta
from io import BytesIO
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from modules.logger import error_logger

logger = logging.getLogger(__name__)

# api.nasa.gov/planetary/apod was retired when APOD moved to science.nasa.gov
# (2026-09-29); it now answers every request with a "NASA Science" logo
# placeholder. This endpoint needs no API key. Collection requests return a
# list (newest first); /YYMMDD returns a single entry.
APOD_API_URL = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"
APOD_FIRST_DATE = date(1995, 6, 16)
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.5
# Asset host resizes on request; keeps uploads well under Telegram's photo limit.
IMAGE_MAX_EDGE_PX = 1280

_IMG_SRC_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _random_apod_url() -> str:
    """URL for a random APOD date between the first APOD and yesterday."""
    span = (date.today() - APOD_FIRST_DATE).days - 1
    picked = APOD_FIRST_DATE + timedelta(days=random.randint(0, max(span, 0)))
    return f"{APOD_API_URL}/{picked.strftime('%y%m%d')}"


async def _fetch_apod(session: aiohttp.ClientSession, random_pick: bool) -> Any:
    """Fetch APOD JSON with retries. Returns parsed JSON or raises on final failure.

    Random picks choose a new date on each attempt, since some early dates
    have no entry.
    """
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if random_pick:
            url, params = _random_apod_url(), None
        else:
            url, params = APOD_API_URL, {"per_page": "1"}
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        data = data[0] if data else None
                    if isinstance(data, dict) and data.get("title"):
                        return data
                    last_error = "empty response"
                else:
                    last_error = f"HTTP {response.status}"
                logger.warning(
                    "NASA APOD attempt %d/%d failed for %s: %s",
                    attempt,
                    MAX_ATTEMPTS,
                    url,
                    last_error,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
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


def _html_to_text(fragment: str) -> str:
    """Strip HTML tags and entities from an APOD field."""
    text = html.unescape(_TAG_RE.sub("", fragment or ""))
    return re.sub(r"\s+", " ", text).strip()


def _image_url(apod: dict) -> Optional[str]:
    """Pick the image URL (hdurl, else first <img> in basic_html), resized."""
    raw = apod.get("hdurl")
    if not raw:
        match = _IMG_SRC_RE.search(apod.get("basic_html") or "")
        raw = html.unescape(match.group(1)) if match else None
    if not raw:
        return None
    if "?" in raw:
        return raw
    query = urlencode({"w": IMAGE_MAX_EDGE_PX, "h": IMAGE_MAX_EDGE_PX, "fit": "clip"})
    return f"{raw}?{query}"


async def nasa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /nasa command - NASA Astronomy Picture of the Day."""
    if not update.message:
        return

    chat_data = context.chat_data or {}

    today = date.today().isoformat()
    shown_today = chat_data.get("nasa_apod_shown_date") == today

    timeout = aiohttp.ClientTimeout(total=15)
    fetched_todays = False

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                data = await _fetch_apod(session, random_pick=shown_today)
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
                try:
                    data = await _fetch_apod(session, random_pick=True)
                except RuntimeError as e2:
                    error_logger.error(
                        "NASA APOD random fallback also failed: %s", e2
                    )
                    return

            apod = data

            title = html.escape(_html_to_text(apod.get("title", "")) or "Unknown")
            explanation = _html_to_text(apod.get("explanation", ""))
            media_type = apod.get("media_type", "image")
            apod_date = html.escape(str(apod.get("date", "")))
            source_link = apod.get("permalink") or apod.get("url") or "https://science.nasa.gov/apod/"
            image_url = _image_url(apod)

            max_explanation = 850
            if len(explanation) > max_explanation:
                explanation = explanation[:max_explanation].rsplit(" ", 1)[0] + "..."
            explanation = html.escape(explanation)

            # Videos have no direct video URL in this API; the article page embeds it.
            links = (
                f"<a href=\"{html.escape(source_link)}\">Watch Video</a>"
                if media_type == "video"
                else f"<a href=\"{html.escape(source_link)}\">APOD Source</a>"
            )
            caption = (
                f"<b>{title}</b>\n"
                f"<i>{apod_date}</i>\n\n"
                f"{explanation}\n\n"
                f"{links}"
            )

            sent_photo = False
            if image_url:
                async with session.get(image_url) as img_response:
                    if img_response.status == 200:
                        image_bytes = await img_response.read()
                    else:
                        image_bytes = None
                        error_logger.error(
                            "NASA APOD image download failed: HTTP %s for %s",
                            img_response.status,
                            image_url,
                        )
                if image_bytes:
                    try:
                        await update.message.reply_photo(
                            photo=BytesIO(image_bytes),
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                        )
                        sent_photo = True
                    except TelegramError as e:
                        error_logger.error(
                            "NASA APOD photo upload failed for %s: %s", image_url, e
                        )
            if not sent_photo:
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
