import re
import requests
import imgkit
import pytz
import os
import asyncio
import aiohttp
import csv
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, List, Dict, Any, Union
import logging

from telegram import Update
from telegram.ext import CallbackContext
# Avoid running code at module import time
from modules.logger import init_error_handler, error_logger, LOG_DIR, general_logger
from modules.const import (
    weather_emojis, city_translations, feels_like_emojis, 
    SCREENSHOT_DIR, DATA_DIR, LOG_DIR, DOWNLOADS_DIR
)
from modules.gpt import ask_gpt_command

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')   
CITY_DATA_FILE = os.path.join(DATA_DIR, 'user_locations.csv')
WEATHER_API_URL = 'https://api.meteoagent.com/widgets/v1/kindex'
WKHTMLTOIMAGE_PATH = '/usr/bin/wkhtmltoimage'

# Define imgkit options once to avoid duplication
IMGKIT_OPTIONS = {
    'quality': '100',
    'format': 'png',
    'width': '1024',  # Set a fixed width
    'enable-javascript': None,
    'javascript-delay': '1000',  # Wait 1 second for JavaScript
    'custom-header': [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    ]
}

# Game state
game_state: Dict[int, str] = {}

def ensure_directory(path: str) -> None:
    """
    Ensure a directory exists.
    
    Args:
        path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)

def init_directories() -> None:
    """Initialize necessary directories for the application."""
    directories = [LOG_DIR, DATA_DIR, DOWNLOADS_DIR, SCREENSHOT_DIR]
    for directory in directories:
        ensure_directory(directory)

# Text processing utilities
def remove_links(text: str) -> str:
    """
    Remove all URLs from the given text.
    
    Args:
        text: Text to process
        
    Returns:
        str: Text with URLs removed
    """
    return re.sub(r'http[s]?://\S+', '', text).strip()

def extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text using regex pattern.
    
    Args:
        text: Text to extract URLs from
        
    Returns:
        List[str]: List of URLs found in the text
    """
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

# Weather-related utilities
def country_code_to_emoji(country_code: str) -> str:
    """
    Convert country code to flag emoji.
    
    Args:
        country_code: Two-letter country code
        
    Returns:
        str: Flag emoji representation
    """
    return ''.join(chr(127397 + ord(c)) for c in country_code.upper())

def get_weather_emoji(weather_id: int) -> str:
    """
    Get weather emoji based on weather ID.
    
    Args:
        weather_id: Weather condition ID
        
    Returns:
        str: Appropriate emoji for the weather condition
    """
    return next((emoji for id_range, emoji in weather_emojis.items()
                if weather_id in id_range), '🌈')

def get_feels_like_emoji(feels_like: float) -> str:
    """
    Get emoji based on 'feels like' temperature.
    
    Args:
        feels_like: Temperature in Celsius
        
    Returns:
        str: Appropriate emoji for the temperature
    """
    for temp_range, emoji in feels_like_emojis.items():
        if feels_like >= temp_range.start and feels_like < temp_range.stop:
            return emoji
    return '🌈'

def get_city_translation(city: str) -> str:
    """
    Get city translation from dictionary.
    
    Args:
        city: City name to translate
        
    Returns:
        str: Translated city name or original if not found
    """
    normalized = city.lower().replace(" ", "")
    return city_translations.get(normalized, city)

