import asyncio
import os
import logging
import nest_asyncio
import random
import pytz
import requests
import imgkit
#import schedule
#import time
#import subprocess

from utils import remove_links, country_code_to_emoji, get_weather_emoji, get_city_translation, get_feels_like_emoji
from const import city_translations, domain_modifications, OPENWEATHER_API_KEY, DISCORD_WEBHOOK_URL, TOKEN, \
    SCREENSHOT_DIR, ALIEXPRESS_STICKER_ID

from datetime import datetime, timedelta, time as dt_time
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ContextTypes
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Apply the patch to allow nested event loops
nest_asyncio.apply()




log_file_path = '/var/log/bot.log'

# Set up a rotating file handler
handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3)  # 5 MB per log file

logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# Load environment variables from .env file
load_dotenv()

OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = ApplicationBuilder().token(TOKEN).build()

# Set local timezone
LOCAL_TZ = pytz.timezone('Europe/Kyiv')



async def start(update: Update, context: CallbackContext):
    logging.info(f"Processing /start command from user {update.message.from_user.id} in chat {update.effective_chat.id}")
    await update.message.reply_text("Hello! Send me TikTok, Twitter, or Instagram links, and I will modify them for you!")

# Function to fetch weather data from OpenWeatherMap
async def get_weather(city: str) -> str:
    # Check if the Ukrainian city name exists in the translation dictionary
    city = get_city_translation(city)
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",  # You can change to 'imperial' if needed
        "lang": "uk"  # Setting language to Ukrainian
    }
    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get("cod") != 200:
            logging.error(f"Weather API error response: {data}")
            return f"Error: {data.get('message', 'Unknown error')}"


        # Ensure the weather data structure is correct
        weather = data.get("weather")
        if not weather:
            return "Failed to retrieve weather data: Weather data not available"

        # Parse the weather data
        city_name = data.get("name", "Unknown city")
        country_code = data["sys"].get("country", "Unknown country")  # Extract the country code
        weather_id = weather[0].get("id", 0)  # Get weather condition ID
        weather_description = weather[0].get("description", "No description")
        temp = round(data["main"].get("temp", "N/A"))  # Round the temperature
        feels_like = round(data["main"].get("feels_like", "N/A"))  # Round "feels like" temperature
        
        # Get the corresponding emoji for the weather condition
        weather_emoji = get_weather_emoji(weather_id)
        
        # Convert country code to flag emoji
        country_flag = country_code_to_emoji(country_code)

        # Get the appropriate emoji based on "feels like" temperature
        feels_like_emoji = get_feels_like_emoji(feels_like)

        # Return weather information with the emoji, country code, and flag
        return (f"Погода в {city_name}, {country_code} {country_flag}:\n"
                f"{weather_emoji} {weather_description.capitalize()}\n"
                f"🌡️ Температура: {temp}°C\n"
                f"{feels_like_emoji} Відчувається як: {feels_like}°C")
    except Exception as e:
        logging.error(f"Error fetching weather data: {e}")
        return f"Failed to retrieve weather data: {str(e)}"

async def cat_command(update: Update, context: CallbackContext):
    try:
        response = requests.get('https://api.thecatapi.com/v1/images/search')
        if response.status_code == 200:
            cat_data = response.json()
            cat_image_url = cat_data[0]['url']
            await update.message.reply_photo(cat_image_url)
        else:
            await update.message.reply_text('Sorry, I could not fetch a cat image at the moment.')
    except Exception as e:
        logging.error(f"Error fetching cat image: {e}")


