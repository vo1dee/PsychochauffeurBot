import re
import imgkit
import pytz
import os
import asyncio
import aiohttp
import csv
import subprocess
from datetime import datetime, time as dt_time, timedelta, date
from typing import Optional, Any, List, Dict, Tuple
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
WKHTMLTOIMAGE_PATH = '/usr/local/bin/wkhtmltoimage'

# Define imgkit options once to avoid duplication
# Imgkit options that match the working direct command
IMGKIT_OPTIONS = {
    'format': 'png',
    'width': 1024,  # Use integer instead of string
    'height': 768,  # Use integer instead of string
    'enable-javascript': None,
    'javascript-delay': 5000,  # Use integer instead of string
    'quality': 100,
    'encoding': 'UTF-8'
}

# Initialize config manager
config_manager = ConfigManager()


class DateParser:
    """Utility class for parsing dates in multiple formats with automatic detection."""
    
    # Supported date formats in order of preference with regex patterns for strict validation
    DATE_FORMATS = [
        ('%Y-%m-%d', r'^\d{4}-\d{2}-\d{2}$'),    # YYYY-MM-DD (ISO format)
        ('%d-%m-%Y', r'^\d{2}-\d{2}-\d{4}$'),    # DD-MM-YYYY (European format)
        ('%d/%m/%Y', r'^\d{2}/\d{2}/\d{4}$'),    # DD/MM/YYYY (Alternative European format)
        ('%Y/%m/%d', r'^\d{4}/\d{2}/\d{2}$'),    # YYYY/MM/DD (Alternative ISO format)
    ]
    
    @staticmethod
    def parse_date(date_str: str) -> date:
        """
        Parse date string in multiple formats with automatic format detection.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            date: Parsed date object
            
        Raises:
            ValueError: If date string cannot be parsed in any supported format
        """
        if not date_str or not isinstance(date_str, str):
            raise ValueError("Date string cannot be empty or None")
        
        date_str = date_str.strip()
        
        # Check if string is empty after stripping
        if not date_str:
            raise ValueError("Date string cannot be empty or None")
        
        # Try each format until one works
        for fmt, pattern in DateParser.DATE_FORMATS:
            # First check if the string matches the expected pattern
            if not re.match(pattern, date_str):
                continue
                
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                # Validate that the date is reasonable (not too far in past/future)
                DateParser._validate_date_range(parsed_date)
                return parsed_date
            except ValueError as e:
                # If it's a date range validation error, re-raise it
                if "too far in the past" in str(e) or "too far in the future" in str(e):
                    raise e
                # Otherwise, continue trying other formats
                continue
        
        # If no format worked, provide helpful error message
        supported_formats = [fmt.replace('%Y', 'YYYY').replace('%m', 'MM').replace('%d', 'DD') 
                           for fmt, _ in DateParser.DATE_FORMATS]
        raise ValueError(
            f"Unable to parse date '{date_str}'. "
            f"Supported formats: {', '.join(supported_formats)}"
        )
    
    @staticmethod
    def validate_date_range(start_date_str: str, end_date_str: str) -> Tuple[date, date]:
        """
        Validate and parse date range ensuring start date is before end date.
        
        Args:
            start_date_str: Start date string
            end_date_str: End date string
            
        Returns:
            Tuple[date, date]: Parsed start and end dates
            
        Raises:
            ValueError: If dates cannot be parsed or start date is after end date
        """
        start_date = DateParser.parse_date(start_date_str)
        end_date = DateParser.parse_date(end_date_str)
        
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date_str}) cannot be after end date ({end_date_str})"
            )
        
        return start_date, end_date
    
    @staticmethod
    def detect_format(date_str: str) -> Optional[str]:
        """
        Detect the format of a date string.
        
        Args:
            date_str: Date string to analyze
            
        Returns:
            Optional[str]: Detected format string or None if no format matches
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        date_str = date_str.strip()
        
        for fmt, pattern in DateParser.DATE_FORMATS:
            # First check if the string matches the expected pattern
            if not re.match(pattern, date_str):
                continue
                
            try:
                datetime.strptime(date_str, fmt)
                return fmt
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def _validate_date_range(parsed_date: date) -> None:
        """
        Validate that a parsed date is within reasonable bounds.
        
        Args:
            parsed_date: Date to validate
            
        Raises:
            ValueError: If date is outside reasonable bounds
        """
        today = date.today()
        min_date = date(1900, 1, 1)  # Minimum reasonable date
        max_date = date(today.year + 10, 12, 31)  # Maximum reasonable date (10 years in future)
        
        if parsed_date < min_date:
            raise ValueError(f"Date {parsed_date} is too far in the past (before {min_date})")
        
        if parsed_date > max_date:
            raise ValueError(f"Date {parsed_date} is too far in the future (after {max_date})")
    
    @staticmethod
    def format_date_for_display(date_obj: date, format_style: str = 'european') -> str:
        """
        Format a date object for display in a specific style.
        
        Args:
            date_obj: Date object to format
            format_style: Style to use ('european' for DD-MM-YYYY, 'iso' for YYYY-MM-DD)
            
        Returns:
            str: Formatted date string
        """
        if format_style == 'european':
            return date_obj.strftime('%d-%m-%Y')
        elif format_style == 'iso':
            return date_obj.strftime('%Y-%m-%d')
        else:
            raise ValueError(f"Unsupported format style: {format_style}")


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
    url_pattern = r'http[s]?://(?:[a-zA-Z0-9]|[\$\-_@.&+?=/]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
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
            return str(emoji)
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
            return str(emoji)
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
            return str(emoji)
    return '💧'

async def get_city_translation(city: str) -> str:
    """
    Get city translation from dictionary.
    """
    weather_config = await config_manager.get_config("weather_config", None, None)
    config_translations = weather_config.get("CITY_TRANSLATIONS", {})
    city_translations = config_translations if config_translations else Weather.CITY_TRANSLATIONS
    normalized = city.lower().replace(" ", "")
    result = city_translations.get(normalized, city)
    return str(result)

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
                    cid_raw = row.get('chat_id')
                    cid = int(cid_raw) if cid_raw and str(cid_raw).isdigit() else 0
                except (ValueError, TypeError):
                    continue
                if uid == user_id and (cid is None or (cid_raw is not None and (str(cid_raw) == '' or str(cid_raw) == 'None'))):
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
    
    # Screenshot freshness threshold (6 hours)
    FRESHNESS_THRESHOLD_HOURS = 6
    
    def __new__(cls) -> 'ScreenshotManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self.timezone = pytz.timezone('Europe/Kyiv')
            self.schedule_time = dt_time(2, 0)  # 2 AM Kyiv time
            self.config = self._initialize_config()
            self._initialized = True

    def _initialize_config(self) -> Optional[Any]:
        """Initialize wkhtmltoimage configuration with error handling."""
        try:
            # Check if wkhtmltoimage tool is available
            if not self._check_wkhtmltoimage_availability():
                error_logger.error("wkhtmltoimage tool is not available")
                return None
            
            return imgkit.config(wkhtmltoimage=WKHTMLTOIMAGE_PATH)
        except Exception as e:
            error_logger.error(f"Error initializing wkhtmltoimage config: {e}")
            return None

    def _check_wkhtmltoimage_availability(self) -> bool:
        """Check if wkhtmltoimage tool is available and executable."""
        try:
            import subprocess
            result = subprocess.run([WKHTMLTOIMAGE_PATH, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
        except Exception as e:
            error_logger.error(f"Error checking wkhtmltoimage availability: {e}")
            return False

    async def ensure_screenshot_directory(self) -> bool:
        """Ensure screenshot directory exists with proper permissions and comprehensive error handling."""
        try:
            # Check if directory already exists
            if os.path.exists(Config.SCREENSHOT_DIR):
                # Verify it's actually a directory
                if not os.path.isdir(Config.SCREENSHOT_DIR):
                    error_logger.error(f"Screenshot path exists but is not a directory: {Config.SCREENSHOT_DIR}")
                    return False
                
                # Verify directory permissions
                if not os.access(Config.SCREENSHOT_DIR, os.R_OK | os.W_OK | os.X_OK):
                    error_logger.error(f"Screenshot directory lacks required permissions: {Config.SCREENSHOT_DIR}")
                    try:
                        # Attempt to fix permissions
                        os.chmod(Config.SCREENSHOT_DIR, 0o755)
                        general_logger.info(f"Fixed permissions for screenshot directory: {Config.SCREENSHOT_DIR}")
                    except Exception as perm_e:
                        error_logger.error(f"Failed to fix directory permissions: {perm_e}")
                        return False
                
                general_logger.debug(f"Screenshot directory already exists with proper permissions: {Config.SCREENSHOT_DIR}")
                return True
            
            # Create directory with proper permissions
            general_logger.info(f"Creating screenshot directory: {Config.SCREENSHOT_DIR}")
            os.makedirs(Config.SCREENSHOT_DIR, mode=0o755, exist_ok=True)
            
            # Double-check the directory was created successfully
            if not os.path.exists(Config.SCREENSHOT_DIR):
                error_logger.error(f"Directory creation appeared to succeed but directory does not exist: {Config.SCREENSHOT_DIR}")
                return False
            
            # Verify all required permissions
            required_permissions = os.R_OK | os.W_OK | os.X_OK
            if not os.access(Config.SCREENSHOT_DIR, required_permissions):
                error_logger.error(f"Screenshot directory created but lacks required permissions: {Config.SCREENSHOT_DIR}")
                try:
                    # Attempt to set correct permissions
                    os.chmod(Config.SCREENSHOT_DIR, 0o755)
                    general_logger.info(f"Set permissions for new screenshot directory: {Config.SCREENSHOT_DIR}")
                except Exception as perm_e:
                    error_logger.error(f"Failed to set directory permissions: {perm_e}")
                    return False
            
            # Test write access by creating and removing a test file
            test_file_path = os.path.join(Config.SCREENSHOT_DIR, '.write_test')
            try:
                with open(test_file_path, 'w') as test_file:
                    test_file.write('test')
                os.remove(test_file_path)
                general_logger.debug(f"Write test successful for screenshot directory: {Config.SCREENSHOT_DIR}")
            except Exception as write_e:
                error_logger.error(f"Write test failed for screenshot directory: {write_e}")
                return False
                
            general_logger.info(f"Screenshot directory successfully ensured with proper permissions: {Config.SCREENSHOT_DIR}")
            return True
            
        except PermissionError as e:
            error_logger.error(f"Permission error ensuring screenshot directory: {e}")
            return False
        except OSError as e:
            error_logger.error(f"OS error ensuring screenshot directory: {e}")
            return False
        except Exception as e:
            error_logger.error(f"Unexpected error ensuring screenshot directory: {e}")
            return False

    def get_screenshot_path(self) -> str:
        """Constructs a path for storing screenshots with a timestamp."""
        # Ensure timezone is correctly handled
        if not self.timezone:
            self.timezone = pytz.timezone('Europe/Kyiv') # Fallback
        
        kyiv_time = datetime.now(self.timezone)
        date_str = kyiv_time.strftime('%Y-%m-%d')
        return os.path.join(Config.SCREENSHOT_DIR, f'flares_{date_str}_kyiv.png')

    def validate_screenshot_freshness(self, screenshot_path: str) -> bool:
        """
        Check if screenshot is less than 6 hours old.
        
        Args:
            screenshot_path: Path to the screenshot file
            
        Returns:
            bool: True if screenshot is fresh (< 6 hours old), False otherwise
        """
        try:
            if not os.path.exists(screenshot_path):
                return False
                
            # Get file modification time
            mod_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path))
            mod_time = mod_time.replace(tzinfo=self.timezone)
            
            # Get current time in Kyiv timezone
            current_time = datetime.now(self.timezone)
            
            # Calculate age in hours
            age_hours = (current_time - mod_time).total_seconds() / 3600
            
            is_fresh = age_hours < self.FRESHNESS_THRESHOLD_HOURS
            general_logger.info(f"Screenshot age: {age_hours:.1f} hours, fresh: {is_fresh}")
            
            return is_fresh
        except Exception as e:
            error_logger.error(f"Error validating screenshot freshness: {e}")
            return False

    def get_latest_screenshot(self) -> Optional[str]:
        """
        Get the latest screenshot from the screenshot directory.
        """
        try:
            if not os.path.exists(Config.SCREENSHOT_DIR):
                general_logger.info("Screenshot directory not found.")
                return None
                
            files = [os.path.join(Config.SCREENSHOT_DIR, f) 
                    for f in os.listdir(Config.SCREENSHOT_DIR) 
                    if f.endswith('.png')]
            
            if not files:
                general_logger.info("No screenshot files found.")
                return None
                
            latest_file = max(files, key=os.path.getctime)
            return latest_file
        except FileNotFoundError:
            general_logger.info("Screenshot directory not found.")
            return None
        except Exception as e:
            error_logger.error(f"Error getting latest screenshot: {e}")
            return None

    async def get_current_screenshot(self) -> Optional[str]:
        """
        Get current screenshot if fresh, otherwise generate new one.
        
        Returns:
            Optional[str]: Path to current screenshot or None on failure
        """
        try:
            # Ensure directory exists with proper permissions
            if not await self.ensure_screenshot_directory():
                error_logger.error("Failed to ensure screenshot directory exists")
                return None
            
            # Check for existing fresh screenshot
            latest_screenshot = self.get_latest_screenshot()
            if latest_screenshot and self.validate_screenshot_freshness(latest_screenshot):
                general_logger.info(f"Using existing fresh screenshot: {latest_screenshot}")
                return latest_screenshot
            
            # Log screenshot generation attempt
            if latest_screenshot:
                general_logger.info(f"Existing screenshot is stale, generating new one. Old: {latest_screenshot}")
            else:
                general_logger.info("No existing screenshot found, generating new one")
            
            # Generate new screenshot if none exists or it's stale
            new_screenshot = await self.take_screenshot(WEATHER_API_URL, self.get_screenshot_path())
            
            if new_screenshot:
                general_logger.info(f"Successfully generated new screenshot: {new_screenshot}")
            else:
                error_logger.error("Failed to generate new screenshot")
                
            return new_screenshot
            
        except Exception as e:
            error_logger.error(f"Error getting current screenshot: {e}")
            return None

    async def take_screenshot_simple(self, url: str, output_path: str) -> Optional[str]:
        """
        Take a screenshot with minimal options that match the working direct command.
        
        Args:
            url: URL to capture
            output_path: Path to save the screenshot
            
        Returns:
            Optional[str]: Path to saved screenshot or None on failure
        """
        try:
            if not self.config:
                return None
                
            general_logger.info(f"Taking simple screenshot of {url}")
            
            # Use the exact same options as the working direct command
            simple_options = {
                'width': '1024',
                'height': '768',
                'enable-javascript': None,
                'javascript-delay': '5000'
            }
            
            # Use a temporary file to ensure atomic operations
            temp_path = output_path + '.tmp'
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                lambda: imgkit.from_url(url, temp_path, options=simple_options, config=self.config)
            )
            
            # Wait a moment and move temp file to final location
            await asyncio.sleep(0.2)
            if os.path.exists(temp_path):
                os.rename(temp_path, output_path)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                general_logger.info(f"Simple screenshot created: {os.path.getsize(output_path)} bytes")
                return output_path
            else:
                return None
                
        except Exception as e:
            error_logger.error(f"Error in simple screenshot: {e}")
            return None

    async def take_screenshot(self, url: str, output_path: str, max_retries: int = 3) -> Optional[str]:
        """
        Take a screenshot of the given URL and save it to the output path with comprehensive error handling.
        
        Args:
            url: URL to capture
            output_path: Path to save the screenshot
            max_retries: Maximum number of retry attempts
            
        Returns:
            Optional[str]: Path to saved screenshot or None on failure
        """
        general_logger.info(f"Starting screenshot generation for URL: {url}")
        
        # Validate inputs
        if not url or not output_path:
            error_logger.error("Invalid URL or output path provided")
            return None
        
        # Check if wkhtmltoimage is available before attempting
        if not self._check_wkhtmltoimage_availability():
            error_logger.error("wkhtmltoimage tool is not available - cannot generate screenshot")
            return None
        
        # Ensure directory exists with proper permissions
        if not await self.ensure_screenshot_directory():
            error_logger.error("Failed to ensure screenshot directory - cannot proceed")
            return None
        
        # First try simple approach with minimal options
        general_logger.info("Attempting simple screenshot generation")
        simple_result = await self.take_screenshot_simple(url, output_path)
        if simple_result and self._validate_screenshot_content(simple_result):
            general_logger.info("Simple screenshot generation successful")
            return simple_result
        else:
            general_logger.warning("Simple screenshot generation failed, trying advanced approach")
        
        # If simple approach fails, try with full options and retries
        for attempt in range(max_retries):
            try:
                # Double-check configuration is available
                if not self.config:
                    error_logger.error("wkhtmltoimage configuration not available")
                    return None
                
                general_logger.info(f"Taking advanced screenshot of {url} (attempt {attempt + 1}/{max_retries})")
                
                # Clean up any existing files from previous attempts
                for cleanup_path in [output_path, output_path + '.tmp']:
                    if os.path.exists(cleanup_path):
                        try:
                            os.remove(cleanup_path)
                            general_logger.debug(f"Cleaned up existing file: {cleanup_path}")
                        except OSError as e:
                            general_logger.warning(f"Could not clean up {cleanup_path}: {e}")
                
                # Use a temporary file to ensure atomic operations
                temp_path = output_path + '.tmp'
                
                # Run imgkit in a thread pool to avoid blocking
                general_logger.debug(f"Executing imgkit with options: {IMGKIT_OPTIONS}")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, 
                    lambda: imgkit.from_url(url, temp_path, options=IMGKIT_OPTIONS, config=self.config)
                )
                
                # Wait a moment to ensure file is completely written
                await asyncio.sleep(0.5)
                
                # Verify temp file was created
                if not os.path.exists(temp_path):
                    error_logger.warning(f"Temporary screenshot file was not created: {temp_path}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                    else:
                        return None
                
                # Move temp file to final location atomically
                try:
                    os.rename(temp_path, output_path)
                    general_logger.debug(f"Moved temporary file to final location: {output_path}")
                except OSError as e:
                    error_logger.error(f"Failed to move temporary file to final location: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                    else:
                        return None
                
                # Verify screenshot was created successfully and contains valid content
                if os.path.exists(output_path) and self._validate_screenshot_content(output_path):
                    file_size = os.path.getsize(output_path)
                    general_logger.info(f"Screenshot saved and validated successfully: {output_path} ({file_size} bytes)")
                    return output_path
                else:
                    error_logger.warning(f"Screenshot validation failed (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        # Wait before retry, increasing delay each time
                        retry_delay = 3 * (attempt + 1)
                        general_logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        error_logger.error("All screenshot attempts failed - validation failed")
                        return None
                        
            except Exception as e:
                error_logger.error(f"Error taking screenshot (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    # Wait before retry, increasing delay each time
                    retry_delay = 2 * (attempt + 1)
                    general_logger.info(f"Retrying in {retry_delay} seconds after error...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    error_logger.error("All screenshot attempts failed due to errors")
                    return None
        
        error_logger.error("Screenshot generation completely failed after all attempts")
        return None

    def _validate_screenshot_content(self, screenshot_path: str) -> bool:
        """
        Validate that the screenshot contains expected content with comprehensive checks.
        
        Args:
            screenshot_path: Path to the screenshot file
            
        Returns:
            bool: True if screenshot appears to contain valid content
        """
        try:
            # Check if file exists
            if not os.path.exists(screenshot_path):
                general_logger.warning(f"Screenshot validation failed: file does not exist: {screenshot_path}")
                return False
            
            # Check if it's actually a file (not a directory)
            if not os.path.isfile(screenshot_path):
                general_logger.warning(f"Screenshot validation failed: path is not a file: {screenshot_path}")
                return False
            
            # Check file permissions
            if not os.access(screenshot_path, os.R_OK):
                general_logger.warning(f"Screenshot validation failed: file is not readable: {screenshot_path}")
                return False
            
            # Check file size - should be reasonable for a chart
            file_size = os.path.getsize(screenshot_path)
            min_size = 50000   # 50KB minimum (reduced from 100KB for more flexibility)
            max_size = 25000000  # 25MB maximum (increased slightly for high-res charts)
            
            if file_size < min_size:
                general_logger.warning(f"Screenshot validation failed: file too small ({file_size} bytes, minimum {min_size})")
                return False
            
            if file_size > max_size:
                general_logger.warning(f"Screenshot validation failed: file too large ({file_size} bytes, maximum {max_size})")
                return False
            
            # Validate PNG header to ensure it's a proper image file
            try:
                with open(screenshot_path, 'rb') as f:
                    header = f.read(8)
                    if len(header) < 8:
                        general_logger.warning(f"Screenshot validation failed: file too short to contain PNG header")
                        return False
                    
                    if not header.startswith(b'\x89PNG\r\n\x1a\n'):
                        general_logger.warning(f"Screenshot validation failed: invalid PNG header: {header.hex()}")
                        return False
                    
                    # Read a bit more to ensure it's not just a header
                    additional_data = f.read(100)
                    if len(additional_data) < 50:
                        general_logger.warning(f"Screenshot validation failed: PNG file appears truncated")
                        return False
                        
            except IOError as e:
                general_logger.warning(f"Screenshot validation failed: error reading file: {e}")
                return False
            except Exception as e:
                general_logger.warning(f"Screenshot validation failed: unexpected error reading PNG header: {e}")
                return False
            
            # Additional validation: check file modification time to ensure it's recent
            try:
                mod_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path))
                current_time = datetime.now()
                age_hours = (current_time - mod_time).total_seconds() / 3600
                
                # If file is older than 24 hours, it might be stale (but still valid)
                if age_hours > 24:
                    general_logger.info(f"Screenshot is quite old ({age_hours:.1f} hours) but still valid")
                    
            except Exception as e:
                general_logger.debug(f"Could not check file modification time: {e}")
            
            general_logger.debug(f"Screenshot validation successful: {screenshot_path} ({file_size} bytes)")
            return True
            
        except Exception as e:
            general_logger.warning(f"Screenshot validation failed with unexpected error: {e}")
            return False
            
        except Exception as e:
            error_logger.error(f"Error validating screenshot: {e}")
            return False

    async def _test_url_accessibility(self, url: str) -> bool:
        """
        Test if the URL is accessible and returns valid content.
        
        Args:
            url: URL to test
            
        Returns:
            bool: True if URL is accessible
        """
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        # Check if it contains expected content
                        if 'solar' in content.lower() and 'forecast' in content.lower():
                            general_logger.info("URL accessibility test passed")
                            return True
                        else:
                            general_logger.warning("URL accessible but content doesn't match expected format")
                            return False
                    else:
                        general_logger.warning(f"URL returned status {response.status}")
                        return False
        except Exception as e:
            error_logger.error(f"Error testing URL accessibility: {e}")
            return False

    def get_screenshot_status_info(self) -> Dict[str, Any]:
        """
        Get comprehensive status information about screenshots.
        
        Returns:
            Dict containing status information
        """
        try:
            latest_screenshot = self.get_latest_screenshot()
            
            status_info: Dict[str, Any] = {
                'has_screenshot': False,
                'is_fresh': False,
                'path': None,
                'age_hours': None,
                'file_size': None,
                'next_update_hours': None,
                'directory_exists': os.path.exists(Config.SCREENSHOT_DIR),
                'directory_writable': os.access(Config.SCREENSHOT_DIR, os.W_OK) if os.path.exists(Config.SCREENSHOT_DIR) else False,
                'tool_available': self._check_wkhtmltoimage_availability()
            }
            
            if latest_screenshot and os.path.exists(latest_screenshot):
                status_info['has_screenshot'] = True
                status_info['path'] = latest_screenshot
                status_info['is_fresh'] = self.validate_screenshot_freshness(latest_screenshot)
                status_info['file_size'] = os.path.getsize(latest_screenshot)
                
                # Calculate age
                mod_time = datetime.fromtimestamp(os.path.getmtime(latest_screenshot))
                current_time = datetime.now()
                age_hours = (current_time - mod_time).total_seconds() / 3600
                status_info['age_hours'] = age_hours
                
                # Calculate next update time
                if age_hours < self.FRESHNESS_THRESHOLD_HOURS:
                    status_info['next_update_hours'] = self.FRESHNESS_THRESHOLD_HOURS - age_hours
                else:
                    status_info['next_update_hours'] = 0  # Update needed now
            
            return status_info
            
        except Exception as e:
            error_logger.error(f"Error getting screenshot status info: {e}")
            return {
                'has_screenshot': False,
                'is_fresh': False,
                'path': None,
                'age_hours': None,
                'file_size': None,
                'next_update_hours': None,
                'directory_exists': False,
                'directory_writable': False,
                'tool_available': False,
                'error': str(e)
            }

    def get_fallback_message(self) -> str:
        """Get comprehensive fallback message when screenshot generation fails."""
        # Check if we have any old screenshot as fallback
        latest_screenshot = self.get_latest_screenshot()
        
        base_message = (
            "На жаль, не вдалося згенерувати актуальний знімок сонячних спалахів.\n\n"
            "Можливі причини:\n"
            "• Проблеми з мережею або інтернет-з'єднанням\n"
            "• Недоступність джерела даних (api.meteoagent.com)\n"
            "• Технічні проблеми сервера\n"
            "• Відсутність необхідних інструментів (wkhtmltoimage)\n"
            "• Проблеми з правами доступу до файлової системи\n\n"
        )
        
        if latest_screenshot and os.path.exists(latest_screenshot):
            # We have an old screenshot, provide info about it
            try:
                mod_time = datetime.fromtimestamp(os.path.getmtime(latest_screenshot))
                mod_time = mod_time.astimezone(self.timezone)
                hours_old = (datetime.now(self.timezone) - mod_time).total_seconds() / 3600
                
                fallback_info = (
                    f"📸 Доступний застарілий знімок від {mod_time.strftime('%H:%M %d.%m.%Y')} "
                    f"(вік: {hours_old:.1f} годин)\n\n"
                    "Для отримання застарілого знімку спробуйте команду ще раз.\n\n"
                )
            except Exception:
                fallback_info = "📸 Доступний застарілий знімок (час невідомий)\n\n"
        else:
            fallback_info = "📸 Застарілих знімків також немає в наявності.\n\n"
        
        footer = (
            "🔄 Спробуйте пізніше (рекомендується через 5-10 хвилин)\n"
            "🌐 Або перевірте дані безпосередньо на сайті:\n"
            "https://api.meteoagent.com/widgets/v1/kindex\n\n"
            "ℹ️ Якщо проблема повторюється, зверніться до адміністратора."
        )
        
        return base_message + fallback_info + footer

    async def schedule_task(self) -> None:
        """
        Schedule a screenshot task every 6 hours.
        
        This is a long-running task that should be started at application startup.
        """
        while True:
            try:
                # Ensure directory exists before scheduling
                if not await self.ensure_screenshot_directory():
                    error_logger.error("Failed to ensure screenshot directory, retrying in 5 minutes")
                    await asyncio.sleep(300)
                    continue
                
                # Check if we need a new screenshot
                latest_screenshot = self.get_latest_screenshot()
                if latest_screenshot and self.validate_screenshot_freshness(latest_screenshot):
                    # Screenshot is still fresh, calculate next update time
                    mod_time = datetime.fromtimestamp(os.path.getmtime(latest_screenshot))
                    mod_time = mod_time.replace(tzinfo=self.timezone)
                    next_update = mod_time + timedelta(hours=self.FRESHNESS_THRESHOLD_HOURS)
                    
                    # Sleep until next update is needed
                    kyiv_now = datetime.now(self.timezone)
                    sleep_seconds = (next_update - kyiv_now).total_seconds()
                    
                    if sleep_seconds > 0:
                        general_logger.info(f"Screenshot is fresh, next update at: {next_update}")
                        await asyncio.sleep(sleep_seconds)
                        continue
                
                # Generate new screenshot
                general_logger.info("Generating scheduled screenshot")
                screenshot_path = await self.take_screenshot(WEATHER_API_URL, self.get_screenshot_path())
                
                if screenshot_path:
                    general_logger.info(f"Scheduled screenshot generated successfully: {screenshot_path}")
                else:
                    error_logger.error("Failed to generate scheduled screenshot")
                
                # Sleep for the full threshold period before next check
                await asyncio.sleep(self.FRESHNESS_THRESHOLD_HOURS * 3600)
                
            except Exception as e:
                error_logger.error(f"Error in screenshot scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry on error

# Command handlers
async def screenshot_command(update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
    """
    Handle /flares command for solar flares screenshot.
    
    Args:
        update: Telegram update
        context: Callback context
    """
    status_msg = None
    try:
        manager = ScreenshotManager()
        
        # Check if wkhtmltoimage tool is available
        if not manager._check_wkhtmltoimage_availability():
            error_msg = (
                "Інструмент для створення знімків недоступний.\n"
                "Зверніться до адміністратора для встановлення wkhtmltoimage."
            )
            if update.message:
                await update.message.reply_text(error_msg)
            return
        
        # Get status information for better progress indicators
        status_info = manager.get_screenshot_status_info()
        
        # Show initial status message with diagnostic info
        initial_status = "🔍 Перевіряю наявність актуального знімку..."
        if not status_info['tool_available']:
            initial_status += "\n⚠️ Інструмент wkhtmltoimage недоступний"
        elif not status_info['directory_exists']:
            initial_status += "\n📁 Створюю директорію для знімків..."
        elif status_info['has_screenshot'] and status_info['is_fresh']:
            initial_status += "\n✅ Знайдено актуальний знімок"
        elif status_info['has_screenshot']:
            initial_status += f"\n🕐 Знайдено застарілий знімок (вік: {status_info['age_hours']:.1f} год)"
        
        if update.message:
            status_msg = await update.message.reply_text(initial_status)
        
        # Try to get current screenshot (fresh or generate new)
        screenshot_path = await manager.get_current_screenshot()
        
        # Update status based on what's happening
        if status_msg:
            if not status_info['has_screenshot'] or not status_info['is_fresh']:
                progress_msg = (
                    "🔄 Генерую новий знімок сонячних спалахів...\n"
                    "⏳ Це може зайняти до 15-30 секунд\n"
                    "📊 Завантажую дані з api.meteoagent.com..."
                )
                await status_msg.edit_text(progress_msg)
            else:
                await status_msg.edit_text("✅ Використовую актуальний знімок...")

        if screenshot_path and os.path.exists(screenshot_path):
            # Get file modification time
            mod_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path))
            mod_time = mod_time.astimezone(pytz.timezone('Europe/Kyiv'))
            
            # Calculate next update time
            kyiv_now = datetime.now(pytz.timezone('Europe/Kyiv'))
            hours_since_update = (kyiv_now - mod_time).total_seconds() / 3600
            hours_until_next = max(0, manager.FRESHNESS_THRESHOLD_HOURS - hours_since_update)
            next_screenshot = kyiv_now + timedelta(hours=hours_until_next)
            
            # Determine freshness status
            freshness_status = "актуальний" if hours_since_update < manager.FRESHNESS_THRESHOLD_HOURS else "застарілий"
            
            caption = (
                f"🌞 Прогноз сонячних спалахів і магнітних бурь\n\n"
                f"📅 Час знімку: {mod_time.strftime('%H:%M %d.%m.%Y')}\n"
                f"📊 Статус: {freshness_status}\n"
                f"🔄 Наступне оновлення: {next_screenshot.strftime('%H:%M %d.%m.%Y')}\n\n"
                f"🔗 Джерело: api.meteoagent.com"
            )
            
            # Delete status message before sending photo
            if status_msg:
                await status_msg.delete()
                status_msg = None
            
            # Send the screenshot
            with open(screenshot_path, 'rb') as photo:
                if update.effective_chat:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption=caption
                    )
                    
            if update.effective_chat:
                general_logger.info(f"Successfully sent flares screenshot to chat {update.effective_chat.id}")
            
        else:
            # Screenshot generation failed, provide fallback
            fallback_msg = manager.get_fallback_message()
            
            if status_msg:
                await status_msg.edit_text(fallback_msg)
            elif update.message:
                await update.message.reply_text(fallback_msg)
                
            error_logger.error("Failed to generate or retrieve screenshot for flares command")
            
    except Exception as e:
        error_logger.error(f"Error in screenshot command: {e}")
        
        # Clean up status message
        if status_msg:
            try:
                await status_msg.delete()
            except:
                pass
        
        # Send error message to user
        error_msg = (
            "Під час обробки вашого запиту сталася помилка.\n"
            "Спробуйте пізніше або зверніться до адміністратора."
        )
        
        if update.message:
            await update.message.reply_text(error_msg)


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