import pytz
import random
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, ChatPermissions
from telegram.ext import CallbackContext
from telegram.error import TelegramError

from modules.logger import general_logger, error_logger
from config.config_manager import ConfigManager
from modules.const import RESTRICTION_STICKERS

# Constants
LOCAL_TZ = pytz.timezone('Europe/Kyiv')
RESTRICT_DURATION_RANGE = (1, 15)  # min and max minutes

config_manager = ConfigManager()

async def restrict_user(update: Update, context: CallbackContext) -> None:
    """
    Restricts a user's ability to send messages for a random duration, using chat_behavior config if present.
    """
    chat = update.effective_chat
    if not chat or chat.type != "supergroup":
        await update.message.reply_text("This command is only available in supergroups.")
        return

    user = update.message.from_user
    if not user:
        error_logger.error("No user found in update")
        return

    # --- Load chat_behavior config ---
    chat_id = str(chat.id)
    chat_type = chat.type
    try:
        chat_config = await config_manager.get_config(chat_id, chat_type)
        chat_behavior = chat_config.get("config_modules", {}).get("chat_behavior", {})
        overrides = chat_behavior.get("overrides", {})
        restrictions_enabled = overrides.get("restrictions_enabled", True)
        restriction_sticker_id = overrides.get("restriction_sticker_id")
    except Exception as e:
        error_logger.error(f"Failed to load chat_behavior config: {e}")
        restrictions_enabled = True
        restriction_sticker_id = None

    if not restrictions_enabled:
        general_logger.info(f"Restrictions are disabled for chat {chat_id}")
        return

    try:
        # Check if user is admin
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status in {"administrator", "creator"}:
            general_logger.info(f"Cannot restrict admin/owner {user.id}")
            return

        # Set up restriction    
        restrict_duration = random.randint(*RESTRICT_DURATION_RANGE)
        until_date = datetime.now(LOCAL_TZ) + timedelta(minutes=restrict_duration)
        until_date_formatted = until_date.strftime("%Y-%m-%d %H:%M:%S")
        permissions = ChatPermissions(
            can_send_messages=False
        )

        # Apply restriction
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=permissions,
            until_date=until_date
        )

        # Send notification
        await update.message.reply_text(
            f"Вас запсихопаркували на {restrict_duration} хвилин.\n"
            f"Ви не можете надсилати повідомлення до {until_date_formatted}."
        )
        
        # Send sticker (always random from RESTRICTION_STICKERS, never custom config)
        try:
            await context.bot.send_sticker(chat_id=chat.id, sticker=random.choice(RESTRICTION_STICKERS))
        except TelegramError as sticker_error:
            error_logger.warning(f"Failed to send restriction sticker: {sticker_error}")

        general_logger.info(f"Restricted user {user.id} for {restrict_duration} minutes until {until_date_formatted}")

    except TelegramError as e:
        error_logger.error(f"Telegram API error while restricting user {user.id}: {e}")
        await update.message.reply_text("An error occurred while trying to restrict the user.")
    except Exception as e:
        error_logger.error(f"Unexpected error while restricting user {user.id}: {e}")
        await update.message.reply_text("An unexpected error occurred.")
