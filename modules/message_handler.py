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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        if not update.message or not update.message.text:
            general_logger.info("Non-text message, skipping further processing")
            return

        # Store the message in the database
        await Database.save_message(update.message)
        general_logger.info("Message saved to database")
        
        # Process the message
        message_text = update.message.text
        user_id = update.message.from_user.id
        chat_id = update.effective_chat.id
        
        # Update message history
        update_message_history(user_id, message_text)
        general_logger.info("Message history updated")
        
        # Check for user restrictions
        if should_restrict_user(message_text):
            general_logger.info(f"Restricting user {user_id} for inappropriate content")
            await restrict_user(update, context)
            return
            
        # Check for AliExpress links
        if 'aliexpress.com' in message_text.lower():
            general_logger.info("Detected AliExpress link, sending sticker")
            # Send AliExpress sticker only
            await update.message.reply_sticker(sticker=ALIEXPRESS_STICKER_ID)
            return
            
        # Process message content
        cleaned_text, modified_links = process_message_content(message_text)
        general_logger.info(f"Processed message content, found {len(modified_links) if modified_links else 0} links")
        
        # Check for GPT response
        needs_response, response_type = needs_gpt_response(update, context, message_text)
        if needs_response:
            general_logger.info(f"Message needs GPT response of type {response_type}")
            await gpt_response(update, context, response_type="command", message_text_override=cleaned_text)
            return
            
        # Handle URLs if we have modified links
        if modified_links:
            general_logger.info(f"Processing {len(modified_links)} modified links")
            from main import process_urls  # Import here to avoid circular import
            await process_urls(update, context, modified_links, cleaned_text)
            
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
    # Add a handler to log all messages
    application.add_handler(MessageHandler(
        filters.ALL,
        handle_message,
        block=False
    ))
    
    # Add the message handler to store and process all messages
    # Use a more specific filter to avoid catching video links but allow AliExpress and x.com links
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (
            ~filters.Regex('|'.join([
                'tiktok.com', 'vm.tiktok.com', 'instagram.com/reels', 'youtube.com/shorts',
                'youtu.be/shorts', 'facebook.com', 'vimeo.com', 'reddit.com', 'twitch.tv',
                'youtube.com/clip'
            ])) | 
            filters.Regex('|'.join(['aliexpress.com', 'x.com', 'twitter.com']))
        ),
        handle_message,
        block=False  # Don't block other handlers
    )) 