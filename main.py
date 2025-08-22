"""
Main entry point for the PsychoChauffeur Telegram bot.
Refactored to use ApplicationBootstrapper for clean architecture.
"""

import asyncio
import logging
import os
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
        logger.info("Bot stopped by user interrupt (KeyboardInterrupt)")
        # Set shutdown event in case signal handler didn't catch it
        if hasattr(app_bootstrapper, '_shutdown_event') and not app_bootstrapper._shutdown_event.is_set():
            app_bootstrapper._shutdown_event.set()
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
        finally:
            # Final cleanup: cancel any remaining tasks
            try:
                current_task = asyncio.current_task()
                remaining_tasks = [task for task in asyncio.all_tasks() if task != current_task and not task.done()]
                
                if remaining_tasks:
                    logger.info(f"Cancelling {len(remaining_tasks)} remaining tasks...")
                    for task in remaining_tasks:
                        task.cancel()
                    
                    # Brief wait for cancellation, then exit regardless
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*remaining_tasks, return_exceptions=True),
                            timeout=0.5
                        )
                        logger.info("All remaining tasks cancelled successfully")
                    except asyncio.TimeoutError:
                        logger.warning("Some tasks didn't cancel in time, exiting anyway...")
                else:
                    logger.info("No remaining tasks to cancel")
            except Exception as cleanup_error:
                logger.error(f"Error during final cleanup: {cleanup_error}")
            
            logger.info("Final shutdown completed!")


def run_bot() -> None:
    """Run the bot with proper event loop handling."""
    import threading
    import time
    
    # Set up a watchdog timer that will force exit if shutdown hangs
    shutdown_started = threading.Event()
    
    def force_exit_watchdog() -> None:
        """Force exit if shutdown takes too long."""
        if shutdown_started.wait(timeout=30):  # Wait for shutdown to start
            time.sleep(2)  # Give 2 seconds for graceful shutdown
            logger.warning("Shutdown taking too long, forcing exit...")
            os._exit(0)
    
    watchdog = threading.Thread(target=force_exit_watchdog, daemon=True)
    watchdog.start()
    
    try:
        # Run the main application
        asyncio.run(main())
    except (SystemExit, KeyboardInterrupt):
        logger.info("Bot stopped by user or system signal")
        shutdown_started.set()  # Signal that shutdown has started
    except Exception as e:
        error_logger.error(f"Bot stopped due to an unhandled exception: {e}", exc_info=True)
        shutdown_started.set()
        sys.exit(1)
    finally:
        shutdown_started.set()
        logger.info("Bot run finished")
        # Give a brief moment for final cleanup, then force exit
        time.sleep(0.1)
        os._exit(0)


if __name__ == "__main__":
    run_bot()