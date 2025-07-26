"""
Comprehensive tests for reminder validation and constraint checking.
This module tests validation logic, constraint enforcement, and error handling
for reminder creation and management.
"""

import pytest
import datetime as dt
from unittest.mock import patch, MagicMock, AsyncMock
from telegram import Update, User, Chat, Message
from telegram.ext import CallbackContext

from modules.reminders.reminders import ReminderManager
from modules.reminders.reminder_models import Reminder
from modules.reminders.reminder_db import ReminderDB
from modules.const import KYIV_TZ


class TestReminderValidation:
    """Comprehensive tests for reminder validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ReminderManager(db_file=':memory:')
        self.base_time = dt.datetime(2025, 7, 25, 10, 0, tzinfo=KYIV_TZ)

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self.manager.db, 'conn'):
            self.manager.db.conn.close()

    def test_reminder_creation_validation(self):
        """Test validation during reminder creation."""
        # Valid reminder
        reminder = Reminder(
            task="Test task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        
        # Test required fields
        assert reminder.task is not None, "Task should not be None"
        assert reminder.user_id is not None, "User ID should not be None"
        assert reminder.chat_id is not None, "Chat ID should not be None"
        
        # Test field types
        assert isinstance(reminder.task, str), "Task should be string"
        assert isinstance(reminder.user_id, int), "User ID should be integer"
        assert isinstance(reminder.chat_id, int), "Chat ID should be integer"

    def test_frequency_validation(self):
        """Test validation of frequency values."""
        valid_frequencies = ['daily', 'weekly', 'monthly', 'yearly', None]
        
        for freq in valid_frequencies:
            reminder = Reminder(
                task="Test task",
                frequency=freq,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time,
                user_id=123456,
                chat_id=-100123456
            )
            assert reminder.frequency == freq, f"Frequency {freq} should be valid"

    def test_datetime_validation(self):
        """Test validation of datetime fields."""
        # Test timezone-aware datetime
        tz_aware = dt.datetime(2025, 7, 25, 10, 0, tzinfo=KYIV_TZ)
        reminder = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=tz_aware,
            user_id=123456,
            chat_id=-100123456
        )
        assert reminder.next_execution.tzinfo is not None, "Datetime should be timezone-aware"
        
        # Test None datetime (should be allowed)
        reminder_none = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=None,
            user_id=123456,
            chat_id=-100123456
        )
        assert reminder_none.next_execution is None, "None datetime should be allowed"

    def test_user_id_validation(self):
        """Test validation of user ID constraints."""
        # Test positive user ID
        reminder = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        assert reminder.user_id > 0, "User ID should be positive"
        
        # Test that user ID is stored correctly
        assert reminder.user_id == 123456, "User ID should be stored correctly"

    def test_chat_id_validation(self):
        """Test validation of chat ID constraints."""
        # Test negative chat ID (group chat)
        reminder_group = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        assert reminder_group.chat_id < 0, "Group chat ID should be negative"
        
        # Test positive chat ID (private chat)
        reminder_private = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=123456
        )
        assert reminder_private.chat_id > 0, "Private chat ID should be positive"

    def test_task_content_validation(self):
        """Test validation of task content."""
        # Test non-empty task
        reminder = Reminder(
            task="Valid task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        assert len(reminder.task.strip()) > 0, "Task should not be empty"
        
        # Test task with special characters
        special_task = "Task with émojis 🎉 and symbols @#$%"
        reminder_special = Reminder(
            task=special_task,
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        assert reminder_special.task == special_task, "Task should preserve special characters"

    @pytest.mark.asyncio
    async def test_reminder_limit_validation(self):
        """Test validation of reminder limits per user."""
        # Mock update and context
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = -100123456
        update.effective_chat.type = 'group'
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        context = MagicMock(spec=CallbackContext)
        context.args = ["to", "test", "task", "at", "3pm"]
        context.job_queue = MagicMock()
        context.job_queue.run_once = MagicMock()
        
        # Create multiple reminders to test limit
        for i in range(5):  # Assuming max limit is 5
            reminder = Reminder(
                task=f"Task {i}",
                frequency=None,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time,
                user_id=123456,
                chat_id=-100123456
            )
            self.manager.save_reminder(reminder)
        
        # Mock load_reminders to return our test reminders
        with patch.object(self.manager, 'load_reminders') as mock_load:
            mock_load.return_value = [
                Reminder(f"Task {i}", None, None, None, self.base_time, 123456, -100123456)
                for i in range(5)
            ]
            
            # Try to add one more reminder (should fail)
            await self.manager.remind(update, context)
            
            # Should have called reply_text with limit message
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "limit" in call_args.lower(), "Should mention limit in error message"

    def test_database_constraint_validation(self):
        """Test database-level constraint validation."""
        # Test saving valid reminder
        reminder = Reminder(
            task="Test task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        
        saved = self.manager.save_reminder(reminder)
        assert saved.reminder_id is not None, "Saved reminder should have ID"
        
        # Test that save operation worked
        assert saved.task == "Test task", "Saved reminder should preserve task"
        assert saved.frequency == "daily", "Saved reminder should preserve frequency"

    def test_next_execution_calculation_validation(self):
        """Test validation of next execution time calculations."""
        reminder = Reminder(
            task="Daily task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        
        # Test that calculate_next_execution doesn't crash
        original_time = reminder.next_execution
        try:
            reminder.calculate_next_execution()
            # If we get here, the method executed without error
            assert True, "calculate_next_execution should not crash"
        except Exception as e:
            # If there's an error, it should be handled gracefully
            assert False, f"calculate_next_execution should not raise exception: {e}"

    def test_timezone_consistency_validation(self):
        """Test validation of timezone consistency."""
        # Test that all datetime operations maintain timezone consistency
        reminder = Reminder(
            task="Test task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        
        # Convert to tuple and back
        tuple_data = reminder.to_tuple()
        restored = Reminder.from_tuple(tuple_data)
        
        # Should maintain timezone
        assert restored.next_execution.tzinfo is not None, "Restored reminder should be timezone-aware"
        assert restored.next_execution.tzinfo == KYIV_TZ or \
               restored.next_execution.utcoffset() == KYIV_TZ.utcoffset(self.base_time), \
               "Timezone should be consistent"

    def test_date_modifier_validation(self):
        """Test validation of date modifier constraints."""
        valid_modifiers = [
            "first day of every month",
            "last day of every month",
            None
        ]
        
        for modifier in valid_modifiers:
            reminder = Reminder(
                task="Test task",
                frequency="monthly" if modifier else None,
                delay=None,
                date_modifier=modifier,
                next_execution=self.base_time,
                user_id=123456,
                chat_id=-100123456
            )
            assert reminder.date_modifier == modifier, f"Date modifier {modifier} should be valid"

    def test_delay_format_validation(self):
        """Test validation of delay format constraints."""
        valid_delays = [
            "in 30 minutes",
            "in 2 hours", 
            "in 3 days",
            "in 1 week",
            "in 6 months",
            None
        ]
        
        for delay in valid_delays:
            reminder = Reminder(
                task="Test task",
                frequency=None,
                delay=delay,
                date_modifier=None,
                next_execution=self.base_time,
                user_id=123456,
                chat_id=-100123456
            )
            assert reminder.delay == delay, f"Delay {delay} should be valid"

    @pytest.mark.asyncio
    async def test_command_validation(self):
        """Test validation of reminder commands."""
        # Mock update and context for invalid commands
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = -100123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        context = MagicMock(spec=CallbackContext)
        
        # Test empty command
        context.args = []
        await self.manager.remind(update, context)
        update.message.reply_text.assert_called()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Usage:" in call_args, "Should show usage for empty command"
        
        # Test invalid delete command
        context.args = ["delete"]
        await self.manager.remind(update, context)
        update.message.reply_text.assert_called()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Usage" in call_args, "Should show usage for invalid delete"

    def test_reminder_serialization_validation(self):
        """Test validation of reminder serialization/deserialization."""
        original = Reminder(
            task="Test task with unicode: 🎉",
            frequency="daily",
            delay="in 1 hour",
            date_modifier="first day of every month",
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="@testuser",
            reminder_id=42
        )
        
        # Serialize to tuple
        tuple_data = original.to_tuple()
        
        # Validate tuple structure
        assert len(tuple_data) == 9, "Tuple should have 9 elements"
        assert tuple_data[0] == 42, "Reminder ID should be preserved"
        assert tuple_data[1] == "Test task with unicode: 🎉", "Task should be preserved"
        assert tuple_data[2] == "daily", "Frequency should be preserved"
        assert tuple_data[3] == "in 1 hour", "Delay should be preserved"
        assert tuple_data[4] == "first day of every month", "Date modifier should be preserved"
        assert tuple_data[6] == 123456, "User ID should be preserved"
        assert tuple_data[7] == -100123456, "Chat ID should be preserved"
        assert tuple_data[8] == "@testuser", "User mention should be preserved"
        
        # Deserialize from tuple
        restored = Reminder.from_tuple(tuple_data)
        
        # Validate restoration
        assert restored.reminder_id == original.reminder_id
        assert restored.task == original.task
        assert restored.frequency == original.frequency
        assert restored.delay == original.delay
        assert restored.date_modifier == original.date_modifier
        assert restored.user_id == original.user_id
        assert restored.chat_id == original.chat_id
        assert restored.user_mention_md == original.user_mention_md

    def test_edge_case_validation(self):
        """Test validation of edge cases and boundary conditions."""
        # Test very long task
        long_task = "a" * 1000
        reminder = Reminder(
            task=long_task,
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        assert len(reminder.task) == 1000, "Long task should be preserved"
        
        # Test extreme user IDs
        max_user_id = 2**31 - 1  # Max 32-bit signed integer
        reminder_max = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=max_user_id,
            chat_id=-100123456
        )
        assert reminder_max.user_id == max_user_id, "Max user ID should be handled"
        
        # Test extreme chat IDs
        min_chat_id = -2**31  # Min 32-bit signed integer
        reminder_min = Reminder(
            task="Test task",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=min_chat_id
        )
        assert reminder_min.chat_id == min_chat_id, "Min chat ID should be handled"

    def test_concurrent_access_validation(self):
        """Test validation under concurrent access scenarios."""
        # This test simulates concurrent access to the database
        db1 = ReminderDB(':memory:')
        db2 = ReminderDB(':memory:')
        
        # Both should be able to create tables without conflict
        reminder1 = Reminder(
            task="Task 1",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        
        reminder2 = Reminder(
            task="Task 2",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=789012,
            chat_id=-100123456
        )
        
        # Both should save successfully
        saved1 = db1.save_reminder(reminder1)
        saved2 = db2.save_reminder(reminder2)
        
        assert saved1.reminder_id is not None
        assert saved2.reminder_id is not None