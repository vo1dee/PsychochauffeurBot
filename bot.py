import asyncio
import hashlib
import logging
import nest_asyncio
import pytz
import random
import pyshorteners
from urllib.parse import urlparse, urlunparse
import re

from modules.keyboards import create_link_keyboard, button_callback
from utils import remove_links, screenshot_command, schedule_task, cat_command, ScreenshotManager, game_state, game_command, end_game_command, clear_words_command, hint_command, load_game_state
from const import domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID
from modules.gpt import ask_gpt_command, analyze_command, answer_from_gpt
from modules.weather import weather
from modules.file_manager import general_logger, chat_logger
from modules.user_management import restrict_user
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, \
    CallbackQueryHandler
from urllib.parse import urlparse, urlunparse

# Apply the patch to allow nested event loops
nest_asyncio.apply()
LOCAL_TZ = pytz.timezone('Europe/Kyiv')

message_counts = {}


def contains_trigger_words(message_text):
    triggers = ["Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)

def sanitize_url(url: str, replace_domain: str = None) -> str:
    parsed_url = urlparse(url)
    netloc = replace_domain if replace_domain else parsed_url.netloc
    sanitized_url = urlunparse((parsed_url.scheme, netloc, parsed_url.path, '', '', ''))
    return sanitized_url

def extract_urls(text):
    """Extract URLs from text using regex pattern."""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

async def start(update: Update, context: CallbackContext):
    general_logger.info(f"Processing /start command from user {update.message.from_user.id} in chat {update.effective_chat.id}")
    await update.message.reply_text("Hello! Send me TikTok, Twitter, or Instagram links, and I will modify them for you!")

async def handle_message(update: Update, context: CallbackContext):
    """Handle incoming messages."""
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    
    # Initialize modified_link before using it
    modified_link = message_text

    # Check for YouTube links first
    if any(domain in message_text for domain in ["youtube.com", "youtu.be"]):
        if len(message_text) > 60:
            modified_link = await shorten_url(message_text)
        # Just send a hashtag reply once
        await update.message.reply_text("#youtube", reply_to_message_id=update.message.message_id)
        return  # Exit the function after handling YouTube link
        
    # Extract URLs if present
    urls = extract_urls(message_text)
    if urls:
        modified_link = urls[0]  # Take the first URL if multiple exist
        

    chat_id = update.message.chat_id
    username = update.message.from_user.username
    chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"

    # Log message with extra fields
    chat_logger.info(f"User message: {message_text}", extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})

    # Handle trigger words
    if contains_trigger_words(message_text):
        await restrict_user(update, context)
        return

    modified_links = []
    original_links = []

    # Process all links in a single pass
    for link in message_text.split():
        sanitized_link = sanitize_url(link)
            
        if any(domain in message_text for domain in ["aliexpress.com/item/", "a.aliexpress.com/"]):
            if len(message_text) > 60:
                modified_link = await shorten_url(message_text)
            modified_link += " #aliexpress"
            modified_links.append(modified_link)
            # Send AliExpress sticker
            await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=ALIEXPRESS_STICKER_ID)
            continue

        # Then check for domain modifications (x.com etc.)
        for domain, modified_domain in domain_modifications.items():
            if domain in sanitized_link:
                modified_link = sanitized_link.replace(domain, modified_domain)
                modified_links.append(modified_link)
                break

    # Send modified message if any links were processed
    if modified_links:
        cleaned_message_text = remove_links(message_text).replace("\n", " ")
        await construct_and_send_message(chat_id, username, cleaned_message_text, modified_links, update, context)

    # Handle GPT queries
    if f"@{context.bot.username}" in message_text:
        # Process the message as a direct mention
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        await ask_gpt_command(cleaned_message, update, context)
        return  # Ensure to return after processing

    # Check if the chat is private and the message does not contain a link
    if update.effective_chat.type == 'private' and not any(domain in message_text for domain in ["youtube.com", "youtu.be", "aliexpress.com/item/", "a.aliexpress.com/"]) and not any(domain in message_text for domain, modified_domain in domain_modifications.items()):
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        await ask_gpt_command(cleaned_message, update, context)
        return  # Ensure to return after processing


    # Call the random GPT response function
    await random_gpt_response(update, context)


