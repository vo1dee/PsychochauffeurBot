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
import asyncpg
import subprocess

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
from modules.keyboards import create_link_keyboard, button_callback, get_language_keyboard
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
from modules.count_command import count_command, missing_command
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
from modules.keyboard_translator import keyboard_mapping
from modules.database import Database
from modules.message_handler import setup_message_handlers, handle_gpt_reply
from modules.chat_streamer import chat_streamer
from modules.speechmatics import transcribe_telegram_voice, SpeechmaticsLanguageNotExpected, SpeechmaticsRussianDetected, SpeechmaticsNoSpeechDetected

# Apply nest_asyncio at the very beginning, as it's crucial for the event loop.
nest_asyncio.apply()

# Initialize global objects
message_counter = MessageCounter()
reminder_manager = ReminderManager()
config_manager = ConfigManager()

# Global persistent mapping for file_id hashes
file_id_hash_map = {}

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

@handle_errors(feedback_message="An error occurred while processing your message.")
async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming non-command text messages."""
    if not update.message or not update.message.text:
        return
        
    message_text = update.message.text.strip()
    user_id = update.message.from_user.id
    # Update message history at the very start
    update_message_history(user_id, message_text)

    # Safeguard: Explicitly ignore commands to prevent interference with CommandHandlers
    if message_text.startswith('/'):
        return
    
    # --- БЛЯ! TRANSLATION COMMAND ---
    if message_text.lower() == "бля!":
        username = update.message.from_user.username or "User"
        previous_message = get_previous_message(user_id)
        if not previous_message:
            await update.message.reply_text("Немає попереднього повідомлення для перекладу.")
            return
        from modules.keyboard_translator import auto_translate_text
        converted_text = auto_translate_text(previous_message)
        response_text = f"@{username} хотів сказати: {converted_text}"
        await update.message.reply_text(response_text)
        return
    # --- END БЛЯ! TRANSLATION COMMAND ---

    chat_id = update.effective_chat.id
    
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
    
    # Check for GPT response
    needs_response, response_type = needs_gpt_response(update, context, message_text)
    if needs_response:
        await gpt_response(update, context, response_type=response_type, message_text_override=cleaned_text)
        return

    # --- RANDOM GPT RESPONSE LOGIC ---
    # Only in group chats, not private
    if update.effective_chat.type in {"group", "supergroup"}:
        # Block random GPT response if message contains any link
        if extract_urls(message_text):
            pass  # Do not trigger random GPT
        else:
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
        
        # Check if the original message was a reply to another message
        if update.message.reply_to_message:
            # If it was a reply, send the modified link message as a reply to the parent message
            await update.message.reply_to_message.reply_text(
                text=message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            # If it wasn't a reply, send the modified link message as a reply to the original message
            await update.message.reply_text(
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
    general_logger.info(f"Received sticker: {sticker.file_id} ({sticker.file_unique_id})")
    
    # Check if this is a restriction sticker
    if sticker.file_unique_id in [
        "AgAD9hQAAtMUCVM",
        "AgADrBgAAk_x0Es",
        "AgADJSsAArOEUEo",
        "AgAD32YAAvgziEo"
    ]:
        await handle_restriction_sticker(update, context)

@handle_errors(feedback_message="An error occurred while handling location.")
async def handle_location(update: Update, context: CallbackContext) -> None:
    """Handle location messages by replying with a sticker."""
    if not update.message or not update.message.location:
        return
        
    location = update.message.location
    general_logger.info(f"Received location: lat={location.latitude}, lon={location.longitude}")
    
    try:
        # Reply with the location sticker
        await update.message.reply_sticker(sticker=Stickers.LOCATION)
        general_logger.info(f"Sent location sticker in response to location message")
    except Exception as e:
        error_logger.error(f"Failed to send location sticker: {e}")
        await update.message.reply_text("📍 Location received!")

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
    # Instead of auto recognition, send the button
    await send_speech_recognition_button(update, context)
    # If you want to keep auto recognition as fallback, comment out the next lines
    # progress_msg = await update.message.reply_text("📝 Transcribing voice message...")
    # try:
    #     transcript = await transcribe_telegram_voice(context.bot, file_id, language="auto")
    #     username = user.username or user.first_name or f"ID:{user.id}"
    #     text = f"🗣️ {username} (Speech):\n{transcript}"
    #     chat_streamer._chat_logger.info(f"[{username}] (Speech): {transcript}", extra={
    #         'chat_id': chat_id,
    #         'chat_type': chat_type,
    #         'chattitle': update.effective_chat.title or f"Private_{chat_id}",
    #         'username': username
    #     })
    #     await context.bot.send_message(chat_id=chat_id, text=text)
    # except ...
    #     ...
    # await progress_msg.delete()

# --- Speech Recognition Callback Handler ---
@handle_errors(feedback_message="An error occurred during manual speech recognition.")
async def speechrec_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data
    # Debug log for callback data
    print(f"[DEBUG] speechrec_callback received data: {data}")
    print(f"[DEBUG] file_id_hash_map keys: {list(file_id_hash_map.keys())}")
    if not data.startswith("speechrec_"):
        await query.edit_message_text("❌ Invalid callback data format. Please try again with a new voice message. If the bot was restarted, old buttons will not work.")
        return
    file_hash = data[len("speechrec_"):]
    file_id = file_id_hash_map.get(file_hash)
    if not file_id:
        print(f"[DEBUG] speechrec_callback: file_hash '{file_hash}' not found in file_id_hash_map.")
        await query.edit_message_text("❌ This speech recognition button has expired or is invalid. Please send a new voice message and use the new button. If the bot was restarted, old buttons will not work.")
        return
    print(f"[DEBUG] speechrec_callback: found file_id for hash {file_hash}")
    await query.edit_message_text("🔄 Recognizing speech, please wait...")
    try:
        transcript = await transcribe_telegram_voice(context.bot, file_id, language="auto")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🗣️ Recognized speech:\n{transcript}"
        )
    except SpeechmaticsNoSpeechDetected:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No speech was detected in the audio. Please try again with a clearer voice message."
        )
    except SpeechmaticsLanguageNotExpected:
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        file_id_hash_map[file_hash] = file_id
        keyboard = get_language_keyboard(file_hash)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Couldn't recognize the language. Please choose the correct language:",
            reply_markup=keyboard
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Speech recognition failed: {e}"
        )

# --- Restore language_selection_callback for language selection buttons ---
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
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        file_id_hash_map[file_hash] = file_id
        keyboard = get_language_keyboard(file_hash)
        transcript = await transcribe_telegram_voice(context.bot, file_id, language=lang_code)
        await query.edit_message_text(f"🗣️ Recognized ({lang_code}):\n{transcript}")
    except SpeechmaticsLanguageNotExpected as e:
        print(f"[DEBUG] Speechmatics identified language not expected: {e}")
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
        file_id_hash_map[file_hash] = file_id
        keyboard = get_language_keyboard(file_hash)
        await query.edit_message_text(
            "❌ Couldn't recognize the language or it is not supported. Please choose another language:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"[DEBUG] Error during manual language selection: {e}")
        await query.edit_message_text(f"❌ Speech recognition failed: {e}", reply_markup=None)

# --- Add Speech Recognition Button ---
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Utility to send a speech recognition button as a reply to a voice message
async def send_speech_recognition_button(update, context):
    message = update.message
    if not message or (not message.voice and not message.video_note):
        return
    file_id = message.voice.file_id if message.voice else message.video_note.file_id
    file_hash = hashlib.md5(file_id.encode()).hexdigest()[:16]
    # Store file_id for callback lookup
    file_id_hash_map[file_hash] = file_id
    print(f"[DEBUG] Added file_id_hash_map entry: {file_hash} -> {file_id}")
    print(f"[DEBUG] Current file_id_hash_map: {file_id_hash_map}")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎤 Recognize Speech", callback_data=f"speechrec_{file_hash}")]
    ])
    await message.reply_text(
        "Press the button to recognize speech in this voice or video message.\n\n⚠️ If the bot was recently restarted, old buttons will not work. Please send a new message if you see an error.",
        reply_markup=keyboard
    )

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
    application.add_handler(CommandHandler("missing", missing_command))
    application.add_handler(CommandHandler("speech", speech_command))
    
    # Group 0: Other specific message handlers.
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_analysis))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.VOICE | filters.VIDEO_NOTE, handle_voice_or_video_note))

    # General text message handler for non-command messages.
    # It has a filter to specifically ignore commands.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register the callback handler for language selection with pattern filter
    application.add_handler(CallbackQueryHandler(language_selection_callback, pattern=r"^lang_"))
    # Register the callback handler for speech recognition button (move this up)
    application.add_handler(CallbackQueryHandler(speechrec_callback, pattern=r"^speechrec_"))
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
                f"• Config Update: ✅ ({success_count}/{total_count})\n"
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
    await init_telegram_error_handler(application.bot, Config.ERROR_CHANNEL_ID)

    # Register command handlers
    register_handlers(application, application.bot, config_manager)
    general_logger.info("Bot polling started.")
    
    # Run polling with proper error handling
    try:
        # Fix: Remove unsupported 'close_loop' argument to avoid NoneType error
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            stop_signals=None  # We handle signals in run_bot
        )
    except Exception as e:
        error_logger.error(f"Error during polling: {str(e)}", exc_info=True)
        raise

async def ensure_db_initialized():
    try:
        conn = await asyncpg.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'telegram_bot'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
        )
        result = await conn.fetchval("SELECT to_regclass('public.chats')")
        await conn.close()
        if result is None:
            print("[INFO] Database not initialized, running scripts/init_database.py ...")
            subprocess.run([sys.executable, 'scripts/init_database.py'], check=True)
        else:
            print("[INFO] Database already initialized.")
    except Exception as e:
        print(f"[ERROR] Could not check or initialize database: {e}")
        subprocess.run([sys.executable, 'scripts/init_database.py'], check=True)

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
    asyncio.run(ensure_db_initialized())
    run_bot()