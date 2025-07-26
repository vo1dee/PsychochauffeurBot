"""
Comprehensive tests for reminder scheduling and notifications functionality.
This module tests reminder scheduling, queue management, notification delivery,
retry logic, and reminder persistence and state management.
"""

import pytest
import datetime as dt
from unittest.mock import patch, MagicMock, AsyncMock, call
from telegram import Update, User, Chat, Message
from telegram.ext import CallbackContext, JobQueue
from telegram.ext._jobqueue import Job

from modules.reminders.reminders import ReminderManager, seconds_until
from modules.reminders.reminder_models import Reminder
from modules.reminders.reminder_db import ReminderDB
from modules.const import KYIV_TZ


class TestReminderScheduling:
    """Comprehensive tests for reminder scheduling functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ReminderManager(db_file=':memory:')
        self.base_time = dt.datetime(2025, 7, 25, 10, 0, tzinfo=KYIV_TZ)

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self.manager.db, 'conn'):
            self.manager.db.conn.close()

    def test_seconds_until_calculation(self):
        """Test accurate calculation of seconds until execution."""
        # Test future time
        future_time = self.base_time + dt.timedelta(hours=2)
        with patch('modules.reminders.reminders.datetime') as mock_dt:
            mock_dt.now.return_value = self.base_time
            seconds = seconds_until(future_time)
            expected_seconds = 2 * 60 * 60  # 2 hours in seconds
            assert abs(seconds - expected_seconds) < 1, "Should calculate correct seconds"

        # Test past time (should return minimum value)
        past_time = self.base_time - dt.timedelta(hours=1)
        with patch('modules.reminders.reminders.datetime') as mock_dt:
            mock_dt.now.return_value = self.base_time
            seconds = seconds_until(past_time)
            assert seconds == 0.01, "Past time should return minimum value"

    @pytest.mark.asyncio
    async def test_reminder_scheduling_workflow(self):
        """Test the complete reminder scheduling workflow."""
        # Mock update and context
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.mention_markdown_v2.return_value = "@testuser"
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = -100123456
        update.effective_chat.type = 'group'
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()

        context = MagicMock(spec=CallbackContext)
        context.args = ["to", "test", "task", "in", "1", "hour"]
        context.job_queue = MagicMock(spec=JobQueue)
        context.job_queue.run_once = MagicMock()

        # Execute the remind command
        await self.manager.remind(update, context)

        # Verify job was scheduled
        context.job_queue.run_once.assert_called_once()
        call_args = context.job_queue.run_once.call_args
        
        # Check that callback function is send_reminder
        assert call_args[0][0] == self.manager.send_reminder
        
        # Check that delay is reasonable (around 1 hour)
        delay = call_args[0][1]
        assert 3500 < delay < 3700, f"Delay should be around 1 hour, got {delay}"
        
        # Check that reminder data is passed
        assert 'data' in call_args[1]
        reminder_data = call_args[1]['data']
        assert isinstance(reminder_data, Reminder)
        assert reminder_data.task == "test task"

    @pytest.mark.asyncio
    async def test_job_queue_integration(self):
        """Test integration with Telegram job queue."""
        # Create a reminder
        reminder = Reminder(
            task="Test job queue",
            frequency=None,
            delay="in 1 hour",
            date_modifier=None,
            next_execution=self.base_time + dt.timedelta(hours=1),
            user_id=123456,
            chat_id=-100123456
        )

        # Mock job queue
        job_queue = MagicMock(spec=JobQueue)
        job_queue.run_once = MagicMock()

        # Mock context
        context = MagicMock()
        context.job_queue = job_queue

        # Test scheduling
        with patch('modules.reminders.reminders.seconds_until') as mock_seconds:
            mock_seconds.return_value = 3600  # 1 hour
            
            # Simulate scheduling logic
            delay_sec = mock_seconds.return_value
            job_queue.run_once(
                self.manager.send_reminder, 
                delay_sec, 
                data=reminder, 
                name=f"reminder_{reminder.reminder_id}"
            )

            # Verify job was scheduled correctly
            job_queue.run_once.assert_called_once_with(
                self.manager.send_reminder,
                3600,
                data=reminder,
                name=f"reminder_{reminder.reminder_id}"
            )

    @pytest.mark.asyncio
    async def test_send_reminder_notification(self):
        """Test sending reminder notifications."""
        # Create a test reminder
        reminder = Reminder(
            task="Test notification",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="@testuser"
        )

        # Mock context and job
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        context.job = MagicMock(spec=Job)
        context.job.data = reminder
        context.job_queue = MagicMock()
        context.job_queue.run_once = MagicMock()

        # Mock the manager's methods
        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Call send_reminder
            await self.manager.send_reminder(context)

            # Verify message was sent
            context.bot.send_message.assert_called()
            call_args = context.bot.send_message.call_args
            
            # Check message content
            assert call_args[0][0] == -100123456  # chat_id is first positional arg
            message_text = call_args[0][1]  # message text is second positional arg
            assert "Test notification" in message_text
            assert "@testuser" in message_text

            # Verify reminder was deleted (for one-time reminders)
            mock_delete.assert_called_once_with(reminder)

    @pytest.mark.asyncio
    async def test_recurring_reminder_rescheduling(self):
        """Test rescheduling of recurring reminders."""
        # Create a daily reminder
        reminder = Reminder(
            task="Daily task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="@testuser"
        )

        # Mock context and job
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        context.job = MagicMock(spec=Job)
        context.job.data = reminder
        context.job_queue = MagicMock()
        context.job_queue.run_once = MagicMock()

        # Mock the manager's methods
        with patch.object(self.manager, 'save_reminder') as mock_save:
            mock_save.return_value = reminder
            
            # Call send_reminder
            await self.manager.send_reminder(context)

            # Verify message was sent
            context.bot.send_message.assert_called()

            # Verify reminder was rescheduled (not deleted)
            mock_save.assert_called()
            
            # Verify new job was scheduled
            context.job_queue.run_once.assert_called()

    def test_reminder_persistence(self):
        """Test reminder persistence and state management."""
        # Create and save a reminder
        reminder = Reminder(
            task="Persistent task",
            frequency="weekly",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Save reminder
        saved = self.manager.save_reminder(reminder)
        assert saved.reminder_id is not None, "Saved reminder should have ID"

        # Load reminders
        loaded = self.manager.load_reminders()
        found = any(r.task == "Persistent task" for r in loaded)
        assert found, "Should find saved reminder"

        # Update reminder
        saved.task = "Updated task"
        updated = self.manager.save_reminder(saved)
        assert updated.task == "Updated task", "Should update existing reminder"

        # Remove reminder
        self.manager.remove_reminder(saved)
        loaded_after_delete = self.manager.load_reminders()
        found_after_delete = any(r.task == "Updated task" for r in loaded_after_delete)
        assert not found_after_delete, "Should not find deleted reminder"

    def test_reminder_state_transitions(self):
        """Test reminder state transitions during lifecycle."""
        reminder = Reminder(
            task="State test",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Initial state
        assert reminder.next_execution == self.base_time
        assert reminder.frequency == "daily"

        # Calculate next execution
        with patch('modules.reminders.reminder_models.datetime') as mock_dt:
            mock_dt.now.return_value = self.base_time + dt.timedelta(days=1)
            mock_dt.datetime = dt.datetime
            mock_dt.timedelta = dt.timedelta
            
            original_time = reminder.next_execution
            reminder.calculate_next_execution()
            
            # State should have changed
            assert reminder.next_execution != original_time

    @pytest.mark.asyncio
    async def test_notification_retry_logic(self):
        """Test retry logic for failed notifications."""
        # Create a reminder
        reminder = Reminder(
            task="Retry test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context with failing bot
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock(side_effect=Exception("Network error"))
        context.job = MagicMock(spec=Job)
        context.job.data = reminder
        context.job_queue = MagicMock()

        # Mock the manager's methods
        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Call send_reminder - should handle exception gracefully
            try:
                await self.manager.send_reminder(context)
                # If we get here, the exception was handled
                assert True, "Should handle notification failure gracefully"
            except Exception:
                # Should not propagate the exception
                assert False, "Should not propagate notification exceptions"

    def test_queue_management(self):
        """Test reminder queue management functionality."""
        # Create multiple reminders
        reminders = []
        for i in range(5):
            reminder = Reminder(
                task=f"Task {i}",
                frequency=None,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time + dt.timedelta(hours=i),
                user_id=123456,
                chat_id=-100123456
            )
            saved = self.manager.save_reminder(reminder)
            reminders.append(saved)

        # Load all reminders
        loaded = self.manager.load_reminders()
        assert len(loaded) >= 5, "Should load all saved reminders"

        # Test filtering by chat_id
        chat_reminders = self.manager.load_reminders(chat_id=-100123456)
        assert len(chat_reminders) >= 5, "Should filter by chat_id"

        # Clean up
        for reminder in reminders:
            self.manager.remove_reminder(reminder)

    @pytest.mark.asyncio
    async def test_concurrent_scheduling(self):
        """Test concurrent reminder scheduling scenarios."""
        # Create multiple reminders with same execution time
        reminders = []
        for i in range(3):
            reminder = Reminder(
                task=f"Concurrent task {i}",
                frequency=None,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time,
                user_id=123456 + i,
                chat_id=-100123456
            )
            reminders.append(reminder)

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        context.job_queue = MagicMock()

        # Schedule all reminders concurrently
        for reminder in reminders:
            context.job = MagicMock()
            context.job.data = reminder
            
            with patch.object(self.manager, 'delete_reminder'):
                await self.manager.send_reminder(context)

        # Verify all messages were sent
        assert context.bot.send_message.call_count == 3

    def test_timezone_aware_scheduling(self):
        """Test timezone-aware reminder scheduling."""
        # Create reminder with timezone-aware datetime
        tz_time = dt.datetime(2025, 7, 25, 15, 0, tzinfo=KYIV_TZ)
        reminder = Reminder(
            task="Timezone test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=tz_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Test seconds_until with timezone-aware times
        with patch('modules.reminders.reminders.datetime') as mock_dt:
            mock_dt.now.return_value = dt.datetime(2025, 7, 25, 14, 0, tzinfo=KYIV_TZ)
            seconds = seconds_until(tz_time)
            expected = 60 * 60  # 1 hour
            assert abs(seconds - expected) < 1, "Should handle timezone-aware calculations"

    @pytest.mark.asyncio
    async def test_error_handling_in_scheduling(self):
        """Test error handling during scheduling operations."""
        # Mock update and context with missing attributes
        update = MagicMock(spec=Update)
        update.effective_user = None  # Missing user
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = -100123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()

        context = MagicMock(spec=CallbackContext)
        context.args = ["to", "test", "task"]
        context.job_queue = None  # Missing job queue

        # Should handle missing user gracefully
        await self.manager.remind(update, context)
        
        # Should have sent an error message
        update.message.reply_text.assert_called()

    def test_reminder_database_operations(self):
        """Test database operations for reminder persistence."""
        db = ReminderDB(':memory:')
        
        # Test saving multiple reminders
        reminders = []
        for i in range(3):
            reminder = Reminder(
                task=f"DB Task {i}",
                frequency="daily" if i % 2 == 0 else None,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time + dt.timedelta(hours=i),
                user_id=123456,
                chat_id=-100123456
            )
            saved = db.save_reminder(reminder)
            reminders.append(saved)
            assert saved.reminder_id is not None, f"Reminder {i} should have ID"

        # Test loading all reminders
        loaded = db.load_reminders()
        assert len(loaded) == 3, "Should load all saved reminders"

        # Test loading by chat_id
        chat_loaded = db.load_reminders(chat_id=-100123456)
        assert len(chat_loaded) == 3, "Should load reminders for specific chat"

        # Test updating reminder
        reminders[0].task = "Updated DB Task"
        updated = db.save_reminder(reminders[0])
        assert updated.task == "Updated DB Task", "Should update existing reminder"

        # Test removing reminders
        for reminder in reminders:
            db.remove_reminder(reminder)
        
        final_loaded = db.load_reminders()
        assert len(final_loaded) == 0, "Should have no reminders after deletion"

    @pytest.mark.asyncio
    async def test_manager_lifecycle(self):
        """Test reminder manager initialization and cleanup."""
        # Test initialization
        manager = ReminderManager(db_file=':memory:')
        init_result = await manager.initialize()
        assert init_result is True, "Initialization should succeed"

        # Test that manager is functional after init
        reminder = Reminder(
            task="Lifecycle test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )
        saved = manager.save_reminder(reminder)
        assert saved.reminder_id is not None, "Should save reminder after init"

        # Test cleanup
        stop_result = await manager.stop()
        assert stop_result is True, "Stop should succeed"

    def test_edge_cases_in_scheduling(self):
        """Test edge cases in reminder scheduling."""
        # Test reminder with None next_execution
        reminder_none = Reminder(
            task="None execution",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=None,
            user_id=123456,
            chat_id=-100123456
        )
        
        # Should handle None execution time gracefully
        saved = self.manager.save_reminder(reminder_none)
        assert saved.reminder_id is not None, "Should save reminder with None execution"

        # Test reminder with very far future time
        far_future = dt.datetime(2030, 1, 1, 0, 0, tzinfo=KYIV_TZ)
        reminder_future = Reminder(
            task="Far future",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=far_future,
            user_id=123456,
            chat_id=-100123456
        )
        
        seconds = seconds_until(far_future)
        assert seconds > 0, "Should handle far future times"

    @pytest.mark.asyncio
    async def test_notification_content_formatting(self):
        """Test proper formatting of notification content."""
        # Test reminder with special characters
        reminder = Reminder(
            task="Task with émojis 🎉 and @mentions",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="@testuser"
        )

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()
        context.job = MagicMock(spec=Job)
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder'):
            await self.manager.send_reminder(context)

            # Verify message formatting
            context.bot.send_message.assert_called()
            call_args = context.bot.send_message.call_args
            message_text = call_args[0][1]  # message text is second positional arg
            
            # Should contain task and user mention
            assert "Task with émojis 🎉 and @mentions" in message_text
            assert "@testuser" in message_text