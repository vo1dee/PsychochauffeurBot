"""
Leveling System Configuration Commands

This module provides command handlers for managing the leveling system configuration
at runtime, including feature toggles and parameter updates.
"""

import logging
from typing import Dict, Any, Optional, List
from telegram import Update
from telegram.ext import ContextTypes

from modules.service_registry import get_service_registry
from modules.leveling_config import LevelingSystemConfig, LevelFormula
from modules.command_registry import CommandInfo, CommandCategory

logger = logging.getLogger(__name__)


async def leveling_config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /leveling_config command for managing leveling system configuration.
    
    Usage:
    /leveling_config - Show current configuration
    /leveling_config get <setting> - Get specific setting value
    /leveling_config set <setting> <value> - Set specific setting value
    /leveling_config toggle <feature> - Toggle a feature on/off
    /leveling_config reload - Reload configuration from file
    /leveling_config reset - Reset to default configuration
    """
    if not update.message or not update.effective_chat:
        return
    
    # Check if user has admin permissions (you may want to implement proper permission checking)
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Unable to verify user permissions.")
        return
    
    # Get the leveling service
    service_registry = get_service_registry()
    if not service_registry:
        await update.message.reply_text("❌ Service registry not available.")
        return
    
    leveling_service = service_registry.get_service('user_leveling_service')
    if not leveling_service:
        await update.message.reply_text("❌ Leveling service not available.")
        return
    
    # Parse command arguments
    args = context.args if context.args else []
    
    if not args:
        # Show current configuration
        await _show_configuration(update, leveling_service)
    elif args[0] == 'get' and len(args) >= 2:
        # Get specific setting
        setting_path = args[1]
        await _get_setting(update, leveling_service, setting_path)
    elif args[0] == 'set' and len(args) >= 3:
        # Set specific setting
        setting_path = args[1]
        value = ' '.join(args[2:])
        await _set_setting(update, leveling_service, setting_path, value)
    elif args[0] == 'toggle' and len(args) >= 2:
        # Toggle feature
        feature_path = args[1]
        await _toggle_feature(update, leveling_service, feature_path)
    elif args[0] == 'reload':
        # Reload configuration
        await _reload_configuration(update, leveling_service)
    elif args[0] == 'reset':
        # Reset to default configuration
        await _reset_configuration(update, leveling_service)
    else:
        await _show_help(update)


async def _show_configuration(update: Update, leveling_service) -> None:
    """Show current leveling system configuration."""
    try:
        config = leveling_service.get_current_configuration()
        if not config:
            await update.message.reply_text("❌ Configuration not available.")
            return
        
        # Format configuration for display
        message = "🔧 **Leveling System Configuration**\n\n"
        
        # System status
        message += f"**System Status:** {'✅ Enabled' if config.get('enabled', False) else '❌ Disabled'}\n\n"
        
        # XP Rates
        xp_rates = config.get('xp_rates', {})
        message += "**XP Rates:**\n"
        message += f"• Message: {xp_rates.get('message', 1)} XP\n"
        message += f"• Link: {xp_rates.get('link', 3)} XP\n"
        message += f"• Thanks: {xp_rates.get('thanks', 5)} XP\n\n"
        
        # Level Formula
        level_formula = config.get('level_formula', {})
        message += "**Level Formula:**\n"
        message += f"• Type: {level_formula.get('formula', 'exponential')}\n"
        message += f"• Base XP: {level_formula.get('base_xp', 50)}\n"
        message += f"• Multiplier: {level_formula.get('multiplier', 2.0)}\n\n"
        
        # Features
        notifications = config.get('notifications', {})
        rate_limiting = config.get('rate_limiting', {})
        cache = config.get('cache', {})
        
        message += "**Features:**\n"
        message += f"• Notifications: {'✅' if notifications.get('enabled', True) else '❌'}\n"
        message += f"• Rate Limiting: {'✅' if rate_limiting.get('enabled', False) else '❌'}\n"
        message += f"• Caching: {'✅' if cache.get('enabled', True) else '❌'}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error showing configuration: {e}", exc_info=True)
        await update.message.reply_text("❌ Error retrieving configuration.")


async def _get_setting(update: Update, leveling_service, setting_path: str) -> None:
    """Get a specific configuration setting."""
    try:
        config = leveling_service.get_current_configuration()
        if not config:
            await update.message.reply_text("❌ Configuration not available.")
            return
        
        # Navigate to the setting
        value = _get_nested_value(config, setting_path)
        if value is None:
            await update.message.reply_text(f"❌ Setting '{setting_path}' not found.")
            return
        
        message = f"🔧 **Configuration Setting**\n\n"
        message += f"**Path:** `{setting_path}`\n"
        message += f"**Value:** `{value}`\n"
        message += f"**Type:** `{type(value).__name__}`"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting setting {setting_path}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error retrieving setting '{setting_path}'.")


async def _set_setting(update: Update, leveling_service, setting_path: str, value_str: str) -> None:
    """Set a specific configuration setting."""
    try:
        # Parse the value
        parsed_value = _parse_value(value_str)
        
        # Create update dictionary
        updates = _create_nested_update(setting_path, parsed_value)
        
        # Apply the update
        success = await leveling_service.update_configuration(updates)
        
        if success:
            message = f"✅ **Configuration Updated**\n\n"
            message += f"**Setting:** `{setting_path}`\n"
            message += f"**New Value:** `{parsed_value}`"
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Failed to update setting '{setting_path}'.")
        
    except Exception as e:
        logger.error(f"Error setting {setting_path} to {value_str}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error updating setting '{setting_path}'.")


async def _toggle_feature(update: Update, leveling_service, feature_path: str) -> None:
    """Toggle a feature on or off."""
    try:
        # Get current status
        current_status = await leveling_service.get_feature_status(feature_path)
        if current_status is None:
            await update.message.reply_text(f"❌ Feature '{feature_path}' not found or not toggleable.")
            return
        
        # Toggle the feature
        new_status = not current_status
        success = await leveling_service.toggle_feature(feature_path, new_status)
        
        if success:
            status_text = "✅ Enabled" if new_status else "❌ Disabled"
            message = f"🔧 **Feature Toggled**\n\n"
            message += f"**Feature:** `{feature_path}`\n"
            message += f"**Status:** {status_text}"
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Failed to toggle feature '{feature_path}'.")
        
    except Exception as e:
        logger.error(f"Error toggling feature {feature_path}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error toggling feature '{feature_path}'.")


async def _reload_configuration(update: Update, leveling_service) -> None:
    """Reload configuration from file."""
    try:
        success = await leveling_service.reload_configuration()
        
        if success:
            await update.message.reply_text("✅ Configuration reloaded successfully.")
        else:
            await update.message.reply_text("❌ Failed to reload configuration.")
        
    except Exception as e:
        logger.error(f"Error reloading configuration: {e}", exc_info=True)
        await update.message.reply_text("❌ Error reloading configuration.")


async def _reset_configuration(update: Update, leveling_service) -> None:
    """Reset configuration to defaults."""
    try:
        # Create default configuration
        default_config = LevelingSystemConfig()
        
        # Apply default configuration
        success = await leveling_service.update_configuration(default_config.to_dict())
        
        if success:
            await update.message.reply_text("✅ Configuration reset to defaults.")
        else:
            await update.message.reply_text("❌ Failed to reset configuration.")
        
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}", exc_info=True)
        await update.message.reply_text("❌ Error resetting configuration.")


async def _show_help(update: Update) -> None:
    """Show help for the leveling_config command."""
    help_text = """🔧 **Leveling Configuration Help**

