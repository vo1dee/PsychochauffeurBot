import os
import csv
import logging
import threading
from typing import Set, Optional
from datetime import datetime
import pytz
from pathlib import Path

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
CSV_FILE = os.path.join(DATA_DIR, "user_locations.csv")
KYIV_TZ = pytz.timezone('Europe/Kiev')

# Initialize Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
general_logger = logging.getLogger('general_logger')
error_logger = logging.getLogger('error_logger')

# File lock for thread safety
file_lock = threading.Lock()

def ensure_directory(directory: str) -> None:
    """Ensure directory exists"""
    Path(directory).mkdir(parents=True, exist_ok=True)

def save_user_location(user_id: int, city: str) -> None:
    """Save user's location to a CSV file using DictWriter."""
    ensure_directory(DATA_DIR)
    file_path = CSV_FILE
    timestamp = datetime.now(KYIV_TZ).isoformat()
    
    with file_lock:
        existing_data = {}
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_data[row['user_id']] = row
        except FileNotFoundError:
            pass
        
        # Update or add new entry
        existing_data[str(user_id)] = {
            'user_id': str(user_id),
            'city': city,
            'timestamp': timestamp
        }
        
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['user_id', 'city', 'timestamp'])
            writer.writeheader()
            writer.writerows(existing_data.values())
    
    general_logger.info(f"Updated location for user {user_id}: {city}")

def get_last_used_city(user_id: int) -> Optional[str]:
    """Retrieve user's last used city from a CSV file."""
    file_path = CSV_FILE
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['user_id'] == str(user_id):
                    city = row['city']
                    return "Kyiv" if city.lower() == "kiev" else city
    except FileNotFoundError:
        return None
    return None

def get_daily_log_path(chat_id: str, date: Optional[datetime] = None) -> str:
    """Generate the path for the daily log file."""
    if date is None:
        date = datetime.now(KYIV_TZ)
    chat_log_dir = os.path.join(LOG_DIR, f"chat_{chat_id}")
    ensure_directory(chat_log_dir)
    return os.path.join(chat_log_dir, f"chat_{date.strftime('%Y-%m-%d')}.log")

def read_last_n_lines(file_path: str, n: int) -> list:
    """Read the last n lines of a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            return lines[-n:]
    except FileNotFoundError:
        return []
    except Exception as e:
        error_logger.error(f"Error reading file {file_path}: {e}")
        return []

# Maintain backwards compatibility with class-based usage
class FileManager:
    """Class wrapper for file operations to maintain backwards compatibility"""
    ensure_directory = staticmethod(ensure_directory)
    save_user_location = staticmethod(save_user_location)
    get_last_used_city = staticmethod(get_last_used_city)
    get_daily_log_path = staticmethod(get_daily_log_path)
    read_last_n_lines = staticmethod(read_last_n_lines)