import asyncio
import logging
import nest_asyncio
import pytz
import random

from utils import remove_links, screenshot_command, schedule_task, cat_command, ScreenshotManager, game_state, game_command, end_game_command, clear_words_command, hint_command, load_game_state
from const import domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID
from modules.gpt import ask_gpt_command, analyze_command 
from modules.weather import weather
from modules.file_manager import general_logger, chat_logger
from modules.user_management import restrict_user
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Apply the patch to allow nested event loops
nest_asyncio.apply()
LOCAL_TZ = pytz.timezone('Europe/Kyiv')

def contains_trigger_words(message_text):
    triggers = ["5€", "€5", "5 євро", "5 єуро", "5 €", "Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)

async def start(update: Update, context: CallbackContext):
    general_logger.info(f"Processing /start command from user {update.message.from_user.id} in chat {update.effective_chat.id}")
    await update.message.reply_text("Hello! Send me TikTok, Twitter, or Instagram links, and I will modify them for you!")

async def handle_message(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"

    # Log message with extra fields
    chat_logger.info(f"User message: {message_text}", extra={'chat_id': chat_id, 'chattitle': chat_title, 'username': username})

    # Check message conditions
    is_private_chat = update.effective_chat.type == 'private'
    is_mention = context.bot.username in message_text
    is_reply = update.message.reply_to_message is not None

    # Handle trigger words
    if contains_trigger_words(message_text):
        await restrict_user(update, context)
        return

    # Handle AliExpress links
    if any(domain in message_text for domain in ["aliexpress.com/item/", "a.aliexpress.com/"]):
        await update.message.reply_sticker(sticker=ALIEXPRESS_STICKER_ID)

    # Handle domain modifications
    modified_links = []
    for link in message_text.split():
        if any(link.startswith(modified_domain) for modified_domain in domain_modifications.values()):
            continue
        
        for domain, modified_domain in domain_modifications.items():
            if domain in link:
                modified_links.append(link.replace(domain, modified_domain))
                break

    if modified_links:
        cleaned_message_text = remove_links(message_text)
        modified_message = "\n".join(modified_links)
        final_message = f"@{username}💬: {cleaned_message_text}\n\nModified links:\n{modified_message}"

        reply_to_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
        await context.bot.send_message(chat_id=chat_id, text=final_message, reply_to_message_id=reply_to_id)
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
        general_logger.info(f"Processed modified links: {final_message}")
        return

    # Handle GPT queries
    if is_mention or is_private_chat:
        # Check if this is a reply to a modified link message
        if is_reply and update.message.reply_to_message.text:
            # Check if the replied message contains "Modified links:"
            if "Modified links:" in update.message.reply_to_message.text:
                return  # Skip GPT processing for replies to modified links
        cleaned_message = message_text.replace(f"@{context.bot.username}", "").strip()
        cleaned_message = update.message.text  # Assuming this is how you get the message
        await ask_gpt_command(cleaned_message, update, context)

    # Call the random GPT response function
    await random_gpt_response(update, context)


async def random_gpt_response(update: Update, context: CallbackContext):
    """Randomly responds to a message with a 2% chance using GPT."""
    if random.random() < 0.02:
        message_text = update.message.text
        general_logger.info(f"Random message to reply to: {message_text}")
        await ask_gpt_command(message_text, update, context)

async def handle_sticker(update: Update, context: CallbackContext):
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username
    
    general_logger.debug(f"Received sticker with file_unique_id: {sticker_id}")
    
    if sticker_id == "AgAD6BQAAh-z-FM":
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)

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
