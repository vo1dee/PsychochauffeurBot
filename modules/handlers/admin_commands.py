"""
Admin command handlers for the PsychoChauffeur bot.

Contains handlers for administrative commands like mute, ban, etc.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from modules.logger import general_logger, error_logger

logger = logging.getLogger(__name__)


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /mute command to mute a user for a specified time in minutes.

    Usage: /mute <@username or user_id> <minutes>
    Or reply to a message: /mute <minutes>
    """
    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Check if command is used in a group/supergroup
    if not chat or chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command can only be used in groups.")
        return

    # Check if user is admin
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command.")
            return
    except TelegramError as e:
        error_logger.error(f"Failed to check admin status: {e}")
        await update.message.reply_text("❌ Failed to verify permissions.")
        return

    # Parse command arguments
    args = context.args or []
    target_user_id = None
    mute_minutes = None

    # Check if replying to a message
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        if target_user:
            target_user_id = target_user.id
        else:
            await update.message.reply_text("❌ Cannot identify the user to mute.")
            return
    elif len(args) >= 2:
        # Try to parse first argument as @username or user ID
        first_arg = args[0]

        if first_arg.startswith('@'):
            # Handle @username mention
            username = first_arg[1:]  # Remove @ symbol
            try:
                # Get all chat members to find user by username
                # Note: This might not work for large groups due to Telegram API limitations
                chat_members = await context.bot.get_chat_administrators(chat.id)
                target_member = None

                for member in chat_members:
                    if member.user.username and member.user.username.lower() == username.lower():
                        target_member = member
                        break

                if not target_member:
                    # Note: Cannot reliably get user by username with get_chat_member
                    # as it requires user ID (int), not username string
                    await update.message.reply_text(f"❌ User @{username} not found in this chat.")
                    return

                if target_member:
                    target_user_id = target_member.user.id
                else:
                    await update.message.reply_text(f"❌ User @{username} not found in this chat or not accessible.")
                    return

            except TelegramError as e:
                error_logger.error(f"Failed to find user by username @{username}: {e}")
                await update.message.reply_text(f"❌ Could not find user @{username}. Try using user ID instead.")
                return
        else:
            # Try to parse as user ID
            try:
                target_user_id = int(first_arg)
            except ValueError:
                await update.message.reply_text("❌ Invalid format. Use @username or numeric user ID.")
                return
    else:
        await update.message.reply_text("❌ Usage: /mute <@username or user_id> <minutes> or reply to message with /mute <minutes>")
        return

    # Parse mute duration
    if update.message.reply_to_message:
        if len(args) >= 1:
            try:
                mute_minutes = int(args[0])
            except ValueError:
                await update.message.reply_text("❌ Invalid duration. Please specify minutes as a number.")
                return
        else:
            await update.message.reply_text("❌ Please specify the mute duration in minutes.")
            return
    else:
        try:
            mute_minutes = int(args[1])
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid duration. Please specify minutes as a number.")
            return

    # Validate mute duration
    if mute_minutes <= 0:
        await update.message.reply_text("❌ Mute duration must be positive.")
        return

    if mute_minutes > 1440:  # Max 24 hours
        await update.message.reply_text("❌ Maximum mute duration is 1440 minutes (24 hours).")
        return

    # Check if target user exists and is not admin
    try:
        target_member = await context.bot.get_chat_member(chat.id, target_user_id)
        if target_member.status in ['administrator', 'creator']:
            await update.message.reply_text("❌ Cannot mute administrators or the group owner.")
            return

        if target_member.status == 'left' or target_member.status == 'kicked':
            await update.message.reply_text("❌ User is not in the group.")
            return

    except TelegramError as e:
        error_logger.error(f"Failed to get target user info: {e}")
        await update.message.reply_text("❌ Failed to get user information.")
        return

    # Calculate mute end time
    mute_until = datetime.now() + timedelta(minutes=mute_minutes)
    mute_until_formatted = mute_until.strftime("%Y-%m-%d %H:%M:%S")

    # Apply mute
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False
    )

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_user_id,
            permissions=permissions,
            until_date=mute_until
        )

        # Get target user info for better message
        target_name = target_member.user.first_name or "User"
        if target_member.user.username:
            target_name += f" (@{target_member.user.username})"

        await update.message.reply_text(
            f"✅ {target_name} has been muted for {mute_minutes} minutes.\n"
            f"Mute expires: {mute_until_formatted}"
        )

        if user is not None:
            general_logger.info(f"User {target_user_id} muted by {user.id} for {mute_minutes} minutes in chat {chat.id}")
        else:
            general_logger.info(f"User {target_user_id} muted for {mute_minutes} minutes in chat {chat.id}")

    except TelegramError as e:
        error_logger.error(f"Failed to mute user {target_user_id}: {e}")
        await update.message.reply_text("❌ Failed to mute the user. The bot may not have sufficient permissions.")
    except Exception as e:
        error_logger.error(f"Unexpected error while muting user {target_user_id}: {e}")
        await update.message.reply_text("❌ An unexpected error occurred.")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /unmute command to unmute a user.

    Usage: /unmute <@username or user_id>
    Or reply to a message: /unmute
    """
    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Check if command is used in a group/supergroup
    if not chat or chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command can only be used in groups.")
        return

    # Check if user is admin
    if user is None:
        await update.message.reply_text("❌ Unable to identify user.")
        return

    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command.")
            return
    except TelegramError as e:
        error_logger.error(f"Failed to check admin status: {e}")
        await update.message.reply_text("❌ Failed to verify permissions.")
        return

    # Parse command arguments
    args = context.args or []
    target_user_id = None

    # Check if replying to a message
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        if target_user:
            target_user_id = target_user.id
        else:
            await update.message.reply_text("❌ Cannot identify the user to unmute.")
            return
    elif len(args) >= 1:
        # Try to parse first argument as @username or user ID
        first_arg = args[0]

        if first_arg.startswith('@'):
            # Handle @username mention
            username = first_arg[1:]  # Remove @ symbol
            try:
                # Get all chat members to find user by username
                chat_members = await context.bot.get_chat_administrators(chat.id)
                target_member = None

                for member in chat_members:
                    if member.user.username and member.user.username.lower() == username.lower():
                        target_member = member
                        break

                if not target_member:
                    # Note: Cannot reliably get user by username with get_chat_member
                    # as it requires user ID (int), not username string
                    await update.message.reply_text(f"❌ User @{username} not found in this chat.")
                    return

                if target_member:
                    target_user_id = target_member.user.id
                else:
                    await update.message.reply_text(f"❌ User @{username} not found in this chat or not accessible.")
                    return

            except TelegramError as e:
                error_logger.error(f"Failed to find user by username @{username}: {e}")
                await update.message.reply_text(f"❌ Could not find user @{username}. Try using user ID instead.")
                return
        else:
            # Try to parse as user ID
            try:
                target_user_id = int(first_arg)
            except ValueError:
                await update.message.reply_text("❌ Invalid format. Use @username or numeric user ID.")
                return
    else:
        await update.message.reply_text("❌ Usage: /unmute <@username or user_id> or reply to a message with /unmute")
        return

    # Check if target user exists
    try:
        target_member = await context.bot.get_chat_member(chat.id, target_user_id)
        if target_member.status == 'left' or target_member.status == 'kicked':
            await update.message.reply_text("❌ User is not in the group.")
            return

    except TelegramError as e:
        error_logger.error(f"Failed to get target user info: {e}")
        await update.message.reply_text("❌ Failed to get user information.")
        return

    # Remove restrictions (unmute)
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,  # Keep these restricted for regular users
        can_invite_users=False,
        can_pin_messages=False
    )

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_user_id,
            permissions=permissions,
            until_date=None  # Remove time limit
        )

        # Get target user info for better message
        target_name = target_member.user.first_name or "User"
        if target_member.user.username:
            target_name += f" (@{target_member.user.username})"

        await update.message.reply_text(f"✅ {target_name} has been unmuted.")

        if user is not None:
            general_logger.info(f"User {target_user_id} unmuted by {user.id} in chat {chat.id}")
        else:
            general_logger.info(f"User {target_user_id} unmuted in chat {chat.id}")

    except TelegramError as e:
        error_logger.error(f"Failed to unmute user {target_user_id}: {e}")
        await update.message.reply_text("❌ Failed to unmute the user. The bot may not have sufficient permissions.")
    except Exception as e:
        error_logger.error(f"Unexpected error while unmuting user {target_user_id}: {e}")
        await update.message.reply_text("❌ An unexpected error occurred.")