import logging
import csv
import os
from typing import Set, Optional
import asyncio
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
import pytz
from const import Config  # Add this import at the top
import sys

CSV_FILE = os.path.join("data", "user_locations.csv")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
USED_WORDS_FILE = "data/used_words.csv"
KYIV_TZ = pytz.timezone('Europe/Kiev')  # Add Kyiv timezone constant

# Get the project root directory (one level up from modules)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')

# Create log directory if it doesn't exist
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    print(f"Log directory created/verified at: {LOG_DIR}")
except Exception as e:
    print(f"Error creating log directory: {e}")
    sys.exit(1)

# Verify write permissions by attempting to create a test file
test_log_path = os.path.join(LOG_DIR, 'test.log')
try:
    with open(test_log_path, 'w') as f:
        f.write('Test log write\n')
    os.remove(test_log_path)
    print("Write permission verified for log directory")
except Exception as e:
    print(f"Error: No write permission for log directory: {e}")
    sys.exit(1)

class KyivTimezoneFormatter(logging.Formatter):
    """Custom formatter that uses Kyiv timezone"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created).astimezone(KYIV_TZ)
        return dt.strftime(datefmt) if datefmt else dt.strftime("%Y-%m-%d %H:%M:%S %z")

def get_daily_log_path(date: Optional[datetime] = None, chat_id: Optional[int] = None) -> str:
    """Get the path to the daily log file for the specified date and chat."""
    date = date or datetime.now(KYIV_TZ)
    if date.tzinfo is None:
        date = KYIV_TZ.localize(date)
    
    if chat_id is not None:
        # Store chat-specific logs in subdirectories
        chat_log_dir = os.path.join(LOG_DIR, f"chat_{chat_id}")
        return os.path.join(chat_log_dir, f"chat_{date.strftime('%Y-%m-%d')}.log")
    else:
        # Default path for general logs
        return os.path.join(LOG_DIR, f"chat_{date.strftime('%Y-%m-%d')}.log")

# Create logs directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Set up logging handlers
handler1 = RotatingFileHandler(os.path.join(LOG_DIR, 'bot.log'), maxBytes=5*1024*1024, backupCount=3)
handler1.setLevel(logging.DEBUG)
handler1.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

class DailyLogHandler(logging.Handler):
    def emit(self, record):
        try:
            # Extract chat_id from the log record
            chat_id = getattr(record, 'chat_id', None)
            daily_log_path = get_daily_log_path(chat_id=chat_id)
            msg = self.format(record)
            os.makedirs(os.path.dirname(daily_log_path), exist_ok=True)
            with open(daily_log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception as e:
            self.handleError(record)

handler2 = DailyLogHandler()
handler2.setLevel(logging.INFO)
handler2.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s - %(chattitle)s - %(username)s - %(message)s'))

general_logger = logging.getLogger('bot_logger')
general_logger.setLevel(logging.DEBUG)
general_logger.addHandler(handler1)

chat_logger = logging.getLogger('bot_chat_logger')
chat_logger.setLevel(logging.INFO)
chat_logger.addHandler(handler2)

logging.getLogger("httpx").setLevel(logging.WARNING)

def save_user_location(user_id: int, city: str) -> None:
    """Save the user's last used city to a CSV file."""
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    updated = False
    rows = []

    try:
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            rows = list(csv.reader(file))
        
        for row in rows:
            if int(row[0]) == user_id:
                row[1], row[2] = city, datetime.now().isoformat()
                updated = True
                break
        
        if not updated:
            rows.append([user_id, city, datetime.now().isoformat()])

    except FileNotFoundError:
        pass  # File will be created below

    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
        csv.writer(file).writerows(rows)

def get_last_used_city(user_id: int) -> Optional[str]:
    """Retrieve the last used city for the user from the CSV file."""
    try:
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            for row in csv.reader(file):
                if int(row[0]) == user_id:
                    return row[1]
    except FileNotFoundError:
        return None

def ensure_data_directory() -> None:
    """Ensure the data directory exists."""
    os.makedirs(os.path.dirname(USED_WORDS_FILE), exist_ok=True)

def load_used_words() -> Set[str]:
    """Load used words from CSV file."""
    ensure_data_directory()
    used_words = set()

    try:
        if os.path.exists(USED_WORDS_FILE):
            with open(USED_WORDS_FILE, mode='r', encoding='utf-8') as file:
                used_words = {word.strip().lower() for row in csv.reader(file) for word in row if word.strip()}
        general_logger.debug(f"Loaded {len(used_words)} used words from file")
    except Exception as e:
        general_logger.error(f"Error loading used words: {e}")

    return used_words

def save_used_words(words: Set[str]) -> None:
    """Save used words to CSV file."""
    ensure_data_directory()
    try:
        with open(USED_WORDS_FILE, mode='w', encoding='utf-8', newline='') as file:
            csv.writer(file).writerow(sorted(words))
        general_logger.debug(f"Saved {len(words)} words to file")
    except Exception as e:
        general_logger.error(f"Error saving used words: {e}")

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

error_logger = logging.getLogger('bot_error_logger')
error_logger.setLevel(logging.ERROR)

def init_error_handler(bot) -> None:
    """Initialize error handler with bot instance"""
    if Config.ERROR_CHANNEL_ID:
        handler = TelegramErrorHandler(bot, Config.ERROR_CHANNEL_ID)
        handler.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s\nFile: %(pathname)s:%(lineno)d\nFunction: %(funcName)s\nMessage: %(message)s'))
        error_logger.addHandler(handler)

def read_last_n_lines(file_path: str, n: int) -> list:
    """Read the last n lines of a file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        return lines[-n:]  # Return the last n lines

# Configure loggers
error_logger = logging.getLogger('error_logger')
error_logger.setLevel(logging.INFO)

chat_logger = logging.getLogger('chat_logger')
chat_logger.setLevel(logging.INFO)

general_logger = logging.getLogger('general_logger')
general_logger.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create file handlers with absolute paths
error_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'error.log'),
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3,
    encoding='utf-8'
)

chat_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'chat.log'),
    maxBytes=5*1024*1024,
    backupCount=3,
    encoding='utf-8'
)

general_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'general.log'),
    maxBytes=5*1024*1024,
    backupCount=3,
    encoding='utf-8'
)

# Create formatters and add it to handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
error_handler.setFormatter(formatter)
chat_handler.setFormatter(formatter)
general_handler.setFormatter(formatter)

# Add both console and file handlers to the loggers
error_logger.addHandler(console_handler)
error_logger.addHandler(error_handler)

chat_logger.addHandler(console_handler)
chat_logger.addHandler(chat_handler)

general_logger.addHandler(console_handler)
general_logger.addHandler(general_handler)

# Prevent duplicate logs
error_logger.propagate = False
chat_logger.propagate = False
general_logger.propagate = False

# Log initial setup success
try:
    error_logger.info("Logging system initialized successfully")
    chat_logger.info("Chat logging system initialized successfully")
    general_logger.info("General logging system initialized successfully")
    print(f"Log files are being written to: {LOG_DIR}")
    print("Available log files:")
    print(f"  - {os.path.join(LOG_DIR, 'error.log')}")
    print(f"  - {os.path.join(LOG_DIR, 'chat.log')}")
    print(f"  - {os.path.join(LOG_DIR, 'general.log')}")
except Exception as e:
    print(f"Error writing initial log messages: {e}")
    sys.exit(1)