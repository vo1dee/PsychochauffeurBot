import unittest
from unittest.mock import patch, MagicMock
import datetime as dt
from modules.reminders.reminder_models import Reminder
from modules.const import KYIV_TZ

class TestReminder(unittest.TestCase):
    def setUp(self):
        # Use a fixed timezone for testing
        self.now = dt.datetime(2025, 4, 15, 9, 0, tzinfo=KYIV_TZ)

    def assertDatetimeEqual(self, dt1, dt2, msg=None):
        """Compare two datetimes, ignoring timezone implementation differences."""
        self.assertEqual(dt1.year, dt2.year, msg)
        self.assertEqual(dt1.month, dt2.month, msg)
        self.assertEqual(dt1.day, dt2.day, msg)
        self.assertEqual(dt1.hour, dt2.hour, msg)
        self.assertEqual(dt1.minute, dt2.minute, msg)
        self.assertEqual(dt1.second, dt2.second, msg)
        # Compare timezone offset instead of timezone object
        self.assertEqual(dt1.utcoffset(), dt2.utcoffset(), msg)

    @patch('modules.reminders.reminder_models.dt')
    def test_advance_weekly(self, mock_datetime):
        """Test calculating the next execution for weekly reminders."""
        # Mock current time
        mock_datetime.datetime.now.return_value = self.now
        
        # Create a reminder
        reminder = Reminder(
            task="Weekly task",
            frequency="weekly",
            delay=None,
            date_modifier=None,
            next_execution=dt.datetime(2025, 4, 15, 9, 0, tzinfo=KYIV_TZ),
            user_id=123456,
            chat_id=-100123456
        )
        
        # Call the calculate_next_execution method
        reminder.calculate_next_execution()
        
        # The next execution should be 1 week later
        expected_next = dt.datetime(2025, 4, 22, 9, 0, tzinfo=KYIV_TZ)
        self.assertDatetimeEqual(reminder.next_execution, expected_next)

    @patch('modules.reminders.reminder_models.dt')
    def test_advance_monthly(self, mock_datetime):
        """Test calculating the next execution for monthly reminders."""
        # Mock current time
        mock_datetime.datetime.now.return_value = self.now
        
        # Create a reminder
        reminder = Reminder(
            task="Monthly task",
            frequency="monthly",
            delay=None,
            date_modifier=None,
            next_execution=dt.datetime(2025, 4, 15, 9, 0, tzinfo=KYIV_TZ),
            user_id=123456,
            chat_id=-100123456
        )
        
        # Call the calculate_next_execution method
        reminder.calculate_next_execution()
        
        # The next execution should be 1 month later
        expected_next = dt.datetime(2025, 5, 15, 9, 0, tzinfo=KYIV_TZ)
        self.assertDatetimeEqual(reminder.next_execution, expected_next)

    @patch('modules.reminders.reminder_models.dt')
    def test_advance_yearly(self, mock_datetime):
        """Test calculating the next execution for yearly reminders."""
        # Mock current time
        mock_datetime.datetime.now.return_value = self.now
        
        # Create a reminder
        reminder = Reminder(
            task="Yearly task",
            frequency="yearly",
            delay=None,
            date_modifier=None,
            next_execution=dt.datetime(2025, 4, 15, 9, 0, tzinfo=KYIV_TZ),
            user_id=123456,
            chat_id=-100123456
        )
        
        # Call the calculate_next_execution method
        reminder.calculate_next_execution()
        
        # The next execution should be 1 year later
        expected_next = dt.datetime(2026, 4, 15, 9, 0, tzinfo=KYIV_TZ)
        self.assertDatetimeEqual(reminder.next_execution, expected_next)

    @patch('modules.reminders.reminder_models.dt')
    def test_calc_last_month(self, mock_datetime):
        """Test calculating the next execution for last day of month reminders."""
        # Mock current time
        mock_datetime.datetime.now.return_value = self.now
        mock_datetime.datetime.side_effect = dt.datetime
        
        # Create a reminder
        reminder = Reminder(
            task="Last day task",
            frequency="monthly",
            delay=None,
            date_modifier="last day of every month",
            next_execution=dt.datetime(2025, 4, 30, 9, 0, tzinfo=KYIV_TZ),
            user_id=123456,
            chat_id=-100123456
        )
        
        # Call the calculate_next_execution method
        reminder.calculate_next_execution()
        
        # The next execution should be the last day of May 2025
        expected_next = dt.datetime(2025, 5, 31, 9, 0, tzinfo=KYIV_TZ)
        self.assertDatetimeEqual(reminder.next_execution, expected_next)

    @patch('modules.reminders.reminder_models.dt')
    def test_calc_first_month(self, mock_datetime):
        """Test calculating the next execution for first day of month reminders."""
        # Mock current time
        mock_datetime.datetime.now.return_value = self.now
        mock_datetime.datetime.side_effect = dt.datetime
        
        # Create a reminder
        reminder = Reminder(
            task="First day task",
            frequency="monthly",
            delay=None,
            date_modifier="first day of every month",
            next_execution=dt.datetime(2025, 4, 1, 9, 0, tzinfo=KYIV_TZ),
            user_id=123456,
            chat_id=-100123456
        )
        
        # Call the calculate_next_execution method
        reminder.calculate_next_execution()
        
        # The next execution should be the first day of May 2025
        expected_next = dt.datetime(2025, 5, 1, 9, 0, tzinfo=KYIV_TZ)
        self.assertDatetimeEqual(reminder.next_execution, expected_next)

    def test_to_tuple(self):
        """Test converting a reminder to a tuple."""
        # Create a reminder with a fixed timezone
        next_execution = dt.datetime(2025, 4, 15, 9, 0, tzinfo=KYIV_TZ)
        reminder = Reminder(
            task="Test task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=next_execution,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="Test User",
            reminder_id=1
        )
        
        # Get the actual tuple
        actual_tuple = reminder.to_tuple()
        
        # Verify each field individually
        self.assertEqual(actual_tuple[0], 1)  # reminder_id
        self.assertEqual(actual_tuple[1], "Test task")  # task
        self.assertEqual(actual_tuple[2], "daily")  # frequency
        self.assertEqual(actual_tuple[3], None)  # delay
        self.assertEqual(actual_tuple[4], None)  # date_modifier
        
        # Parse the datetime string and compare with the original
        actual_dt = dt.datetime.fromisoformat(actual_tuple[5])
        self.assertDatetimeEqual(actual_dt, next_execution)
        
        self.assertEqual(actual_tuple[6], 123456)  # user_id
        self.assertEqual(actual_tuple[7], -100123456)  # chat_id
        self.assertEqual(actual_tuple[8], "Test User")  # user_mention_md

    def test_from_tuple(self):
        """Test creating a reminder from a tuple."""
        data = (
            1,  # reminder_id
            "Test task",  # task
            "daily",  # frequency
            None,  # delay
            None,  # date_modifier
            "2025-04-15T09:00:00+03:00",  # next_execution
            123456,  # user_id
            -100123456,  # chat_id
            "Test User"  # user_mention_md
        )
        
        reminder = Reminder.from_tuple(data)
        
        # Verify each field individually
        self.assertEqual(reminder.reminder_id, 1)
        self.assertEqual(reminder.task, "Test task")
        self.assertEqual(reminder.frequency, "daily")
        self.assertEqual(reminder.delay, None)
        self.assertEqual(reminder.date_modifier, None)
        
        # Parse the expected datetime and compare
        expected_dt = dt.datetime.fromisoformat("2025-04-15T09:00:00+03:00")
        self.assertDatetimeEqual(reminder.next_execution, expected_dt)
        
        self.assertEqual(reminder.user_id, 123456)
        self.assertEqual(reminder.chat_id, -100123456)
        self.assertEqual(reminder.user_mention_md, "Test User") 