**Usage:**
• `/leveling_config` - Show current configuration
• `/leveling_config get <setting>` - Get specific setting
• `/leveling_config set <setting> <value>` - Set specific setting
• `/leveling_config toggle <feature>` - Toggle feature on/off
• `/leveling_config reload` - Reload from file
• `/leveling_config reset` - Reset to defaults

**Examples:**
• `/leveling_config get xp_rates.message`
• `/leveling_config set xp_rates.message 2`
• `/leveling_config toggle notifications.enabled`
• `/leveling_config toggle rate_limiting.enabled`

**Common Settings:**
• `enabled` - Enable/disable entire system
• `xp_rates.message` - XP per message
• `xp_rates.link` - XP per link
• `xp_rates.thanks` - XP per thanks
• `level_formula.base_xp` - Base XP for levels
• `level_formula.multiplier` - Level multiplier
• `notifications.enabled` - Enable notifications
• `rate_limiting.enabled` - Enable rate limiting
• `cache.enabled` - Enable caching"""

    await update.message.reply_text(help_text, parse_mode='Markdown')


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get a nested value from a dictionary using dot notation."""
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    
    return current


def _create_nested_update(path: str, value: Any) -> Dict[str, Any]:
    """Create a nested update dictionary from a dot-separated path."""
    keys = path.split('.')
    result = {}
    current = result
    
    for i, key in enumerate(keys):
        if i == len(keys) - 1:
            current[key] = value
        else:
            current[key] = {}
            current = current[key]
    
    return result


def _parse_value(value_str: str) -> Any:
    """Parse a string value to appropriate Python type."""
    # Try boolean
    if value_str.lower() in ('true', 'yes', '1', 'on', 'enabled'):
        return True
    elif value_str.lower() in ('false', 'no', '0', 'off', 'disabled'):
        return False
    
    # Try integer
    try:
        return int(value_str)
    except ValueError:
        pass
    
    # Try float
    try:
        return float(value_str)
    except ValueError:
        pass
    
    # Return as string
    return value_str


# Command registration information
LEVELING_CONFIG_COMMAND = CommandInfo(
    name="leveling_config",
    description="Manage leveling system configuration",
    category=CommandCategory.ADMIN,
    handler_func=leveling_config_command,
    usage="/leveling_config [action] [parameters]",
    examples=[
        "/leveling_config",
        "/leveling_config get xp_rates.message",
        "/leveling_config set xp_rates.message 2",
        "/leveling_config toggle notifications.enabled"
    ],
    admin_only=True
)