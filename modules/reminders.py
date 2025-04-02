# Install necessary library if you haven't already:
# pip install python-telegram-bot python-dateutil pytz

import sqlite3
import datetime
import pytz
import re
import os
from dateutil.relativedelta import relativedelta # For easier date math
from dateutil import rrule # Potentially useful for complex recurrence
from telegram.ext import CallbackContext
from telegram import Update
from modules.logger import error_logger # Assuming this logger is configured
from modules.const import KYIV_TZ # Assuming this is defined e.g., KYIV_TZ = pytz.timezone('Europe/Kyiv')

# --- Reminder Class ---
class Reminder:
    def __init__(self, task, frequency, delay, date_modifier, next_execution, user_id, chat_id, reminder_id=None):
        self.reminder_id = reminder_id
        self.task = task
        self.frequency = frequency # e.g., "daily", "weekly", "monthly", None
        self.delay = delay # Store the original delay string if needed, e.g., "in 5 minutes"
        self.date_modifier = date_modifier # e.g., "first day of month", "last day of month", None
        
        # Ensure next_execution is timezone-aware
        if isinstance(next_execution, datetime.datetime):
            if next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(next_execution)
            else:
                self.next_execution = next_execution.astimezone(KYIV_TZ)
        else:
             self.next_execution = None # Should ideally always be a datetime after initial setup
             
        self.user_id = user_id
        self.chat_id = chat_id
        
        # Store original time components if set explicitly (for recurring)
        self._original_hour = next_execution.hour if next_execution else None
        self._original_minute = next_execution.minute if next_execution else None
        self._original_day = next_execution.day if next_execution else None # Used for specific day-of-month monthly


    def calculate_next_execution(self):
        """
        Calculate the next execution time AFTER the current one has passed.
        Assumes self.next_execution holds the time that just triggered.
        Updates self.next_execution to the next scheduled time.
        Returns True if successfully calculated, False otherwise (e.g., for one-off reminders).
        """
        if not self.frequency and not self.date_modifier:
            # This is likely a one-off reminder based on delay or specific time, 
            # no further execution calculation needed here.
            return False

        # Use the time that just triggered as the base for the next calculation
        # If next_execution wasn't set somehow, default to now
        base_time = self.next_execution if self.next_execution else datetime.datetime.now(KYIV_TZ)
        now = datetime.datetime.now(KYIV_TZ) # Get current time for comparison logic

        # --- Handle Special Date Modifiers ---
        if self.date_modifier == 'first day of month':
            # Find the first day of the month *after* the base_time's month
            next_month_first_day = (base_time.replace(day=1) + relativedelta(months=1))
            target_hour = self._original_hour if self._original_hour is not None else 9 # Default time
            target_minute = self._original_minute if self._original_minute is not None else 0
            self.next_execution = next_month_first_day.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            return True
            
        elif self.date_modifier == 'last day of month':
            # Find the first day of the month *after* next month, then subtract one day
            next_next_month_first_day = (base_time.replace(day=1) + relativedelta(months=2))
            next_month_last_day = next_next_month_first_day - datetime.timedelta(days=1)
            target_hour = self._original_hour if self._original_hour is not None else 9 # Default time
            target_minute = self._original_minute if self._original_minute is not None else 0
            self.next_execution = next_month_last_day.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            return True

        # --- Handle Standard Recurring Frequencies ---
        if not self.frequency:
             return False # Should have been caught by date_modifier or earlier check
        
        if self.frequency == "daily":
             # Add one day to the last execution time
            self.next_execution = base_time + relativedelta(days=1)
            # Ensure time components are preserved if they were set
            if self._original_hour is not None and self._original_minute is not None:
                 self.next_execution = self.next_execution.replace(hour=self._original_hour, minute=self._original_minute, second=0, microsecond=0)
            return True
            
        elif self.frequency == "weekly":
            # Add one week to the last execution time
            self.next_execution = base_time + relativedelta(weeks=1)
            # Time components are inherently preserved by adding weeks
            return True
            
        elif self.frequency == "monthly":
            # Add one month to the last execution time
            # relativedelta handles month length variations gracefully
            self.next_execution = base_time + relativedelta(months=1)
            
            # If original day was > 28, ensure we didn't roll over incorrectly
            # e.g. if scheduled for 31st Jan, next should be 28/29th Feb, then 31st Mar
            # Try setting day back if it was specific, otherwise relativedelta handles it well.
            if self._original_day and self._original_day > 28:
                try:
                    test_date = self.next_execution.replace(day=self._original_day)
                    # Check if replacing day changed the month (meaning day is invalid for new month)
                    if test_date.month == self.next_execution.month:
                         self.next_execution = test_date
                    # else: keep the date from relativedelta (end of month)
                except ValueError: 
                     # Day doesn't exist in the new month, relativedelta would have put it at the end, which is fine.
                     pass 
            return True
            
        elif self.frequency == "seconds": # Test mode - run 5 seconds after the *last* execution
            self.next_execution = base_time + datetime.timedelta(seconds=5)
            return True
            
        else:
             error_logger.warning(f"Unknown frequency '{self.frequency}' for reminder {self.reminder_id}")
             return False

    def to_tuple(self):
        """Convert reminder to tuple for database storage"""
        next_execution_iso = self.next_execution.isoformat() if isinstance(self.next_execution, datetime.datetime) else None
        return (
            self.reminder_id,
            self.task,
            self.frequency,
            self.delay,
            self.date_modifier,
            next_execution_iso,
            self.user_id,
            self.chat_id
        )

    @classmethod
    def from_tuple(cls, data):
        """Create reminder from database tuple"""
        (reminder_id, task, frequency, delay, date_modifier, 
         next_execution_str, user_id, chat_id) = data
        
        next_execution = None
        if next_execution_str:
            try:
                # Use fromisoformat, handles timezone info if present
                dt_naive_or_aware = datetime.datetime.fromisoformat(next_execution_str)
                if dt_naive_or_aware.tzinfo is None:
                    # If loaded string had no timezone, assume it was stored in KYIV_TZ
                    # and make it aware. Crucial for comparisons.
                    next_execution = KYIV_TZ.localize(dt_naive_or_aware)
                else:
                    # If it had timezone info, ensure it's converted to KYIV_TZ
                    next_execution = dt_naive_or_aware.astimezone(KYIV_TZ)
            except ValueError as e:
                 error_logger.error(f"Error parsing date '{next_execution_str}' for reminder {reminder_id}: {e}")
                 next_execution = None # Or handle differently? Maybe reschedule?

        return cls(task, frequency, delay, date_modifier, next_execution, user_id, chat_id, reminder_id)

    def __repr__(self):
        return (f"<Reminder id={self.reminder_id} task='{self.task[:20]}...' "
                f"freq='{self.frequency}' mod='{self.date_modifier}' "
                f"next='{self.next_execution.isoformat() if self.next_execution else 'None'}' "
                f"chat={self.chat_id}>")