def contains_trigger_words(message_text):
    triggers = ["5€", "€5", "5 євро", "5 єуро", "5 €", "Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)

async def handle_message(update: Update, context: CallbackContext):
    if update.message and update.message.text:
        message_text = update.message.text
        chat_id = update.message.chat_id
        username = update.message.from_user.username

        logging.info(f"Processing message: {message_text}")

        # Check for trigger words in the message
        if contains_trigger_words(message_text):
            await restrict_user(update, context)
            return

        if any(domain in message_text for domain in ["aliexpress.com/item/", "a.aliexpress.com/"]):
            # Reply to the message containing the link by sending a sticker
            await update.message.reply_sticker(sticker=ALIEXPRESS_STICKER_ID)

        # Initialize modified_links list
        modified_links = []

        # Check for specific domain links and modify them
        if any(domain in message_text for domain in ["tiktok.com", "twitter.com", "x.com", "instagram.com"]):
            links = message_text.split()  # This initializes 'links' only if the condition is true
            for link in links:
                # Check if the link is already modified (exists in the modified domains)
                if any(modified_domain in link for modified_domain in domain_modifications.values()):
                    break
                # Otherwise, proceed to modify the link
                for domain, modified_domain in domain_modifications.items():
                    if domain in link:
                        modified_link = link.replace(domain, modified_domain)
                        modified_links.append(modified_link)
                        break

        # If there are modified links, send the modified message
        if modified_links:
            cleaned_message_text = remove_links(message_text)
            modified_message = "\n".join(modified_links)
            final_message = f"@{username}💬: {cleaned_message_text}\n\nModified links:\n{modified_message}"

            # Check if the original message is a reply
            if update.message.reply_to_message:
                original_message_id = update.message.reply_to_message.message_id
                # Send the modified message as a reply to the original message
                await context.bot.send_message(chat_id=chat_id, text=final_message, reply_to_message_id=original_message_id)
            else:
                # If not a reply, send the modified message normally
                await context.bot.send_message(chat_id=chat_id, text=final_message)

            logging.info(f"Sent modified message: {final_message}")

            # Delete the original message (your message containing the link)
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            logging.info("Deleted the original message containing the link.")

async def restrict_user(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user_id = update.message.from_user.id
    username = update.message.from_user.username  # Get the username for the reply message

    # Check if the user is the chat owner or an admin
    chat_member = await context.bot.get_chat_member(chat.id, user_id)
    if chat_member.status in ["administrator", "creator"]:
        logging.info("Cannot restrict an admin or chat owner.")
        return

    if chat.type == "supergroup":
        try:
            restrict_duration = random.randint(1, 15)  # Restriction duration in minutes
            permissions = ChatPermissions(can_send_messages=False)

            # Get current time in EEST
            until_date = datetime.now(LOCAL_TZ) + timedelta(minutes=restrict_duration)

            # Restrict user in the chat
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )

            # Notify user with a custom sticker
            sticker_id = "CAACAgQAAxkBAAEt8tNm9Wc6jYEQdAgQzvC917u3e8EKPgAC9hQAAtMUCVP4rJSNEWepBzYE"
            await update.message.reply_text(f"Вас запсихопаркували на {restrict_duration} хвилин. Ви не можете надсилати повідомлення.")
            await context.bot.send_sticker(chat_id=chat.id, sticker=sticker_id)
            logging.info(f"Restricted user {user_id} for {restrict_duration} minutes.")

        except Exception as e:
            logging.error(f"Failed to restrict user: {e}")
    else:
        await update.message.reply_text("This command is only available in supergroups.")

async def handle_sticker(update: Update, context: CallbackContext):
    # Get unique ID of the sticker
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username  # Getting the sender's username

    logging.debug(f"Received sticker with file_unique_id: {sticker_id}")

    # Check if the sticker ID matches the specific stickers you want to react to
    if sticker_id == "AgAD6BQAAh-z-FM":  # Replace with your actual unique sticker ID
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)
    else:
        logging.info(f"Sticker ID {sticker_id} does not match the trigger sticker.")


# Command handler for /weather <city>
async def weather(update: Update, context: CallbackContext):
    if context.args:
        city = " ".join(context.args)
        weather_info = await get_weather(city)
        if update.message:
            await update.message.reply_text(weather_info)
    else:
        await update.message.reply_text("Будь ласка, вкажіть назву міста.")



# Screenshot command to capture the current state of a webpage
async def screenshot_command(update, context):
    try:
        # Make sure to await the coroutine and get the file path
        screenshot_path = await take_screenshot()
        
        # Open the file path correctly
        with open(screenshot_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)
    except Exception as e:
        # Log the error or send a message indicating the issue
        logging.info(f"Screenshot taken at {datetime.now()}")



# Define your screenshot function
async def take_screenshot():
    adjusted_time = datetime.now(pytz.timezone('Europe/Kyiv'))
    date_str = adjusted_time.strftime('%Y-%m-%d')
    screenshot_path = os.path.join(SCREENSHOT_DIR, f'flares_{date_str}.png')

    # Check if the screenshot for the adjusted date already exists
    if os.path.exists(screenshot_path):
        logging.info(f"Screenshot for today already exists: {screenshot_path}")
        return screenshot_path

    config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')
    print(f"Screenshot taken at {datetime.now()}")
    try:
        # Run from_url in a non-blocking way using asyncio.to_thread
        await asyncio.to_thread(imgkit.from_url, 'https://api.meteoagent.com/widgets/v1/kindex', screenshot_path, config=config)
        logging.info(f"Screenshot taken and saved to: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logging.error(f"Error taking screenshot: {e}")
        return None

    
def schedule_screenshot():
    # Schedule the coroutine using `asyncio.create_task`.
    asyncio.create_task(take_screenshot())

async def schedule_task():
    # Set the time for 01:00 Kyiv time every day
    kyiv_time = pytz.timezone('Europe/Kyiv')
    schedule_time = dt_time(1, 0)  # 1 AM Kyiv time
    last_run_date = None  # To keep track of the last run date

    while True:
        # Get the current time in Kyiv timezone
        now = datetime.now(kyiv_time)
        
        # Check if it's past 1 AM and the task hasn't been run today
        if now.time() >= schedule_time and last_run_date != now.date():
            await take_screenshot()
            last_run_date = now.date()  # Update the last run date to today
            
        # Sleep for an hour before checking again
        await asyncio.sleep(3600)

# Main function to initialize and run the bot
async def main():
    # Add handlers outside the reminders loop
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message_for_links))
    bot.add_handler(CommandHandler('flares', screenshot_command))
    bot.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))  # Add sticker handler
    weather_handler = CommandHandler("weather", weather)
    bot.add_handler(weather_handler)
    bot.add_handler(CommandHandler('cat', cat_command))



    asyncio.create_task(schedule_task())


    # Start the bot
    await bot.run_polling()
    await bot.idle()
    # await schedule_task()  # Await the coroutine

# Function to run the bot, handles event loop issues
async def run_bot():
    await main()

if __name__ == '__main__':
    # Create a new event loop
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(main())