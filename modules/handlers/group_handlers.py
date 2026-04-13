"""
Group membership handlers for the PsychoChauffeur bot.

Contains handlers for group-related events like member joins/leaves.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from modules.logger import general_logger, error_logger

logger = logging.getLogger(__name__)

# Default values (used when config is unavailable)
_DEFAULT_TARGET_USERS = ["vo1dee"]
_DEFAULT_TARGET_GROUPS = [-1002096701815, -1002107242572]


async def handle_member_left(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle members leaving the group.

    Deletes the 'User left the group' message for configured users in configured groups.
    Settings are read from the 'group_behavior' config module.
    """
    if not update.message or not update.effective_chat:
        return

    try:
        if not update.message.left_chat_member:
            return

        left_user = update.message.left_chat_member
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        # Load settings from config, fall back to defaults
        target_users, target_groups = await _get_leave_message_settings(context)

        if (left_user.username in target_users and chat_id in target_groups):
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )
                general_logger.info(
                    f"Deleted exit message for {left_user.username} in group {chat_id} (message_id: {message_id})"
                )
            except Exception as delete_error:
                error_logger.error(
                    f"Failed to delete exit message in group {chat_id}: {delete_error}"
                )

    except Exception as e:
        error_logger.error(f"Error handling member left event: {e}", exc_info=True)


async def _get_leave_message_settings(context: ContextTypes.DEFAULT_TYPE):
    """Get auto-delete leave message settings from config."""
    try:
        app: Any = context.application
        service_registry = app.bot_data.get('service_registry') if hasattr(app, 'bot_data') else None
        if not service_registry:
            return _DEFAULT_TARGET_USERS, _DEFAULT_TARGET_GROUPS

        config_manager = service_registry.get_service('config_manager')
        if not config_manager:
            return _DEFAULT_TARGET_USERS, _DEFAULT_TARGET_GROUPS

        config = await config_manager.get_config()
        group_behavior = config.get("config_modules", {}).get("group_behavior", {})
        settings = group_behavior.get("overrides", {}).get("auto_delete_leave_messages", {})

        target_users = settings.get("target_users", _DEFAULT_TARGET_USERS)
        target_groups = settings.get("target_groups", _DEFAULT_TARGET_GROUPS)
        return target_users, target_groups

    except Exception as e:
        logger.warning(f"Failed to load group_behavior config, using defaults: {e}")
        return _DEFAULT_TARGET_USERS, _DEFAULT_TARGET_GROUPS
