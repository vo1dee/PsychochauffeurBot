import pytz
import random

from modules.file_manager import general_logger

from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import CallbackContext


# Set local timezone
LOCAL_TZ = pytz.timezone('Europe/Kyiv')

async def restrict_user(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user_id = update.message.from_user.id
    username = update.message.from_user.username  # Get the username for the reply message

    # Check if the user is the chat owner or an admin
    chat_member = await context.bot.get_chat_member(chat.id, user_id)
    if chat_member.status in ["administrator", "creator"]:
        general_logger.info("Cannot restrict an admin or chat owner.")
        return

    if chat.type == "supergroup":
        try:
            restrict_duration = random.randint(1, 15)  # Restriction duration in minutes
            permissions = ChatPermissions(can_send_messages=False)

            # Get current time in EEST
            until_date = datetime.now(LOCAL_TZ) + timedelta(minutes=restrict_duration)

            # Restrict user in the chat
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )

            # Notify user with a custom sticker
            sticker_id = "CAACAgQAAxkBAAEt8tNm9Wc6jYEQdAgQzvC917u3e8EKPgAC9hQAAtMUCVP4rJSNEWepBzYE"
            await update.message.reply_text(f"Вас запсихопаркували на {restrict_duration} хвилин. Ви не можете надсилати повідомлення.")
            await context.bot.send_sticker(chat_id=chat.id, sticker=sticker_id)
            general_logger.info(f"Restricted user {user_id} for {restrict_duration} minutes.")

        except Exception as e:
            general_logger.error(f"Failed to restrict user: {e}")
    else:
        await update.message.reply_text("This command is only available in supergroups.")
