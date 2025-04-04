import sqlite3
import datetime
import pytz
import re
import os
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from modules.const import KYIV_TZ
from telegram.ext import CallbackContext
from telegram import Update
from modules.logger import error_logger

class Reminder:
    def __init__(self, task, frequency, delay, date_modifier, next_execution, user_id, chat_id, user_mention_md=None, reminder_id=None):
        self.reminder_id = reminder_id
        self.task = task
        self.frequency = frequency
        self.delay = delay
        self.date_modifier = date_modifier
        self.next_execution = next_execution
        self.user_id = user_id
        self.chat_id = chat_id
        self.user_mention_md = user_mention_md

    def calculate_next_execution(self):
        """Calculate the next execution time based on frequency and date modifiers"""
        now = datetime.datetime.now(KYIV_TZ)
        
        # Handle special date modifiers
        if self.date_modifier:
            if self.date_modifier == 'first day of every month':
                self._calculate_first_day_of_month(now)
                return
            elif self.date_modifier == 'last day of every month':
                self._calculate_last_day_of_month(now)
                return

        # Handle recurring frequencies
        if not self.frequency:
            return
            
        if self.frequency == "daily":
            if self.next_execution and self.next_execution <= now:
                # For daily recurring events, preserve the hour and minute
                next_day = now + datetime.timedelta(days=1)
                self.next_execution = next_day.replace(
                    hour=self.next_execution.hour, 
                    minute=self.next_execution.minute, 
                    second=0, 
                    microsecond=0
                )
            elif not self.next_execution:
                self.next_execution = now + datetime.timedelta(days=1)
                
        elif self.frequency == "weekly":
            if self.next_execution and self.next_execution <= now:
                # Add 7 days from the last execution
                self.next_execution = self.next_execution + datetime.timedelta(days=7)
            else:
                self.next_execution = now + datetime.timedelta(days=7)
                
        elif self.frequency == "monthly":
            if self.next_execution and self.next_execution <= now:
                # For monthly events, preserve day of month, hour, and minute
                day = min(self.next_execution.day, 28)  # Handle month variations
                hour = self.next_execution.hour
                minute = self.next_execution.minute

                # Calculate next month's date
                if now.month == 12:
                    next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                else:
                    next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)

                # Try to keep same day of month, clamping to month end if needed
                try:
                    self.next_execution = next_month.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                except ValueError:  # Day doesn't exist in target month
                    # Get last day of month
                    if next_month.month == 12:
                        last_day = datetime.datetime(next_month.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                    else:
                        last_day = datetime.datetime(next_month.year, next_month.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                    self.next_execution = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                self.next_execution = now + datetime.timedelta(days=30)
                
        elif self.frequency == "seconds":  # Test mode
            self.next_execution = now + datetime.timedelta(seconds=5)

    def _calculate_first_day_of_month(self, now):
        """Calculate the next first day of month from the given time"""
        # Determine which month's first day we need
        if now.day == 1 and now.hour < 9:
            # It's the first day and before 9 AM, use today
            target_date = now.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            # Use next month's first day
            if now.month == 12:
                target_date = datetime.datetime(now.year + 1, 1, 1, 
                                               hour=9, minute=0, second=0, 
                                               microsecond=0, tzinfo=KYIV_TZ)
            else:
                target_date = datetime.datetime(now.year, now.month + 1, 1, 
                                               hour=9, minute=0, second=0, 
                                               microsecond=0, tzinfo=KYIV_TZ)
        
        # If we have a previous execution time, preserve the hour and minute
        if self.next_execution:
            target_date = target_date.replace(hour=self.next_execution.hour, 
                                             minute=self.next_execution.minute)
            
        self.next_execution = target_date

    def _calculate_last_day_of_month(self, now):
        """Calculate the next last day of month from the given time"""
        # Calculate current month's last day
        if now.month == 12:
            current_last_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
        else:
            current_last_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
            
        # Calculate next month's last day
        if current_last_day.month == 12:
            next_last_day = datetime.datetime(current_last_day.year + 1, 2, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
        else:
            next_month_num = current_last_day.month + 1
            next_year = current_last_day.year
            if next_month_num > 12:
                next_month_num = 1
                next_year += 1
            next_last_day = datetime.datetime(next_year, next_month_num + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
            
        # If today is the last day and it's before target time, use today
        target_hour = self.next_execution.hour if self.next_execution else 9
        target_minute = self.next_execution.minute if self.next_execution else 0
            
        if now.day == current_last_day.day and now.month == current_last_day.month and now.hour < target_hour:
            self.next_execution = current_last_day.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        else:
            self.next_execution = next_last_day.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

    def to_tuple(self):
        """Convert reminder to tuple for database operations"""
        # Include reminder_id (or None if not set) as first element
        return (
            self.reminder_id,  # Might be None for new reminders
            self.task,
            self.frequency,
            self.delay,
            self.date_modifier,
            self.next_execution,
            self.user_id,
            self.chat_id,
            self.user_mention_md  # Add the new field
        )


    @classmethod
    def from_tuple(cls, data):
        """Create reminder from database tuple"""
        # Adjust tuple unpacking based on your actual number of columns
        try:
            reminder_id, task, frequency, delay, date_modifier, next_execution_str, user_id, chat_id, user_mention_md = data # Added user_mention_md
        except ValueError:
            # Handle case where column might not exist in older rows
            reminder_id, task, frequency, delay, date_modifier, next_execution_str, user_id, chat_id = data
            user_mention_md = None # Default to None if column is missing
            error_logger.warning(f"Reminder data tuple has incorrect length for ID {reminder_id}. Assuming missing user_mention_md.")


        if next_execution_str:
            # ... (datetime parsing logic remains the same) ...
            next_execution = datetime.datetime.fromisoformat(next_execution_str)
            if next_execution.tzinfo is None:
                next_execution = KYIV_TZ.localize(next_execution) # Use your timezone
        else:
            next_execution = None

        return cls(task, frequency, delay, date_modifier, next_execution, user_id, chat_id, user_mention_md, reminder_id)


class ReminderManager:
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
        self.create_table()
        self.reminders = self.load_reminders()
        
        # Common patterns for date modifier detection
        self.last_day_patterns = [
            "last day of every month", "on the last day of every month",
            "on last day of every month", "on the last day of month",
            "last day of month", "last day of the month"
        ]
        
        self.first_day_patterns = [
            "first day of every month", "first of every month", 
            "1st day of every month", "1st of every month",
            "on the first day of every month", "on first day of every month",
            "on the first of every month", "on first of every month",
            "every first day of month"
        ]

    def create_table(self):
        """Create reminders table if it doesn't exist"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT,
                frequency TEXT,
                delay TEXT,
                date_modifier TEXT,
                next_execution TEXT,
                user_id INTEGER,
                chat_id INTEGER,
                user_mention_md TEXT  -- Add this line
            )
        ''')
        # Handle potential ALTER TABLE if the column doesn't exist
        try:
            cursor.execute("SELECT user_mention_md FROM reminders LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            error_logger.info("Adding user_mention_md column to reminders table.")
            cursor.execute("ALTER TABLE reminders ADD COLUMN user_mention_md TEXT")

        self.conn.commit()

    def add_reminder(self, reminder):
        """Add a reminder to the database"""
        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO reminders (task, frequency, delay, date_modifier, next_execution, user_id, chat_id, user_mention_md)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', reminder.to_tuple()[1:])  # Skip reminder_id if it's None/autoincrement

            self.conn.commit()

            if cursor:
                reminder.reminder_id = cursor.lastrowid
            else:
                error_logger.error("Cursor was not created in add_reminder")
                return None

        except sqlite3.Error as db_error:
            error_logger.error(f"Database error during INSERT in add_reminder: {db_error}", exc_info=True)
            if self.conn:
                self.conn.rollback() # Roll back changes on error
            return None # Indicate failure
        except Exception as e:
             error_logger.error(f"Unexpected error in add_reminder: {e}", exc_info=True)
             if self.conn:
                  self.conn.rollback()
             return None # Indicate failure
        # --- End of ensured block ---

        # Reload reminders to get the full list including the new one
        # This is less efficient than just adding the new one, but simpler for now
        try:
            self.reminders = self.load_reminders()
        except Exception as load_error:
             error_logger.error(f"Failed to reload reminders after adding: {load_error}", exc_info=True)
             # Decide if you should still return the reminder object even if reload failed
             # For now, let's return the object we have, but log the error

        # Find the newly added reminder in the reloaded list (or use the existing object if ID was set)
        if reminder.reminder_id:
            # We successfully got the ID, try to find the matching object in the reloaded list
             newly_added = next((r for r in self.reminders if r.reminder_id == reminder.reminder_id), None)
             if newly_added:
                  return newly_added
             else:
                  # It was added to DB, but load_reminders failed or didn't find it? Return the object we have.
                  error_logger.warning(f"add_reminder: Added reminder {reminder.reminder_id} but couldn't find it in reloaded list.")
                  return reminder # Return the object with the ID set
        else:
             # Failed to get reminder_id earlier
             return None



    def remove_reminder(self, reminder):
        """Remove a reminder from the database"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM reminders WHERE reminder_id = ?', (reminder.reminder_id,))
        self.conn.commit()
        self.reminders = [r for r in self.reminders if r.reminder_id != reminder.reminder_id]

    def get_reminders(self, chat_id=None):
        """Get reminders, optionally filtered by chat_id"""
        if chat_id:
            return [r for r in self.reminders if r.chat_id == chat_id]
        return self.reminders

    def load_reminders(self):
        """Load all reminders from the database"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM reminders')
        data = cursor.fetchall()
        return [Reminder.from_tuple(r) for r in data]

    def update_reminder(self, reminder):
        """Update a reminder in the database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE reminders 
            SET task = ?, frequency = ?, delay = ?, date_modifier = ?, 
                next_execution = ?, user_id = ?, chat_id = ?
            WHERE reminder_id = ?
        ''', (
            reminder.task,
            reminder.frequency,
            reminder.delay,
            reminder.date_modifier,
            reminder.next_execution.isoformat() if isinstance(reminder.next_execution, datetime.datetime) else None,
            reminder.user_id,
            reminder.chat_id,
            reminder.reminder_id
        ))
        self.conn.commit()

    async def send_reminder(self, context: CallbackContext):
        """Send a reminder message AND handle next steps (remove or reschedule)."""
        # ... (initial context/job checks remain the same) ...
        try:
            if not context or not context.job or not context.job.data:
                error_logger.error("Invalid context in send_reminder")
                return

            reminder: Reminder = context.job.data # Type hint for clarity

            # Reload fresh state from DB is safer
            current_reminders = self.load_reminders()
            active_reminder = next((r for r in current_reminders if r.reminder_id == reminder.reminder_id), None)

            if not active_reminder:
                error_logger.warning(f"Reminder {reminder.reminder_id} not found in DB upon execution. Might have been deleted.")
                return
            reminder = active_reminder # Use the fresh data

            # --- Prepare Message ---
            message_text = ""
            parse_mode = None  # Default to no Markdown parsing

            is_group = reminder.chat_id < 0
            is_one_time = not reminder.frequency

            if is_group and is_one_time and reminder.user_mention_md:
                # Escape the main task text for Markdown conflicts
                escaped_task = escape_markdown(reminder.task, version=2)
                message_text = f"{reminder.user_mention_md}: {escaped_task}"
                parse_mode = ParseMode.MARKDOWN_V2
            else:
                # For recurring or no mention: simply use the task
                message_text = f"⏰ REMINDER: {reminder.task}"

            # --- Send Message ---
            try:
                # Use message_text in send_message instead of escaped_task
                await context.bot.send_message(
                    chat_id=reminder.chat_id,
                    text=message_text,
                    parse_mode=parse_mode
                )
                error_logger.info(f"Sent reminder {reminder.reminder_id} for task: '{reminder.task}'")
            except Exception as send_exc:
                error_logger.error(f"Failed to send reminder {reminder.reminder_id} (parse_mode={parse_mode}): {send_exc}", exc_info=True)
                # Optionally try fallback handling ...
                # (fallback code here)

            # --- Handle next steps (remove or reschedule) ---
            # This logic remains the same as in the previous version of Option 1
            if reminder.frequency:
                # ... (reschedule logic) ...
                old_time = reminder.next_execution
                reminder.calculate_next_execution()
                if reminder.next_execution and reminder.next_execution > (old_time or datetime.datetime.now(KYIV_TZ)): # Check new time is valid future time
                    error_logger.info(f"Rescheduling reminder {reminder.reminder_id} from {old_time.isoformat() if old_time else 'None'} to {reminder.next_execution.isoformat()}")
                    self.update_reminder(reminder)
                    if context.job_queue:
                        context.job_queue.run_once(
                            self.send_reminder,
                            when=reminder.next_execution,
                            data=reminder,
                            name=f"reminder_{reminder.reminder_id}"
                        )
                else:
                    error_logger.warning(f"Reminder {reminder.reminder_id} frequency '{reminder.frequency}' did not calculate a valid future execution time. Removing.")
                    self.remove_reminder(reminder)
            else:
                # One-time reminder, remove it
                error_logger.info(f"Removing one-time reminder {reminder.reminder_id}")
                self.remove_reminder(reminder)

        except Exception as e:
            # ... (outer error handling) ...
            reminder_id = context.job.data.reminder_id if context and context.job and context.job.data else "Unknown"
            error_logger.error(f"Error in send_reminder for ID {reminder_id}: {e}", exc_info=True)



    def parse_reminder(self, reminder_text):
        """Parse reminder text to extract frequency, date modifier, and time"""
        reminder_text_lower = reminder_text.lower()
        result = {
            'task': reminder_text,
            'frequency': None,
            'date_modifier': None,
            'time': None,
            'delay': None
        }
        
        # Extract time pattern "at HH:MM"
        time_at_pattern = re.compile(r'at\s+(\d{1,2}):(\d{2})')
        time_match = time_at_pattern.search(reminder_text_lower)
        if time_match:
            result['time'] = (int(time_match.group(1)), int(time_match.group(2)))
            
        # Parse frequency
        if any(word in reminder_text_lower for word in ["every day", "daily", "everyday"]):
            result['frequency'] = "daily"
        elif any(word in reminder_text_lower for word in ["every week", "weekly"]):
            result['frequency'] = "weekly"
        elif any(word in reminder_text_lower for word in ["every month", "monthly"]):
            result['frequency'] = "monthly"
        elif "every second" in reminder_text_lower:
            result['frequency'] = "seconds"
            
        # Parse date modifiers
        if any(pattern in reminder_text_lower for pattern in self.last_day_patterns):
            result['date_modifier'] = "last day of every month"
            result['frequency'] = "monthly"
        elif any(pattern in reminder_text_lower for pattern in self.first_day_patterns):
            result['date_modifier'] = "first day of every month"
            result['frequency'] = "monthly"
            
        # Parse delay
        time_pattern = re.compile(r'in\s+(\d+)\s+(second|minute|hour|day|month)s?')
        delay_match = time_pattern.search(reminder_text_lower)
        if delay_match:
            amount = int(delay_match.group(1))
            unit = delay_match.group(2)
            result['delay'] = f"in {amount} {unit}"
            
        return result

    async def remind(self, update: Update, context: CallbackContext):
        """Handle the /remind command"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if not context.args:
            # Show help text (Updated for 'to')
            help_text = (
                "📅 Reminder Commands:\n\n"
                "/remind to <task> [time info] - Add a reminder\n"
                # Examples using 'to'
                "/remind to Buy milk in 2 hours\n"
                "/remind to Team meeting daily at 10:00\n"
                "/remind to Pay rent on first day of every month\n"
                "/remind to Pay bills on last day of month monthly\n" # Added monthly for clarity
                # Other commands
                "/remind list - Show your reminders\n"
                "/remind delete <id> - Delete a specific reminder\n"
                "/remind delete all - Delete all your reminders\n\n"
                "Time formats supported:\n"
                "• in X seconds/minutes/hours/days/months (e.g., in 30 minutes)\n"
                "• at HH:MM (e.g., at 16:30)\n"
                "• daily / weekly / monthly\n"
                "• first day of every month / last day of every month (implies monthly)\n\n"
                 "Note: For recurring times (daily, weekly, monthly), you can specify 'at HH:MM'.\n"
                 "If no time is given for recurring, it might default or use a standard time.\n"
                 "If no time info is given at all, it defaults to 5 minutes from now."

            )
            await update.message.reply_text(help_text)
            return

        command = context.args[0].lower()

        # Changed 'add' to 'to'
        if command == "to":
            if len(context.args) < 2:
                await update.message.reply_text("Please specify what you want to be reminded 'to' do.")
                return

            # Extract the reminder text
            reminder_text = " ".join(context.args[1:])

            # Parse reminder parameters
            parsed = self.parse_reminder(reminder_text) # Assumes parse_reminder extracts task, freq, etc.
            task = parsed['task']
            frequency = parsed['frequency']
            date_modifier = parsed['date_modifier']
            time_tuple = parsed['time']
            delay = parsed['delay']

            # --- Calculate initial next execution time ---
            now = datetime.datetime.now(KYIV_TZ)
            next_execution = None # Start with None

            # 1. Apply delay if provided (takes precedence for initial calculation)
            if delay:
                # First, try to match with "in" prefix
                match = re.search(r'in\s+(\d+)\s+(second|sec|minute|min|hour|hr|day|month)s?', delay.lower())
                
                # If that doesn't match, try without the "in" prefix
                if not match:
                    match = re.search(r'(\d+)\s+(second|sec|minute|min|hour|hr|day|month)s?', delay.lower())
                    
                if match:
                    amount = int(match.group(1))
                    unit_str = match.group(2)  # Get the matched unit string

                    # Normalize the unit string
                    unit = None
                    if unit_str in ['second', 'sec', 's']:
                        unit = 'second'
                    elif unit_str in ['minute', 'min', 'm']:
                        unit = 'minute'
                    elif unit_str in ['hour', 'hr', 'h']:
                        unit = 'hour'
                    elif unit_str == 'day':
                        unit = 'day'
                    elif unit_str == 'month':
                        unit = 'month'

                    if unit == 'second':
                        next_execution = now + datetime.timedelta(seconds=amount)
                    elif unit == 'minute':
                        next_execution = now + datetime.timedelta(minutes=amount)
                    elif unit == 'hour':
                        next_execution = now + datetime.timedelta(hours=amount)
                    elif unit == 'day':
                        next_execution = now + datetime.timedelta(days=amount)
                    elif unit == 'month':
                        from dateutil.relativedelta import relativedelta
                        next_execution = now + relativedelta(months=amount)

            # 2. Apply specific time if no delay was set
            elif time_tuple:
                hour, minute = time_tuple
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # If time is in the past *for today*, move to the next appropriate day
                # This needs careful handling with frequency/date_modifier
                if target_time <= now and not frequency and not date_modifier:
                    # Simple case: one-off reminder for a time already passed today -> schedule for tomorrow
                    target_time += datetime.timedelta(days=1)
                elif target_time <= now and frequency == "daily":
                    # Daily reminder for time passed today -> schedule for tomorrow same time
                    target_time += datetime.timedelta(days=1)
                # (Add similar logic for weekly/monthly if needed, though calculate_next_execution handles rescheduling)

                next_execution = target_time


            # 3. Apply default if no delay or time was specified
            if next_execution is None and not frequency and not date_modifier:
                 next_execution = now + datetime.timedelta(minutes=5) # Default: 5 mins from now
                 error_logger.info(f"No time specified for reminder '{task[:30]}...', defaulting to 5 minutes.")

            # If next_execution is still None here, it might be a recurring reminder
            # without a specific initial time (e.g., "remind me monthly").
            # calculate_next_execution should handle this. Let's pass now as a base.
            if next_execution is None and not frequency and not date_modifier:
                next_execution = now + datetime.timedelta(minutes=5) # Default: 5 mins from now
                error_logger.info(f"No time specified for reminder '{task[:30]}...', defaulting to 5 minutes.")

            # If next_execution is still None here, it might be a recurring reminder
            # without a specific initial time (e.g., "remind me monthly").
            # calculate_next_execution should handle this. Let's pass now as a base.
            if next_execution is None:
                next_execution = now # provide a base for calculation

            # Get user's mention string (using MarkdownV2)
            user_mention_md = update.effective_user.mention_markdown_v2()

            # Create the reminder object (initially without ID)
            reminder = Reminder(
                task=task,
                frequency=frequency,
                delay=delay, # Store original delay text if needed, though less useful now
                date_modifier=date_modifier,
                next_execution=next_execution, # Pass the calculated or base time
                user_id=user_id,
                chat_id=chat_id,
                user_mention_md=user_mention_md # Store the mention string
            )

            # --- Database and Scheduling ---
            try:
                # Add to database - Assume add_reminder now returns the object with the ID
                added_reminder = self.add_reminder(reminder)

                if not added_reminder:
                    error_logger.error(f"Failed to save reminder to DB or retrieve it after saving: {reminder_text}")
                    await update.message.reply_text("❌ Error: Could not save the reminder.")
                    return

            except Exception as db_error:
                 error_logger.error(f"Database error adding reminder: {db_error}", exc_info=True)
                 await update.message.reply_text("❌ Database error occurred while saving the reminder.")
                 return


            # Schedule the reminder using the object returned from DB (which has the ID)
            if context.job_queue and added_reminder.next_execution:
                try:
                    context.job_queue.run_once(
                        self.send_reminder, # This function now handles rescheduling/deletion
                        when=added_reminder.next_execution,
                        # Use the object with the ID from the DB
                        data=added_reminder,
                        # Add a job name for easier identification/debugging
                        name=f"reminder_{added_reminder.reminder_id}"
                    )
                    error_logger.info(f"Scheduled job for reminder {added_reminder.reminder_id} at {added_reminder.next_execution.isoformat()}")
                except Exception as schedule_error:
                     error_logger.error(f"Failed to schedule job for reminder {added_reminder.reminder_id}: {schedule_error}", exc_info=True)
                     await update.message.reply_text("❌ Error scheduling the reminder job.")
                     # Consider deleting the reminder from DB if scheduling fails permanently
                     # self.remove_reminder(added_reminder)
                     return

            # --- Confirmation Message ---
            # Use the final calculated time from the added_reminder object
            time_str = added_reminder.next_execution.strftime("%d.%m.%Y %H:%M")

            if added_reminder.date_modifier == "first day of every month":
                month_name = added_reminder.next_execution.strftime("%B")
                await update.message.reply_text(
                    f"✅ Reminder set: '{added_reminder.task}'\n"
                    f"Next execution: First day of {month_name} ({time_str} Kyiv time).\n"
                    f"Repeats monthly."
                )
            elif added_reminder.date_modifier == "last day of every month":
                month_name = added_reminder.next_execution.strftime("%B")
                await update.message.reply_text(
                    f"✅ Reminder set: '{added_reminder.task}'\n"
                    f"Next execution: Last day of {month_name} ({time_str} Kyiv time).\n"
                    f"Repeats monthly."
                )
            elif added_reminder.frequency:
                 # Clarify the first execution time for recurring reminders
                 await update.message.reply_text(
                     f"✅ Recurring reminder set: '{added_reminder.task}'\n"
                     f"First execution: {time_str} (Kyiv time).\n"
                     f"Frequency: {added_reminder.frequency.capitalize()}."
                 )
            else:
                 # One-time reminder
                await update.message.reply_text(f"✅ One-time reminder set: '{added_reminder.task}'\n"
                                                f"Time: {time_str} (Kyiv time).")


        elif command == "list":
            # ... (keep list logic as is, it seems fine)
             # Get reminders for this chat
            chat_reminders = self.get_reminders(chat_id)

            if not chat_reminders:
                await update.message.reply_text("You don't have any reminders set.")
                return

            # Format the list of reminders
            now = datetime.datetime.now(KYIV_TZ)
            upcoming = []
            recurring = []
            # past = [] # Let's not show past/completed in list unless specifically asked

            for r in chat_reminders:
                # Ensure timezone for comparison and display
                if r.next_execution and r.next_execution.tzinfo is None:
                    r.next_execution = KYIV_TZ.localize(r.next_execution)

                time_str = r.next_execution.strftime("%d.%m.%Y %H:%M") if r.next_execution else "Unknown"

                if r.frequency:
                    status = "🔄 Testing" if r.frequency == "seconds" else "🔁 Recurring"
                    recurring.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Next: {time_str})\n"))
                elif r.next_execution and r.next_execution > now:
                     minutes_left = (r.next_execution - now).total_seconds() / 60
                     status = f"⏳ in {int(minutes_left)} min" if minutes_left < 60 else f"⏰ {time_str}"
                     upcoming.append((r, f"ID: {r.reminder_id} - {r.task} ({status})\n"))
                # else: # It's a past one-time reminder, ignore for the default list

            # Sort each category
            upcoming.sort(key=lambda x: x[0].next_execution or datetime.datetime.max)
            recurring.sort(key=lambda x: x[0].next_execution or datetime.datetime.max)

            # Build the message
            result = "📝 Your active reminders:\n\n"
            found_any = False

            if upcoming:
                result += "📅 UPCOMING (One-Time):\n"
                result += "".join([item[1] for item in upcoming])
                result += "\n"
                found_any = True

            if recurring:
                result += "🔁 RECURRING:\n"
                result += "".join([item[1] for item in recurring])
                result += "\n"
                found_any = True

            if not found_any:
                 result = "You have no active upcoming or recurring reminders."

            await update.message.reply_text(result)


        elif command == "delete":
            # ... (keep delete logic as is, but ensure remove_reminder also cancels jobs if possible)
            # Note: PTB doesn't easily allow canceling jobs by arbitrary data or ID without knowing the job name.
            # Using job names like f"reminder_{reminder_id}" helps.

            if len(context.args) < 2:
                await update.message.reply_text("Please specify a reminder ID to delete, or use 'all'.")
                return

            target = context.args[1].lower()

            if target == "all":
                chat_reminders = self.get_reminders(chat_id)
                if not chat_reminders:
                    await update.message.reply_text("You don't have any reminders to delete.")
                    return

                count = 0
                deleted_ids = []
                for reminder in chat_reminders[:]: # Iterate over a copy
                    try:
                        self.remove_reminder(reminder) # This deletes from DB and internal list
                        deleted_ids.append(reminder.reminder_id)
                        count += 1
                    except Exception as e:
                        error_logger.error(f"Failed to delete reminder {reminder.reminder_id} during 'delete all': {e}")

                # Attempt to remove scheduled jobs
                if context.job_queue:
                     active_jobs = context.job_queue.get_jobs_by_name(None) # Get all jobs (might be large)
                     jobs_removed_count = 0
                     for job in active_jobs:
                          # Check if the job name matches the pattern and the deleted ID
                          if job.name and job.name.startswith("reminder_"):
                               try:
                                   job_id = int(job.name.split("_")[1])
                                   if job_id in deleted_ids:
                                       job.schedule_removal()
                                       jobs_removed_count +=1
                               except (IndexError, ValueError):
                                    pass # Ignore jobs with names not matching the pattern
                     error_logger.info(f"Attempted to remove {jobs_removed_count} scheduled jobs for 'delete all'.")


                await update.message.reply_text(f"✅ All {count} reminders deleted.")
                return

            # Delete specific reminder
            try:
                reminder_id = int(target)
                # Find reminder in the current list (assuming it's loaded)
                # It's safer to fetch directly/reload before deleting
                self.reminders = self.load_reminders() # Ensure we have the latest list
                reminder_to_delete = next((r for r in self.reminders
                                           if r.reminder_id == reminder_id and r.chat_id == chat_id), None)

                if not reminder_to_delete:
                    await update.message.reply_text(f"Reminder ID {reminder_id} not found.")
                    return

                self.remove_reminder(reminder_to_delete) # Deletes from DB and list

                 # Attempt to remove the specific job
                job_removed = False
                if context.job_queue:
                     job_name = f"reminder_{reminder_id}"
                     jobs = context.job_queue.get_jobs_by_name(job_name)
                     if jobs:
                          for job in jobs:
                               job.schedule_removal()
                          job_removed = True
                          error_logger.info(f"Removed scheduled job '{job_name}'.")


                await update.message.reply_text(f"✅ Reminder {reminder_id} deleted." + (" (Job also removed)" if job_removed else ""))

            except ValueError:
                await update.message.reply_text("Invalid reminder ID. Please provide a valid number or use 'all'.")
            except Exception as e:
                 error_logger.error(f"Error deleting reminder ID {target}: {e}", exc_info=True)
                 await update.message.reply_text("❌ An error occurred while deleting the reminder.")


        else:
            # Updated unknown command message
            await update.message.reply_text(
                "❌ Unknown command\n\n"
                "Available commands:\n"
                "/remind to <task> [time info] - Add a reminder\n"
                "/remind list - Show your reminders\n"
                "/remind delete <id>|all - Delete a reminder\n\n"
                "Type /remind for full usage instructions."
            )


    def schedule_reminders(self, bot, job_queue):
        """Schedule reminders from DB on startup."""
        now = datetime.datetime.now(KYIV_TZ)
        self.reminders = self.load_reminders() # Load fresh from DB
        scheduled_count = 0
        past_count = 0
        for reminder in self.reminders:
            if reminder.next_execution:
                # Ensure timezone (already handled in from_tuple, but good practice)
                if reminder.next_execution.tzinfo is None:
                    reminder.next_execution = KYIV_TZ.localize(reminder.next_execution)

                if reminder.next_execution > now:
                    job_queue.run_once(
                        self.send_reminder,
                        when=reminder.next_execution,
                        data=reminder, # Pass the specific reminder instance
                        name=f"reminder_{reminder.reminder_id}" # Optional: Give job a name
                    )
                    scheduled_count += 1
                    # print(f"Scheduled reminder {reminder.reminder_id} for {reminder.next_execution}") # Use logger ideally
                else:
                    # Handle past-due reminders found on startup
                    # Option 1: Send immediately and reschedule/remove (could spam if many are past)
                    # Option 2: Just reschedule/remove without sending the missed ones
                    # Option 3: Log them
                    error_logger.warning(f"Reminder {reminder.reminder_id} ('{reminder.task[:30]}...') execution time {reminder.next_execution} is in the past. Handling post-execution logic.")
                    # Simulate what send_reminder would do after sending:
                    if reminder.frequency:
                        old_time = reminder.next_execution
                        reminder.calculate_next_execution()
                        if reminder.next_execution > now: # Check if new time is valid future time
                            self.update_reminder(reminder)
                            job_queue.run_once(self.send_reminder, when=reminder.next_execution, data=reminder, name=f"reminder_{reminder.reminder_id}")
                            # print(f"Rescheduled past recurring reminder {reminder.reminder_id} for {reminder.next_execution}")
                        else:
                            # print(f"Removing past recurring reminder {reminder.reminder_id} as new time is not in future.")
                            self.remove_reminder(reminder)

                    else:
                        # print(f"Removing past one-time reminder {reminder.reminder_id}.")
                        self.remove_reminder(reminder)

                    past_count += 1

            else:
                error_logger.warning(f"Reminder {reminder.reminder_id} has no next_execution time. Skipping.")
                past_count += 1 # Or handle as error

        error_logger.info(f"Reminder scheduling on startup: {scheduled_count} future jobs scheduled, {past_count} past/invalid reminders handled.")
