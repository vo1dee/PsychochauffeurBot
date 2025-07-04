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
import re
import hashlib
import logging

# Third-party imports
import nest_asyncio
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler, ContextTypes, Application
)
from telegram.error import BadRequest

# Local module imports
from modules.keyboards import create_link_keyboard, button_callback, get_language_keyboard as original_get_language_keyboard
from modules.utils import (
    ScreenshotManager, MessageCounter, screenshot_command, cat_command,
    init_directories, chat_history_manager
)
from modules.image_downloader import ImageDownloader
from modules.const import (
    KYIV_TZ, VideoPlatforms, LinkModification, Config, Stickers
)
from modules.gpt import (
    ask_gpt_command, analyze_command, answer_from_gpt, handle_photo_analysis,
    gpt_response, mystats_command
)
from modules.count_command import count_command
from modules.weather import WeatherCommandHandler
from modules.logger import (
    TelegramErrorHandler,
    general_logger, chat_logger, error_logger,
    init_telegram_error_handler, shutdown_logging
)
from modules.user_management import restrict_user, handle_restriction_sticker
from modules.video_downloader import setup_video_handlers
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity
from modules.geomagnetic import GeomagneticCommandHandler
from modules.reminders.reminders import ReminderManager
from modules.error_analytics import error_report_command, error_tracker
from config.config_manager import ConfigManager
from modules.safety import safety_manager
from modules.url_processor import (
    sanitize_url, shorten_url, extract_urls,
    is_modified_domain, modify_url, is_meta_platform
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
from modules.speechmatics import transcribe_telegram_voice, SpeechmaticsLanguageNotExpected, SpeechmaticsRussianDetected

# Apply nest_asyncio at the very beginning, as it's crucial for the event loop.
nest_asyncio.apply()

# Initialize global objects
message_counter = MessageCounter()
reminder_manager = ReminderManager()
config_manager = ConfigManager()

# Global persistent mapping for file_id hashes
file_id_hash_map = {}

def get_language_keyboard(file_id, context=None):
    import hashlib
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
    file_id_hash_map[file_hash] = file_id
    print(f"[DEBUG] (keyboard) Storing file_id in file_id_hash_map: {file_id} -> {file_hash}")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English", callback_data=f"lang_en|{file_hash}"),
            InlineKeyboardButton("🇮🇱 Hebrew", callback_data=f"lang_he|{file_hash}"),
            InlineKeyboardButton("🇺🇦 Ukrainian", callback_data=f"lang_uk|{file_hash}")
        ]
    ])

