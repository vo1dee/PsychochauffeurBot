import random
import time

from typing import Optional

from telegram import Update, ChatPermissions
from telegram.ext import CallbackContext
from typing import Any
from telegram.error import TelegramError

from modules.logger import general_logger, error_logger
from config.config_manager import get_shared_config_manager
from modules.const import Stickers

# Constants
RESTRICT_DURATION_RANGE = (1, 15)  # min and max minutes


async def _unrestrict_user(context: CallbackContext[Any, Any, Any, Any]) -> None:
    """Job callback to unrestrict a user and notify them."""
    job = context.job
    chat_id = job.data["chat_id"]
    user_id = job.data["user_id"]
    user_name = job.data.get("user_name", "User")

    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
        can_pin_messages=False,
        can_change_info=False,
    )
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔓 {user_name}, вас розпсихопаркували. Можете знову писати.",
        )
        general_logger.info(f"Auto-unrestricted user {user_id} in chat {chat_id}")
    except TelegramError as e:
        error_logger.error(f"Failed to auto-unrestrict user {user_id} in chat {chat_id}: {e}")


async def restrict_user(update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
    """
    Restricts a user's ability to send messages for a random duration, using chat_behavior config if present.
    """
    if not update.message:
        error_logger.error("No message found in update")
        return

    chat = update.effective_chat
    general_logger.info(f"[restrict_user] Called for chat_id={chat.id if chat else None}, chat_type={getattr(chat, 'type', None)}")
    if not chat or chat.type != "supergroup":
        general_logger.info("[restrict_user] Not a supergroup or chat missing, returning early.")
        await update.message.reply_text("This command is only available in supergroups.")
        return

    user = update.message.from_user
    if user and update.message.sticker:
        general_logger.info(f"[restrict_user] User: {user.id if user else None}, sticker.file_id={update.message.sticker.file_id}, sticker.file_unique_id={update.message.sticker.file_unique_id}")
    else:
        general_logger.info(f"[restrict_user] User: {user.id if user else None}")
    if not user:
        error_logger.error("No user found in update")
        return

    # --- Load chat_behavior config ---
    chat_id = str(chat.id)
    chat_type = chat.type
    try:
        chat_config = await get_shared_config_manager().get_config(chat_id, chat_type)
        chat_behavior = chat_config.get("config_modules", {}).get("chat_behavior", {})
        overrides = chat_behavior.get("overrides", {})
        restrictions_enabled = overrides.get("restrictions_enabled", True)
        restriction_sticker_unique_id = overrides.get("restriction_sticker_unique_id")
        general_logger.info(f"[restrict_user] restrictions_enabled={restrictions_enabled}, restriction_sticker_unique_id={restriction_sticker_unique_id}")
    except Exception as e:
        error_logger.error(f"Failed to load chat_behavior config: {e}")
        restrictions_enabled = True
        restriction_sticker_unique_id = None

    if not restrictions_enabled:
        general_logger.info(f"[restrict_user] Restrictions are disabled for chat {chat_id}, returning early.")
        return

    try:
        # Check if user is admin
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        general_logger.info(f"[restrict_user] chat_member.status={chat_member.status}")
        if chat_member.status in {"administrator", "creator"}:
            general_logger.info(f"[restrict_user] Cannot restrict admin/owner {user.id}, returning early.")
            return

        # Set up restriction
        restrict_duration = random.randint(*RESTRICT_DURATION_RANGE)
        until_date = int(time.time()) + restrict_duration * 60
        permissions = ChatPermissions(
            can_send_messages=False
        )
        general_logger.info(
            f"Attempting to restrict user {user.id} in chat {chat.id} for {restrict_duration} min (until_date={until_date})"
        )
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=permissions,
                until_date=until_date
            )
            general_logger.info(f"Restriction API call succeeded for user {user.id}")
        except TelegramError as e:
            error_logger.error(f"Telegram API error while restricting user {user.id}: {e}")
            await update.message.reply_text("An error occurred while trying to restrict the user.")
            return
        except Exception as e:
            error_logger.error(f"Unexpected error while restricting user {user.id}: {e}")
            await update.message.reply_text("An unexpected error occurred.")
            return

        # Schedule auto-unrestrict job
        user_name = user.first_name or "User"
        context.job_queue.run_once(
            _unrestrict_user,
            when=restrict_duration * 60,
            data={"chat_id": chat.id, "user_id": user.id, "user_name": user_name},
            name=f"unrestrict_{chat.id}_{user.id}",
        )

        # Send notification
        await update.message.reply_text(
            f"Вас запсихопаркували на {restrict_duration} хвилин."
        )

        # Send sticker (always random from RESTRICTION_STICKERS, never custom config)
        try:
            await context.bot.send_sticker(chat_id=chat.id, sticker=random.choice(Stickers.RESTRICTION_STICKERS))
        except TelegramError as sticker_error:
            error_logger.warning(f"Failed to send restriction sticker: {sticker_error}")

        general_logger.info(f"Restricted user {user.id} for {restrict_duration} min (until_date={until_date})")

    except TelegramError as e:
        error_logger.error(f"Telegram API error while restricting user {user.id}: {e}")
        await update.message.reply_text("An error occurred while trying to restrict the user.")
    except Exception as e:
        error_logger.error(f"Unexpected error while restricting user {user.id}: {e}")
        await update.message.reply_text("An unexpected error occurred.")

