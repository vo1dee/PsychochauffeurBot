"""
Speech recognition command handlers.

Contains handlers for speech-related functionality.
"""

import logging
from typing import Any, Dict, Optional
from telegram import Update, Chat, User
from telegram.ext import ContextTypes

# Service registry will be accessed through context

logger = logging.getLogger(__name__)


async def speech_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /speech command for speech recognition toggle."""
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
        service_registry = context.application.bot_data.get('service_registry')
    
    if not service_registry:
        logger.warning("Service registry not available in context")
        if update.message:
            await update.message.reply_text("❌ Service registry not available.")
        return
    
    # Get config manager service
    config_manager = service_registry.get_service('config_manager')
    
    speech_config = await get_speech_config(chat_id, chat_type, config_manager)
    
    # Ensure 'overrides' exists in config before updating
    if 'overrides' not in speech_config:
        speech_config['overrides'] = {}
        # Save the updated config immediately
        config = await config_manager.get_config(chat_id, chat_type)
        config['config_modules']['speechmatics'] = speech_config
        await config_manager.save_config(config, chat_id, chat_type)
    
    overrides = speech_config.get("overrides", {})
    allow_all = overrides.get("allow_all_users", False)
    
    if not update.message:
        return
        
    if not allow_all and not await is_admin(update, context):
        await update.message.reply_text("❌ Only admins can use this command.")
        return
    
    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /speech on|off")
        return
    
    enabled = args[0] == "on"
    
    # Update config
    await config_manager.update_module_setting(
        module_name="speechmatics",
        setting_path="overrides.enabled",
        value=enabled,
        chat_id=chat_id,
        chat_type=chat_type
    )
    
    if update.message:
        await update.message.reply_text(f"Speech recognition {'enabled' if enabled else 'disabled'}.")


async def get_speech_config(chat_id: str, chat_type: str, config_manager: Any) -> Dict[str, Any]:
    """Get speech configuration for a chat."""
    config = await config_manager.get_config(chat_id, chat_type)
    # Explicitly type the return value to avoid Any return
    result: Dict[str, Any] = config.get("config_modules", {}).get("speechmatics", {})
    return result


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