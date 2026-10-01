"""
Daily chat recap.

Builds and sends a Ukrainian-language digest of the previous day's chat
activity for chats that have opted in via /recap on. See modules.handlers.recap_commands
for the command surface and modules.bot_application for the job wiring.
"""

import asyncio
import re
from datetime import date, datetime, timedelta
from typing import Any, List, Optional, Tuple

from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext

from config_v2.compat import get_shared_config_manager
from modules.chat_analysis import get_messages_for_recap
from modules.database import Database
from modules.const import KYIV_TZ
from modules.gpt import client, get_system_prompt
from modules.logger import general_logger, error_logger

import os

# Minimum number of qualifying messages a day needs before a recap is generated
# for it. Below this, the day is considered too quiet and is skipped silently.
RECAP_MIN_MESSAGES = int(os.getenv('RECAP_MIN_MESSAGES', '20'))

DEFAULT_RECAP_TIME = "09:30"

# Cap on how much chat text is sent to the LLM in one go (characters).
RECAP_MAX_INPUT_CHARS = 120_000
RECAP_MAX_TOKENS = 6000
RECAP_TEMPERATURE = float(os.getenv('RECAP_TEMPERATURE', '0.3'))
RECAP_MODEL = os.getenv('RECAP_MODEL', 'openai/gpt-6-sol')

# Telegram messages are capped at 4096 chars; leave headroom for HTML tags.
RECAP_CHUNK_LIMIT = 4000

UKRAINIAN_MONTHS_GENITIVE = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня",
}

# Serializes recap_tick invocations so overlapping JobQueue runs (or a slow
# LLM call spanning a tick boundary) can't send the same chat's recap twice.
_tick_lock = asyncio.Lock()


def format_recap_header(chat_title: Optional[str], target_date: date) -> str:
    """Build the '📜 РЕКАП ... | D → D місяць' header for a recap."""
    prev_day = target_date - timedelta(days=1)
    month = UKRAINIAN_MONTHS_GENITIVE[target_date.month]

    if prev_day.month == target_date.month:
        date_part = f"{prev_day.day} → {target_date.day} {month}"
    else:
        prev_month = UKRAINIAN_MONTHS_GENITIVE[prev_day.month]
        date_part = f"{prev_day.day} {prev_month} → {target_date.day} {month}"

    title_part = f" {chat_title}" if chat_title else ""
    return f"📜 <b>РЕКАП{title_part} | {date_part}</b>"


def _format_sender(username: Optional[str], first_name: Optional[str]) -> str:
    if username:
        return f"@{username}"
    return first_name or "Хтось"


def _build_input_text(
    rows: List[Tuple[datetime, Optional[str], Optional[str], str]]
) -> str:
    lines = [
        f"[{ts.strftime('%H:%M')}] {_format_sender(username, first_name)}: {text}"
        for ts, username, first_name, text in rows
    ]
    text = "\n".join(lines)
    if len(text) <= RECAP_MAX_INPUT_CHARS:
        return text

    # Keep the most recent messages when the day is too big to fit whole.
    kept: List[str] = []
    total = 0
    for line in reversed(lines):
        total += len(line) + 1
        if total > RECAP_MAX_INPUT_CHARS:
            break
        kept.append(line)
    kept.reverse()
    return "\n".join(kept)


def _split_recap(text: str, max_len: int = RECAP_CHUNK_LIMIT) -> List[str]:
    """Split recap text into Telegram-sized chunks, preferring section boundaries."""
    if len(text) <= max_len:
        return [text]

    sections = text.split("\n\n")
    chunks: List[str] = []
    current = ""
    for section in sections:
        candidate = f"{current}\n\n{section}" if current else section
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = section
        else:
            current = candidate
    if current:
        chunks.append(current)

    # Guard against a single section still being too long on its own.
    final: List[str] = []
    for chunk in chunks:
        if len(chunk) <= max_len:
            final.append(chunk)
        else:
            final.extend(chunk[i:i + max_len] for i in range(0, len(chunk), max_len))
    return final


