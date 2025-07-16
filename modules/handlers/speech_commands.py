"""
Speech recognition command handlers.

Contains handlers for speech-related functionality.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from modules.service_registry import service_registry

logger = logging.getLogger(__name__)


async def speech_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /speech command for speech recognition toggle."""
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    args = context.args if hasattr(context, 'args') else []
    
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
    
    await update.message.reply_text(f"Speech recognition {'enabled' if enabled else 'disabled'}.")


async def get_speech_config(chat_id: str, chat_type: str, config_manager):
    """Get speech configuration for a chat."""
    config = await config_manager.get_config(chat_id, chat_type)
    return config.get("config_modules", {}).get("speechmatics", {})


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is admin."""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == 'private':
        return True
        
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False