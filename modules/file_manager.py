import os
import csv
import logging
from logging.handlers import RotatingFileHandler
import threading
from typing import Set, Optional, Dict, List
from datetime import datetime
import pytz
from pathlib import Path
import sys

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
ANALYTICS_DIR = os.path.join(LOG_DIR, 'analytics')
CSV_FILE = os.path.join(DATA_DIR, "user_locations.csv")
# (deprecated: used_words.csv removed)
KYIV_TZ = pytz.timezone('Europe/Kyiv')


# Ensure directories exist
def ensure_directories() -> bool:
    """Ensure all required directories exist with proper permissions."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(ANALYTICS_DIR, exist_ok=True)
        
        # Verify write permissions
        test_log_path = os.path.join(LOG_DIR, 'test.log')
        with open(test_log_path, 'w') as f:
            f.write('Test log write\n')
        os.remove(test_log_path)
        logging.getLogger(__name__).info("Write permission verified for log directory")
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Error setting up directories: {e}")
        return False

# Custom formatter for Kyiv timezone
class KyivTimezoneFormatter(logging.Formatter):
    """Custom formatter that uses Kyiv timezone"""
    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        dt = datetime.fromtimestamp(record.created).astimezone(KYIV_TZ)
        return dt.strftime(datefmt) if datefmt else dt.strftime("%Y-%m-%d %H:%M:%S %z")


# Telegram error reporting handler



# CSV file management
def ensure_csv_headers(file_path: str, headers: List[str]) -> None:
    """Ensure CSV file exists and has the proper headers.
    
    Args:
        file_path (str): Path to the CSV file
        headers (List[str]): List of column headers
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Check if file exists
    if not os.path.exists(file_path):
        # Create new file with headers
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        logging.getLogger(__name__).info(
            f"Created new CSV file with headers: {file_path}"
        )
        return
    
    # File exists, check if it has headers
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            first_row = next(reader, None)
            
            # If file is empty or headers don't match, add headers
            if not first_row or set(first_row) != set(headers):
                # Read all existing data
                f.seek(0)
                all_data = list(reader)
                
                # Write back with headers
                with open(file_path, mode='w', newline='', encoding='utf-8') as wf:
                    writer = csv.writer(wf)
                    writer.writerow(headers)
                    writer.writerows(all_data)
        logging.getLogger(__name__).info(f"Added or corrected headers in CSV file: {file_path}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error checking CSV headers: {e}")

# Data management functions
def save_user_location(user_id: int, city: str, chat_id: Optional[int] = None) -> None:
    """Save user's location to a CSV file.
    
    Args:
        user_id (int): User ID
        city (str): City name
        chat_id (int, optional): Chat ID for group-specific cities
    """
    # Use the constant instead of hardcoded path
    file_path = CSV_FILE
    
    # Always use "Kyiv" instead of "kiev"
    if city and city.lower() == "kiev":
        city = "Kyiv"
    
    # Ensure CSV file has proper headers
    ensure_csv_headers(file_path, ["user_id", "city", "timestamp", "chat_id"])
    
    # Read existing data first
    existing_data = []
    headers = ["user_id", "city", "timestamp", "chat_id"]
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            file_headers = next(reader, None)  # Skip header row
            if file_headers:
                headers = file_headers
            existing_data = list(reader)
    except FileNotFoundError:
        existing_data = []
    
    # Update or add new entry
    timestamp = datetime.now().isoformat()
    updated = False
    
    for i, row in enumerate(existing_data):
        # Check if we're updating a chat-specific entry
        if chat_id and len(row) >= 4:
            if row[0] == str(user_id) and row[3] == str(chat_id):
                existing_data[i] = [str(user_id), city, timestamp, str(chat_id)]
                updated = True
                break
        # Or a user-specific entry (no chat_id provided)
        elif not chat_id and (len(row) < 4 or not row[3]):
            if row[0] == str(user_id):
                # Preserve or update row based on length
                if len(row) >= 4:
                    existing_data[i] = [str(user_id), city, timestamp, row[3]]
                else:
                    existing_data[i] = [str(user_id), city, timestamp, ""]
                updated = True
                break
    
    if not updated:
        # Add the new entry with appropriate chat_id
        entry = [str(user_id), city, timestamp, str(chat_id) if chat_id else ""]
        existing_data.append(entry)
    
    # Write back to file with headers
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)  # Write headers first
        writer.writerows(existing_data)
    
def get_last_used_city(user_id: int, chat_id: Optional[int] = None) -> Optional[str]:
    """
    Retrieve the last city set by a user, preferring chat-specific entry.
    Returns None if no city is found.
    """
    headers = ["user_id", "city", "timestamp", "chat_id"]
    # Use CSV_FILE for data storage
    file_path = CSV_FILE
    # Ensure CSV file and headers exist
    ensure_csv_headers(file_path, headers)
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # First, look for a chat-specific entry
            if chat_id is not None:
                for row in reader:
                    if row.get('user_id') == str(user_id) and row.get('chat_id') == str(chat_id):
                        city = row.get('city')
                        if city:
                            return 'Kyiv' if city.lower() == 'kiev' else city
                # rewind reader to search default
                f.seek(0)
                next(reader, None)
            # Next, look for a user default entry
            for row in reader:
                if row.get('user_id') == str(user_id) and not row.get('chat_id'):
                    city = row.get('city')
                    if city:
                        return 'Kyiv' if city.lower() == 'kiev' else city
    except FileNotFoundError:
        logging.getLogger(__name__).warning(f"City data file not found: {file_path}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error reading city data: {e}")
    return None
