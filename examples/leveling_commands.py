"""
Example command handlers for the leveling system.

This module shows how to implement /profile and /leaderboard commands
that integrate with the UserLevelingService.
"""

from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /profile command to show user stats and achievements.
    
    Usage: /profile [@username]
    """
    if not update.message or not update.effective_chat:
        return
    
    try:
        # Get the leveling service
        service_registry = context.bot_data.get('service_registry')
        if not service_registry:
            await update.message.reply_text("❌ Leveling system not available")
            return
        
        leveling_service = service_registry.get_service('user_leveling_service')
        if not leveling_service or not leveling_service.is_enabled():
            await update.message.reply_text("❌ Leveling system is disabled")
            return
        
        # Determine which user to show profile for
        target_user_id = update.message.from_user.id
        target_username = update.message.from_user.username or update.message.from_user.first_name
        
        # Check if a username was mentioned
        if context.args and len(context.args) > 0:
            mentioned_username = context.args[0].lstrip('@')
            # In a real implementation, you'd need to resolve the username to user_id
            # For this example, we'll just show the current user's profile
            await update.message.reply_text(
                f"🔍 Looking up profile for @{mentioned_username}...\n"
                f"(Username lookup not implemented in this example)"
            )
            return
        
        # Get user profile
        profile = await leveling_service.get_user_profile(
            user_id=target_user_id,
            chat_id=update.effective_chat.id
        )
        
        if not profile:
            await update.message.reply_text(
                "📊 No profile found!\n"
                "Send some messages to start earning XP! 🚀"
            )
            return
        
        # Format profile message
        message_lines = [
            f"👤 **Profile for {target_username}**",
            "",
            f"🏆 **Level:** {profile.level}",
            f"⭐ **XP:** {profile.xp:,}",
            f"📈 **Progress:** {profile.progress_percentage:.1f}% to Level {profile.level + 1}",
            f"🎯 **Next Level:** {profile.next_level_xp:,} XP",
            "",
            "📊 **Activity Stats:**",
            f"💬 Messages: {profile.stats['messages_count']:,}",
            f"🔗 Links shared: {profile.stats['links_shared']:,}",
            f"🙏 Thanks received: {profile.stats['thanks_received']:,}",
        ]
        
        # Add achievements
        if profile.achievements:
            message_lines.extend([
                "",
                f"🏅 **Achievements ({len(profile.achievements)}):**"
            ])
            
            # Group achievements by category for better display
            achievement_text = ""
            for achievement in profile.achievements[:10]:  # Show first 10
                achievement_text += f"{achievement.emoji} "
            
            if achievement_text:
                message_lines.append(achievement_text)
            
            if len(profile.achievements) > 10:
                message_lines.append(f"... and {len(profile.achievements) - 10} more!")
        else:
            message_lines.extend([
                "",
                "🏅 **Achievements:** None yet",
                "Keep being active to unlock achievements! 🎯"
            ])
        
        # Add rank if available
        if hasattr(profile, 'rank') and profile.rank:
            message_lines.insert(4, f"🥇 **Rank:** #{profile.rank}")
        
        profile_text = "\n".join(message_lines)
        await update.message.reply_text(profile_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Error retrieving profile. Please try again later."
        )
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in profile command: {e}", exc_info=True)


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /leaderboard command to show chat rankings.
    
    Usage: /leaderboard [limit]
    """
    if not update.message or not update.effective_chat:
        return
    
    try:
        # Get the leveling service
        service_registry = context.bot_data.get('service_registry')
        if not service_registry:
            await update.message.reply_text("❌ Leveling system not available")
            return
        
        leveling_service = service_registry.get_service('user_leveling_service')
        if not leveling_service or not leveling_service.is_enabled():
            await update.message.reply_text("❌ Leveling system is disabled")
            return
        
        # Parse limit argument
        limit = 10  # Default limit
        if context.args and len(context.args) > 0:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 50))  # Clamp between 1 and 50
            except ValueError:
                await update.message.reply_text("❌ Invalid limit. Please use a number between 1 and 50.")
                return
        
        # Get leaderboard
        leaderboard = await leveling_service.get_leaderboard(
            chat_id=update.effective_chat.id,
            limit=limit
        )
        
        if not leaderboard:
            await update.message.reply_text(
                "📊 No users found in this chat!\n"
                "Start chatting to appear on the leaderboard! 🚀"
            )
            return
        
        # Format leaderboard message
        message_lines = [
            f"🏆 **Chat Leaderboard (Top {len(leaderboard)})**",
            ""
        ]
        
        # Add each user to the leaderboard
        for profile in leaderboard:
            rank_emoji = "🥇" if profile.rank == 1 else "🥈" if profile.rank == 2 else "🥉" if profile.rank == 3 else "🏅"
            
            # In a real implementation, you'd resolve user_id to username
            username = f"User {profile.user_id}"  # Placeholder
            
            message_lines.append(
                f"{rank_emoji} **#{profile.rank}** {username}\n"
                f"    Level {profile.level} • {profile.xp:,} XP • {len(profile.achievements)} achievements"
            )
        
        leaderboard_text = "\n".join(message_lines)
        await update.message.reply_text(leaderboard_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Error retrieving leaderboard. Please try again later."
        )
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in leaderboard command: {e}", exc_info=True)


