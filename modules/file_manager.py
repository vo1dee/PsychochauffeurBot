import logging
import csv

from datetime import datetime, timedelta, time as dt_time
from logging.handlers import RotatingFileHandler



CSV_FILE = "user_locations.csv"



log_file_path = '/var/log/psychochauffeurbot/bot.log'
chatlog_file_path = '/var/log/psychochauffeurbot/bot_chat.log'

# Set up a rotating file handler for general logs
handler1 = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3)  # 5 MB per log file
handler1.setLevel(logging.INFO)
formatter1 = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler1.setFormatter(formatter1)

# Set up a rotating file handler for chat logs
handler2 = RotatingFileHandler(chatlog_file_path, maxBytes=5*1024*1024, backupCount=3)  # 5 MB per log file
handler2.setLevel(logging.INFO)
formatter2 = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s -  %(chattitle)s - %(username)s - %(message)s')
handler2.setFormatter(formatter2)

# Configure the logger for general logs
general_logger = logging.getLogger('bot_logger')
general_logger.setLevel(logging.INFO)
general_logger.addHandler(handler1)

# Configure a separate logger for chat logs
chat_logger = logging.getLogger('bot_chat_logger')
chat_logger.setLevel(logging.INFO)
chat_logger.addHandler(handler2)


# Set a higher logging level for the 'httpx' logger to avoid logging all requests
logging.getLogger("httpx").setLevel(logging.WARNING)


def save_user_location(user_id: int, city: str):
    """Save the user's last used city to a CSV file."""
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

