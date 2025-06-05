"""
Main entry point for the PsychoChauffeur Telegram bot.
Handles message processing, command registration, and bot initialization.
"""

# Standard library imports
import asyncio
import os
import signal
import sys
from datetime import datetime

# Third-party imports
import nest_asyncio
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler, ContextTypes, Application
)

# Local module imports
from modules.keyboards import create_link_keyboard, button_callback
from modules.utils import (
    ScreenshotManager, MessageCounter, screenshot_command, cat_command,
    init_directories
)
from modules.image_downloader import ImageDownloader
from modules.const import (
    TOKEN, OPENAI_API_KEY, KYIV_TZ, ALIEXPRESS_STICKER_ID,
    VideoPlatforms, LinkModification, Config
)
from modules.gpt import (
    ask_gpt_command, analyze_command, answer_from_gpt, handle_photo_analysis,
    gpt_response, mystats_command
)
from modules.weather import WeatherCommandHandler
from modules.logger import (
    TelegramErrorHandler,
    general_logger, chat_logger, error_logger,
    init_telegram_error_handler, shutdown_logging
)
from modules.user_management import restrict_user
from modules.video_downloader import setup_video_handlers
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity
from modules.geomagnetic import GeomagneticCommandHandler
from modules.reminders.reminders import ReminderManager
from modules.error_analytics import error_report_command, error_tracker
from config.config_manager import ConfigManager
from modules.safety import safety_manager
from modules.url_processor import (
    sanitize_url, shorten_url, extract_urls,
    is_modified_domain, modify_url
)
from modules.message_processor import (
    needs_gpt_response, update_message_history,
    get_previous_message, process_message_content,
    should_restrict_user
)
from modules.keyboard_translator import translate_text, keyboard_mapping
from modules.database import Database
from modules.message_handler import setup_message_handlers, handle_gpt_reply
from modules.chat_streamer import chat_streamer

# Apply nest_asyncio at the very beginning, as it's crucial for the event loop.
nest_asyncio.apply()

# Initialize global objects
message_counter = MessageCounter()
reminder_manager = ReminderManager()
config_manager = ConfigManager()

# --- Command Handlers ---
@handle_errors(feedback_message="An error occurred in /start command.")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    welcome_text = (
        "🤖 PsychoChauffeur Bot\n\n"
        "🎥 Video Downloads from:\n"
        "• TikTok\n• Instagram\n• YouTube Shorts\n"
        "• Facebook\n• Twitter\n• Vimeo\n• Reddit\n• Twitch\n"
        "🔗 Link Processing:\n"
        "• AliExpress link optimization\n"
        "• Link modification for restricted domains\n\n"
        "🤖 Additional Features:\n"
        "• GPT responses\n"
        "• Weather updates -- /weather [city]\n"
        "• Solar flares screenshot -- /flares\n"
        "• Geomagnetic activity -- /gm\n"
        "• Random cat photos -- /cat \n\n"
        "• Reminders -- /remind\n\n"
        "❓ Questions or issues?\n"
        "Contact @vo1dee"
    )
    await update.message.reply_text(welcome_text)
    general_logger.info(f"Handled /start command for user {update.effective_user.id}")

@handle_errors(feedback_message="An error occurred while translating the last message.")
async def translate_last_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the keyboard layout translation command."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "User"
    previous_message = get_previous_message(user_id)
    
    if not previous_message:
        await update.message.reply_text("No previous message found to convert.")
        return
        
    converted_text = translate_text(previous_message)
    response_text = f"@{username} хотів сказати: {converted_text}"
    await update.message.reply_text(response_text)

@handle_errors(feedback_message="An error occurred while processing your message.")
async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming non-command text messages."""
    if not update.message or not update.message.text:
        return
        
    message_text = update.message.text
    
    # Safeguard: Explicitly ignore commands to prevent interference with CommandHandlers
    if message_text.startswith('/'):
        return
        
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    
    # Update message history
    update_message_history(user_id, message_text)
    
    # Check for user restrictions
    if should_restrict_user(message_text):
        await restrict_user(update, context)
        return
        
    # Process message content and extract URLs
    cleaned_text, modified_links = process_message_content(message_text)
    
    # Check for GPT response
    needs_response, response_type = needs_gpt_response(update, context, message_text)
    if needs_response:
        await gpt_response(update, context, response_type=response_type, message_text_override=cleaned_text)
        return
        
    # Handle modified links if any were found
    if modified_links:
        await process_urls(update, context, modified_links, cleaned_text)

@handle_errors(feedback_message="An error occurred while processing your links.")
async def process_urls(update: Update, context: CallbackContext, urls: list[str], message_text: str) -> None:
    """Process URLs in the message."""
    chat_id = update.effective_chat.id
    username = update.message.from_user.username or f"ID:{update.message.from_user.id}"
    
    if urls:
        await construct_and_send_message(chat_id, username, message_text, urls, update, context)

@handle_errors(feedback_message="An error occurred while constructing the message.")
async def construct_and_send_message(
    chat_id: int,
    username: str,
    cleaned_message_text: str,
    modified_links: list[str],
    update: Update,
    context: CallbackContext
) -> None:
    """Construct and send a message with modified links."""
    try:
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        escaped_username = username
        for char in special_chars:
            escaped_username = escaped_username.replace(char, f'\\{char}')
        escaped_text = cleaned_message_text
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        escaped_links = []
        for url in modified_links:
            escaped_url = url
            for char in special_chars:
                escaped_url = escaped_url.replace(char, f'\\{char}')
            escaped_links.append(escaped_url)
        message = f"@{escaped_username} хотів відправити:\n{escaped_text}"
        keyboard = create_link_keyboard(escaped_links, context)
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        error_logger.error(f"Failed to send message: {str(e)}", exc_info=True)
        raise

@handle_errors(feedback_message="An error occurred while handling sticker.")
async def handle_sticker(update: Update, context: CallbackContext) -> None:
    """Handle sticker messages."""
    if not update.message or not update.message.sticker:
        return
    sticker = update.message.sticker
    if sticker.file_unique_id == ALIEXPRESS_STICKER_ID:
        await update.message.reply_text(
            "🔗 *AliExpress Link Detected*\n\nPlease send the product link and I'll optimize it for you\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )

@handle_errors(feedback_message="An error occurred in /ping command.")
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ping command."""
    await update.message.reply_text("Pong! 🏓")
    general_logger.info(f"Handled /ping command for user {update.effective_user.id}")

