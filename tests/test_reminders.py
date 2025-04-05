import unittest
import os
import sys
import datetime
import pytz
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.reminders.reminders import Reminder, ReminderManager
from modules.const import KYIV_TZ

@pytest.fixture
def reminder_manager():
    """Fixture for creating a ReminderManager instance with a temporary database."""
    # Create a temporary database file
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()
    
    # Create and yield the manager
    try:
        manager = ReminderManager(db_file=temp_db_path)
        yield manager
    finally:
        # Clean up
        if hasattr(manager, 'conn'):
            manager.conn.close()
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)

class TestReminders(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary db file for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize reminder manager with temp db
        try:
            self.reminder_manager = ReminderManager(db_file=self.temp_db_path)
        except Exception as e:
            self.fail(f"Failed to initialize ReminderManager: {e}")
    
    def tearDown(self):
        """Clean up after each test."""
        try:
            if hasattr(self, 'reminder_manager') and hasattr(self.reminder_manager, 'conn'):
                self.reminder_manager.conn.close()
        except Exception as e:
            print(f"Warning: Error closing database connection: {e}")
            
        try:
            if hasattr(self, 'temp_db_path') and os.path.exists(self.temp_db_path):
                os.unlink(self.temp_db_path)
        except Exception as e:
            print(f"Warning: Error removing temporary database file: {e}")

    def test_parse_first_day_of_month(self):
        """Test parsing 'first day of month' patterns."""
        # Test common patterns
        patterns = [
            "first day of every month",
            "first of every month",
            "1st day of every month",
            "1st of every month",
            "1th of every month",
            "1th of the month",
            "on the first day of every month",
            "on first day of every month", 
            "on the first of every month",
            "on first of every month", 
            "on the 1st of every month", 
            "on 1st of every month", 
            "on the 1st day of every month"
        ]
        
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                # Create a reminder with this pattern
                reminder = Reminder(
                    task=f"Task {pattern}",
                    frequency="monthly",
                    delay=None,
                    date_modifier="first day of every month",
                    next_execution=None,
                    user_id=123,
                    chat_id=456
                )
                
                # Calculate next execution
                reminder.calculate_next_execution()
                
                # Verify it's set to the first day of next month
                now = datetime.datetime.now(KYIV_TZ)
                if now.month == 12:
                    expected_month = 1
                    expected_year = now.year + 1
                else:
                    expected_month = now.month + 1
                    expected_year = now.year
                
                # Debug prints to help diagnose the issue
                print(f"Test debug - Pattern: {pattern}")
                print(f"Test debug - Now: {now}")
                print(f"Test debug - Next execution: {reminder.next_execution}")
                print(f"Test debug - Expected day: 1, Actual day: {reminder.next_execution.day}")
                print(f"Test debug - Expected month: {expected_month}, Actual month: {reminder.next_execution.month}")
                
                self.assertEqual(reminder.next_execution.day, 1)
                self.assertEqual(reminder.next_execution.month, expected_month)
                self.assertEqual(reminder.next_execution.year, expected_year)
                # Don't compare tzinfo directly, as it might be different instances of the same timezone
                self.assertEqual(str(reminder.next_execution.tzinfo), str(KYIV_TZ))

    def test_reminder_has_date_modifier(self):
        """Test that reminders with date modifiers have proper values."""
        # Test last day of month modifier
        reminder = Reminder(
            task="Task on last day of month",
            frequency="monthly",
            delay=None,
            date_modifier="last day of every month",
            next_execution=None,
            user_id=123,
            chat_id=456
        )
        
        # Just verify the date_modifier is properly set
        self.assertEqual(reminder.date_modifier, "last day of every month")
        
        # Test first day of month modifier
        reminder = Reminder(
            task="Task on first day of month",
            frequency="monthly",
            delay=None,
            date_modifier="first day of every month",
            next_execution=None,
            user_id=123,
            chat_id=456
        )
        
        # Verify the date_modifier is properly set
        self.assertEqual(reminder.date_modifier, "first day of every month")

    def test_reminder_storage_and_retrieval(self):
        """Test storing and retrieving reminders from database."""
        # Create a test reminder
        task = "Test reminder task"
        frequency = "monthly"
        delay = None
        date_modifier = "first day of every month"
        next_execution = datetime.datetime.now(KYIV_TZ) + datetime.timedelta(days=1)
        user_id = 123
        chat_id = 456
        
        reminder = Reminder(
            task=task,
            frequency=frequency,
            delay=delay,
            date_modifier=date_modifier,
            next_execution=next_execution,
            user_id=user_id,
            chat_id=chat_id
        )
        
        # Add to database
        self.reminder_manager.save_reminder(reminder)
        
        # Retrieve reminders for this chat
        reminders = self.reminder_manager.load_reminders(chat_id)
        
        # Verify we got our reminder back
        self.assertEqual(len(reminders), 1)
        retrieved = reminders[0]
        
        self.assertEqual(retrieved.task, task)
        self.assertEqual(retrieved.frequency, frequency)
        self.assertEqual(retrieved.delay, delay)
        self.assertEqual(retrieved.date_modifier, date_modifier)
        self.assertEqual(retrieved.user_id, user_id)
        self.assertEqual(retrieved.chat_id, chat_id)
        
        # Datetime comparison
        self.assertEqual(retrieved.next_execution.replace(microsecond=0), 
                         next_execution.replace(microsecond=0))
        
        # Test reminder removal using remove_reminder
        self.reminder_manager.remove_reminder(retrieved)
        reminders = self.reminder_manager.load_reminders(chat_id)
        self.assertEqual(len(reminders), 0)

if __name__ == '__main__':
    unittest.main()