import os
from const import LOG_DIR
from datetime import datetime
from typing import Optional

def ensure_directory(path: str) -> None:
    """Ensure the directory exists."""
    os.makedirs(path, exist_ok=True)


def get_daily_log_path(chat_id: str, date: Optional[datetime] = None) -> str:
    """Returns the daily log file path for a specific chat."""
    if date is None:
        date = datetime.now()  # Use current date if none provided
    chat_log_dir = os.path.join(LOG_DIR, f"chat_{chat_id}")
    ensure_directory(chat_log_dir)  # Ensure the directory exists
    return os.path.join(chat_log_dir, f"chat_{date.strftime('%Y-%m-%d')}.log")