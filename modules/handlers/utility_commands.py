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


async def _find_user_by_username(username: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, str]:
    """
    Find a user by username in the chat.
    
    Args:
        username: Username to search for (without @)
        chat_id: Chat ID to search in
        context: Bot context
        
    Returns:
        Tuple of (user_id, display_name) or (None, None) if not found
    """
    try:
        # Get database service
        service_registry = context.bot_data.get('service_registry')
        if not service_registry:
            return None, None
        
        # Try to get user from database by username
        from modules.database import Database
        
        # Query users table for username and check if they have leveling data in this chat
        query = """
            SELECT u.user_id, u.username, u.first_name, u.last_name 
            FROM users u
            INNER JOIN user_chat_stats us ON u.user_id = us.user_id
            WHERE LOWER(u.username) = LOWER($1) AND us.chat_id = $2
        """
        
        manager = Database.get_connection_manager()
        async with manager.get_connection() as conn:
            result = await conn.fetchrow(query, username, chat_id)
        
        if result:
            user_id = result['user_id']
            display_name = result['username'] or result['first_name'] or f"User {user_id}"
            return user_id, display_name
        
        return None, None
        
    except Exception as e:
        logger.error(f"Error finding user by username {username}: {e}", exc_info=True)
        return None, None


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
        
        # Check if user wants to view another user's profile
        if context.args and len(context.args) > 0:
            username_arg = context.args[0]
            
            # Remove @ if present
            if username_arg.startswith('@'):
                username_arg = username_arg[1:]
            
            # Try to find user by username in the chat
            target_user_id, target_username = await _find_user_by_username(
                username_arg, update.effective_chat.id, context
            )
            
            if not target_user_id:
                await update.message.reply_text(
                    f"❌ User @{username_arg} not found in this chat or has no leveling data."
                )
                return
        
        # Get user profile
        chat_id = update.effective_chat.id
        profile = await leveling_service.get_user_profile(target_user_id, chat_id)
        
        if not profile:
            if target_user_id == update.message.from_user.id:
                await update.message.reply_text(
                    "📊 No leveling data found. Send some messages to start earning XP!"
                )
            else:
                await update.message.reply_text(
                    f"📊 No leveling data found for {target_username}."
                )
            return
        
        # Format profile message using HTML parse mode to avoid Markdown issues
        profile_text = f"📊 <b>Profile for {target_username}</b>\n\n"
        profile_text += f"🏆 <b>Level:</b> {profile.level}\n"
        profile_text += f"⭐ <b>XP:</b> {profile.xp:,}\n"
        profile_text += f"📈 <b>Progress:</b> {profile.progress_percentage:.1f}% to Level {profile.level + 1}\n"
        profile_text += f"🎯 <b>Next Level:</b> {profile.next_level_xp:,} XP\n\n"
        
        # Activity stats
        profile_text += "📈 <b>Activity Stats:</b>\n"
        profile_text += f"💬 Messages: {profile.stats.get('messages_count', 0):,}\n"
        profile_text += f"🔗 Links shared: {profile.stats.get('links_shared', 0):,}\n"
        profile_text += f"🙏 Thanks received: {profile.stats.get('thanks_received', 0):,}\n\n"
        
        # Achievements
        if profile.achievements:
            profile_text += f"🏆 <b>Achievements ({len(profile.achievements)}):</b>\n"
            # Show achievements with both emoji and title
            for i, ach in enumerate(profile.achievements[:5]):  # Show first 5 with names
                profile_text += f"{ach.emoji} {ach.title}\n"
            
            # If more than 5, show remaining as emojis only
            if len(profile.achievements) > 5:
                remaining_emojis = [ach.emoji for ach in profile.achievements[5:10]]
                if remaining_emojis:
                    profile_text += " ".join(remaining_emojis)
                if len(profile.achievements) > 10:
                    profile_text += f" +{len(profile.achievements) - 10} more"
        else:
            profile_text += "🏆 <b>Achievements:</b> None yet - keep chatting to unlock some!"
        
        await update.message.reply_text(profile_text, parse_mode='HTML')
        
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
        
        # Format leaderboard message using HTML to avoid Markdown parsing issues
        leaderboard_text = f"🏆 <b>Chat Leaderboard (Top {len(leaderboard)})</b>\n\n"
        
        for profile in leaderboard:
            rank_emoji = "🥇" if profile.rank == 1 else "🥈" if profile.rank == 2 else "🥉" if profile.rank == 3 else f"{profile.rank}."
            username = profile.username or f"User {profile.user_id}"
            
            # Escape HTML characters in username
            import html
            username_escaped = html.escape(username)
            
            leaderboard_text += f"{rank_emoji} <b>{username_escaped}</b>\n"
            leaderboard_text += f"   Level {profile.level} • {profile.xp:,} XP\n"
            
            # Show top achievements for top 3
            if profile.rank <= 3 and profile.achievements:
                top_achievements = [ach.emoji for ach in profile.achievements[:3]]
                leaderboard_text += f"   {' '.join(top_achievements)}\n"
            
            leaderboard_text += "\n"
        
        await update.message.reply_text(leaderboard_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}", exc_info=True)
        await update.message.reply_text("❌ Error retrieving leaderboard. Please try again later.")