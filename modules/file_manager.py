import os
import csv
import logging
from logging.handlers import RotatingFileHandler
import threading
from typing import Set, Optional
from datetime import datetime
import pytz
from pathlib import Path
import sys

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
CSV_FILE = os.path.join(DATA_DIR, "user_locations.csv")
USED_WORDS_FILE = os.path.join(DATA_DIR, "used_words.csv")
KYIV_TZ = pytz.timezone('Europe/Kyiv')


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


# Telegram error reporting handler



# Data management functions
def save_user_location(user_id, city):
    """Save user's location to a CSV file.
    
    Args:
        user_id (int): User ID
        city (str): City name
    """
    # Use the constant instead of hardcoded path
    file_path = CSV_FILE
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Read existing data first
    existing_data = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
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
    
    # Write back to file - ensure exact parameter naming to match the test
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(existing_data)
