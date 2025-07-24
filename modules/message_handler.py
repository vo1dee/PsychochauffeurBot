from telegram import Update, Message
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters, Application
from typing import Any, List
from .database import Database
from .message_processor import (
    needs_gpt_response, update_message_history,
    process_message_content, should_restrict_user
)
from .url_processor import extract_urls, shorten_url
from .user_management import restrict_user
from .gpt import gpt_response
from .const import Stickers
from .logger import error_logger, general_logger
from .chat_streamer import chat_streamer

async def handle_message_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming messages and store them in the database.
    This handler should be added to the application's message handlers.
    """
    try:
        # Log that we received a message
        if update.effective_chat:
            general_logger.info(f"Received message in chat {update.effective_chat.id}")
        else:
            general_logger.info("Received message in unknown chat")
        
        # Stream message to log file first - this handles ALL message types
        await chat_streamer.stream_message(update, context)
        general_logger.info("Message streamed to log file")
        
        # Only save to database if it's a text message, bot reply, or has image description
        if update.message:
            should_save = (
                update.message.text or  # Text message
                update.message.caption or  # Image/video caption
                (update.message.from_user and update.message.from_user.is_bot)  # Bot's reply
            )
            
            # --- AliExpress sticker logic ---
            if update.message.text:
                urls = extract_urls(update.message.text)
                if any(url.lower().startswith(('https://aliexpress.com/', 'https://www.aliexpress.com/', 'https://m.aliexpress.com/')) for url in urls):
                    try:
                        await update.message.reply_sticker(sticker=Stickers.ALIEXPRESS)
                    except Exception as e:
                        error_logger.error(f"Failed to send AliExpress sticker: {e}")
            # --- End AliExpress sticker logic ---

            # --- URL shortening logic ---
            if update.message.text:
                urls = extract_urls(update.message.text)
                url_map = {}
                for url in urls:
                    if len(url) > 123:
                        try:
                            short_url = await shorten_url(url)
                            if short_url != url:
                                url_map[url] = short_url
                        except Exception as e:
                            error_logger.error(f"Failed to shorten URL {url}: {e}")
                if url_map:
                    new_text = update.message.text
                    for orig, short in url_map.items():
                        new_text = new_text.replace(orig, short)
                    try:
                        await update.message.reply_text(new_text)
                    except Exception as e:
                        error_logger.error(f"Failed to send shortened message: {e}")
            # --- End URL shortening logic ---
            
            if should_save:
                general_logger.info(f"Attempting to save message: {update.message.text!r}")
                await Database.save_message(update.message)
                general_logger.info("Message saved to database")
            
    except Exception as e:
        # Log the error but don't interrupt the bot's operation
        error_logger.error(f"Error processing message: {str(e)}", exc_info=True)

async def handle_gpt_reply(
    message: Message,
    context_message_ids: List[int],
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle and store a GPT-generated reply message.
    This should be called after generating a GPT response.
    """
    try:
        # Store the GPT reply with its context
        await Database.save_message(
            message=message,
            is_gpt_reply=True,
            gpt_context_message_ids=context_message_ids
        )
    except Exception as e:
        print(f"Error storing GPT reply: {e}")

def setup_message_handlers(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """
    Set up message handlers for the bot.
    This function should be called during bot initialization.
    """
    # Add a handler to log all messages and save them to the database.
    # It's in group -1 to ensure it runs before all other handlers.
    # block=False allows the update to be processed by other handlers.
    application.add_handler(MessageHandler(
        filters.ALL,
        handle_message_logging,
        block=False
    ), group=-1)

# Duplicate function removed - see above for the actual implementation