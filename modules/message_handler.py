from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters
from .database import Database
from .message_processor import (
    needs_gpt_response, update_message_history,
    process_message_content, should_restrict_user
)
from .url_processor import extract_urls
from .user_management import restrict_user
from .gpt import gpt_response
from .const import ALIEXPRESS_STICKER_ID
from .logger import error_logger, general_logger
from .chat_streamer import chat_streamer

async def handle_message_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming messages and store them in the database.
    This handler should be added to the application's message handlers.
    """
    try:
        # Log that we received a message
        general_logger.info(f"Received message in chat {update.effective_chat.id}")
        
        # Stream message to log file first
        await chat_streamer.stream_message(update, context)
        general_logger.info("Message streamed to log file")
        
        # If it's not a text message, we're done after logging
        if not update.message or not (update.message.text or update.message.caption):
            general_logger.info("Non-text message, skipping further processing")
            return

        # Store the message in the database
        await Database.save_message(update.message)
        general_logger.info("Message saved to database")
            
    except Exception as e:
        # Log the error but don't interrupt the bot's operation
        error_logger.error(f"Error processing message: {str(e)}", exc_info=True)

async def handle_gpt_reply(
    message: Update.message,
    context_message_ids: list[int],
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

def setup_message_handlers(application):
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

async def handle_gpt_reply(
    message: Update.message,
    context_message_ids: list[int],
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