def get_last_used_city(user_id: int) -> Optional[str]:
    """
    Retrieve user's last used city.
    
    Args:
        user_id: User ID
        
    Returns:
        str: City name or None if not found
    """
    try:
        with open(CITY_DATA_FILE, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['user_id'] == str(user_id):
                    city = row['city']
                    return "Kyiv" if city.lower() == "kiev" else city
    except FileNotFoundError:
        general_logger.warning(f"City data file not found: {CITY_DATA_FILE}")
        return None
    except Exception as e:
        general_logger.error(f"Error reading city data: {e}")
        return None
    return None

# Cat API command
async def cat_command(update: Update, context: CallbackContext) -> None:
    """
    Send random cat image.
    
    Args:
        update: Telegram update
        context: Callback context
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.thecatapi.com/v1/images/search') as response:
                if response.status == 200:
                    data = await response.json()
                    cat_image_url = data[0]['url']
                    await update.message.reply_photo(cat_image_url)
                else:
                    await update.message.reply_text('Sorry, I could not fetch a cat image at the moment.')
    except Exception as e:
        general_logger.error(f"Error fetching cat image: {e}")
        await update.message.reply_text('An error occurred while fetching a cat image.')

# Screenshot functionality
class ScreenshotManager:
    _instance = None  # Singleton instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.timezone = pytz.timezone('Europe/Kyiv')
            self.schedule_time = dt_time(2, 0)  # 2 AM Kyiv time
            self.config = imgkit.config(wkhtmltoimage=WKHTMLTOIMAGE_PATH)
            self._initialized = True

    def get_screenshot_path(self) -> str:
        """
        Generate screenshot path for current date.
        
        Returns:
            str: Path to the screenshot file
        """
        kyiv_time = datetime.now(self.timezone)
        date_str = kyiv_time.strftime('%Y-%m-%d')
        return os.path.join(SCREENSHOT_DIR, f'flares_{date_str}_kyiv.png')

    def get_latest_screenshot(self) -> Optional[str]:
        """
        Get the path to the latest screenshot.
        
        Returns:
            Optional[str]: Path to screenshot or None if not found
        """
        screenshot_path = self.get_screenshot_path()
        if os.path.exists(screenshot_path):
            return screenshot_path
        return None

    async def take_screenshot(self, url: str, output_path: str) -> Optional[str]:
        """
        Take a screenshot of the given URL and save it to the output path.
        
        Args:
            url: URL to capture
            output_path: Path to save the screenshot
            
        Returns:
            Optional[str]: Path to saved screenshot or None on failure
        """
        try:
            # Run imgkit in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                lambda: imgkit.from_url(url, output_path, options=IMGKIT_OPTIONS, config=self.config)
            )
            return output_path
        except Exception as e:
            error_logger.error(f"Error taking screenshot: {str(e)}")
            return None

    async def schedule_task(self) -> None:
        """
        Schedule a screenshot task every 6 hours.
        
        This is a long-running task that should be started at application startup.
        """
        while True:
            try:
                # Get current time in Kyiv timezone
                kyiv_now = datetime.now(self.timezone)

                # Create target time for the next screenshot (6 hours from now)
                target_time = kyiv_now + timedelta(hours=6)

                # Convert target time to server's local time for sleep calculation
                server_now = datetime.now(pytz.UTC).astimezone()  # Get server's local time
                target_time_local = target_time.astimezone(server_now.tzinfo)

                # Calculate sleep duration based on server time
                sleep_seconds = (target_time_local - server_now).total_seconds()
                general_logger.info(f"Current server time: {server_now}")
                general_logger.info(f"Current Kyiv time: {kyiv_now}")
                general_logger.info(f"Next screenshot scheduled for: {target_time} (Kyiv time)")
                general_logger.info(f"Sleep duration: {sleep_seconds} seconds")

                # Sleep until next run
                await asyncio.sleep(max(1, sleep_seconds))  # Ensure positive sleep time
                await self.take_screenshot(WEATHER_API_URL, self.get_screenshot_path())
            except Exception as e:
                general_logger.error(f"Error in screenshot scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry on error

# Command handlers
async def screenshot_command(update: Update, context: CallbackContext) -> None:
    """
    Handle /screenshot command.
    
    Args:
        update: Telegram update
        context: Callback context
    """
    try:
        manager = ScreenshotManager()
        # Try to get today's existing screenshot first
        screenshot_path = manager.get_latest_screenshot()

        # If no screenshot exists for today, take a new one
        if not screenshot_path:
            await update.message.reply_text("Taking a new screenshot, please wait...")
            screenshot_path = await manager.take_screenshot(
                WEATHER_API_URL,
                manager.get_screenshot_path()
            )

        if screenshot_path:
            with open(screenshot_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption="Weather data screenshot"
                )
        else:
            await update.message.reply_text("Failed to generate screenshot. Please try again later.")
    except Exception as e:
        general_logger.error(f"Error in screenshot command: {e}")
        await update.message.reply_text("An error occurred while processing your request.")


# Initialization and main functions
def setup_bot():
    """
    Set up the bot and initialize all necessary components.
    
    Returns:
        None
    """
    # Initialize directories
    init_directories()
    
    # Log startup
    general_logger.info("Bot initialized successfully")

async def start_background_tasks():
    """
    Start all background tasks.
    
    This should be called when the bot starts.
    """
    # Start screenshot scheduler
    manager = ScreenshotManager()
    asyncio.create_task(manager.schedule_task())
    general_logger.info("Background tasks started")

def ensure_city_data_file():
    """Ensure the city data file exists in the root/data directory."""
    city_data_path = os.path.join(PROJECT_ROOT, 'data', 'user_locations.csv')
    
    if not os.path.exists(city_data_path):
        logging.warning(f"City data file not found: {city_data_path}")
        
        # Create the data directory if it doesn't exist
        os.makedirs(os.path.dirname(city_data_path), exist_ok=True)
        
        # Create the user_locations.csv file with headers
        with open(city_data_path, 'w', encoding='utf-8') as f:
            f.write("city_name,country_code\n")  # Add headers or initial data
        logging.info(f"Created city data file: {city_data_path}")
    else:
        logging.info(f"City data file already exists: {city_data_path}")

# Call this function during initialization
ensure_city_data_file()

# Only run setup code if this module is the main script
if __name__ == "__main__":
    setup_bot()
    # This would normally be run in the main application:
    # asyncio.run(start_background_tasks())