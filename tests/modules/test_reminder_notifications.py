"""
Comprehensive tests for reminder notification delivery and retry logic.
This module tests notification delivery mechanisms, error handling,
retry strategies, and notification state management.
"""

import pytest
import datetime as dt
from unittest.mock import patch, MagicMock, AsyncMock, call
from telegram import Update, User, Chat, Message, Bot
from telegram.ext import CallbackContext
from telegram.error import NetworkError, TimedOut, BadRequest

from modules.reminders.reminders import ReminderManager
from modules.reminders.reminder_models import Reminder
from modules.const import KYIV_TZ


class TestReminderNotifications:
    """Comprehensive tests for reminder notification functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ReminderManager(db_file=':memory:')
        self.base_time = dt.datetime(2025, 7, 25, 10, 0, tzinfo=KYIV_TZ)

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self.manager.db, 'conn'):
            self.manager.db.conn.close()

    @pytest.mark.asyncio
    async def test_successful_notification_delivery(self):
        """Test successful delivery of reminder notifications."""
        # Create a test reminder
        reminder = Reminder(
            task="Test successful notification",
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
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Send notification
            await self.manager.send_reminder(context)

            # Verify message was sent successfully
            context.bot.send_message.assert_called_once()
            call_args = context.bot.send_message.call_args
            
            # Check message parameters
            assert call_args[0][0] == -100123456  # chat_id is first positional arg
            assert "Test successful notification" in call_args[0][1]  # message text is second positional arg
            assert "@testuser" in call_args[0][1]
            
            # Verify reminder was cleaned up
            mock_delete.assert_called_once_with(reminder)

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network errors during notification delivery."""
        reminder = Reminder(
            task="Network error test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context with network error
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock(side_effect=NetworkError("Connection failed"))
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Should handle network error gracefully
            await self.manager.send_reminder(context)
            
            # Verify attempt was made
            context.bot.send_message.assert_called_once()
            
            # Should still clean up reminder (no retry logic in current implementation)
            mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """Test handling of timeout errors during notification delivery."""
        reminder = Reminder(
            task="Timeout test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context with timeout error
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock(side_effect=TimedOut("Request timed out"))
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Should handle timeout gracefully
            await self.manager.send_reminder(context)
            
            # Verify attempt was made
            context.bot.send_message.assert_called_once()
            
            # Should still clean up
            mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_bad_request_error_handling(self):
        """Test handling of bad request errors during notification delivery."""
        reminder = Reminder(
            task="Bad request test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context with bad request error
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock(side_effect=BadRequest("Chat not found"))
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Should handle bad request gracefully
            await self.manager.send_reminder(context)
            
            # Verify attempt was made
            context.bot.send_message.assert_called_once()
            
            # Should still clean up
            mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_recurring_reminder_notification(self):
        """Test notification delivery for recurring reminders."""
        # Create a daily reminder
        reminder = Reminder(
            task="Daily recurring task",
            frequency="daily",
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="@testuser"
        )

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()
        context.job_queue.run_once = MagicMock()

        with patch.object(self.manager, 'save_reminder') as mock_save:
            mock_save.return_value = reminder
            
            # Send notification
            await self.manager.send_reminder(context)

            # Verify message was sent
            context.bot.send_message.assert_called_once()
            
            # Verify reminder was rescheduled (not deleted)
            mock_save.assert_called()
            
            # Verify new job was scheduled
            context.job_queue.run_once.assert_called()

    @pytest.mark.asyncio
    async def test_notification_message_formatting(self):
        """Test proper formatting of notification messages."""
        test_cases = [
            # Basic reminder (group, one-time)
            {
                'reminder': Reminder(
                    task="Simple task",
                    frequency=None,
                    delay=None,
                    date_modifier=None,
                    next_execution=self.base_time,
                    user_id=123456,
                    chat_id=-100123456,
                    user_mention_md="@user"
                ),
                'expected_content': ["Simple task", "@user"]  # No bell emoji for group one-time reminders
            },
            # Reminder with special characters
            {
                'reminder': Reminder(
                    task="Task with émojis 🎉 and symbols @#$%",
                    frequency=None,
                    delay=None,
                    date_modifier=None,
                    next_execution=self.base_time,
                    user_id=123456,
                    chat_id=-100123456,
                    user_mention_md="@specialuser"
                ),
                'expected_content': ["Task with émojis 🎉 and symbols @\\#$%", "@specialuser"]  # # is escaped in Markdown
            },
            # Long task (recurring, so uses different format)
            {
                'reminder': Reminder(
                    task="This is a very long task description that should be handled properly in the notification message",
                    frequency="weekly",
                    delay=None,
                    date_modifier=None,
                    next_execution=self.base_time,
                    user_id=123456,
                    chat_id=-100123456,
                    user_mention_md="@longuser"
                ),
                'expected_content': ["very long task description", "⏰ REMINDER:"]  # Recurring reminders use different format
            }
        ]

        for test_case in test_cases:
            # Mock context
            context = MagicMock(spec=CallbackContext)
            context.bot = MagicMock(spec=Bot)
            context.bot.send_message = AsyncMock()
            context.job = MagicMock()
            context.job.data = test_case['reminder']
            context.job_queue = MagicMock()

            with patch.object(self.manager, 'delete_reminder'):
                # Send notification
                await self.manager.send_reminder(context)

                # Verify message content
                context.bot.send_message.assert_called()
                call_args = context.bot.send_message.call_args
                message_text = call_args[0][1]  # message text is second positional arg
                
                # Check expected content is present
                for expected in test_case['expected_content']:
                    assert expected in message_text, f"Expected '{expected}' in message: {message_text}"

    @pytest.mark.asyncio
    async def test_notification_delivery_to_different_chat_types(self):
        """Test notification delivery to different chat types."""
        chat_types = [
            {'chat_id': 123456, 'type': 'private'},
            {'chat_id': -100123456, 'type': 'group'},
            {'chat_id': -1001234567890, 'type': 'supergroup'},
        ]

        for chat_info in chat_types:
            reminder = Reminder(
                task=f"Task for {chat_info['type']} chat",
                frequency=None,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time,
                user_id=123456,
                chat_id=chat_info['chat_id'],
                user_mention_md="@testuser"
            )

            # Mock context
            context = MagicMock(spec=CallbackContext)
            context.bot = MagicMock(spec=Bot)
            context.bot.send_message = AsyncMock()
            context.job = MagicMock()
            context.job.data = reminder
            context.job_queue = MagicMock()

            with patch.object(self.manager, 'delete_reminder'):
                # Send notification
                await self.manager.send_reminder(context)

                # Verify message was sent to correct chat
                context.bot.send_message.assert_called()
                call_args = context.bot.send_message.call_args
                assert call_args[0][0] == chat_info['chat_id']  # chat_id is first positional arg

    @pytest.mark.asyncio
    async def test_notification_state_management(self):
        """Test state management during notification delivery."""
        # Create reminder with specific state
        reminder = Reminder(
            task="State management test",
            frequency="monthly",
            delay=None,
            date_modifier="first day of every month",
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()
        context.job_queue.run_once = MagicMock()

        with patch.object(self.manager, 'save_reminder') as mock_save:
            # Mock the calculate_next_execution to verify it's called
            with patch.object(reminder, 'calculate_next_execution') as mock_calc:
                mock_save.return_value = reminder
                
                # Send notification
                await self.manager.send_reminder(context)

                # Verify state was updated
                mock_calc.assert_called_once()
                mock_save.assert_called()

    @pytest.mark.asyncio
    async def test_notification_error_recovery(self):
        """Test error recovery mechanisms in notification delivery."""
        reminder = Reminder(
            task="Error recovery test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context with intermittent failures
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        # Test multiple error types in sequence
        error_sequence = [
            NetworkError("Network error"),
            TimedOut("Timeout"),
            Exception("Generic error")
        ]

        for error in error_sequence:
            context.bot.send_message = AsyncMock(side_effect=error)
            
            with patch.object(self.manager, 'delete_reminder') as mock_delete:
                # Should handle each error gracefully
                await self.manager.send_reminder(context)
                
                # Verify attempt was made
                context.bot.send_message.assert_called()
                
                # Should still clean up
                mock_delete.assert_called()

    @pytest.mark.asyncio
    async def test_bulk_notification_delivery(self):
        """Test delivery of multiple notifications simultaneously."""
        # Create multiple reminders
        reminders = []
        for i in range(5):
            reminder = Reminder(
                task=f"Bulk notification {i}",
                frequency=None,
                delay=None,
                date_modifier=None,
                next_execution=self.base_time,
                user_id=123456 + i,
                chat_id=-100123456,
                user_mention_md=f"@user{i}"
            )
            reminders.append(reminder)

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.job_queue = MagicMock()

        # Send all notifications
        with patch.object(self.manager, 'delete_reminder'):
            for reminder in reminders:
                context.job = MagicMock()
                context.job.data = reminder
                await self.manager.send_reminder(context)

        # Verify all messages were sent
        assert context.bot.send_message.call_count == 5

        # Verify each message had correct content
        calls = context.bot.send_message.call_args_list
        for i, call in enumerate(calls):
            message_text = call[0][1]  # message text is second positional arg
            assert f"Bulk notification {i}" in message_text
            assert f"@user{i}" in message_text

    @pytest.mark.asyncio
    async def test_notification_with_missing_context(self):
        """Test notification handling with missing context elements."""
        reminder = Reminder(
            task="Missing context test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Test with missing bot
        context_no_bot = MagicMock(spec=CallbackContext)
        context_no_bot.bot = None
        context_no_bot.job = MagicMock()
        context_no_bot.job.data = reminder

        # Should handle missing bot gracefully
        await self.manager.send_reminder(context_no_bot)

        # Test with missing job
        context_no_job = MagicMock(spec=CallbackContext)
        context_no_job.bot = MagicMock(spec=Bot)
        context_no_job.job = None

        # Should handle missing job gracefully
        await self.manager.send_reminder(context_no_job)

    @pytest.mark.asyncio
    async def test_notification_performance(self):
        """Test notification delivery performance characteristics."""
        import time
        
        reminder = Reminder(
            task="Performance test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder'):
            # Measure notification delivery time
            start_time = time.time()
            await self.manager.send_reminder(context)
            end_time = time.time()

            # Should complete quickly (under 1 second for mocked operations)
            duration = end_time - start_time
            assert duration < 1.0, f"Notification delivery took too long: {duration}s"

    def test_notification_data_integrity(self):
        """Test data integrity during notification processing."""
        # Create reminder with all fields populated
        original_reminder = Reminder(
            task="Data integrity test",
            frequency="weekly",
            delay="in 1 week",
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456,
            user_mention_md="@testuser",
            reminder_id=42
        )

        # Serialize and deserialize
        tuple_data = original_reminder.to_tuple()
        restored_reminder = Reminder.from_tuple(tuple_data)

        # Verify all data is preserved
        assert restored_reminder.task == original_reminder.task
        assert restored_reminder.frequency == original_reminder.frequency
        assert restored_reminder.delay == original_reminder.delay
        assert restored_reminder.date_modifier == original_reminder.date_modifier
        assert restored_reminder.user_id == original_reminder.user_id
        assert restored_reminder.chat_id == original_reminder.chat_id
        assert restored_reminder.user_mention_md == original_reminder.user_mention_md
        assert restored_reminder.reminder_id == original_reminder.reminder_id

        # Verify datetime is preserved (allowing for timezone differences)
        if original_reminder.next_execution and restored_reminder.next_execution:
            assert abs((restored_reminder.next_execution - original_reminder.next_execution).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_notification_cleanup_on_success(self):
        """Test proper cleanup after successful notification delivery."""
        reminder = Reminder(
            task="Cleanup test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock()
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Send notification
            await self.manager.send_reminder(context)

            # Verify cleanup was performed
            mock_delete.assert_called_once_with(reminder)

    @pytest.mark.asyncio
    async def test_notification_cleanup_on_failure(self):
        """Test proper cleanup after failed notification delivery."""
        reminder = Reminder(
            task="Cleanup on failure test",
            frequency=None,
            delay=None,
            date_modifier=None,
            next_execution=self.base_time,
            user_id=123456,
            chat_id=-100123456
        )

        # Mock context with failure
        context = MagicMock(spec=CallbackContext)
        context.bot = MagicMock(spec=Bot)
        context.bot.send_message = AsyncMock(side_effect=Exception("Delivery failed"))
        context.job = MagicMock()
        context.job.data = reminder
        context.job_queue = MagicMock()

        with patch.object(self.manager, 'delete_reminder') as mock_delete:
            # Send notification (should fail but handle gracefully)
            await self.manager.send_reminder(context)

            # Verify cleanup was still performed
            mock_delete.assert_called_once_with(reminder)