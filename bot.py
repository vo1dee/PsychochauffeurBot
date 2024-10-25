import asyncio
import logging
import nest_asyncio
import pytz

from utils import remove_links, screenshot_command, schedule_task, cat_command
from const import domain_modifications, TOKEN, ALIEXPRESS_STICKER_ID
from modules.gpt import ask_gpt_command, analyze_command
from modules.weather import weather
from modules.file_manager import general_logger, chat_logger, read_last_n_lines
from modules.user_management import restrict_user
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Apply the patch to allow nested event loops
nest_asyncio.apply()

bot = ApplicationBuilder().token(TOKEN).build()

# Set local timezone
LOCAL_TZ = pytz.timezone('Europe/Kyiv')


# Dictionary to store conversation history for each chat
conversation_history = {}

# Maximum number of previous messages to store for context
MAX_HISTORY_LENGTH = 10



async def start(update: Update, context: CallbackContext):
    general_logger.info(f"Processing /start command from user {update.message.from_user.id} in chat {update.effective_chat.id}")
    await update.message.reply_text("Hello! Send me TikTok, Twitter, or Instagram links, and I will modify them for you!")

def contains_trigger_words(message_text):
    triggers = ["5€", "€5", "5 євро", "5 єуро", "5 €", "Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)


async def handle_message(update: Update, context: CallbackContext):
    if update.message and update.message.text:
        message_text = update.message.text
        chat_id = update.message.chat_id
        username = update.message.from_user.username
        user_id = update.effective_user.id
        bot_username = context.bot.username
        chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"
        user_name = update.message.from_user.username if update.message.from_user.username else "Unknown User"

        # Check if the message is in a private chat, mentions the bot, or is a reply to the bot's message
        is_private_chat = update.effective_chat.type == 'private'
        is_mention = bot_username in message_text if message_text else False
        is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.username == bot_username
        
        chat_logger.info(f"{message_text}", extra={'chattitle': chat_title, 'username': user_name, 'chat_id': chat_id})

        # Initialize conversation history if not already present
        if chat_id not in conversation_history:
            conversation_history[chat_id] = []

        # Check for trigger words in the message
        if contains_trigger_words(message_text):
            await restrict_user(update, context)
            return

        if any(domain in message_text for domain in ["aliexpress.com/item/", "a.aliexpress.com/"]):
            await update.message.reply_sticker(sticker=ALIEXPRESS_STICKER_ID)

       # Initialize modified_links list
        modified_links = []

        # Check for specific domain links and modify them, but only if they're not already in domain_modifications
        links = message_text.split()
        for link in links:
            # Check if the link is already a modified link
            if any(link.startswith(modified_domain) for modified_domain in domain_modifications.values()):
                continue  # Skip this link if it's already modified

            # Otherwise, check for domains that need modification
            for domain, modified_domain in domain_modifications.items():
                if domain in link:
                    modified_link = link.replace(domain, modified_domain)
                    modified_links.append(modified_link)
                    break  # Move to next link after modification

        # If there are modified links, send the modified message
        if modified_links:
            cleaned_message_text = remove_links(message_text)
            modified_message = "\n".join(modified_links)
            final_message = f"@{username}💬: {cleaned_message_text}\n\nModified links:\n{modified_message}"

            if update.message.reply_to_message:
                original_message_id = update.message.reply_to_message.message_id
                await context.bot.send_message(chat_id=chat_id, text=final_message, reply_to_message_id=original_message_id)
            else:
                await context.bot.send_message(chat_id=chat_id, text=final_message)

            general_logger.info(f"Sent modified message: {final_message}")

            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            general_logger.info("Deleted the original message containing the link.")
            return  # Exit after handling the modified links

        # Handle context for GPT query
        if is_reply:
            # If it's a reply, get the text from the replied message
            replied_message_text = update.message.reply_to_message.text
            context_text = replied_message_text  # Use only the body of the message replied to
        else:
            # For mentions and direct messages, append the current message text
            context_text = message_text if is_mention or is_private_chat else None

        if context_text:
            await ask_gpt_command(context_text, update, context)  # Pass the specific context to GPT


async def handle_sticker(update: Update, context: CallbackContext):
    # Get unique ID of the sticker
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username  # Getting the sender's username

    general_logger.debug(f"Received sticker with file_unique_id: {sticker_id}")

    # Check if the sticker ID matches the specific stickers you want to react to
    if sticker_id == "AgAD6BQAAh-z-FM":  # Replace with your actual unique sticker ID
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)
    else:
        general_logger.info(f"Sticker ID {sticker_id} does not match the trigger sticker.")


# Main function to initialize and run the bot
async def main():
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CommandHandler('cat', cat_command))
    bot.add_handler(CommandHandler("gpt", ask_gpt_command))
    bot.add_handler(CommandHandler("analyze", analyze_command))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gpt_command))
    bot.add_handler(CommandHandler('flares', screenshot_command))
    bot.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))  # Add sticker handler
    
    weather_handler = CommandHandler("weather", weather)
    bot.add_handler(weather_handler)

    asyncio.create_task(schedule_task())

    # Start the bot
    await bot.run_polling()
    await bot.idle()

# Function to run the bot, handles event loop issues
async def run_bot():
    await main()

if __name__ == '__main__':
    # Create a new event loop
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(main())