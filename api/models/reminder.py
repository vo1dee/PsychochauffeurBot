"""
Thread-safe version of ReminderManager for the API.
"""
import sqlite3
from modules.reminders.reminders import Reminder, ReminderManager as OriginalReminderManager


from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class ReminderBase(BaseModel):
    """Base reminder schema without DB-specific fields"""
    task: str
    frequency: Optional[str] = None
    delay: Optional[str] = None
    date_modifier: Optional[str] = None
    next_execution: Optional[datetime] = None
    user_id: int
    chat_id: int
    user_mention_md: Optional[str] = None


class ReminderRead(ReminderBase):
    """Schema for reading reminders, includes ID"""
    reminder_id: int

    class Config:
        from_attributes = True


class ReminderList(BaseModel):
    """Schema for list of reminders"""
    items: List[ReminderRead]
    count: int

class ThreadSafeReminderManager(OriginalReminderManager):
    """
    Thread-safe version of ReminderManager for use in FastAPI.
    Each method creates its own connection to avoid SQLite thread issues.
    """
    
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        # Don't keep a persistent connection - create as needed
        self._create_table()
        # Don't load reminders in constructor
        self.reminders = []
        
    def _create_table(self):
        """Create reminders table if it doesn't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    frequency TEXT,
                    delay TEXT,
                    date_modifier TEXT,
                    next_execution TEXT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_mention_md TEXT
                )
            ''')
            conn.commit()

    def get_connection(self):
        """Get a new database connection with thread safety enabled"""
        return sqlite3.connect(self.db_file, check_same_thread=False)
        
    def load_reminders(self, chat_id=None):
        """Load all reminders from the database, optionally filtered by chat_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if chat_id:
                cursor.execute('SELECT * FROM reminders WHERE chat_id = ?', (chat_id,))
            else:
                cursor.execute('SELECT * FROM reminders')
            data = cursor.fetchall()
            return [Reminder.from_tuple(r) for r in data]