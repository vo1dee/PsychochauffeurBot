import re
import requests
import imgkit
import pytz
import os
import asyncio
from datetime import datetime, time as dt_time, timedelta

from telegram import Update
from telegram.ext import CallbackContext
from modules.file_manager import general_logger
from const import weather_emojis, city_translations, feels_like_emojis, SCREENSHOT_DIR

# Text processing utilities
def remove_links(text: str) -> str:
    """Remove all URLs from given text."""
    return re.sub(r'http[s]?://\S+', '', text).strip()

# Weather-related utilities
def country_code_to_emoji(country_code: str) -> str:
    """Convert country code to flag emoji."""
    return ''.join(chr(127397 + ord(c)) for c in country_code.upper())

def get_weather_emoji(weather_id: int) -> str:
    """Get weather emoji based on weather ID."""
    return next((emoji for id_range, emoji in weather_emojis.items() 
                if weather_id in id_range), '🌈')

def get_feels_like_emoji(feels_like: float) -> str:
    """Get emoji based on 'feels like' temperature."""
    for temp_range, emoji in feels_like_emojis.items():
        if feels_like >= temp_range.start and feels_like < temp_range.stop:
            return emoji
    return '🌈'

def get_city_translation(city: str) -> str:
    """Get city translation from dictionary."""
    normalized = city.lower().replace(" ", "")
    return city_translations.get(normalized, city)

# Cat API command
async def cat_command(update: Update, context: CallbackContext) -> None:
    """Send random cat image."""
    try:
        response = requests.get('https://api.thecatapi.com/v1/images/search')
        if response.status_code == 200:
            cat_image_url = response.json()[0]['url']
            await update.message.reply_photo(cat_image_url)
        else:
            await update.message.reply_text('Sorry, I could not fetch a cat image at the moment.')
    except Exception as e:
        general_logger.error(f"Error fetching cat image: {e}")

# Screenshot functionality
class ScreenshotManager:
    def __init__(self):
        self.timezone = pytz.timezone('Europe/Kyiv')
        self.schedule_time = dt_time(1, 0)  # 1 AM Kyiv time
        self.config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')
        
    def get_screenshot_path(self) -> str:
        """Generate screenshot path for current date."""
        date_str = datetime.now(self.timezone).strftime('%Y-%m-%d')
        return os.path.join(SCREENSHOT_DIR, f'flares_{date_str}.png')

    async def take_screenshot(self) -> str | None:
        """Take screenshot if it doesn't exist for today."""
        screenshot_path = self.get_screenshot_path()

        if os.path.exists(screenshot_path):
            general_logger.info(f"Screenshot for today already exists: {screenshot_path}")
            return screenshot_path

        general_logger.info(f"Taking screenshot at {datetime.now()}")
        try:
            await asyncio.to_thread(
                imgkit.from_url, 
                'https://api.meteoagent.com/widgets/v1/kindex', 
                screenshot_path, 
                config=self.config
            )
            general_logger.info(f"Screenshot taken and saved to: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            general_logger.error(f"Error taking screenshot: {e}")
            return None

    async def schedule_task(self) -> None:
        """Schedule daily screenshot task."""
        while True:
            now = datetime.now(self.timezone)
            
            # Calculate next run time
            tomorrow = now.date() + timedelta(days=1)
            next_run = datetime.combine(tomorrow, self.schedule_time)
            next_run = self.timezone.localize(next_run)
            
            # Calculate and log sleep duration
            sleep_seconds = (next_run - now).total_seconds()
            general_logger.info(f"Next screenshot scheduled for: {next_run}")
            
            # Sleep until next run
            await asyncio.sleep(sleep_seconds)
            await self.take_screenshot()

# Command handlers
async def screenshot_command(update: Update, context: CallbackContext) -> None:
    """Handle /screenshot command."""
    try:
        screenshot_manager = ScreenshotManager()
        screenshot_path = await screenshot_manager.take_screenshot()
        if screenshot_path:
            with open(screenshot_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, 
                    photo=photo
                )
    except Exception as e:
        general_logger.error(f"Error in screenshot command: {e}")

# Initialize screenshot manager for scheduling
screenshot_manager = ScreenshotManager()

def schedule_screenshot():
    """Schedule screenshot task."""
    asyncio.create_task(screenshot_manager.take_screenshot())

async def schedule_task():
    """Main scheduling task."""
    await screenshot_manager.schedule_task()
