"""
/webapp command: opens the demo weather Mini App.

Telegram only allows `web_app` inline buttons in private chats. In groups we
send a t.me direct link instead, which requires the Mini App to be registered
with BotFather (/newapp) under WEBAPP_SHORT_NAME; otherwise we point the user
to the bot's private chat.
"""

import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ChatType
from telegram.ext import ContextTypes


def _webapp_url() -> str:
    return os.getenv("WEBAPP_URL", "").strip()


def _webapp_short_name() -> str:
    return os.getenv("WEBAPP_SHORT_NAME", "").strip()


async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /webapp command."""
    if not update.message:
        return

    url = _webapp_url()
    if not url:
        await update.message.reply_text("Web App не налаштовано (WEBAPP_URL порожній).")
        return

    chat_type = update.effective_chat.type if update.effective_chat else ChatType.PRIVATE
    if chat_type == ChatType.PRIVATE:
        button = InlineKeyboardButton("🌤 Відкрити погоду", web_app=WebAppInfo(url=url))
        text = "Демо Web App з погодою:"
    else:
        bot_username = context.bot.username
        short_name = _webapp_short_name()
        if short_name:
            button = InlineKeyboardButton("🌤 Відкрити погоду", url=f"https://t.me/{bot_username}/{short_name}")
            text = "Демо Web App з погодою (відкриється всередині Telegram):"
        else:
            button = InlineKeyboardButton("💬 Відкрити в приватному чаті", url=f"https://t.me/{bot_username}?start=webapp")
            text = "У групах Web App доступний через приватний чат з ботом — надішліть там /webapp."

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[button]]))