def register_handlers(application: Application, bot: Bot, config_manager: ConfigManager) -> None:
    """Register all command and message handlers in the correct order."""
    
    # Group 0: General logger for all messages (non-blocking).
    # This runs first but allows other handlers to proceed.
    setup_message_handlers(application)

    # Group 0: Command Handlers. These will be checked next.
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("cat", cat_command))
    application.add_handler(CommandHandler("error_report", error_report_command))
    application.add_handler(CommandHandler("ask", ask_gpt_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    application.add_handler(CommandHandler("weather", WeatherCommandHandler()))
    application.add_handler(CommandHandler("flares", screenshot_command))
    application.add_handler(CommandHandler("gm", GeomagneticCommandHandler()))
    application.add_handler(CommandHandler("remind", reminder_manager.remind))
    
    # Group 0: Other specific message handlers.
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_analysis))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))

    # Group 0: General text message handler for non-command messages.
    # It has a filter to specifically ignore commands.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Group 0: Callback query handler for buttons.
    application.add_handler(CallbackQueryHandler(button_callback))

    # Group 1: Video handlers. These have a higher group number so they are checked
    # after all of the default group 0 handlers.
    setup_video_handlers(application, extract_urls_func=extract_urls)
    general_logger.info("All handlers registered.")

async def initialize_all_components():
    """Initialize all bot components in the correct order."""
    try:
        init_directories()
        await Database.initialize()
        await init_telegram_error_handler(TOKEN, Config.ERROR_CHANNEL_ID)
        await config_manager.initialize()
        await reminder_manager.initialize()
        await safety_manager.initialize()
        general_logger.info("All components initialized successfully.")
    except Exception as e:
        error_logger.error(f"Failed to initialize components: {str(e)}", exc_info=True)
        raise

async def cleanup_all_components():
    """Cleanup all bot components in reverse order of initialization."""
    general_logger.info("Cleaning up all components...")
    try:
        if hasattr(safety_manager, 'stop'):
            await safety_manager.stop()
        if hasattr(reminder_manager, 'stop'):
            await reminder_manager.stop()
        if hasattr(config_manager, 'stop'):
            await config_manager.stop()
        if hasattr(Database, 'close'):
            await Database.close()
        await shutdown_logging()
        general_logger.info("All components cleaned up successfully.")
    except Exception as e:
        error_logger.error(f"Error during component cleanup: {e}", exc_info=True)

def handle_shutdown_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    general_logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    # This will cause the asyncio event loop to stop.
    # The 'finally' block in run_bot will then handle cleanup.
    raise SystemExit("Shutdown signal received.")

async def main():
    """Main bot initialization and run loop."""
    application = None
    try:
        await initialize_all_components()
        application = (
            ApplicationBuilder()
            .token(TOKEN)
            .connection_pool_size(32)
            .connect_timeout(60.0)
            .read_timeout(60.0)
            .write_timeout(60.0)
            .pool_timeout(60.0)
            .get_updates_connection_pool_size(32)
            .get_updates_read_timeout(60.0)
            .build()
        )
        register_handlers(application, application.bot, config_manager)
        general_logger.info("Bot polling started.")
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False,
            stop_signals=None  # We handle signals in run_bot
        )
    except (SystemExit, KeyboardInterrupt):
        general_logger.info("Bot shutdown requested.")
    except Exception as e:
        error_logger.error(f"Bot execution failed: {str(e)}", exc_info=True)
        raise
    finally:
        general_logger.info("Starting final cleanup...")
        if application and application.running:
             await application.stop()
             await application.shutdown()
        await cleanup_all_components()

def run_bot():
    """Run the bot with proper event loop handling and graceful shutdown."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    loop = None
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
             # This can happen with nest_asyncio. We just run the main coroutine.
             main_task = loop.create_task(main())
             loop.run_until_complete(main_task)
        else:
             loop.run_until_complete(main())
    except (SystemExit, KeyboardInterrupt):
        general_logger.info("Bot stopped by user or system signal.")
    except Exception as e:
        error_logger.error(f"Bot stopped due to an unhandled exception: {e}", exc_info=True)
    finally:
        general_logger.info("Bot run finished.")
        # The loop and tasks should be handled by run_until_complete and graceful shutdown logic.

if __name__ == "__main__":
    run_bot()