async def random_gpt_response(update: Update, context: CallbackContext):
    """Randomly responds to a message with a 2% chance using GPT, only if the message has 5 or more words."""
    chat_id = update.message.chat_id
    message_counts[chat_id] = message_counts.get(chat_id, 0) + 1

    message_text = update.message.text

    if not message_text:
        general_logger.info("Message text is empty or None.")
        return

    word_count = len(message_text.split())  # Count the number of words
    # general_logger.info(f"Message text: '{message_text}' | Word count: {word_count}")

    if word_count < 5:  # Check if the message has less than 5 words
        # general_logger.info("Message has less than 5 words, skipping processing.")
        return  # Skip processing if not enough words

    random_value = random.random()
    current_message_count = message_counts[chat_id]
    # general_logger.info(f"Random value: {random_value} | Current message count: {current_message_count}")

    if random_value < 0.02 and current_message_count > 50:
        general_logger.info(
            f"Random GPT response triggered in chat {chat_id}: "
            f"Message: '{message_text}' | Random value: {random_value:.4f} | "
            f"Current message count: {current_message_count}"
        )

        
        # Call the GPT function
        await answer_from_gpt(message_text, update, context)
        
        # Reset message count for the chat
        message_counts[chat_id] = 0

async def handle_sticker(update: Update, context: CallbackContext):
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username
    
    general_logger.info(f"Received sticker with file_unique_id: {sticker_id}")
    
    if sticker_id == "AgAD6BQAAh-z-FM":
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)

async def shorten_url(url):
    # Create a Shortener object
    s = pyshorteners.Shortener()

    try:
        # Use a specific shortening service (e.g., TinyURL)
        short_url = s.tinyurl.short(url)
        return short_url
    except Exception as e:
        logging.error(f"Error shortening URL {url}: {str(e)}")
        return url  # Return the original URL if there's an error

async def construct_and_send_message(chat_id, username, cleaned_message_text, modified_links, update, context):
    try:
        # Log the function call for debugging
        general_logger.info(f"Constructing and sending message for chat_id: {chat_id}, username: {username}")

        # Log the cleaned message text and modified links
        general_logger.info(f"Cleaned message text: {cleaned_message_text}")
        general_logger.info(f"Modified links: {modified_links}")

        # Create the message
        modified_message = " ".join(modified_links)  # Use space to join links
        final_message = f"@{username}💬: {cleaned_message_text}\nWants to share: {modified_message}"

        # Log the final message
        general_logger.info(f"Final message: {final_message}")

        # Store the link and create keyboard
        link_hash = hashlib.md5(modified_links[0].encode()).hexdigest()[:8]
        context.bot_data[link_hash] = modified_links[0]
        # reply_markup = create_link_keyboard(modified_links[0])
        # Send modified message and delete original
        await context.bot.send_message(
            chat_id=chat_id,
            text=final_message,
            reply_to_message_id=update.message.reply_to_message.message_id if update.message.reply_to_message else None,
            # reply_markup=reply_markup
        )
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

    except Exception as e:
        general_logger.error(f"Error modifying links: {str(e)}")
        await update.message.reply_text("Sorry, an error occurred. Please try again.")

async def main():
    # Load game state at startup
    load_game_state()
    
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Add command handlers
    commands = {
        'start': start,
        'cat': cat_command,
        'gpt': ask_gpt_command,
        'analyze': analyze_command,
        'flares': screenshot_command,
        'weather': weather,
        'game': game_command,
        'endgame': end_game_command,
        'clearwords': clear_words_command,
        'hint': hint_command  # Add hint command
    }
    
    for command, handler in commands.items():
        bot.add_handler(CommandHandler(command, handler))

    # Add message handlers
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    bot.add_handler(CallbackQueryHandler(button_callback))

    # Start the screenshot scheduler
    screenshot_manager = ScreenshotManager()  # Create instance first
    asyncio.create_task(screenshot_manager.schedule_task())

    # Start bot
    await bot.run_polling()
    await bot.idle()

if __name__ == '__main__':
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(main())