# --- Reminder Manager Class ---
class ReminderManager:
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        # Ensure connection is thread-safe for use with PTB's async nature
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False) 
        self.create_table()
        
        # No need to load all reminders into memory constantly if using JobQueue properly
        # self.reminders = self.load_reminders() 
        
        # Store patterns directly here
        self.patterns = {
            "last_day": [
                "last day of every month", "on the last day of every month",
                "on last day of every month", "on the last day of month",
                "last day of month", "last day of the month"
            ],
            "first_day": [
                "first day of every month", "first of every month", 
                "1st day of every month", "1st of every month",
                "on the first day of every month", "on first day of every month",
                "on the first of every month", "on first of every month",
                "every first day of month"
            ],
            "daily": ["every day", "daily", "everyday"],
            "weekly": ["every week", "weekly"],
            "monthly": ["every month", "monthly"],
            "seconds": ["every second", "every 5 seconds"], # Testing
            "time_at": re.compile(r'at\s+(\d{1,2}):(\d{2})\b', re.IGNORECASE),
            "delay_in": re.compile(r'in\s+(\d+)\s+(second|minute|hour|day|week|month)s?\b', re.IGNORECASE)
        }

    def create_table(self):
        """Create reminders table if it doesn't exist"""
        with self.conn: # Use context manager for automatic commit/rollback
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    frequency TEXT,
                    delay TEXT,
                    date_modifier TEXT,
                    next_execution TEXT, -- Store as ISO 8601 string
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL
                )
            ''')
            # Consider adding indexes for performance if the table grows large
            # self.conn.execute('CREATE INDEX IF NOT EXISTS idx_next_execution ON reminders(next_execution);')
            # self.conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_id ON reminders(chat_id);')

    def add_reminder(self, reminder: Reminder) -> Reminder:
        """Add a reminder to the database and return it with its ID."""
        with self.conn:
            cursor = self.conn.cursor()
            next_execution_iso = reminder.next_execution.isoformat() if reminder.next_execution else None
            cursor.execute('''
                INSERT INTO reminders (task, frequency, delay, date_modifier, next_execution, user_id, chat_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (reminder.task, reminder.frequency, reminder.delay, reminder.date_modifier, 
                  next_execution_iso, reminder.user_id, reminder.chat_id))
            reminder.reminder_id = cursor.lastrowid
            error_logger.info(f"Added reminder to DB: {reminder}")
            return reminder

    def remove_reminder(self, reminder_id: int):
        """Remove a reminder from the database by ID."""
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM reminders WHERE reminder_id = ?', (reminder_id,))
            if cursor.rowcount > 0:
                error_logger.info(f"Removed reminder ID {reminder_id} from DB.")
                return True
            else:
                error_logger.warning(f"Attempted to remove non-existent reminder ID {reminder_id}.")
                return False

    def update_reminder(self, reminder: Reminder):
        """Update a reminder in the database."""
        if not reminder.reminder_id:
            error_logger.error("Cannot update reminder without an ID.")
            return False
            
        with self.conn:
            next_execution_iso = reminder.next_execution.isoformat() if reminder.next_execution else None
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE reminders 
                SET task = ?, frequency = ?, delay = ?, date_modifier = ?, 
                    next_execution = ?, user_id = ?, chat_id = ?
                WHERE reminder_id = ?
            ''', (
                reminder.task, reminder.frequency, reminder.delay, reminder.date_modifier,
                next_execution_iso, reminder.user_id, reminder.chat_id,
                reminder.reminder_id
            ))
            if cursor.rowcount > 0:
                 error_logger.info(f"Updated reminder ID {reminder.reminder_id} in DB. Next exec: {next_execution_iso}")
                 return True
            else:
                 error_logger.warning(f"Attempted to update non-existent reminder ID {reminder.reminder_id}")
                 return False


    def get_reminders(self, chat_id=None):
        """Get reminders, optionally filtered by chat_id. Returns a list of Reminder objects."""
        cursor = self.conn.cursor()
        if chat_id:
            cursor.execute('SELECT * FROM reminders WHERE chat_id = ? ORDER BY next_execution', (chat_id,))
        else:
            # Generally avoid loading ALL reminders unless necessary (e.g., for recovery)
            error_logger.warning("Loading all reminders from DB. Consider filtering.")
            cursor.execute('SELECT * FROM reminders ORDER BY next_execution')
            
        data = cursor.fetchall()
        return [Reminder.from_tuple(r) for r in data]

    def get_reminder_by_id(self, reminder_id: int) -> Reminder | None:
         """Fetch a single reminder by its ID."""
         cursor = self.conn.cursor()
         cursor.execute('SELECT * FROM reminders WHERE reminder_id = ?', (reminder_id,))
         data = cursor.fetchone()
         return Reminder.from_tuple(data) if data else None


    async def send_reminder_callback(self, context: CallbackContext):
        """
        Callback executed by the JobQueue. Sends the message and reschedules if necessary.
        """
        job = context.job
        if not job or not job.data or not isinstance(job.data, dict) or 'reminder_id' not in job.data:
            error_logger.error(f"Invalid job data in send_reminder_callback: {job.data if job else 'No Job'}")
            return

        reminder_id = job.data['reminder_id']
        error_logger.info(f"Job triggered for reminder ID {reminder_id}")

        # Fetch the latest reminder state from DB
        reminder = self.get_reminder_by_id(reminder_id)

        if not reminder:
            error_logger.warning(f"Reminder ID {reminder_id} not found in DB for sending. Job might be stale.")
            # Optionally remove the job if it persists? Be careful with race conditions.
            return
            
        if not reminder.next_execution:
             error_logger.warning(f"Reminder ID {reminder_id} has no next_execution time. Skipping send.")
             return

        # Double check if it's actually due (e.g., bot restarted, job triggered slightly late)
        now = datetime.datetime.now(KYIV_TZ)
        # Allow a small grace period (e.g., 5 minutes) for late jobs
        grace_period = datetime.timedelta(minutes=5) 
        if reminder.next_execution > now + grace_period:
             error_logger.warning(f"Reminder ID {reminder_id} job triggered too early? Expected: {reminder.next_execution}, Now: {now}. Rescheduling.")
             # Reschedule for the correct time
             context.job_queue.run_once(
                 self.send_reminder_callback,
                 when=reminder.next_execution,
                 data={'reminder_id': reminder.reminder_id},
                 name=f"reminder_{reminder.reminder_id}"
             )
             return # Stop processing this early trigger


        try:
            # --- Send the message ---
            url_pattern = r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            has_urls = bool(re.search(url_pattern, reminder.task))

            await context.bot.send_message(
                chat_id=reminder.chat_id,
                text=f"⏰ REMINDER: {reminder.task}",
                parse_mode=None, # Let Telegram auto-detect links etc.
                disable_web_page_preview=not has_urls
            )
            error_logger.info(f"Sent reminder ID {reminder_id} to chat {reminder.chat_id}")

            # --- Reschedule or Remove ---
            is_recurring = bool(reminder.frequency or reminder.date_modifier)

            if is_recurring:
                if reminder.calculate_next_execution(): # Calculate the *next* time
                    if self.update_reminder(reminder): # Save the new time to DB
                        # Schedule the next occurrence
                        context.job_queue.run_once(
                            self.send_reminder_callback,
                            when=reminder.next_execution,
                            data={'reminder_id': reminder.reminder_id},
                            name=f"reminder_{reminder.reminder_id}" # Use name for potential management
                        )
                        error_logger.info(f"Rescheduled reminder ID {reminder.reminder_id} for {reminder.next_execution.isoformat()}")
                    else:
                         error_logger.error(f"Failed to update reminder {reminder.reminder_id} after execution. It will not run again.")
                else:
                     error_logger.info(f"Reminder {reminder.reminder_id} finished its recurrence or failed calculation.")
                     self.remove_reminder(reminder.reminder_id) # Clean up if calculation failed for recurring
            else:
                # One-time reminder, remove it
                self.remove_reminder(reminder.reminder_id)
                error_logger.info(f"Removed one-time reminder ID {reminder.reminder_id} after sending.")

        except Exception as e:
            # Log error specific to this reminder ID
            error_logger.error(f"Error processing reminder ID {reminder_id}: {e}", exc_info=True)
            # Decide if you want to retry or remove the reminder after errors
            # For now, we let it potentially get rescheduled if it was recurring and calculation succeeded before error.


    def parse_reminder(self, text: str) -> dict:
        """
        Parse reminder text to extract task, frequency, date modifier, time, and delay.
        Tries to remove matched patterns from the task text.
        """
        original_text = text
        text_lower = text.lower()
        
        result = {
            'task': original_text.strip(), # Start with original, clean later
            'frequency': None,
            'date_modifier': None,
            'time': None, # Tuple (hour, minute)
            'delay': None, # Tuple (amount, unit)
        }

        # --- Extract Time (at HH:MM) ---
        time_match = self.patterns['time_at'].search(text_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                 result['time'] = (hour, minute)
                 # Remove the matched part from the task
                 result['task'] = self.patterns['time_at'].sub('', result['task']).strip()
                 text_lower = result['task'].lower() # Update lower text for next matches

        # --- Extract Delay (in X unit) ---
        # Run this *before* frequency as "daily in 5 minutes" should prioritize delay
        delay_match = self.patterns['delay_in'].search(text_lower)
        if delay_match:
            amount = int(delay_match.group(1))
            unit = delay_match.group(2).lower()
            result['delay'] = (amount, unit)
            # Remove matched part
            result['task'] = self.patterns['delay_in'].sub('', result['task']).strip()
            text_lower = result['task'].lower()
            # If delay is found, frequency/date modifiers usually don't apply to *first* execution
            result['frequency'] = None 
            result['date_modifier'] = None
            return result # Prioritize delay

        # --- Extract Date Modifiers (First/Last day) ---
        for pattern in self.patterns['last_day']:
            if pattern in text_lower:
                result['date_modifier'] = "last day of month"
                result['frequency'] = "monthly" # Implied frequency
                result['task'] = result['task'].lower().replace(pattern, '').strip()
                text_lower = result['task'].lower()
                break # Found modifier
        if not result['date_modifier']: # Only check if not already found
             for pattern in self.patterns['first_day']:
                if pattern in text_lower:
                    result['date_modifier'] = "first day of month"
                    result['frequency'] = "monthly"
                    result['task'] = result['task'].lower().replace(pattern, '').strip()
                    text_lower = result['task'].lower()
                    break

        # --- Extract Frequency (daily, weekly, monthly, seconds) ---
        # Only if delay wasn't found and date modifier wasn't 'first/last day' specific
        if not result['delay'] and not result['date_modifier']: 
            freq_map = {
                 "daily": self.patterns["daily"],
                 "weekly": self.patterns["weekly"],
                 "monthly": self.patterns["monthly"],
                 "seconds": self.patterns["seconds"] # Test
             }
            found_freq = False
            for freq_key, patterns in freq_map.items():
                for pattern in patterns:
                    # Use regex word boundary to avoid matching parts of words
                    if re.search(r'\b' + re.escape(pattern) + r'\b', text_lower):
                        result['frequency'] = freq_key
                        result['task'] = re.sub(r'\b' + re.escape(pattern) + r'\b', '', result['task'], flags=re.IGNORECASE).strip()
                        text_lower = result['task'].lower()
                        found_freq = True
                        break
                if found_freq:
                    break
                    
        # Final task cleanup (remove extra spaces, capitalize)
        result['task'] = ' '.join(result['task'].split())
        if result['task']:
             result['task'] = result['task'][0].upper() + result['task'][1:]

        return result

    def _calculate_initial_next_execution(self, parsed_data: dict) -> datetime.datetime | None:
        """Calculates the *first* next_execution time based on parsed user input."""
        now = datetime.datetime.now(KYIV_TZ)
        target_dt = None

        delay = parsed_data.get('delay')
        time_tuple = parsed_data.get('time')
        frequency = parsed_data.get('frequency')
        date_modifier = parsed_data.get('date_modifier')
        
        # 1. Priority: Delay ("in X units")
        if delay:
            amount, unit = delay
            delta = relativedelta()
            if unit == 'second': delta = relativedelta(seconds=amount)
            elif unit == 'minute': delta = relativedelta(minutes=amount)
            elif unit == 'hour': delta = relativedelta(hours=amount)
            elif unit == 'day': delta = relativedelta(days=amount)
            elif unit == 'week': delta = relativedelta(weeks=amount)
            elif unit == 'month': delta = relativedelta(months=amount)
            target_dt = now + delta
            # Delay usually implies one-off, clear frequency/modifier for initial calculation
            frequency = None
            date_modifier = None
            
        # 2. Specific Time ("at HH:MM") potentially combined with frequency/modifier
        elif time_tuple:
            hour, minute = time_tuple
            target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If the specified time is in the past *today*...
            if target_dt <= now:
                # ...and it's NOT a specific date modifier (like first/last day)
                if not date_modifier:
                     # ...move to the next day (or next week/month if frequency specified)
                    if frequency == 'weekly':
                         target_dt += relativedelta(weeks=1)
                    elif frequency == 'monthly':
                          # This gets tricky if time is past today but day is e.g. 31st.
                          # Let's just advance one day and rely on calculate_next_execution for subsequent.
                          # Or, more robustly, set to the correct day next month.
                          target_dt += relativedelta(months=1) 
                          # Try to keep original day, fallback to end of month
                          original_day = target_dt.day # Day from adding month
                          try:
                               target_dt = target_dt.replace(day=original_day) # Keep day if valid
                          except ValueError: 
                               pass # Keep end of month if day invalid
                    else: # Includes daily or no frequency
                         target_dt += relativedelta(days=1)
                # else: If it *is* a date modifier, we handle the date part below, keep time.

        # 3. Handle Date Modifiers (First/Last Day) - Calculate the *date* part
        if date_modifier == 'first day of month':
            first_of_this_month = now.replace(day=1, hour=9, minute=0, second=0, microsecond=0) # Default time 9:00
            if time_tuple: # If time was specified, use it
                first_of_this_month = first_of_this_month.replace(hour=time_tuple[0], minute=time_tuple[1])
                
            if first_of_this_month > now: # If 1st@time is still in the future this month
                 target_dt = first_of_this_month
            else: # Otherwise, use the first day of *next* month
                 target_dt = (now.replace(day=1) + relativedelta(months=1))
                 if time_tuple:
                      target_dt = target_dt.replace(hour=time_tuple[0], minute=time_tuple[1], second=0, microsecond=0)
                 else: # Default time
                      target_dt = target_dt.replace(hour=9, minute=0, second=0, microsecond=0)

        elif date_modifier == 'last day of month':
            # Calculate last day of *current* month
            next_month_first_day = (now.replace(day=1) + relativedelta(months=1))
            last_of_this_month = next_month_first_day - datetime.timedelta(days=1)
            last_of_this_month = last_of_this_month.replace(hour=9, minute=0, second=0, microsecond=0) # Default time
            if time_tuple:
                 last_of_this_month = last_of_this_month.replace(hour=time_tuple[0], minute=time_tuple[1])

            if last_of_this_month > now: # If last_day@time is still in the future this month
                 target_dt = last_of_this_month
            else: # Otherwise, use the last day of *next* month
                 next_next_month_first_day = (now.replace(day=1) + relativedelta(months=2))
                 last_of_next_month = next_next_month_first_day - datetime.timedelta(days=1)
                 if time_tuple:
                     target_dt = last_of_next_month.replace(hour=time_tuple[0], minute=time_tuple[1], second=0, microsecond=0)
                 else: # Default time
                     target_dt = last_of_next_month.replace(hour=9, minute=0, second=0, microsecond=0)

        # 4. Frequency only (daily, weekly, monthly) - no specific time/delay/modifier
        elif frequency and not target_dt: # Target not set by time/modifier yet
            target_dt = now.replace(hour=9, minute=0, second=0, microsecond=0) # Default to 9:00 AM
            if target_dt <= now: # If 9 AM already passed today
                if frequency == 'daily': target_dt += relativedelta(days=1)
                elif frequency == 'weekly': target_dt += relativedelta(weeks=1)
                elif frequency == 'monthly': target_dt += relativedelta(months=1)
                elif frequency == 'seconds': target_dt = now + relativedelta(seconds=5) # Immediate start for testing

        # 5. No time/delay/freq/modifier specified - one-off, default? Error?
        elif not target_dt:
             # Option 1: Error - require time info
             # return None 
             # Option 2: Default (e.g., 5 mins from now) - less explicit
             target_dt = now + datetime.timedelta(minutes=5)
             error_logger.info("No time specified for reminder, defaulting to 5 minutes from now.")

        return target_dt


    async def remind(self, update: Update, context: CallbackContext):
        """Handle the /remind command (add, list, delete)."""
        if not update.effective_chat or not update.effective_user:
            error_logger.warning("Cannot process remind command without chat/user.")
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if not context.args:
            # Show help text (minor updates to examples)
            help_text = (
                 "📅 **Reminder Commands:**\n\n"
                 "`/remind add <task details>` - Add reminder\n"
                 "`/remind list` - Show your reminders\n"
                 "`/remind delete <id>` - Delete a reminder\n"
                 "`/remind delete all` - Delete all reminders\n\n"
                 "**How to specify time for `add`:**\n"
                 "• `in 5 minutes`, `in 2 hours`, `in 1 day`...\n"
                 "• `at 16:30`, `at 9:00`\n"
                 "• `daily`, `weekly`, `monthly` (defaults to 9:00 AM if no time)\n"
                 "• `every day at 14:00`\n"
                 "• `first day of month` (at 9:00 or specified time)\n"
                 "• `last day of month at 17:00`\n\n"
                 "**Examples:**\n"
                 "`/remind add Buy milk in 2 hours`\n"
                 "`/remind add Team meeting weekly at 10:00`\n"
                 "`/remind add Pay rent first day of month`\n"
                 "`/remind add Submit report last day of month at 17:30`"
            )
            await update.message.reply_text(help_text, parse_mode='Markdown')
            return

        command = context.args[0].lower()

        # --- ADD Command ---
        if command == "add":
            if len(context.args) < 2:
                await update.message.reply_text("Please specify the task and time for your reminder. Example: `/remind add Call John in 1 hour`")
                return

            reminder_text = " ".join(context.args[1:])
            parsed = self.parse_reminder(reminder_text)

            if not parsed.get('task'):
                 await update.message.reply_text("Could not extract a task description from your reminder.")
                 return

            initial_next_execution = self._calculate_initial_next_execution(parsed)

            if not initial_next_execution:
                 await update.message.reply_text("❌ Could not determine a time for the reminder. Please specify like 'in 5 minutes', 'at 14:30', 'daily', etc.")
                 return
                 
            # Store original parsed components for the Reminder object
            delay_str = f"in {parsed['delay'][0]} {parsed['delay'][1]}" if parsed.get('delay') else None

            reminder