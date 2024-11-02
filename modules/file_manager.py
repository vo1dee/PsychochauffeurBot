import logging
import csv
import os
from typing import Set

from datetime import datetime
from logging.handlers import RotatingFileHandler
import pytz



CSV_FILE = os.path.join("data", "user_locations.csv")



LOG_DIR = '/var/log/psychochauffeurbot'

USED_WORDS_FILE = "data/used_words.csv"

# Add Kyiv timezone constant
KYIV_TZ = pytz.timezone('Europe/Kiev')

# Update the formatters to use Kyiv timezone
class KyivTimezoneFormatter(logging.Formatter):
    """Custom formatter that uses Kyiv timezone"""
    def formatTime(self, record, datefmt=None):
        # Convert to Kyiv timezone
        dt = datetime.fromtimestamp(record.created).astimezone(KYIV_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %z")

def get_daily_log_path(date=None):
    """Get the path to the daily log file for the specified date."""
    if date is None:
        date = datetime.now(KYIV_TZ)
    elif date.tzinfo is None:
        # If date has no timezone, assume it's in Kyiv timezone
        date = KYIV_TZ.localize(date)
    
    log_path = os.path.join(
        LOG_DIR, 
        f"chat_{date.strftime('%Y-%m-%d')}.log"
    )
    
    general_logger.debug(f"get_daily_log_path: Input date={date}, Generated path={log_path}")
    return log_path

# Set up a rotating file handler for general logs
handler1 = RotatingFileHandler(os.path.join(LOG_DIR, 'bot.log'), maxBytes=5*1024*1024, backupCount=3)
handler1.setLevel(logging.DEBUG)
handler1.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Set up daily chat logs
class DailyLogHandler(logging.Handler):
    def emit(self, record):
        try:
            daily_log_path = get_daily_log_path()
            msg = self.format(record)
            os.makedirs(os.path.dirname(daily_log_path), exist_ok=True)
            with open(daily_log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            self.handleError(record)

# Configure handlers
handler2 = DailyLogHandler()
handler2.setLevel(logging.INFO)
handler2.setFormatter(KyivTimezoneFormatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s - %(chattitle)s - %(username)s - %(message)s'))

# Configure the loggers
general_logger = logging.getLogger('bot_logger')
general_logger.setLevel(logging.DEBUG)
general_logger.addHandler(handler1)

chat_logger = logging.getLogger('bot_chat_logger')
chat_logger.setLevel(logging.INFO)
chat_logger.addHandler(handler2)

# Set a higher logging level for the 'httpx' logger to avoid logging all requests
logging.getLogger("httpx").setLevel(logging.WARNING)


def save_user_location(user_id: int, city: str):
    """Save the user's last used city to a CSV file."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    
    rows = []
    updated = False
    try:
        # Read existing data
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            rows = list(reader)

        # Update if user exists
        for row in rows:
            if int(row[0]) == user_id:
                row[1] = city
                row[2] = datetime.now().isoformat()
                updated = True

        # Add new entry if user doesn't exist
        if not updated:
            rows.append([user_id, city, datetime.now().isoformat()])

        # Write back to CSV
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
    except FileNotFoundError:
        # If CSV doesn't exist, create it and add the user's data
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([user_id, city, datetime.now().isoformat()])

def get_last_used_city(user_id: int) -> str:
    """Retrieve the last used city for the user from the CSV file."""
    try:
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if int(row[0]) == user_id:
                    return row[1]
    except FileNotFoundError:
        # If the CSV file doesn't exist, return None
        return None
    return None


# Function to read the last n lines of the chat log for a specific chat ID
def read_last_n_lines(file_path, chat_id, n=10):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        
        # Filter lines by chat_id (converting chat_id to str as it appears in the log)
        filtered_lines = [line for line in lines if f' {chat_id} ' in line]

        # Debugging output to verify filtering
        print(f"Total lines read: {len(lines)}")  # Total lines in log
        print(f"Filtered lines count for chat_id {chat_id}: {len(filtered_lines)}")  # Filtered lines

        # Return the last n messages for the specific chat
        return filtered_lines[-n:] if len(filtered_lines) >= n else filtered_lines

def ensure_data_directory():
    """Ensure the data directory exists."""
    os.makedirs(os.path.dirname(USED_WORDS_FILE), exist_ok=True)

def load_used_words() -> Set[str]:
    """Load used words from CSV file."""
    ensure_data_directory()
    used_words = set()
    try:
        if os.path.exists(USED_WORDS_FILE):
            with open(USED_WORDS_FILE, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                used_words = set(word.strip().lower() for row in reader for word in row if word.strip())
        general_logger.debug(f"Loaded {len(used_words)} used words from file")
    except Exception as e:
        general_logger.error(f"Error loading used words: {e}")
    return used_words

def save_used_words(words: Set[str]) -> None:
    """Save used words to CSV file."""
    ensure_data_directory()
    try:
        with open(USED_WORDS_FILE, mode='w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(sorted(words))  # Save as a single row
        general_logger.debug(f"Saved {len(words)} words to file")
    except Exception as e:
        general_logger.error(f"Error saving used words: {e}")


