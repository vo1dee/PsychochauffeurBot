import pytz
import random
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, ChatPermissions
from telegram.ext import CallbackContext
from telegram.error import TelegramError

from modules.logger import init_error_handler, error_logger

# Constants
LOCAL_TZ = pytz.timezone('Europe/Kyiv')
RESTRICT_DURATION_RANGE = (1, 15)  # min and max minutes
RESTRICTION_STICKER = "CAACAgQAAxkBAAEt8tNm9Wc6jYEQdAgQzvC917u3e8EKPgAC9hQAAtMUCVP4rJSNEWepBzYE"

async def restrict_user(update: Update, context: CallbackContext) -> None:
    """
    Restricts a user's ability to send messages for a random duration.
    
    Args:
        update (Update): The update object from Telegram
        context (CallbackContext): The context object from Telegram
    """
    chat = update.effective_chat
    if not chat or chat.type != "supergroup":
        await update.message.reply_text("This command is only available in supergroups.")
        return

    user = update.message.from_user
    if not user:
        general_logger.error("No user found in update")
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
        permissions = ChatPermissions(
            can_send_messages=False,        # ❌ Blocks text messages
            can_send_polls=False,           # ❌ Blocks polls
            can_send_other_messages=True,  # ❌ Blocks inline bots and games
            can_send_audios=True,           # ✅ Allows voice messages
            can_send_documents=True,        # ✅ Allows GIFs (sent as files)
            can_send_photos=True,           # ✅ Allows images
            can_send_videos=True,           # ✅ Allows videos
            can_send_video_notes=True,      # ✅ Allows video notes
            can_send_voice_notes=True,      # ✅ Allows voice messages
            can_add_web_page_previews=False # ❌ Blocks link previews
)
        # Apply restriction
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=permissions,
            until_date=until_date
        )

        # Send notifications
        await update.message.reply_text(
            f"Вас запсихопаркували на {restrict_duration} хвилин. "
            "Ви не можете надсилати повідомлення, але можете спробувати стікер або гіфку."
        )
        await context.bot.send_sticker(chat_id=chat.id, sticker=RESTRICTION_STICKER)
        
        general_logger.info(f"Restricted user {user.id} for {restrict_duration} minutes")

    except TelegramError as e:
        general_logger.error(f"Telegram API error while restricting user {user.id}: {e}")
        await update.message.reply_text("An error occurred while trying to restrict the user.")
    except Exception as e:
        general_logger.error(f"Unexpected error while restricting user {user.id}: {e}")
        await update.message.reply_text("An unexpected error occurred.")
