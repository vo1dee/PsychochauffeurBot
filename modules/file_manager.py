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

CSV_FILE = os.path.join("data", "user_locations.csv")
LOG_DIR = '/var/log/psychochauffeurbot'
USED_WORDS_FILE = "data/used_words.csv"
KYIV_TZ = pytz.timezone('Europe/Kiev')  # Add Kyiv timezone constant

class KyivTimezoneFormatter(logging.Formatter):
    """Custom formatter that uses Kyiv timezone"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created).astimezone(KYIV_TZ)
        return dt.strftime(datefmt) if datefmt else dt.strftime("%Y-%m-%d %H:%M:%S %z")

def get_daily_log_path(date: Optional[datetime] = None) -> str:
    """Get the path to the daily log file for the specified date."""
    date = date or datetime.now(KYIV_TZ)
    if date.tzinfo is None:
        date = KYIV_TZ.localize(date)
    return os.path.join(LOG_DIR, f"chat_{date.strftime('%Y-%m-%d')}.log")

# Set up logging handlers
handler1 = RotatingFileHandler(os.path.join(LOG_DIR, 'bot.log'), maxBytes=5*1024*1024, backupCount=3)
handler1.setLevel(logging.DEBUG)
handler1.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

class DailyLogHandler(logging.Handler):
    def emit(self, record):
        try:
            daily_log_path = get_daily_log_path()
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


