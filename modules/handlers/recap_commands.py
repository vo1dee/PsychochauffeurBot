"""
Daily chat recap command handlers.

/recap on|off toggles a per-chat daily digest of the previous day's
conversation (see modules.recap for generation/sending, and the JobQueue
wiring in modules.bot_application). Off by default in every chat.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from modules.const import KYIV_TZ
from modules.database import Database
from modules.handlers.speech_commands import is_admin
from modules.recap import DEFAULT_RECAP_TIME, generate_recap, send_recap

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

USAGE_TEXT = (
    "Використання:\n"
    "/recap on [HH:MM] — увімкнути щоденний рекап (за замовчуванням 09:30)\n"
    "/recap off — вимкнути\n"
    "/recap time HH:MM — змінити час надсилання"
)


async def recap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /recap command: on/off/time/status, plus a hidden 'now'."""
    if not update.effective_chat or not update.message:
        return
    chat_id = update.effective_chat.id

    if not await is_admin(update, context):
        await update.message.reply_text("❌ Тільки адміністратори можуть керувати рекапом.")
        return

    args = context.args if hasattr(context, 'args') and context.args else []

    if not args:
        await _send_status(update, chat_id)
        return

    subcommand = args[0].lower()

    if subcommand == "on":
        send_time: Optional[str] = None
        if len(args) > 1:
            if not _TIME_RE.match(args[1]):
                await update.message.reply_text(
                    "❌ Невірний формат часу. Використовуйте HH:MM, наприклад 09:30."
                )
                return
            send_time = args[1]

        await Database.upsert_recap_settings(chat_id, enabled=True, send_time=send_time)
        effective_time = send_time or DEFAULT_RECAP_TIME
        await update.message.reply_text(
            f"✅ Щоденний рекап увімкнено. Надсилатиметься о {effective_time} (Київ)."
        )

    elif subcommand == "off":
        await Database.upsert_recap_settings(chat_id, enabled=False)
        await update.message.reply_text("🔕 Щоденний рекап вимкнено.")

    elif subcommand == "time":
        if len(args) < 2 or not _TIME_RE.match(args[1]):
            await update.message.reply_text(
                "❌ Вкажіть час у форматі HH:MM, наприклад:\n/recap time 09:30"
            )
            return
        await Database.upsert_recap_settings(chat_id, send_time=args[1])
        await update.message.reply_text(f"🕒 Час рекапу змінено на {args[1]} (Київ).")

    elif subcommand == "now":
        # Hidden: not listed in USAGE_TEXT or help. Generates yesterday's
        # recap immediately regardless of the on/off toggle or send time.
        yesterday = (datetime.now(KYIV_TZ) - timedelta(days=1)).date()
        status_msg = await update.message.reply_text("🔄 Генерую рекап...")
        text = await generate_recap(chat_id, yesterday, min_messages=1)
        if not text:
            await status_msg.edit_text("За вчора в чаті не було повідомлень для рекапу.")
            return
        await status_msg.delete()
        await send_recap(context.bot, chat_id, text)

    else:
        await update.message.reply_text(USAGE_TEXT)


async def _send_status(update: Update, chat_id: int) -> None:
    if not update.message:
        return
    settings = await Database.get_recap_settings(chat_id)
    if settings and settings.get('enabled'):
        send_time = settings.get('send_time') or DEFAULT_RECAP_TIME
        status_line = f"Рекап зараз увімкнено, надсилається о {send_time} (Київ)."
    else:
        status_line = "Рекап зараз вимкнено."
    await update.message.reply_text(f"{status_line}\n\n{USAGE_TEXT}")
