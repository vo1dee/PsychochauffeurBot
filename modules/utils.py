import re
import imgkit
import pytz
import os
import asyncio
import aiohttp
import csv
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, Any, List, Dict
import logging

from telegram import Update
from telegram.ext import CallbackContext
# Avoid running code at module import time
from modules.logger import error_logger, LOG_DIR, general_logger
from modules.const import (
    Weather, Config, DATA_DIR, DOWNLOADS_DIR
)
from config.config_manager import ConfigManager
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

# Initialize config manager
config_manager = ConfigManager()

class MessageCounter:
    """Manages message counts per chat for random GPT responses."""
    counts: Dict[int, int]
    def __init__(self) -> None:
        self.counts = {}

    def increment(self, chat_id: int) -> int:
        """Increment message count for a chat and return new count."""
        self.counts[chat_id] = self.counts.get(chat_id, 0) + 1
        return self.counts[chat_id]

    def reset(self, chat_id: int) -> None:
        """Reset message count for a chat."""
        self.counts[chat_id] = 0


class ChatHistoryManager:
    """Manages chat history for context in GPT responses."""
    chat_histories: Dict[int, List[Dict[str, Any]]]
    def __init__(self) -> None:
        self.chat_histories = {}  # chat_id -> list of messages

    def add_message(self, chat_id: int, message: Dict[str, Any]) -> None:
        """Add a message to chat history."""
        if chat_id not in self.chat_histories:
            self.chat_histories[chat_id] = []
        
        self.chat_histories[chat_id].append(message)
        
        # Keep only the last 50 messages to prevent memory issues
        if len(self.chat_histories[chat_id]) > 50:
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-50:]

    def get_history(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get chat history for a specific chat."""
        return self.chat_histories.get(chat_id, [])

    def clear_history(self, chat_id: int) -> None:
        """Clear chat history for a specific chat."""
        if chat_id in self.chat_histories:
            del self.chat_histories[chat_id]


# Global instances
message_counter = MessageCounter()
chat_history_manager = ChatHistoryManager()

def ensure_directory(path: str) -> None:
    """
    Ensure a directory exists.
    
    Args:
        path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)

def ensure_directory_permissions(path: str) -> None:
    """
    Ensure a directory has proper permissions.
    
    Args:
        path: Directory path to set permissions for
    """
    try:
        # Get the current user's uid and gid
        uid = os.getuid()
        gid = os.getgid()
        
        # Set ownership
        os.chown(path, uid, gid)
        
        # Set permissions (750 for directories)
        os.chmod(path, 0o750)
        
        general_logger.info(f"Set permissions for directory: {path}")
    except Exception as e:
        error_logger.error(f"Error setting permissions for {path}: {e}")
        raise

def init_directories() -> None:
    """Initialize necessary directories for the application."""
    directories = [LOG_DIR, DATA_DIR, DOWNLOADS_DIR, Config.SCREENSHOT_DIR]
    for directory in directories:
        try:
            # First ensure directory exists
            ensure_directory(directory)
            # Then set permissions
            ensure_directory_permissions(directory)
        except Exception as e:
            error_logger.error(f"Error initializing directory {directory}: {e}")
            raise

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
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
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

# Weather-related utilities (now async)
async def get_weather_emoji(weather_id: int) -> str:
    """
    Get weather emoji based on weather ID. Use config if available, else fallback to CONDITION_EMOJIS from const.
    """
    weather_config = await config_manager.get_config("weather_config", None, None)
    config_emojis = weather_config.get("CONDITION_EMOJIS", {})
    emojis = config_emojis if config_emojis else Weather.CONDITION_EMOJIS
    general_logger.info(f"CONDITION_EMOJIS used: {emojis}")
    for rng, emoji in emojis.items():
        if weather_id in rng:
            return emoji
    return '🌈'

async def get_feels_like_emoji(feels_like: float) -> str:
    """
    Get emoji based on 'feels like' temperature. Use config if available, else fallback to FEELS_LIKE_EMOJIS from const.
    """
    weather_config = await config_manager.get_config("weather_config", None, None)
    config_emojis = weather_config.get("FEELS_LIKE_EMOJIS", {})
    emojis = config_emojis if config_emojis else Weather.FEELS_LIKE_EMOJIS
    general_logger.info(f"FEELS_LIKE_EMOJIS used: {emojis}")
    feels_like_int = int(round(feels_like))
    for rng, emoji in emojis.items():
        if feels_like_int in rng:
            return emoji
    return '🌈'

async def get_humidity_emoji(humidity: int) -> str:
    """
    Get emoji based on humidity percentage. Use config if available, else fallback to HUMIDITY_EMOJIS from const.
    """
    weather_config = await config_manager.get_config("weather_config", None, None)
    config_emojis = weather_config.get("HUMIDITY_EMOJIS", {})
    emojis = config_emojis if config_emojis else Weather.HUMIDITY_EMOJIS
    general_logger.info(f"HUMIDITY_EMOJIS used: {emojis}")
    for rng, emoji in emojis.items():
        if humidity in rng:
            return emoji
    return '💧'

async def get_city_translation(city: str) -> str:
    """
    Get city translation from dictionary.
    """
    weather_config = await config_manager.get_config("weather_config", None, None)
    config_translations = weather_config.get("CITY_TRANSLATIONS", {})
    city_translations = config_translations if config_translations else Weather.CITY_TRANSLATIONS
    normalized = city.lower().replace(" ", "")
    return city_translations.get(normalized, city)