async def level_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /levelstats command to show leveling system statistics.
    
    This is an admin/debug command to show service statistics.
    """
    if not update.message or not update.effective_chat:
        return
    
    try:
        # Get the leveling service
        service_registry = context.bot_data.get('service_registry')
        if not service_registry:
            await update.message.reply_text("❌ Leveling system not available")
            return
        
        leveling_service = service_registry.get_service('user_leveling_service')
        if not leveling_service:
            await update.message.reply_text("❌ Leveling service not found")
            return
        
        # Get service statistics
        stats = leveling_service.get_service_stats()
        
        message_lines = [
            "📊 **Leveling System Statistics**",
            "",
            f"🔧 **Status:** {'✅ Enabled' if stats['enabled'] else '❌ Disabled'}",
            f"🚀 **Initialized:** {'✅ Yes' if stats['initialized'] else '❌ No'}",
            "",
            "📈 **Activity Stats:**",
            f"💬 Messages processed: {stats['stats']['messages_processed']:,}",
            f"⭐ XP awarded: {stats['stats']['xp_awarded']:,}",
            f"📈 Levels gained: {stats['stats']['levels_gained']:,}",
            f"🏆 Achievements unlocked: {stats['stats']['achievements_unlocked']:,}",
            f"❌ Errors: {stats['stats']['errors']:,}",
            "",
            "⚙️ **Configuration:**",
            f"Base XP: {stats['config'].get('level_base_xp', 'N/A')}",
            f"Level multiplier: {stats['config'].get('level_multiplier', 'N/A')}",
            f"Notifications: {'✅' if stats['config'].get('notifications_enabled', True) else '❌'}",
        ]
        
        stats_text = "\n".join(message_lines)
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Error retrieving statistics. Please try again later."
        )
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in level stats command: {e}", exc_info=True)


def register_leveling_commands(command_registry):
    """
    Register leveling system commands with the command registry.
    
    Args:
        command_registry: The CommandRegistry instance
    """
    from modules.command_registry import CommandInfo, CommandCategory
    
    # Register /profile command
    command_registry.register_command(CommandInfo(
        name="profile",
        description="Show your level, XP, and achievements",
        category=CommandCategory.UTILITY,
        handler_func=profile_command,
        usage="/profile [@username]",
        examples=["/profile", "/profile @john"],
        aliases=["stats", "me"]
    ))
    
    # Register /leaderboard command
    command_registry.register_command(CommandInfo(
        name="leaderboard",
        description="Show chat leaderboard",
        category=CommandCategory.UTILITY,
        handler_func=leaderboard_command,
        usage="/leaderboard [limit]",
        examples=["/leaderboard", "/leaderboard 20"],
        aliases=["top", "rank", "lb"]
    ))
    
    # Register /levelstats command (admin/debug)
    command_registry.register_command(CommandInfo(
        name="levelstats",
        description="Show leveling system statistics",
        category=CommandCategory.ADMIN,
        handler_func=level_stats_command,
        usage="/levelstats",
        examples=["/levelstats"],
        aliases=["leveling_stats"]
    ))
    
    print("Leveling system commands registered successfully")