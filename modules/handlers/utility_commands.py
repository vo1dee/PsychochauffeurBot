"""
Utility command handlers.

Contains handlers for utility commands like cat, screenshot, count, etc.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import existing utility functions
from modules.utils import cat_command as _cat, screenshot_command as _screenshot
from modules.count_command import count_command as _count, missing_command as _missing
from modules.error_analytics import error_report_command as _error_report

logger = logging.getLogger(__name__)


async def cat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cat command for random cat photos."""
    await _cat(update, context)


async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /flares command for solar flares screenshot."""
    await _screenshot(update, context)


async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /count command for message counting."""
    await _count(update, context)


async def missing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /missing command for missing features."""
    await _missing(update, context)


async def error_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /error_report command for error reporting."""
    await _error_report(update, context)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /profile command for user leveling stats."""
    try:
        # Get service registry from bot_data
        service_registry = context.bot_data.get('service_registry')
        if not service_registry:
            await update.message.reply_text("❌ Leveling system is not available.")
            return
        
        # Get leveling service
        try:
            leveling_service = service_registry.get_service('user_leveling_service')
        except (ValueError, KeyError):
            await update.message.reply_text("❌ Leveling system is not available.")
            return
        
        if not leveling_service or not leveling_service.is_enabled():
            await update.message.reply_text("❌ Leveling system is disabled.")
            return
        
        # Determine target user
        target_user_id = update.message.from_user.id
        target_username = update.message.from_user.username or update.message.from_user.first_name
        
        # Check if user mentioned another user
        if context.args and len(context.args) > 0:
            # For now, only show own profile (can be extended later)
            await update.message.reply_text("🔒 You can only view your own profile for now.")
            return
        
        # Get user profile
        chat_id = update.effective_chat.id
        profile = await leveling_service.get_user_profile(target_user_id, chat_id)
        
        if not profile:
            await update.message.reply_text(
                "📊 No leveling data found. Send some messages to start earning XP!"
            )
            return
        
        # Format profile message
        profile_text = f"📊 **Profile for {target_username}**\n\n"
        profile_text += f"🏆 **Level:** {profile.level}\n"
        profile_text += f"⭐ **XP:** {profile.xp:,}\n"
        profile_text += f"📈 **Progress:** {profile.progress_percentage:.1f}% to Level {profile.level + 1}\n"
        profile_text += f"🎯 **Next Level:** {profile.next_level_xp:,} XP\n\n"
        
        # Activity stats
        profile_text += "📈 **Activity Stats:**\n"
        profile_text += f"💬 Messages: {profile.stats.get('messages_count', 0):,}\n"
        profile_text += f"🔗 Links shared: {profile.stats.get('links_shared', 0):,}\n"
        profile_text += f"🙏 Thanks received: {profile.stats.get('thanks_received', 0):,}\n\n"
        
        # Achievements
        if profile.achievements:
            profile_text += f"🏆 **Achievements ({len(profile.achievements)}):**\n"
            achievement_emojis = [ach.emoji for ach in profile.achievements[:10]]  # Show first 10
            profile_text += " ".join(achievement_emojis)
            if len(profile.achievements) > 10:
                profile_text += f" +{len(profile.achievements) - 10} more"
        else:
            profile_text += "🏆 **Achievements:** None yet - keep chatting to unlock some!"
        
        await update.message.reply_text(profile_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in profile command: {e}", exc_info=True)
        await update.message.reply_text("❌ Error retrieving profile. Please try again later.")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /leaderboard command for chat rankings."""
    try:
        # Get service registry from bot_data
        service_registry = context.bot_data.get('service_registry')
        if not service_registry:
            await update.message.reply_text("❌ Leveling system is not available.")
            return
        
        # Get leveling service
        try:
            leveling_service = service_registry.get_service('user_leveling_service')
        except (ValueError, KeyError):
            await update.message.reply_text("❌ Leveling system is not available.")
            return
        
        if not leveling_service or not leveling_service.is_enabled():
            await update.message.reply_text("❌ Leveling system is disabled.")
            return
        
        # Parse limit from arguments
        limit = 10  # Default limit
        if context.args and len(context.args) > 0:
            try:
                limit = min(int(context.args[0]), 20)  # Max 20 users
            except ValueError:
                await update.message.reply_text("❌ Invalid limit. Please use a number (max 20).")
                return
        
        # Get leaderboard
        chat_id = update.effective_chat.id
        leaderboard = await leveling_service.get_leaderboard(chat_id, limit)
        
        if not leaderboard:
            await update.message.reply_text("📊 No leaderboard data available yet.")
            return
        
        # Format leaderboard message
        leaderboard_text = f"🏆 **Chat Leaderboard (Top {len(leaderboard)})**\n\n"
        
        for profile in leaderboard:
            rank_emoji = "🥇" if profile.rank == 1 else "🥈" if profile.rank == 2 else "🥉" if profile.rank == 3 else f"{profile.rank}."
            username = profile.username or f"User {profile.user_id}"
            
            leaderboard_text += f"{rank_emoji} **{username}**\n"
            leaderboard_text += f"   Level {profile.level} • {profile.xp:,} XP\n"
            
            # Show top achievements for top 3
            if profile.rank <= 3 and profile.achievements:
                top_achievements = [ach.emoji for ach in profile.achievements[:3]]
                leaderboard_text += f"   {' '.join(top_achievements)}\n"
            
            leaderboard_text += "\n"
        
        await update.message.reply_text(leaderboard_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}", exc_info=True)
        await update.message.reply_text("❌ Error retrieving leaderboard. Please try again later.")