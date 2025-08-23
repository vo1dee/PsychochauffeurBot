"""
Example integration of UserLevelingService with the message handler.

This example shows how to integrate the leveling service with the existing
message processing pipeline.
"""

from telegram import Update
from telegram.ext import ContextTypes
from modules.logger import error_logger, general_logger


async def handle_message_logging_with_leveling(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced message handler that includes leveling system processing.
    
    This is an example of how to integrate the UserLevelingService with
    the existing message processing pipeline.
    """
    try:
        # Log that we received a message
        if update.effective_chat:
            general_logger.info(f"Received message in chat {update.effective_chat.id}")
        else:
            general_logger.info("Received message in unknown chat")
        
        # Stream message to log file first - this handles ALL message types
        from modules.chat_streamer import chat_streamer
        await chat_streamer.stream_message(update, context)
        general_logger.info("Message streamed to log file")
        
        # --- LEVELING SYSTEM INTEGRATION ---
        # Process message for XP and achievements
        try:
            # Get the leveling service from the service registry
            service_registry = context.bot_data.get('service_registry')
            if service_registry:
                leveling_service = service_registry.get_service('user_leveling_service')
                if leveling_service:
                    await leveling_service.process_message(update, context)
        except Exception as e:
            error_logger.error(f"Error in leveling system: {e}")
            # Don't interrupt normal message processing
        # --- END LEVELING SYSTEM INTEGRATION ---
        
        # Only save to database if it's a text message, bot reply, or has image description
        if update.message:
            should_save = (
                update.message.text or  # Text message
                update.message.caption or  # Image/video caption
                (update.message.from_user and update.message.from_user.is_bot)  # Bot's reply
            )
            
            # ... rest of existing message processing logic ...
            
            if should_save:
                general_logger.info(f"Attempting to save message: {update.message.text!r}")
                from modules.database import Database
                await Database.save_message(update.message)
                general_logger.info("Message saved to database")
            
    except Exception as e:
        # Log the error but don't interrupt the bot's operation
        error_logger.error(f"Error processing message: {str(e)}", exc_info=True)


def setup_leveling_service_integration(application, service_registry):
    """
    Example of how to set up the leveling service integration.
    
    This function shows how to register the UserLevelingService with the
    service registry and integrate it with the bot application.
    
    Args:
        application: The Telegram bot application
        service_registry: The service registry instance
    """
    
    # Register the UserLevelingService with the service registry
    from modules.user_leveling_service import UserLevelingService
    
    service_registry.register_singleton(
        'user_leveling_service',
        UserLevelingService,
        dependencies=['config_manager']  # Depends on config manager
    )
    
    # The service will be automatically initialized when the service registry
    # initializes all services during bot startup
    
    # Store service registry in bot_data for access in handlers
    application.bot_data['service_registry'] = service_registry
    
    print("UserLevelingService integration configured successfully")


# Example of how to use the service directly
async def example_direct_service_usage():
    """
    Example of how to use the UserLevelingService directly.
    
    This shows how to get user profiles and leaderboards programmatically.
    """
    from modules.user_leveling_service import UserLevelingService
    from config.config_manager import ConfigManager
    
    # Create and initialize the service
    config_manager = ConfigManager()
    leveling_service = UserLevelingService(config_manager)
    
    try:
        await leveling_service.initialize()
        
        # Get a user's profile
        user_profile = await leveling_service.get_user_profile(
            user_id=12345, 
            chat_id=67890
        )
        
        if user_profile:
            print(f"User Level: {user_profile.level}")
            print(f"User XP: {user_profile.xp}")
            print(f"Achievements: {len(user_profile.achievements)}")
            print(f"Messages: {user_profile.stats['messages_count']}")
        
        # Get chat leaderboard
        leaderboard = await leveling_service.get_leaderboard(
            chat_id=67890,
            limit=10
        )
        
        print(f"Top {len(leaderboard)} users:")
        for profile in leaderboard:
            print(f"  Rank {profile.rank}: Level {profile.level} ({profile.xp} XP)")
        
        # Get service statistics
        stats = leveling_service.get_service_stats()
        print(f"Service stats: {stats}")
        
    finally:
        await leveling_service.shutdown()


if __name__ == "__main__":
    import asyncio
    
    # Run the example
    asyncio.run(example_direct_service_usage())