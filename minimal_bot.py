import asyncio
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, filters
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your actual token
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hello! I'm your bot.")

async def main():
    # Set up the application with the token
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handler for the /start command
    application.add_handler(CommandHandler('start', start))

    # Start the bot
    await application.run_polling()

if __name__ == '__main__':
    # Use asyncio.run() to manage the event loop automatically
    asyncio.run(main())

