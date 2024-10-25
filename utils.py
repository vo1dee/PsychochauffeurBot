import re
import requests
import imgkit
import pytz
import os
import asyncio


from datetime import datetime, time as dt_time
from telegram import Update
from telegram.ext import CallbackContext
from modules.file_manager import general_logger
from const import weather_emojis, city_translations, feels_like_emojis, SCREENSHOT_DIR


# Utility function to remove all URLs from a given text
def remove_links(text):
    return re.sub(r'http[s]?://\S+', '', text).strip()

# Function to convert country code to flag emoji
def country_code_to_emoji(country_code: str) -> str:
    return ''.join(chr(127397 + ord(c)) for c in country_code.upper())

def get_weather_emoji(weather_id: int) -> str:
    return next((emoji for id_range, emoji in weather_emojis.items() if weather_id in id_range), '🌈')

def get_feels_like_emoji(feels_like: float) -> str:
    for temp_range, emoji in feels_like_emojis.items():
        if feels_like >= temp_range.start and feels_like < temp_range.stop:
            return emoji
    return '🌈'  # Default emoji if no range matches

def get_city_translation(city: str) -> str:
    normalized = city.lower().replace(" ", "")
    return city_translations.get(normalized, city)



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
        general_logger.error(f"Error fetching cat image: {e}")


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
        general_logger.info(f"Screenshot taken at {datetime.now()}")



# Define your screenshot function
async def take_screenshot():
    adjusted_time = datetime.now(pytz.timezone('Europe/Kyiv'))
    date_str = adjusted_time.strftime('%Y-%m-%d')
    screenshot_path = os.path.join(SCREENSHOT_DIR, f'flares_{date_str}.png')

    # Check if the screenshot for the adjusted date already exists
    if os.path.exists(screenshot_path):
        general_logger.info(f"Screenshot for today already exists: {screenshot_path}")
        return screenshot_path

    config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')
    print(f"Screenshot taken at {datetime.now()}")
    try:
        # Run from_url in a non-blocking way using asyncio.to_thread
        await asyncio.to_thread(imgkit.from_url, 'https://api.meteoagent.com/widgets/v1/kindex', screenshot_path, config=config)
        general_logger.info(f"Screenshot taken and saved to: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        general_logger.error(f"Error taking screenshot: {e}")
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
        await asyncio.sleep(10800)