async def handle_restriction_sticker(update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
    """
    Restricts a user if they send a sticker matching the restriction_sticker_unique_id from config.
    """
    chat = update.effective_chat
    message = update.effective_message
    if not chat or chat.type != "supergroup":
        return
    if not message or not message.sticker:
        return
    user = message.from_user
    if not user:
        return
    chat_id = str(chat.id)
    chat_type = chat.type
    general_logger.info(f"[handle_restriction_sticker] Received sticker: file_id={message.sticker.file_id}, file_unique_id={message.sticker.file_unique_id}")
    try:
        chat_config = await get_shared_config_manager().get_config(chat_id, chat_type)
        chat_behavior = chat_config.get("config_modules", {}).get("chat_behavior", {})
        overrides = chat_behavior.get("overrides", {})
        restriction_sticker_unique_id = overrides.get("restriction_sticker_unique_id")
        general_logger.info(f"[handle_restriction_sticker] restriction_sticker_unique_id from config: {restriction_sticker_unique_id}")
    except Exception as e:
        error_logger.error(f"Failed to load chat_behavior config: {e}")
        restriction_sticker_unique_id = None
    if not restriction_sticker_unique_id:
        return
    # Check if the sticker matches the restriction_sticker_unique_id
    if message.sticker.file_unique_id != restriction_sticker_unique_id:
        return
    # Check if user is admin
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status in {"administrator", "creator"}:
            return
    except Exception as e:
        error_logger.error(f"Failed to get chat member: {e}")
        return
    # Restrict user
    restrict_duration = random.randint(*RESTRICT_DURATION_RANGE)
    until_date = int(time.time()) + restrict_duration * 60
    permissions = ChatPermissions(
        can_send_messages=False
    )
    try:
        result = await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=permissions,
            until_date=until_date
        )
        general_logger.info(f"[handle_restriction_sticker] restrict_chat_member result: {result}")

        # Schedule auto-unrestrict job
        user_name = user.first_name or "User"
        context.job_queue.run_once(
            _unrestrict_user,
            when=restrict_duration * 60,
            data={"chat_id": chat.id, "user_id": user.id, "user_name": user_name},
            name=f"unrestrict_{chat.id}_{user.id}",
        )

        await message.reply_text(
            f"Вас запсихопаркували на {restrict_duration} хвилин."
        )
        try:
            await context.bot.send_sticker(chat_id=chat.id, sticker=random.choice(Stickers.RESTRICTION_STICKERS))
        except TelegramError as sticker_error:
            error_logger.warning(f"Failed to send restriction sticker: {sticker_error}")
        general_logger.info(f"[handle_restriction_sticker] Restricted user {user.id} for {restrict_duration} min (until_date={until_date})")
    except TelegramError as e:
        error_logger.error(f"Telegram API error while restricting user {user.id}: {e}")
        await message.reply_text("An error occurred while trying to restrict the user.")
    except Exception as e:
        error_logger.error(f"Unexpected error while restricting user {user.id}: {e}")
        await message.reply_text("An unexpected error occurred.")