# --- Command Handlers ---
@handle_errors(feedback_message="An error occurred in /start command.")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    welcome_text = (
        "🤖 PsychoChauffeur Bot\n\n"
        "🎥 Video Downloads from:\n"
        "• TikTok\n• YouTube Shorts\n"
        "• Twitter\n• Vimeo\n• Reddit\n• Twitch\n"
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
    # Add a static test button for callback debugging
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    await update.message.reply_text(
        "Test callback button:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Test Callback", callback_data="test_callback")]
        ])
    )
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
    
    # Update chat history for context using the global manager
    chat_history_manager.add_message(chat_id, {
        'text': message_text,
        'is_user': True,
        'user_id': user_id,
        'timestamp': update.message.date
    })
    
    # Check for user restrictions
    if should_restrict_user(message_text):
        await restrict_user(update, context)
        return
        
    # Process message content and extract URLs
    cleaned_text, modified_links = process_message_content(message_text)
    
    # If all modified links are AliExpress, skip sending the "modified link" message
    if modified_links and all("aliexpress.com" in link for link in modified_links):
        return
    
    # Check for Meta platform links
    urls = extract_urls(message_text)
    for url in urls:
        if is_meta_platform(url):
            await update.message.reply_text("цукерберг уйобок, мета - корпорація гівна")
            return
    
    # Check for GPT response
    needs_response, response_type = needs_gpt_response(update, context, message_text)
    if needs_response:
        await gpt_response(update, context, response_type=response_type, message_text_override=cleaned_text)
        return

    # --- RANDOM GPT RESPONSE LOGIC ---
    # Only in group chats, not private
    if update.effective_chat.type in {"group", "supergroup"}:
        chat_id = str(update.effective_chat.id)
        chat_type = update.effective_chat.type
        config = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name="chat_behavior")
        
        # Check if chat_behavior module is enabled
        module_enabled = config.get("enabled", False)
        overrides = config.get("overrides", {})
        random_settings = overrides.get("random_response_settings", {})
        random_enabled = random_settings.get("enabled", False)
        
        # Both module and random settings must be enabled
        if module_enabled and random_enabled:
            min_words = random_settings.get("min_words", 5)
            message_threshold = random_settings.get("message_threshold", 50)
            probability = random_settings.get("probability", 0.02)
            
            # Only consider messages with enough words
            if len(message_text.split()) >= min_words:
                count = message_counter.increment(update.effective_chat.id)
                general_logger.info(f"Random response check: chat_id={chat_id}, count={count}/{message_threshold}, probability={probability}")
                
                if count >= message_threshold:
                    import random
                    if random.random() < probability:
                        message_counter.reset(update.effective_chat.id)
                        general_logger.info(f"Triggering random response in chat {chat_id}")
                        await gpt_response(update, context, response_type="random", message_text_override=cleaned_text)
                        return
        else:
            # Log why random responses are disabled
            if not module_enabled:
                general_logger.debug(f"Random responses disabled: chat_behavior module not enabled in chat {chat_id}")
            elif not random_enabled:
                general_logger.debug(f"Random responses disabled: random_response_settings not enabled in chat {chat_id}")

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
    general_logger.info(f"Sticker received: file_id={sticker.file_id}, file_unique_id={sticker.file_unique_id}")
    # AliExpress sticker logic
    if sticker.file_unique_id == Stickers.ALIEXPRESS:
        await update.message.reply_text(
            "🔗 *AliExpress Link Detected*\n\nPlease send the product link and I'll optimize it for you\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # Restrict user if they send the specific sticker in a supergroup (never in private chats)
    await handle_restriction_sticker(update, context)

@handle_errors(feedback_message="An error occurred in /ping command.")
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ping command."""
    await update.message.reply_text("Pong! 🏓")
    general_logger.info(f"Handled /ping command for user {update.effective_user.id}")

# --- Speech Recognition State Management ---
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == 'private':
        return True
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in {"administrator", "creator"}

async def get_speech_config(chat_id: str, chat_type: str):
    config = await config_manager.get_config(chat_id, chat_type)
    return config.get("config_modules", {}).get("speechmatics", {})

@handle_errors(feedback_message="An error occurred in /speech command.")
async def speech_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    args = context.args if hasattr(context, 'args') else []
    speech_config = await get_speech_config(chat_id, chat_type)
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

# --- Voice/Video Note Handler ---
@handle_errors(feedback_message="An error occurred during speech recognition.")
async def handle_voice_or_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    speech_config = await get_speech_config(chat_id, chat_type)
    if not speech_config.get("enabled", False):
        return
    message = update.message
    user = message.from_user
    file_id = None
    if message.voice:
        file_id = message.voice.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    else:
        return
    progress_msg = await update.message.reply_text("📝 Transcribing voice message...")
    try:
        transcript = await transcribe_telegram_voice(context.bot, file_id, language="auto")
        username = user.username or user.first_name or f"ID:{user.id}"
        text = f"🗣️ {username} (Speech):\n{transcript}"
        # Log to chat history
        chat_streamer._chat_logger.info(f"[{username}] (Speech): {transcript}", extra={
            'chat_id': chat_id,
            'chat_type': chat_type,
            'chattitle': update.effective_chat.title or f"Private_{chat_id}",
            'username': username
        })
        # Save to database as a bot message
        await context.bot.send_message(chat_id=chat_id, text=text)
    except SpeechmaticsRussianDetected as e:
        # Russian was detected, automatically retry with Ukrainian
        logging.info(f"[Auto-management] Russian detected, retrying with Ukrainian: {e}")
        await progress_msg.edit_text("🔄 Russian detected, retrying with Ukrainian...")
        try:
            transcript = await transcribe_telegram_voice(context.bot, file_id, language="uk")
            username = user.username or user.first_name or f"ID:{user.id}"
            text = f"🗣️ {username} (Speech - Ukrainian):\n{transcript}"
            # Log to chat history
            chat_streamer._chat_logger.info(f"[{username}] (Speech - Ukrainian): {transcript}", extra={
                'chat_id': chat_id,
                'chat_type': chat_type,
                'chattitle': update.effective_chat.title or f"Private_{chat_id}",
                'username': username
            })
            # Save to database as a bot message
            await context.bot.send_message(chat_id=chat_id, text=text)
        except Exception as retry_error:
            logging.error(f"[Auto-management] Ukrainian retry failed: {retry_error}")
            await progress_msg.edit_text(f"❌ Speech recognition failed: {retry_error}")
            await asyncio.sleep(3)
            await progress_msg.delete()
            return
    except Exception as e:
        error_text = str(e)
        if (
            "not one of the expected languages" in error_text or
            "language identification" in error_text or
            "timed out" in error_text or
            isinstance(e, TimeoutError) or
            isinstance(e, asyncio.TimeoutError)
        ):
            keyboard = get_language_keyboard(file_id, context)
            try:
                await update.message.reply_text(
                    "❌ Couldn't recognize the language or timed out. Please choose the correct language:",
                    reply_markup=keyboard
                )
            except BadRequest as br:
                error_logger.error(f"Failed to send language selection keyboard: {br}")
                await update.message.reply_text("❌ Couldn't recognize the language or timed out. Please try again.")
            await progress_msg.delete()
            return
        else:
            await progress_msg.edit_text(f"❌ Speech recognition failed: {e}")
            await asyncio.sleep(3)
            await progress_msg.delete()
            return
    await progress_msg.delete()

@handle_errors(feedback_message="An error occurred during manual language selection.")
async def language_selection_callback(update: Update, context: CallbackContext):
    print("[DEBUG] Callback handler entered (any callback)")
    print(f"[DEBUG] Full update: {update}")
    query = update.callback_query
    await query.answer()
    data = query.data
    print(f"[DEBUG] Language selection callback triggered. Data: {data}")
    if data == "test_callback":
        await query.edit_message_text("✅ Test callback received and handled!")
        return
    if '|' not in data:
        print(f"[DEBUG] Invalid callback data received: {data}")
        await query.edit_message_text("❌ Invalid callback data. Please try again.")
        return
    lang_code, file_hash = data.split('|', 1)
    lang_code = lang_code.replace('lang_', '')
    file_id = file_id_hash_map.get(file_hash)
    print(f"[DEBUG] (callback) Callback data hash lookup: {file_hash} -> {file_id}")
    if not file_id:
        print(f"[DEBUG] (callback) Hash {file_hash} not found in file_id_hash_map. Callback data: {data}")
        await query.edit_message_text("❌ This button has expired or is invalid. Please try again.")
        return
    
    # Show progress immediately
    await query.edit_message_text(f"🔄 Processing with {lang_code} language...", reply_markup=None)
    
    try:
        transcript = await transcribe_telegram_voice(context.bot, file_id, language=lang_code)
        await query.edit_message_text(f"🗣️ Recognized ({lang_code}):\n{transcript}")
    except SpeechmaticsLanguageNotExpected as e:
        print(f"[DEBUG] Speechmatics identified language not expected: {e}")
        keyboard = get_language_keyboard(file_id, context)
        await query.edit_message_text(
            "❌ Couldn't recognize the language. Please choose the correct language:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"[DEBUG] Error during manual language selection: {e}")
        await query.edit_message_text(f"❌ Speech recognition failed: {e}", reply_markup=None)

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
    application.add_handler(CommandHandler("count", count_command))
    application.add_handler(CommandHandler("speech", speech_command))
    
    # Group 0: Other specific message handlers.
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_analysis))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(MessageHandler(filters.VOICE | filters.VIDEO_NOTE, handle_voice_or_video_note))

    # General text message handler for non-command messages.
    # It has a filter to specifically ignore commands.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register the callback handler for language selection FIRST (no pattern)
    application.add_handler(CallbackQueryHandler(language_selection_callback))
    # Callback query handler for buttons (link modifications, etc)
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
        await init_telegram_error_handler(Config.TELEGRAM_BOT_TOKEN, Config.ERROR_CHANNEL_ID)
        await config_manager.initialize()
        
        # Update all chat configs with new template fields
        update_results = await config_manager.update_chat_configs_with_template()
        success_count = sum(1 for v in update_results.values() if v)
        total_count = len(update_results)
        general_logger.info(f"Updated {success_count}/{total_count} chat configs with new template fields")
        
        await reminder_manager.initialize()
        await safety_manager.initialize()
        
        # Send startup message to error channel
        try:
            bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
            startup_time = datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
            startup_message = (
                "🚀 *Bot Started Successfully*\n\n"
                f"*Time:* `{startup_time}`\n"
                "*Status:* `Online`\n"
                "*Components:*\n"
                "• Database: ✅\n"
                "• Error Handler: ✅\n"
                "• Config Manager: ✅\n"
                f"• Config Update: ✅ \({success_count}/{total_count}\)\n"
                "• Reminder Manager: ✅\n"
                "• Safety Manager: ✅"
            )
            
            # Parse channel ID and topic ID
            if ':' in Config.ERROR_CHANNEL_ID:
                channel_id, topic_id = Config.ERROR_CHANNEL_ID.split(':')
                message_params = {
                    'chat_id': channel_id,
                    'text': startup_message,
                    'parse_mode': 'MarkdownV2',
                    'message_thread_id': int(topic_id)
                }
            else:
                message_params = {
                    'chat_id': Config.ERROR_CHANNEL_ID,
                    'text': startup_message,
                    'parse_mode': 'MarkdownV2'
                }
                
            await bot.send_message(**message_params)
        except Exception as e:
            error_logger.error(f"Failed to send startup message: {str(e)}", exc_info=True)
            
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
    """
    Initialize and run the bot application.
    """
    if not Config.TELEGRAM_BOT_TOKEN:
        error_logger.critical("TELEGRAM_BOT_TOKEN is not set. The bot cannot start.")
        return

    # Initialize directories and ensure city data file exists
    init_directories()

    # Create the Application
    application = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Initialize error handler with the bot instance
    init_telegram_error_handler(application.bot, Config.ERROR_CHANNEL_ID)

    # Register command handlers
    register_handlers(application, application.bot, config_manager)
    general_logger.info("Bot polling started.")
    
    # Run polling with proper error handling
    try:
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False,
            stop_signals=None  # We handle signals in run_bot
        )
    except Exception as e:
        error_logger.error(f"Error during polling: {str(e)}", exc_info=True)
        raise

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