"""
Reaction command handlers.

Contains handlers for toggling emoji reactions on specific users' messages.
"""

import logging
from typing import Any, Dict
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def reaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /reaction command for toggling reactions on/off."""
    if not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    if not update.effective_user:
        return

    args = context.args if hasattr(context, 'args') else []

    # Get service registry from bot application
    service_registry = None
    if hasattr(context, 'application') and context.application and hasattr(context.application, 'bot_data'):
        app: Any = context.application
        if hasattr(app, 'bot_data'):
            service_registry = app.bot_data.get('service_registry')

    if not service_registry:
        logger.warning("Service registry not available in context")
        if update.message:
            await update.message.reply_text("Service registry not available.")
        return

    config_manager = service_registry.get_service('config_manager')

    if not update.message:
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can use this command.")
        return

    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /reaction on|off")
        return

    enabled = args[0] == "on"

    await config_manager.enable_custom_config(chat_id, chat_type)

    await config_manager.update_module_setting(
        module_name="reactions",
        setting_path="enabled",
        value=enabled,
        chat_id=chat_id,
        chat_type=chat_type
    )

    if update.message:
        await update.message.reply_text(f"Reactions {'enabled' if enabled else 'disabled'}.")


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is admin."""
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type == 'private':
        return True

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False