async def generate_recap(
    chat_id: int,
    target_date: date,
    min_messages: int = RECAP_MIN_MESSAGES,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Build the previous day's recap text (HTML, header included) for a chat.

    Returns None when the day had fewer than min_messages qualifying messages,
    or when the LLM call fails.
    """
    try:
        rows = await get_messages_for_recap(chat_id, target_date)
    except Exception as e:
        error_logger.error(f"Recap: failed to fetch messages for chat {chat_id}: {e}")
        return None

    if len(rows) < min_messages:
        general_logger.info(
            f"Recap: chat {chat_id} had {len(rows)} qualifying messages on {target_date}, "
            f"below threshold {min_messages}; skipping"
        )
        return None

    input_text = _build_input_text(rows)

    chat_info = None
    try:
        chat_info = await Database.get_chat_info(chat_id)
    except Exception as e:
        error_logger.error(f"Recap: failed to load chat info for {chat_id}: {e}")

    chat_type = (chat_info or {}).get('chat_type') or 'group'
    chat_title = (chat_info or {}).get('title')

    try:
        chat_config = await get_shared_config_manager().get_config(
            str(chat_id), chat_type, chat_name=chat_title
        )
    except Exception as e:
        error_logger.error(f"Recap: failed to load config for chat {chat_id}: {e}")
        chat_config = {}

    system_prompt = await get_system_prompt("recap", chat_config)

    try:
        response = await client.chat.completions.create(
            model=model or RECAP_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ],
            max_tokens=RECAP_MAX_TOKENS,
            temperature=RECAP_TEMPERATURE,
        )
        body = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        error_logger.error(f"Recap: LLM call failed for chat {chat_id}: {e}")
        return None

    if not body:
        return None

    header = format_recap_header(chat_title, target_date)
    return f"{header}\n\n{body}"


async def send_recap(bot: Any, chat_id: int, text: str, pin: bool = True) -> None:
    """
    Send a recap to a chat, splitting long text and falling back to plain text
    on bad HTML. Afterwards, silently pins the first sent message (no
    notification); earlier recap pins are left in place, building a history.
    """
    sent_messages = []
    for chunk in _split_recap(text):
        message = await _send_recap_chunk(bot, chat_id, chunk)
        if message is not None:
            sent_messages.append(message)

    if pin and sent_messages:
        await _pin_recap_message(bot, chat_id, sent_messages[0])


async def _send_recap_chunk(bot: Any, chat_id: int, chunk: str) -> Optional[Any]:
    """Send one chunk, falling back to plain text if the HTML is rejected. Returns the sent Message, or None on failure."""
    try:
        return await bot.send_message(chat_id, chunk, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        error_logger.warning(
            f"Recap: HTML send failed for chat {chat_id}, retrying as plain text: {e}"
        )
        plain = re.sub(r"<[^>]+>", "", chunk)
        try:
            return await bot.send_message(chat_id, plain)
        except Exception as e2:
            error_logger.error(f"Recap: plain-text fallback also failed for chat {chat_id}: {e2}")
            return None
    except Exception as e:
        error_logger.error(f"Recap: failed to send to chat {chat_id}: {e}")
        return None


async def _pin_recap_message(bot: Any, chat_id: int, message: Any) -> None:
    """
    Pin the given recap message without notifying. Earlier recap pins are left
    in place (not unpinned), so the chat's pinned-messages list builds up into
    a browsable history of past recaps.
    """
    try:
        await bot.pin_chat_message(chat_id, message.message_id, disable_notification=True)
        await Database.set_recap_pinned_message(chat_id, message.message_id)
    except Exception as e:
        error_logger.error(f"Recap: failed to pin recap message in chat {chat_id}: {e}")


def _parse_send_time(send_time: Optional[str]) -> Tuple[int, int]:
    try:
        hour_str, minute_str = (send_time or DEFAULT_RECAP_TIME).split(":")
        return int(hour_str), int(minute_str)
    except Exception:
        return 9, 30


async def recap_tick(context: CallbackContext[Any, Any, Any, Any]) -> None:
    """
    JobQueue callback, run every ~60s. Sends yesterday's recap to each enabled
    chat once per day, at or after that chat's configured send time.
    """
    if _tick_lock.locked():
        return

    async with _tick_lock:
        try:
            chats = await Database.get_enabled_recap_chats() or []
        except Exception as e:
            error_logger.error(f"Recap tick: failed to load enabled chats: {e}")
            return

        now = datetime.now(KYIV_TZ)
        today = now.date()
        yesterday = today - timedelta(days=1)

        for row in chats:
            chat_id = row['chat_id']
            last_sent = row.get('last_sent_date')
            if last_sent == today:
                continue

            send_hour, send_minute = _parse_send_time(row.get('send_time'))
            if (now.hour, now.minute) < (send_hour, send_minute):
                continue

            # Atomically claim today for this chat before generating, so a
            # slow LLM call spanning ticks, an overlapping run, or even a
            # second bot instance sharing this database can't send the same
            # chat's recap twice: only the caller that flips last_sent_date
            # proceeds, everyone else sees claimed=False and skips.
            try:
                claimed = await Database.mark_recap_sent(chat_id, today)
            except Exception as e:
                error_logger.error(f"Recap tick: failed to mark chat {chat_id} as sent: {e}")
                continue

            if not claimed:
                continue

            try:
                text = await generate_recap(chat_id, yesterday)
                if text:
                    await send_recap(context.bot, chat_id, text)
                    general_logger.info(f"Recap sent for chat {chat_id}")
                else:
                    general_logger.info(f"Recap skipped for chat {chat_id} (below activity threshold)")
            except Exception as e:
                error_logger.error(f"Recap tick: failed to generate/send recap for chat {chat_id}: {e}")
