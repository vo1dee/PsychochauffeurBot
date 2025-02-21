import logging
import csv
import os
from typing import Set, Optional
import asyncio
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
import pytz
import sys

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CSV_FILE = os.path.join(DATA_DIR, "user_locations.csv")
USED_WORDS_FILE = os.path.join(DATA_DIR, "used_words.csv")
KYIV_TZ = pytz.timezone('Europe/Kiev')

# Ensure directories exist
def ensure_directories():
    """Ensure all required directories exist with proper permissions."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Verify write permissions
        test_log_path = os.path.join(LOG_DIR, 'test.log')
        with open(test_log_path, 'w') as f:
            f.write('Test log write\n')
        os.remove(test_log_path)
        print("Write permission verified for log directory")
        return True
    except Exception as e:
        print(f"Error setting up directories: {e}")
        return False

# Custom formatter for Kyiv timezone
class KyivTimezoneFormatter(logging.Formatter):
    """Custom formatter that uses Kyiv timezone"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created).astimezone(KYIV_TZ)
        return dt.strftime(datefmt) if datefmt else dt.strftime("%Y-%m-%d %H:%M:%S %z")

# Chat-specific daily log handler
class DailyLogHandler(logging.Handler):
    def emit(self, record):
        # Ensure chat_id is included in the record if available
        if hasattr(record, 'chat_id'):
            record.chattitle = getattr(record, 'chattitle', 'Unknown')
            record.username = getattr(record, 'username', 'Unknown')
        else:
            record.chat_id = 'N/A'  # Default value if chat_id is not present
            record.chattitle = 'Unknown'  # Default value for chattitle
            record.username = 'Unknown'  # Default value for username
        try:
            # Format date in Kyiv timezone
            date = datetime.now(KYIV_TZ)
            
            # Create path
            if record.chat_id is not None:
                chat_log_dir = os.path.join(LOG_DIR, f"chat_{record.chat_id}")
                os.makedirs(chat_log_dir, exist_ok=True)
                daily_log_path = os.path.join(chat_log_dir, f"chat_{date.strftime('%Y-%m-%d')}.log")
            else:
                daily_log_path = os.path.join(LOG_DIR, f"chat_{date.strftime('%Y-%m-%d')}.log")
            
            msg = self.format(record)
            with open(daily_log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            self.handleError(record)

# Telegram error reporting handler
class TelegramErrorHandler(logging.Handler):
    """Custom handler for sending error logs to Telegram channel"""
    def __init__(self, bot, channel_id):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self.buffer = []
        self.last_sent = 0
        self.rate_limit = 1  # Minimum seconds between messages

    async def emit_async(self, record):
        try:
            msg = self.format(record)
            now = time.time()
            error_msg = (
                f"🚨 *Error Report*\n"
                f"```\n"
                f"Time: {datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Level: {record.levelname}\n"
                f"Location: {record.pathname}:{record.lineno}\n"
                f"Function: {record.funcName}\n"
                f"Message: {msg}\n"
                f"```"
            )
            if now - self.last_sent >= self.rate_limit:
                await self.bot.send_message(chat_id=self.channel_id, text=error_msg, parse_mode='MarkdownV2')
                self.last_sent = now
            else:
                self.buffer.append(error_msg)
        except Exception as e:
            print(f"Error in TelegramErrorHandler: {e}")

    def emit(self, record):
        asyncio.create_task(self.emit_async(record))

# Initialize logging system
def initialize_logging():
    """Set up all loggers and handlers"""
    if not ensure_directories():
        sys.exit(1)
    
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            record.chat_id = getattr(record, 'chat_id', 'N/A')
            record.chattitle = getattr(record, 'chattitle', 'Unknown')
            record.username = getattr(record, 'username', 'Unknown')
            return super().format(record)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # --- General Logger ---
    general_logger = logging.getLogger('general_logger')
    general_logger.setLevel(logging.INFO)
    
    general_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'general.log'),
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    general_file_handler.setFormatter(CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s - %(chattitle)s - %(username)s - %(message)s'))
    general_file_handler.setLevel(logging.INFO)
    
    general_logger.addHandler(console_handler)
    general_logger.addHandler(general_file_handler)
    general_logger.propagate = False
    
    # --- Chat Logger ---
    chat_logger = logging.getLogger('chat_logger')
    chat_logger.setLevel(logging.INFO)
    
    chat_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'chat.log'),
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    chat_file_handler.setFormatter(CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s - %(chattitle)s - %(username)s - %(message)s'))
    
    daily_handler = DailyLogHandler()
    daily_handler.setLevel(logging.INFO)
    daily_handler.setFormatter(CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s - %(chattitle)s - %(username)s - %(message)s'))
    
    chat_logger.addHandler(console_handler)
    chat_logger.addHandler(chat_file_handler)
    chat_logger.addHandler(daily_handler)
    chat_logger.propagate = False
    
    # --- Error Logger ---
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    
    error_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'error.log'),
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_file_handler.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    error_logger.addHandler(console_handler)
    error_logger.addHandler(error_file_handler)
    error_logger.propagate = False
    
    # Suppress other library logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log initialization success
    general_logger.info("Logging system initialized successfully")
    chat_logger.info("Chat logging system initialized successfully")
    error_logger.info("Error logging system initialized successfully")
    
    print(f"Log files are being written to: {LOG_DIR}")
    
    return general_logger, chat_logger, error_logger

# Initialize telegram error handler
def init_error_handler(bot, error_channel_id):
    """Initialize error handler with bot instance"""
    if error_channel_id:
        error_logger = logging.getLogger('error_logger')
        handler = TelegramErrorHandler(bot, error_channel_id)
        handler.setFormatter(KyivTimezoneFormatter(
            '%(asctime)s - %(name)s - %(levelname)s\nFile: %(pathname)s:%(lineno)d\nFunction: %(funcName)s\nMessage: %(message)s'
        ))
        error_logger.addHandler(handler)

# Data management functions
def save_user_location(user_id, city):
    """Save user's location to a CSV file.
    
    Args:
        user_id (int): User ID
        city (str): City name
    """
    # Use relative path that works in both local and CI environments
    file_path = 'data/user_locations.csv'
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Read existing data first
    existing_data = []
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            existing_data = list(reader)
    except FileNotFoundError:
        pass  # File doesn't exist yet, that's fine
    
    # Update or add new entry
    timestamp = datetime.now().isoformat()
    updated = False
    
    for i, row in enumerate(existing_data):
        if len(row) > 0 and row[0] == str(user_id):
            existing_data[i] = [str(user_id), city, timestamp]
            updated = True
            break
    
    if not updated:
        existing_data.append([str(user_id), city, timestamp])
    
    # Write back to file
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(existing_data)

def get_last_used_city(user_id):
    """Retrieve user's last used city.
    
    Args:
        user_id (int): User ID
        
    Returns:
        str: City name or None if not found
    """
    file_path = 'data/user_locations.csv'
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2 and row[0] == str(user_id):
                    # Standardize city name - Kiev should be Kyiv
                    city = row[1]
                    if city == "Kiev":
                        return "Kyiv"
                    return city
    except FileNotFoundError:
        return None
    
    return None


def load_used_words() -> Set[str]:
    """Load used words from CSV file."""
    used_words = set()
    logger = logging.getLogger('general_logger')

    try:
        if os.path.exists(USED_WORDS_FILE):
            with open(USED_WORDS_FILE, mode='r', encoding='utf-8') as file:
                used_words = {word.strip().lower() for row in csv.reader(file) for word in row if word.strip()}
        logger.debug(f"Loaded {len(used_words)} used words from file")
    except Exception as e:
        logger.error(f"Error loading used words: {e}")

    return used_words

def save_used_words(words: Set[str]) -> None:
    """Save used words to CSV file."""
    logger = logging.getLogger('general_logger')
    try:
        with open(USED_WORDS_FILE, mode='w', encoding='utf-8', newline='') as file:
            csv.writer(file).writerow(sorted(words))
        logger.debug(f"Saved {len(words)} words to file")
    except Exception as e:
        logger.error(f"Error saving used words: {e}")

def read_last_n_lines(file_path: str, n: int) -> list:
    """Read the last n lines of a file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        return lines[-n:]  # Return the last n lines

def get_daily_log_path(chat_id: str, date: Optional[datetime] = None) -> str:
    """Generate the path for the daily log file based on chat_id and optional date."""
    if date is None:
        date = datetime.now(KYIV_TZ)
    return os.path.join(LOG_DIR, f"chat_{chat_id}", f"chat_{date.strftime('%Y-%m-%d')}.log")

# Initialize logging when this module is imported
general_logger, chat_logger, error_logger = initialize_logging()