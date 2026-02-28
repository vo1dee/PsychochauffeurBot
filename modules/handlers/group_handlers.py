"""
Group membership handlers for the PsychoChauffeur bot.

Contains handlers for group-related events like member joins/leaves.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from modules.logger import general_logger, error_logger

logger = logging.getLogger(__name__)


async def handle_member_left(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle members leaving the group.

    This handler deletes the 'User left the group' message for specific users in specific groups.
    Currently configured to delete the exit message when vo1dee leaves groups -1002096701815 or -1002107242572.
    """
    if not update.message or not update.effective_chat:
        return

    try:
        # Check if this message is about someone leaving the group
        if not update.message.left_chat_member:
            return

        left_user = update.message.left_chat_member
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        # Check if this is vo1dee leaving one of the target groups
        if (left_user.username == "vo1dee" and chat_id in (-1002096701815, -1002107242572)):
            try:
                # Delete the exit message
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )
                general_logger.info(
                    f"Deleted exit message for vo1dee in group {chat_id} (message_id: {message_id})"
                )
            except Exception as delete_error:
                error_logger.error(
                    f"Failed to delete exit message in group {chat_id}: {delete_error}"
                )

    except Exception as e:
        error_logger.error(f"Error handling member left event: {e}", exc_info=True)
