"""
Main entry point for the PsychoChauffeur Telegram bot.
Refactored to use ApplicationBootstrapper for clean architecture.
"""

import asyncio
import logging
import sys

# Apply nest_asyncio at the very beginning for event loop compatibility
import nest_asyncio
nest_asyncio.apply()

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.logger import error_logger
from modules.const import Config

logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialize and run the bot application using ApplicationBootstrapper."""
    # Validate configuration
    if not Config.TELEGRAM_BOT_TOKEN:
        error_logger.critical("TELEGRAM_BOT_TOKEN is not set. The bot cannot start.")
        return
    
    # Create and start the application bootstrapper
    app_bootstrapper = ApplicationBootstrapper()
    
    try:
        # Start the application (includes service configuration and signal handling)
        await app_bootstrapper.start_application()
        
        # Wait for shutdown signal
        logger.info("Bot started successfully. Press Ctrl+C to stop.")
        await app_bootstrapper.wait_for_shutdown()
        
        logger.info("Shutdown signal received, stopping bot...")
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user interrupt")
    except Exception as e:
        error_logger.error(f"Bot stopped due to an unhandled exception: {e}", exc_info=True)
        raise
    finally:
        try:
            # Perform graceful shutdown
            if app_bootstrapper.is_running:
                logger.info("Performing graceful shutdown...")
                await app_bootstrapper.shutdown_application()
                logger.info("Bot shutdown completed successfully")
            else:
                logger.info("Bot was already shut down")
        except Exception as shutdown_error:
            logger.error(f"Error during shutdown: {shutdown_error}")
            # Force exit if shutdown fails
            sys.exit(1)


def run_bot() -> None:
    """Run the bot with proper event loop handling."""
    try:
        # Run the main application
        asyncio.run(main())
    except (SystemExit, KeyboardInterrupt):
        logger.info("Bot stopped by user or system signal")
    except Exception as e:
        error_logger.error(f"Bot stopped due to an unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot run finished")


if __name__ == "__main__":
    run_bot()