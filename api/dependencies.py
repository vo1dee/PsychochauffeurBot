"""
Dependencies for FastAPI routes.
"""
import os
from fastapi import Depends
from api.models.reminder import ThreadSafeReminderManager


def get_reminder_manager() -> ThreadSafeReminderManager:
    """
    Create and return a thread-safe ReminderManager instance.
    Used as a FastAPI dependency.
    """
    db_path = os.getenv("REMINDER_DB_PATH", "reminders.db")
    return ThreadSafeReminderManager(db_file=db_path)