# get_last_used_city wrapper to use local CITY_DATA_FILE
# Now robust to empty/invalid fields

def get_last_used_city(user_id: int, chat_id: Optional[int] = None) -> Optional[str]:
    """
    Retrieve the last city set by a user, preferring chat-specific entry.
    Uses CITY_DATA_FILE for data storage. Skips rows with invalid user_id/chat_id.
    """
    try:
        with open(CITY_DATA_FILE, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            # Prefer chat-specific entry
            if chat_id is not None:
                for row in reader:
                    try:
                        uid = int(row.get('user_id', -1))
                        cid = int(row.get('chat_id', -1))
                    except (ValueError, TypeError):
                        continue
                    if uid == user_id and cid == chat_id:
                        city = row.get('city')
                        return "Kyiv" if city and city.lower() == "kiev" else city
            # Fallback to user default
            csvfile.seek(0)
            for row in reader:
                try:
                    uid = int(row.get('user_id', -1))
                    cid = row.get('chat_id')
                except (ValueError, TypeError):
                    continue
                if uid == user_id and (cid is None or cid == '' or cid == 'None'):
                    city = row.get('city')
                    return "Kyiv" if city and city.lower() == "kiev" else city
    except Exception as e:
        error_logger.error(f"Error reading city data: {e}")
        return None
    return None

# Cat API command
async def cat_command(update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
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
                    if update.message:
                        await update.message.reply_photo(cat_image_url)
                else:
                    if update.message:
                        await update.message.reply_text('Sorry, I could not fetch a cat image at the moment.')
    except Exception as e:
        error_logger.error(f"Error fetching cat image: {e}")
        if update.message:
            await update.message.reply_text('An error occurred while fetching a cat image.')

# Screenshot functionality
class ScreenshotManager:
    _instance: Optional['ScreenshotManager'] = None
    _initialized: bool
    timezone: Any
    schedule_time: dt_time
    config: Any
    def __new__(cls) -> 'ScreenshotManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self.timezone = pytz.timezone('Europe/Kyiv')
            self.schedule_time = dt_time(2, 0)  # 2 AM Kyiv time
            self.config = imgkit.config(wkhtmltoimage=WKHTMLTOIMAGE_PATH)
            self._initialized = True

    def get_screenshot_path(self) -> str:
        """Constructs a path for storing screenshots with a timestamp."""
        # Ensure timezone is correctly handled
        if not self.timezone:
            self.timezone = pytz.timezone('Europe/Kyiv') # Fallback
        
        kyiv_time = datetime.now(self.timezone)
        date_str = kyiv_time.strftime('%Y-%m-%d')
        return os.path.join(Config.SCREENSHOT_DIR, f'flares_{date_str}_kyiv.png')

    def get_latest_screenshot(self) -> Optional[str]:
        """
        Get the latest screenshot from the screenshot directory.
        """
        try:
            files = [os.path.join(Config.SCREENSHOT_DIR, f) for f in os.listdir(Config.SCREENSHOT_DIR) if f.endswith('.png')]
            if not files:
                return None
            latest_file = max(files, key=os.path.getctime)
            return latest_file
        except FileNotFoundError:
            general_logger.info("Screenshot directory not found.")
            return None
        except Exception as e:
            error_logger.error(f"Error getting latest screenshot: {e}")
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
                error_logger.error(f"Error in screenshot scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry on error

# Command handlers
async def screenshot_command(update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
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

        # Get current time in Kyiv timezone
        kyiv_now = datetime.now(pytz.timezone('Europe/Kyiv'))
        next_screenshot = kyiv_now + timedelta(hours=6)

        # If no screenshot exists for today, take a new one
        if not screenshot_path:
            status_msg = await update.message.reply_text("Роблю новий знімок, будь ласка зачекайте...") if update.message else None
            screenshot_path = await manager.take_screenshot(
            WEATHER_API_URL,
            manager.get_screenshot_path()
            )
            if status_msg:
                await status_msg.delete()

        if screenshot_path:
            # Get file modification time
            mod_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path))
            mod_time = mod_time.astimezone(pytz.timezone('Europe/Kyiv'))
            
            caption = (
                f"Прогноз сонячних спалахів і магнітних бурь\n"
                f"Час знімку: {mod_time.strftime('%H:%M %d.%m.%Y')}\n"
                f"Наступний знімок: {next_screenshot.strftime('%H:%M %d.%m.%Y')}"
            )
            
            with open(screenshot_path, 'rb') as photo:
                if update.effective_chat:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption=caption
                    )
        else:
            if update.message:
                await update.message.reply_text("Не вдалося згенерувати знімок. Спробуйте пізніше.")
    except Exception as e:
        error_logger.error(f"Error in screenshot command: {e}")
        if update.message:
            await update.message.reply_text("Під час обробки вашого запиту сталася помилка.")


# Initialization and main functions
def setup_bot() -> None:
    """
    Set up the bot and initialize all necessary components.
    
    Returns:
        None
    """
    # Initialize directories
    init_directories()
    
    # Log startup
    general_logger.info("Bot initialized successfully")

def ensure_city_data_file() -> None:
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

async def initialize_utils() -> None:
    """Initialize utility modules."""
    await config_manager.initialize()

# Only run setup code if this module is the main script
if __name__ == "__main__":
    setup_bot()
    # This would normally be run in the main application:
    # asyncio.run(start_background_tasks())