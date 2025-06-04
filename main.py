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
    ask_gpt_command, analyze_command, answer_from_gpt, analyze_image,
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

# Apply nest_asyncio
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
    """Handle incoming messages."""
    if not update.message or not update.message.text:
        return
        
    message_text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    
    # Update message history
    update_message_history(user_id, message_text)
    
    # Check for user restrictions
    if should_restrict_user(message_text):
        await restrict_user(update, context)
        return
        
    # Process message content
    cleaned_text, modified_links = process_message_content(message_text)
    
    # Check for GPT response
    needs_response, response_type = needs_gpt_response(update, context, message_text)
    if needs_response:
        await gpt_response(update, context, cleaned_text, response_type)
        return
        
    # Handle URLs
    urls = extract_urls(cleaned_text)
    if urls:
        await process_urls(update, context, urls, cleaned_text)

@handle_errors(feedback_message="An error occurred while processing your links.")
async def process_urls(update: Update, context: CallbackContext, urls: list[str], message_text: str) -> None:
    """Process URLs in the message."""
    chat_id = update.effective_chat.id
    username = update.message.from_user.username or f"ID:{update.message.from_user.id}"
    
    modified_links = []
    for url in urls:
        try:
            sanitized_url = sanitize_url(url)
            modified_url = modify_url(sanitized_url)
            if modified_url:
                modified_links.append(modified_url)
        except ValueError as e:
            error_logger.warning(f"URL processing failed: {str(e)}")
            continue
            
    if modified_links:
        await construct_and_send_message(chat_id, username, message_text, modified_links, update, context)

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
    message = f"@{username} хотів відправити:\n{cleaned_message_text}"
    keyboard = create_link_keyboard(modified_links)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=keyboard
    )

@handle_errors(feedback_message="An error occurred while handling private message.")
async def handle_private_message(update: Update, context: CallbackContext, message_text: str) -> None:
    """Handle private chat messages."""
    # Add private message handling logic here
    pass

@handle_errors(feedback_message="An error occurred while handling sticker.")
async def handle_sticker(update: Update, context: CallbackContext) -> None:
    """Handle sticker messages."""
    if not update.message or not update.message.sticker:
        return
        
    sticker = update.message.sticker
    chat_id = update.effective_chat.id
    
    # Check if it's the AliExpress sticker
    if sticker.file_unique_id == ALIEXPRESS_STICKER_ID:
        await update.message.reply_text(
            "🔗 *AliExpress Link Detected*\n\n"
            "Please send the product link and I'll optimize it for you\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
        
    # Handle other stickers if needed
    general_logger.info(f"Received sticker {sticker.file_unique_id} in chat {chat_id}")

@handle_errors(feedback_message="An error occurred in /ping command.")
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ping command."""
    await update.message.reply_text("Pong! 🏓")
    general_logger.info(f"Handled /ping command for user {update.effective_user.id}")

def register_handlers(application: Application, bot: Bot, config_manager: ConfigManager) -> None:
    """Register all command and message handlers."""
    # Basic commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("cat", cat_command))
    application.add_handler(CommandHandler("errors", error_report_command))
    
    # GPT commands
    application.add_handler(CommandHandler("gpt", lambda u, c: ask_gpt_command(u, u, c)))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    
    # Weather and environment
    weather_handler = WeatherCommandHandler()
    application.add_handler(CommandHandler("weather", weather_handler))
    application.add_handler(CommandHandler("flares", screenshot_command))
    
    # Geomagnetic activity
    geomagnetic_handler = GeomagneticCommandHandler()
    application.add_handler(CommandHandler("gm", geomagnetic_handler))
    
    # Reminders
    application.add_handler(CommandHandler("remind", reminder_manager.remind))
    
    # Setup video handlers first (before general message handlers)
    setup_video_handlers(application, extract_urls_func=extract_urls)
    
    # Message handlers for non-text content
    application.add_handler(MessageHandler(filters.PHOTO, analyze_image))
    application.add_handler(MessageHandler(filters.Sticker(), handle_sticker))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))

async def initialize_all_components():
    """Initialize all bot components."""
    try:
        # Initialize directories
        init_directories()
        
        # Initialize error handler
        await init_telegram_error_handler(TOKEN, Config.ERROR_CHANNEL_ID)
        
        # Initialize other components
        await reminder_manager.initialize()
        
        general_logger.info("All components initialized successfully")
        
    except Exception as e:
        error_logger.error(f"Failed to initialize components: {str(e)}", exc_info=True)
        raise

async def cleanup_all_components():
    """Cleanup all bot components."""
    try:
        # Cleanup logging
        await shutdown_logging()
        
        # Cleanup other components
        if hasattr(reminder_manager, 'stop'):
            await reminder_manager.stop()
        
        general_logger.info("All components cleaned up successfully")
        
    except Exception as e:
        error_logger.error(f"Failed to cleanup components: {str(e)}", exc_info=True)
        raise

def handle_shutdown_signal(signum, frame):
    """Handle shutdown signals."""
    general_logger.info(f"Received signal {signum}, initiating shutdown...")
    sys.exit(0)

async def main():
    """Main bot initialization and run loop."""
    try:
        # Initialize the database
        await Database.initialize()
        
        # Initialize components
        await initialize_all_components()
        
        # Create application
        application = ApplicationBuilder().token(TOKEN).build()
        
        # Set up message handlers
        setup_message_handlers(application)
        
        # Register handlers
        register_handlers(application, application.bot, config_manager)
        
        # Start the bot
        await application.initialize()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        error_logger.error(f"Bot startup failed: {str(e)}", exc_info=True)
        raise
        
    finally:
        # Cleanup
        await cleanup_all_components()
        if application:
            await application.stop()
            await application.shutdown()

def run_bot():
    """Run the bot with proper signal handling."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    
    # Run the bot
    asyncio.run(main())

if __name__ == "__main__":
    run_bot()