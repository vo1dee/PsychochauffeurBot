import os
import re
import logging
import httpx
import random
import pytz
import requests
import json
import imgkit
import asyncio
import nest_asyncio

from utils import remove_links, country_code_to_emoji, get_weather_emoji, get_city_translation, get_feels_like_emoji
from const import domain_modifications, ALIEXPRESS_STICKER_ID

from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv


# Apply the patch to allow nested event loops
nest_asyncio.apply()

# Configure logging to an external file
logging.basicConfig(
    filename='bot.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables from .env file
load_dotenv()

OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = ApplicationBuilder().token(TOKEN).build()

# Set local timezone
LOCAL_TZ = pytz.timezone('Europe/Kyiv')

async def start(update: Update, context: CallbackContext):
    logging.info("Received /start command.")
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

async def handle_message(update: Update, context: CallbackContext):
    if update.message and update.message.text:
        message_text = update.message.text
        chat_id = update.message.chat_id
        username = update.message.from_user.username

        logging.info(f"Processing message: {message_text}")

        if any(trigger in message_text for trigger in ["5€", "€5", "5 євро", "5 єуро", "5 €"]):
            await restrict_user(update, context)
            return

        if any(domain in message_text for domain in ["aliexpress.com/item/", "a.aliexpress.com/"]):
            await update.message.reply_sticker(sticker=ALIEXPRESS_STICKER_ID)

        modified_links = []
        if any(domain in message_text for domain in ["tiktok.com", "twitter.com", "x.com", "instagram.com"]):
            links = message_text.split()
            for link in links:
                for domain, modified_domain in domain_modifications.items():
                    if domain in link:
                        modified_link = link.replace(domain, modified_domain)
                        modified_links.append(modified_link)
                        break

        if modified_links:
            cleaned_message_text = remove_links(message_text)
            modified_message = "\n".join(modified_links)
            final_message = f"@{username}💬: {cleaned_message_text}\n\nModified links:\n{modified_message}"

            if update.message.reply_to_message:
                original_message_id = update.message.reply_to_message.message_id
                await context.bot.send_message(chat_id=chat_id, text=final_message, reply_to_message_id=original_message_id)
            else:
                await context.bot.send_message(chat_id=chat_id, text=final_message)

            logging.info(f"Sent modified message: {final_message}")
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

async def restrict_user(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user_id = update.message.from_user.id

    chat_member = await context.bot.get_chat_member(chat.id, user_id)
    if chat_member.status in ["administrator", "creator"]:
        logging.info("Cannot restrict an admin or chat owner.")
        return

    if chat.type == "supergroup":
        try:
            restrict_duration = random.randint(1, 15)
            permissions = ChatPermissions(can_send_messages=False)
            until_date = datetime.now(LOCAL_TZ) + timedelta(minutes=restrict_duration)

            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )

            await update.message.reply_text(f"Вас запсихопаркували на {restrict_duration} хвилин.")
            logging.info(f"Restricted user {user_id} for {restrict_duration} minutes.")
        except Exception as e:
            logging.error(f"Failed to restrict user: {e}")
    else:
        await update.message.reply_text("This command is only available in supergroups.")

async def weather_command(update: Update, context: CallbackContext):
    if context.args:
        city = " ".join(context.args)
        weather_info = await get_weather(city)
        await update.message.reply_text(weather_info)
    else:
        await update.message.reply_text("Please provide a city name. Usage: /weather <city>")


# Screenshot command to capture the current state of a webpage
async def screenshot_command(update: Update, context: CallbackContext):
    screenshot_path = await asyncio.to_thread(take_screenshot)

    if screenshot_path:
        chat_id = update.effective_chat.id
        with open(screenshot_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo)
    else:
        await update.message.reply_text("Failed to take screenshot. Please try again later.")

def take_screenshot():
    # Get the current time in UTC or EEST as needed
    adjusted_time = datetime.now(pytz.timezone('Europe/Kyiv'))
    date_str = adjusted_time.strftime('%Y-%m-%d')
    screenshot_path = os.path.join(SCREENSHOT_DIR, f'flares_{date_str}.png')

    # Check if the screenshot for the adjusted date already exists
    if os.path.exists(screenshot_path):
        logging.info(f"Screenshot for today already exists: {screenshot_path}")
        return screenshot_path

    config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')

    try:
        # Capture the screenshot of the desired webpage
        imgkit.from_url('https://api.meteoagent.com/widgets/v1/kindex', screenshot_path, config=config)
        logging.info(f"Screenshot taken and saved to: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logging.error(f"Error taking screenshot: {e}")
        return None


async def main():
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CommandHandler('weather', weather_command))
    bot.add_handler(CommandHandler('cat', cat_command))
    bot.add_handler(CommandHandler('flares', flares))  # Adding the flares command
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    await bot.run_polling()

if __name__ == '__main__':
    # Use the current event loop and run the main function
    asyncio.run(main())