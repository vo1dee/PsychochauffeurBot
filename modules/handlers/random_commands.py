"""
Random response command handlers.

Contains handlers for random response toggle functionality.
"""

import logging
from typing import Any, Dict, Optional
from telegram import Update, Chat, User
from telegram.ext import ContextTypes, Application

# Service registry will be accessed through context

logger = logging.getLogger(__name__)


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /random command for random response toggle."""
    if not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    args = context.args if hasattr(context, 'args') else []

    # Get service registry from bot application
    service_registry = None
    if hasattr(context, 'application') and context.application and hasattr(context.application, 'bot_data'):
        # Type annotation to help mypy understand the context structure
        app: Any = context.application
        if hasattr(app, 'bot_data'):
            service_registry = app.bot_data.get('service_registry')

    if not service_registry:
        logger.warning("Service registry not available in context")
        if update.message:
            await update.message.reply_text("❌ Service registry not available.")
        return

    # Get config manager service
    config_manager = service_registry.get_service('config_manager')

    if not update.message:
        return

    if not await is_admin(update, context):
        await update.message.reply_text("❌ Only admins can use this command.")
        return

    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /random on|off")
        return

    enabled = args[0] == "on"

    # Random responses live under chat_behavior — the module the runtime reads
    # (message_handler_service / gpt.py), not gpt.
    from config_v2.manager import telegram_actor

    await config_manager.update_module_setting(
        module_name="chat_behavior",
        setting_path="random_response_settings.enabled",
        value=enabled,
        chat_id=chat_id,
        chat_type=chat_type,
        actor=telegram_actor(update.effective_user),
    )

    if update.message:
        await update.message.reply_text(f"Random responses {'enabled' if enabled else 'disabled'}.")


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
    except Exception as e:
        logger.warning(f"Failed to check admin status for user {user.id} in chat {chat.id}: {e}")
        return False