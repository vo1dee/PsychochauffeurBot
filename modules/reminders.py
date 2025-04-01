import sqlite3
import datetime
import pytz
import re
import os
from modules.const import KYIV_TZ
from telegram.ext import CallbackContext
from telegram import Update
from modules.logger import error_logger
class Reminder:
    def __init__(self, task, frequency, delay, date_modifier, next_execution, user_id, chat_id, reminder_id=None):
        self.reminder_id = reminder_id
        self.task = task
        self.frequency = frequency
        self.delay = delay
        self.date_modifier = date_modifier
        self.next_execution = next_execution
        self.user_id = user_id
        self.chat_id = chat_id

    def calculate_next_execution(self):
        now = datetime.datetime.now(KYIV_TZ)

        # If this is a special date modifier, handle it first
        if self.date_modifier:
            # These date modifiers are handled specially and take precedence
            if self.date_modifier == 'first day of every month':
                return self._calculate_first_day_of_month(now)
            elif self.date_modifier == 'last day of every month':
                return self._calculate_last_day_of_month(now)

        # Handle recurring frequencies next
        if self.frequency:
            if self.frequency == "daily":
                if self.next_execution and self.next_execution <= now:
                    # For daily recurring events, preserve the hour and minute
                    hour = self.next_execution.hour
                    minute = self.next_execution.minute

                    # Move to next day but keep the same time
                    next_day = now + datetime.timedelta(days=1)
                    self.next_execution = next_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                elif not self.next_execution:
                    self.next_execution = now + datetime.timedelta(days=1)
            elif self.frequency == "weekly":
                if self.next_execution and self.next_execution <= now:
                    # For weekly events, preserve hour, minute, and weekday
                    hour = self.next_execution.hour
                    minute = self.next_execution.minute

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
                    next_month = now.replace(day=1) + datetime.timedelta(days=32)
                    next_month = next_month.replace(day=1)  # First day of next month

                    # Try to keep same day of month, clamping to month end if needed
                    try:
                        self.next_execution = next_month.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                    except ValueError:  # Day doesn't exist in target month
                        # Get last day of month
                        last_day = (next_month.replace(day=1) + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
                        self.next_execution = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    self.next_execution = now + datetime.timedelta(days=30)
            elif self.frequency == "seconds":
                # For testing - every few seconds
                self.next_execution = now + datetime.timedelta(seconds=5)
            return

    def _calculate_first_day_of_month(self, now):
        """Calculate the next first day of month from the given time"""
        # If current date is already the first day of the month AND it's after the reminder time,
        # schedule for first day of next month
        if now.day == 1:
            # If we already have a next_execution, use its time
            if self.next_execution:
                hour = self.next_execution.hour
                minute = self.next_execution.minute

                # Check if we're past the time today
                today_execution = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now > today_execution:
                    # We're past today's time, go to next month
                    if now.month == 12:
                        next_month_year = now.year + 1
                        next_month = 1
                    else:
                        next_month_year = now.year
                        next_month = now.month + 1
                else:
                    # Still early enough today, use today
                    self.next_execution = today_execution
                    return
            else:
                # Default to 9 AM
                hour = 9
                minute = 0

                # If we're past 9 AM, we need the next month
                if now.hour >= 9:
                    if now.month == 12:
                        next_month_year = now.year + 1
                        next_month = 1
                    else:
                        next_month_year = now.year
                        next_month = now.month + 1
                else:
                    # Still before 9 AM, use today
                    self.next_execution = now.replace(hour=9, minute=0, second=0, microsecond=0)
                    return
        else:
            # Not the first day, go to next month
            if now.month == 12:
                next_month_year = now.year + 1
                next_month = 1
            else:
                next_month_year = now.year
                next_month = now.month + 1

            # Use time from existing reminder if available
            if self.next_execution:
                hour = self.next_execution.hour
                minute = self.next_execution.minute
            else:
                hour = 9  # Default to 9 AM
                minute = 0

        # Set the next execution to the first day of next month
        self.next_execution = datetime.datetime(
            year=next_month_year,
            month=next_month,
            day=1,
            hour=hour,
            minute=minute, 
            second=0,
            microsecond=0,
            tzinfo=KYIV_TZ
        )

    def _calculate_last_day_of_month(self, now):
        """Calculate the next last day of month from the given time"""
        # Find the last day of current month
        if now.month == 12:
            next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
        else:
            next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)

        last_day_of_month = next_month - datetime.timedelta(days=1)

        # Check if today is the last day of the month
        if now.day == last_day_of_month.day:
            # If we already have a next_execution, use its time
            if self.next_execution:
                hour = self.next_execution.hour
                minute = self.next_execution.minute

                # Check if we're past the time today
                today_execution = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now > today_execution:
                    # We've passed the time today, calculate last day of next month
                    if now.month == 12:
                        year = now.year + 1
                        month = 2  # February of next year
                    elif now.month == 11:
                        year = now.year + 1
                        month = 1  # January of next year
                    else:
                        year = now.year
                        month = now.month + 2  # Two months ahead

                    # Get first day of month after next
                    first_day = datetime.datetime(year, month, 1, tzinfo=KYIV_TZ)

                    # Subtract one day to get last day of next month
                    next_last_day = first_day - datetime.timedelta(days=1)

                    self.next_execution = next_last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    # Still early enough today
                    self.next_execution = today_execution
            else:
                # Default time is 9 AM
                hour = 9
                minute = 0

                # Check if we're past default time
                if now.hour >= 9:
                    # Calculate last day of next month
                    if now.month == 12:
                        year = now.year + 1
                        month = 2  # February of next year
                    elif now.month == 11:
                        year = now.year + 1
                        month = 1  # January of next year
                    else:
                        year = now.year
                        month = now.month + 2  # Two months ahead

                    # Get first day of month after next
                    first_day = datetime.datetime(year, month, 1, tzinfo=KYIV_TZ)

                    # Subtract one day to get last day of next month
                    next_last_day = first_day - datetime.timedelta(days=1)

                    self.next_execution = next_last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    # Still early enough today
                    self.next_execution = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # Not the last day, aim for this month's last day
            if self.next_execution:
                hour = self.next_execution.hour
                minute = self.next_execution.minute
            else:
                hour = 9  # Default
                minute = 0

            self.next_execution = last_day_of_month.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Handle specific time delays for one-time reminders
        if self.delay:
            # Check for patterns like "in X seconds/minutes/hours/days/months"
            time_pattern = re.compile(r'in\s+(\d+)\s+(second|minute|hour|day|month)s?')
            match = time_pattern.search(self.delay)

            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == 'second':
                    self.next_execution = now + datetime.timedelta(seconds=amount)
                elif unit == 'minute':
                    self.next_execution = now + datetime.timedelta(minutes=amount)
                elif unit == 'hour':
                    self.next_execution = now + datetime.timedelta(hours=amount)
                elif unit == 'day':
                    self.next_execution = now + datetime.timedelta(days=amount)
                elif unit == 'month':
                    self.next_execution = now + datetime.timedelta(days=amount*30)  # approximate
            elif self.delay == 'in 1 hour':
                self.next_execution = now + datetime.timedelta(hours=1)
            elif self.delay == 'in 1 day':
                self.next_execution = now + datetime.timedelta(days=1)
            elif self.delay == 'in 1 month':
                self.next_execution = now + datetime.timedelta(days=30)  # approximate month

        # Handle specific date modifiers
        if self.date_modifier == 'first day of every month':
            # Always calculate first day of next month
            if now.month == 12:
                next_month_year = now.year + 1
                next_month_num = 1
            else:
                next_month_year = now.year
                next_month_num = now.month + 1

            # Create datetime with explicit timezone
            # Preserve the original time if it exists
            if self.next_execution:
                original_hour = self.next_execution.hour
                original_minute = self.next_execution.minute
                self.next_execution = datetime.datetime(
                    year=next_month_year,
                    month=next_month_num,
                    day=1,  # First day of month
                    hour=original_hour,
                    minute=original_minute,
                    second=0,
                    microsecond=0,
                    tzinfo=KYIV_TZ
                )
            else:
                # Default to 9 AM if no previous time
                self.next_execution = datetime.datetime(
                    year=next_month_year,
                    month=next_month_num,
                    day=1,  # First day of month
                    hour=9,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=KYIV_TZ
                )

        elif self.date_modifier == 'last day of every month':
            # Current month's last day
            if now.month == 12:
                next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
            else:
                next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)

            # Get last day of current month
            last_day_current = next_month - datetime.timedelta(days=1)

            # We always want the next month's last day when recalculating
            # Get the last day of next month
            if next_month.month == 12:
                next_next_month = datetime.datetime(next_month.year + 1, 1, 1, tzinfo=KYIV_TZ)
            else:
                next_next_month = datetime.datetime(next_month.year, next_month.month + 1, 1, tzinfo=KYIV_TZ)

            last_day = next_next_month - datetime.timedelta(days=1)

            # Preserve the original time
            if self.next_execution:
                original_hour = self.next_execution.hour
                original_minute = self.next_execution.minute
                self.next_execution = last_day.replace(hour=original_hour, minute=original_minute, second=0, microsecond=0)
            else:
                # Default to 9 AM if no previous time
                self.next_execution = last_day.replace(hour=9, minute=0, second=0, microsecond=0)

    def to_tuple(self):
        return (self.reminder_id, self.task, self.frequency, self.delay, self.date_modifier, self.next_execution.isoformat() if isinstance(self.next_execution, datetime.datetime) else None, self.user_id, self.chat_id)

    @classmethod
    def from_tuple(cls, data):
        reminder_id, task, frequency, delay, date_modifier, next_execution_str, user_id, chat_id = data
        # Parse datetime and ensure timezone is set
        if next_execution_str:
            next_execution = datetime.datetime.fromisoformat(next_execution_str)
            # Add timezone if not present
            if next_execution.tzinfo is None:
                next_execution = KYIV_TZ.localize(next_execution)
        else:
            next_execution = None

        return cls(task, frequency, delay, date_modifier, next_execution, user_id, chat_id, reminder_id)

class ReminderManager:
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
        self.create_table()
        self.reminders = self.load_reminders()

    def create_table(self):
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
                chat_id INTEGER
            )
        ''')
        self.conn.commit()

    def add_reminder(self, reminder):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (task, frequency, delay, date_modifier, next_execution, user_id, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', reminder.to_tuple()[1:]) # Skip reminder_id
        self.conn.commit()
        reminder.reminder_id = cursor.lastrowid
        self.reminders.append(reminder)
        return reminder

    def remove_reminder(self, reminder):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM reminders WHERE reminder_id = ?', (reminder.reminder_id,))
        self.conn.commit()
        self.reminders = [r for r in self.reminders if r.reminder_id != reminder.reminder_id]

    def get_reminders(self, chat_id=None):
        if chat_id:
            return [r for r in self.reminders if r.chat_id == chat_id]
        return self.reminders

    def load_reminders(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM reminders')
        data = cursor.fetchall()
        return [Reminder.from_tuple(r) for r in data]

    def schedule_reminders(self, bot, job_queue):
        now = datetime.datetime.now(KYIV_TZ)

        for reminder in self.reminders:
            try:
                # Make sure next_execution has proper timezone
                if reminder.next_execution:
                    # Ensure timezone information is present
                    if reminder.next_execution.tzinfo is None:
                        reminder.next_execution = KYIV_TZ.localize(reminder.next_execution)

                    # Handle reminders based on their time
                    if reminder.next_execution > now:
                        # Future reminder - schedule it
                        when_utc = reminder.next_execution.astimezone(pytz.UTC)
                        job = job_queue.run_once(self.send_reminder, when=when_utc, data=reminder)
                    else:
                        # Past reminder - handle immediately
                        job = job_queue.run_once(self.send_reminder, when=1, data=reminder)
            except Exception as e:
                error_logger.error(f"Error scheduling reminder {reminder.reminder_id}: {e}")

    async def check_reminders(self, context: CallbackContext):
        try:
            if context is None:
                return

            bot = context.bot
            now = datetime.datetime.now(KYIV_TZ)
            error_logger.info(f"Checking reminders at {now.isoformat()}")

            # First, load the latest reminders from the database
            self.reminders = self.load_reminders()
            error_logger.info(f"Loaded {len(self.reminders)} reminders from database")

            # Process reminders that need to be sent
            reminders_to_send = []
            for reminder in self.reminders:
                if reminder.next_execution:
                    # Ensure timezone is set
                    if reminder.next_execution.tzinfo is None:
                        reminder.next_execution = KYIV_TZ.localize(reminder.next_execution)

                    # Log time difference for debugging
                    time_diff = (reminder.next_execution - now).total_seconds()
                    error_logger.info(f"Reminder {reminder.reminder_id}: '{reminder.task}' scheduled for {reminder.next_execution.isoformat()}, diff: {time_diff:.1f}s, freq: {reminder.frequency}")

                    # Check if it's time to send
                    if reminder.next_execution <= now:
                        error_logger.info(f"Reminder {reminder.reminder_id} is due, adding to send queue")
                        reminders_to_send.append(reminder)

            # Send reminders and update them
            for reminder in reminders_to_send:
                # Create a simulated context with the reminder data
                try:
                    class MockJob:
                        def __init__(self, data):
                            self.data = data

                    # Make a copy of the existing context and add our job
                    mock_context = context
                    mock_context.job = MockJob(data=reminder)

                    await self.send_reminder(mock_context)

                    # Calculate next time if this is a recurring reminder
                    if reminder.frequency:
                        error_logger.info(f"Recalculating next time for recurring reminder {reminder.reminder_id}")
                        old_time = reminder.next_execution
                        reminder.calculate_next_execution()
                        error_logger.info(f"Updated reminder {reminder.reminder_id} from {old_time.isoformat()} to {reminder.next_execution.isoformat()}")
                        self.update_reminder(reminder)

                        # Special case for seconds frequency - reschedule immediately
                        if reminder.frequency == "seconds" and context.job_queue:
                            # This is intentional for testing - creates a separate job outside the normal checking
                            job = context.job_queue.run_once(
                                self.send_reminder, 
                                when=5,  # Fixed 5 seconds interval for testing
                                data=reminder
                            )
                            error_logger.info(f"Created special testing job for seconds-based reminder {reminder.reminder_id}")
                    else:
                        # One-time reminder, remove it
                        error_logger.info(f"Removing one-time reminder {reminder.reminder_id} after execution")
                        self.remove_reminder(reminder)
                except Exception as e:
                    error_logger.error(f"Error processing reminder {reminder.reminder_id}: {e}", exc_info=True)

        except Exception as e:
            error_logger.error(f"Error in check_reminders: {e}", exc_info=True)

    async def send_reminder(self, context: CallbackContext):
        try:
            if context is None:
                error_logger.error("send_reminder: Context is None")
                return

            if context.job is None:
                error_logger.error("send_reminder: Context.job is None")
                return

            if not hasattr(context.job, 'data') or context.job.data is None:
                error_logger.error("send_reminder: Context.job.data is None")
                return

            reminder = context.job.data

            # Format message properly with links
            try:
                task_text = reminder.task
                url_pattern = r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                urls = re.findall(url_pattern, task_text)

                # This reminder contains URLs
                if urls:
                    # Use HTML formatting for proper link display 
                    await context.bot.send_message(
                        chat_id=reminder.chat_id, 
                        text=f"⏰ REMINDER: {task_text}",
                        parse_mode=None,  # Let Telegram auto-format
                        disable_web_page_preview=False  # Allow link previews
                    )
                else:
                    # No URLs, send regular message
                    await context.bot.send_message(
                        chat_id=reminder.chat_id, 
                        text=f"⏰ REMINDER: {task_text}"
                    )
            except Exception as e:
                error_logger.error(f"Failed to send reminder {reminder.reminder_id}: {e}", exc_info=True)

            # Remove one-time reminders after execution
            if reminder.frequency is None:
                self.remove_reminder(reminder)

        except Exception as e:
            error_logger.error(f"Critical error in send_reminder: {e}", exc_info=True)

    def update_reminder(self, reminder):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE reminders 
            SET task = ?, 
                frequency = ?, 
                delay = ?, 
                date_modifier = ?, 
                next_execution = ?, 
                user_id = ?, 
                chat_id = ?
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

    def parse_natural_language_date(self, text):
        try:
            # Initialize OpenAI client only when method is called
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                error_logger.error("OpenAI API key not set in environment variables")
                return None
                
            client = OpenAI(api_key=api_key)
            
            prompt = f"Convert the following natural language date/time to ISO 8601 format: {text}"
            response = client.completions.create(
                model="gpt-3.5-turbo-instruct",  # Updated model name
                prompt=prompt,
                max_tokens=50
            )
            iso_date = response.choices[0].text.strip()
            return datetime.datetime.fromisoformat(iso_date).astimezone(KYIV_TZ)
        except Exception as e:
            error_logger.error(f"Error parsing date with OpenAI: {e}", exc_info=True)
            return None

    def parse_reminder_with_ai(self, reminder_text):
        """
        Use OpenAI GPT to parse reminder text into structured parameters.
        This handles flexible natural language formats including:
        - Different variations of "first/last day of month"
        - Different time specifications
        - Different frequency patterns
        
        Returns a dict with the parsed parameters:
        - task: The actual reminder task
        - frequency: daily, weekly, monthly, or None for one-time
        - date_modifier: Special date patterns like "first day of month", "last day of month"
        - time: Specific time if provided (HH:MM)
        """

        try:
            # Initialize OpenAI client only when method is called
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                error_logger.error("OpenAI API key not set in environment variables")
                return None
                
            client = OpenAI(api_key=api_key)
            
            system_prompt = """You are a reminder parser that extracts the core reminder task and timing information.
            Analyze the text and extract:
            1. The actual reminder task (without timing info)
            2. Frequency (daily, weekly, monthly, or none for one-time)
            3. Special date patterns: detect if this is for "first day of month" or "last day of month"
            4. Time specification (HH:MM format if present)
            
            Return a JSON object with these fields:
            {
                "task": "string", 
                "frequency": "daily|weekly|monthly|null",
                "date_modifier": "first day of every month|last day of every month|null",
                "time": "HH:MM|null"
            }
            
            Examples:
            For "Увімкнути кешбек every first day of month" return:
            {
                "task": "Увімкнути кешбек",
                "frequency": "monthly",
                "date_modifier": "first day of every month",
                "time": null
            }
            
            For "Pay rent on last day of month at 15:00" return:
            {
                "task": "Pay rent",
                "frequency": "monthly",
                "date_modifier": "last day of every month",
                "time": "15:00"
            }"""

            user_prompt = f"Parse this reminder request: {reminder_text}"

            # Use ChatGPT API
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )

            result = response.choices[0].message.content

            # Try to parse JSON response
            import json
            try:
                parsed_data = json.loads(result)
                error_logger.info(f"AI parsed reminder: {parsed_data}")
                return parsed_data
            except json.JSONDecodeError:
                error_logger.error(f"Failed to parse AI response as JSON: {result}")
                return None

        except Exception as e:
            error_logger.error(f"Error parsing reminder with OpenAI: {e}", exc_info=True)
            return None

    async def remind(self, update, context):
        """
        Handle the /remind command to create, list, or delete reminders.
        Usage:
        /remind add <task> [frequency] [delay] - Add a new reminder
        /remind list - List all reminders for this chat
        /remind delete <id> - Delete a reminder by ID
        """
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if not context.args:
            help_text = (
                "📅 Reminder Commands:\n\n"
                "/remind add <task> - Add a one-time reminder\n"
                "/remind add <task> daily - Add a daily reminder\n"
                "/remind add <task> weekly - Add a weekly reminder\n"
                "/remind add <task> monthly - Add a monthly reminder\n"
                "/remind add <task> every first day of month - Set first-of-month reminder\n"
                "/remind add <task> on last day of month - Set end-of-month reminder\n"
                "/remind list - Show your reminders\n"
                "/remind delete <id> - Delete a specific reminder\n"
                "/remind delete all - Delete all your reminders\n\n"
                "💡 NEW: AI-powered natural language parsing!\n"
                "Just describe your reminder in natural language, and the bot will understand.\n\n"
                "Time formats supported:\n"
                "• in X minutes/hours/days (e.g., in 30 minutes)\n" 
                "• at HH:MM (e.g., at 16:30)\n"
                "• daily/weekly/monthly\n"
                "• first/last day of month\n\n"
                "Examples:\n"
                "/remind add Buy milk in 2 hrs\n"
                "/remind add Take a break in 30 min\n"
                "/remind add Team meeting every Monday at 10:00\n"
                "/remind add Pay rent on first day of every month\n"
                "/remind add Увімкнути кешбек every first day of month\n"
                "/remind add Pay bills on last day of month\n"
                "/remind add Play Wordle everyday at 16:20\n"
                "Note: URLs in reminders will be automatically converted to clickable links!"
            )
            await update.message.reply_text(help_text)
            return

        command = context.args[0].lower()

        if command == "add":
            if len(context.args) < 2:
                await update.message.reply_text("Please specify a task for your reminder.")
                return

            # Extract the reminder text from args
            reminder_text = " ".join(context.args[1:])

            # Default values
            frequency = None
            delay = None
            date_modifier = None

            # First, try to parse the reminder using AI
            ai_parsed = self.parse_reminder_with_ai(reminder_text)

            if ai_parsed:
                # Extract values from AI parsing
                task = ai_parsed.get("task", reminder_text)
                frequency = ai_parsed.get("frequency")
                date_modifier = ai_parsed.get("date_modifier")
                time_str = ai_parsed.get("time")

                # If AI didn't find a task, use the original text
                if not task or task.strip() == "":
                    task = reminder_text

                # Parse time if provided by AI
                specified_hour = None
                specified_minute = None
                specific_time = None

                if time_str:
                    try:
                        hour_str, minute_str = time_str.split(":")
                        specified_hour = int(hour_str)
                        specified_minute = int(minute_str)

                        # Calculate next occurrence of this time
                        now = datetime.datetime.now(KYIV_TZ)
                        target_time = now.replace(hour=specified_hour, minute=specified_minute, second=0, microsecond=0)

                        # If the time is already past for today, move to tomorrow
                        if target_time <= now and not date_modifier:
                            target_time += datetime.timedelta(days=1)

                        # Store it for later use
                        specific_time = target_time
                    except (ValueError, TypeError):
                        specified_hour = None
                        specified_minute = None

                # Use the task as the reminder text for further processing
                reminder_text = task

                print(f"AI parsed reminder: task='{task}', frequency='{frequency}', date_modifier='{date_modifier}', time='{time_str}'")

            else:
                # Fall back to rule-based parsing if AI fails
                print("AI parsing failed, falling back to rule-based parsing")

                # Parse frequency and timing from the text
                if "every day" in reminder_text or "daily" in reminder_text or "everyday" in reminder_text:
                    frequency = "daily"
                elif "every week" in reminder_text or "weekly" in reminder_text:
                    frequency = "weekly"
                elif "every month" in reminder_text or "monthly" in reminder_text:
                    frequency = "monthly"
                elif "every second" in reminder_text or "every seconds" in reminder_text:
                    frequency = "seconds"

                # Parse date modifiers
                reminder_text_lower = reminder_text.lower()
                print(f"Checking for date modifiers in: {reminder_text_lower}")

                # Common patterns for last day of month
                last_day_patterns = [
                    "last day of every month",
                    "on the last day of every month",
                    "on last day of every month",
                    "on the last day of month",
                    "last day of month",
                    "last day of the month"
                ]

                # Common patterns for first day of month
                first_day_patterns = [
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
                    "on the 1st day of every month",
                    "every first day of month"
                ]

                # Check for any last day pattern
                if any(pattern in reminder_text_lower for pattern in last_day_patterns):
                    print("Found 'last day of month' pattern")
                    date_modifier = "last day of every month"
                    frequency = "monthly"  # Make sure it's recurring
                # Check for any first day pattern
                elif any(pattern in reminder_text_lower for pattern in first_day_patterns):
                    print("Found 'first day of month' pattern")
                    date_modifier = "first day of every month"
                    frequency = "monthly"  # Make sure it's recurring

                print(f"Date modifier after parsing: {date_modifier}")

                # Look for specific time pattern "at HH:MM"
                specific_time = None
                time_at_pattern = re.compile(r'at\s+(\d{1,2}):(\d{2})')
                time_match = time_at_pattern.search(reminder_text)

                # Extract hours and minutes if there's a time specification
                specified_hour = None
                specified_minute = None
                if time_match:
                    specified_hour = int(time_match.group(1))
                    specified_minute = int(time_match.group(2))

                    # If no date modifier, calculate next occurrence of this time
                    if not date_modifier:
                        now = datetime.datetime.now(KYIV_TZ)
                        target_time = now.replace(hour=specified_hour, minute=specified_minute, second=0, microsecond=0)

                        # If the time is already past for today, move to tomorrow
                        if target_time <= now:
                            target_time += datetime.timedelta(days=1)

                        # Store it for later use
                        specific_time = target_time

            # Parse delay using regex for more flexibility
            reminder_text = self.normalize_time_unit(reminder_text)  # Normalize time units first
            time_pattern = re.compile(r'(in\s+(\d+)\s+(?:second|minute|hour|day|month)s?)')
            time_match = time_pattern.search(reminder_text)
            if time_match:
                delay = time_match.group(1)

                # Direct handling for "seconds" specifically
                if "second" in delay:
                    try:
                        seconds = int(time_match.group(2))

                        # Special handling for "every X seconds" case
                        if "every" in reminder_text:
                            # Define a separate callback function for testing reminders
                            async def test_reminder_callback(context):
                                # Get the data from the context
                                reminder_data = context.job.data

                                # Process the text for links
                                task_text = reminder_data

                                # Direct link support - just send the message with the URL
                                # Telegram will auto-detect the URL and make it clickable
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"⏰ TEST REMINDER: {task_text}"
                                )

                            # Extract just the task part (remove timing info)
                            task_only = re.sub(r'every\s+\d+\s+seconds?', '', reminder_text).strip()

                            # Schedule directly with run_repeating, which is designed for this
                            if context.job_queue:
                                # This creates a job that runs every 5 seconds
                                context.job_queue.run_repeating(
                                    callback=test_reminder_callback,
                                    interval=5,  # Every 5 seconds
                                    first=1,     # Start after 1 second
                                    data=task_only
                                )

                            # Confirm to user - don't store in database since it's just a test feature
                            await update.message.reply_text(f"⚠️ TEST MODE: '{task_only}' reminder will repeat every 5 seconds")
                            return

                        # Normal "in X seconds" case (one-time)
                        now = datetime.datetime.now(KYIV_TZ)
                        next_execution = now + datetime.timedelta(seconds=seconds)

                        # Create reminder object with direct execution time
                        reminder = Reminder(
                            task=reminder_text,
                            frequency=None,  # One-time reminder
                            delay=delay,
                            date_modifier=date_modifier,
                            next_execution=next_execution,
                            user_id=user_id,
                            chat_id=chat_id
                        )

                        # Add to database
                        self.add_reminder(reminder)

                        # Schedule execution based on time
                        if context.job_queue:
                            # Always use direct seconds for short times
                            context.job_queue.run_once(
                                self.send_reminder, 
                                when=seconds,  # Use seconds directly for scheduling
                                data=reminder
                            )

                        # Confirm to user
                        time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M:%S")
                        await update.message.reply_text(f"✅ Reminder set for {time_str} (Kyiv time)")
                        return
                    except (ValueError, IndexError):            
                        pass  # Continue with normal processing if parsing fails

            elif "in 1 hour" in reminder_text:
                delay = "in 1 hour"
            elif "in 1 day" in reminder_text:
                delay = "in 1 day"
            elif "in 1 month" in reminder_text:
                delay = "in 1 month"

            # Calculate next execution time
            now = datetime.datetime.now(KYIV_TZ)

            # Use specific time if it was captured, otherwise default to 5 minutes
            if specific_time:
                next_execution = specific_time
                print(f"Using specific time: {next_execution}")
            elif delay:  # If there's a delay specified
                # Parse the delay and calculate next_execution
                if "second" in delay:
                    seconds = int(re.search(r'\d+', delay).group())
                    next_execution = now + datetime.timedelta(seconds=seconds)
                elif "minute" in delay:
                    minutes = int(re.search(r'\d+', delay).group())
                    next_execution = now + datetime.timedelta(minutes=minutes)
                elif "hour" in delay:
                    hours = int(re.search(r'\d+', delay).group())
                    next_execution = now + datetime.timedelta(hours=hours)
                elif "day" in delay:
                    days = int(re.search(r'\d+', delay).group())
                    next_execution = now + datetime.timedelta(days=days)
                elif "month" in delay:
                    # Approximate month as 30 days
                    next_execution = now + datetime.timedelta(days=30)
                else:
                    next_execution = now + datetime.timedelta(minutes=5)  # Default
            else:
                next_execution = now + datetime.timedelta(minutes=5)  # Default delay

            # Special handling for date modifiers
            if date_modifier:
                # For first or last day of month reminders, we'll use our helper methods
                # to calculate the proper next execution date
                reminder = Reminder(
                    task=reminder_text,
                    frequency="monthly",  # Always monthly for these special date modifiers
                    delay=delay,
                    date_modifier=date_modifier,
                    next_execution=None,  # Will be calculated by helper methods
                    user_id=user_id,
                    chat_id=chat_id
                )

                # Calculate the next execution based on date modifier
                if date_modifier == "first day of every month":
                    reminder._calculate_first_day_of_month(now)
                    print(f"Calculated first day of month: {reminder.next_execution}")
                elif date_modifier == "last day of every month":
                    reminder._calculate_last_day_of_month(now)
                    print(f"Calculated last day of month: {reminder.next_execution}")

                # Use specified time if provided
                if specified_hour is not None and specified_minute is not None:
                    reminder.next_execution = reminder.next_execution.replace(
                        hour=specified_hour,
                        minute=specified_minute
                    )

                # Set the next_execution for later use
                next_execution = reminder.next_execution

            # Ensure the timezone is set
            if next_execution.tzinfo is None:
                next_execution = KYIV_TZ.localize(next_execution)

            # Create reminder object
            reminder = Reminder(
                task=reminder_text,
                frequency=frequency,
                delay=delay,
                date_modifier=date_modifier,
                next_execution=next_execution,
                user_id=user_id,
                chat_id=chat_id
            )

            # Calculate actual next execution time based on parameters
            reminder.calculate_next_execution()

            # Add to database
            self.add_reminder(reminder)

            # Schedule the reminder
            if context.job_queue:
                context.job_queue.run_once(
                    self.send_reminder, 
                    when=reminder.next_execution, 
                    data=reminder
                )

            # Print actual reminder execution time for debugging
            print(f"Final reminder next_execution: {reminder.next_execution}")

            # For date modifiers, use a standardized display format
            if date_modifier:
                # Calculate the execution date based on modifier
                if date_modifier == "last day of every month":
                    # Extract date components
                    month_name = reminder.next_execution.strftime("%B")
                    day = reminder.next_execution.day
                    month = reminder.next_execution.month
                    year = reminder.next_execution.year
                    time_str = reminder.next_execution.strftime("%H:%M")

                    await update.message.reply_text(
                        f"✅ Reminder set for the last day of {month_name} ({day}.{month}.{year} {time_str} Kyiv time)\n"
                        f"Will repeat monthly on the last day of each month."
                    )
                elif date_modifier == "first day of every month":
                    # Extract date components
                    month_name = reminder.next_execution.strftime("%B")
                    month = reminder.next_execution.month
                    year = reminder.next_execution.year
                    time_str = reminder.next_execution.strftime("%H:%M")

                    await update.message.reply_text(
                        f"✅ Reminder set for the first day of {month_name} (1.{month}.{year} {time_str} Kyiv time)\n"
                        f"Will repeat monthly on the first day of each month."
                    )
            elif frequency:
                # Calculate formatted time string here
                time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M")
                await update.message.reply_text(
                    f"✅ Recurring reminder set for {time_str} (Kyiv time)\n"
                    f"Frequency: {frequency}"
                )
            else:
                # Calculate formatted time string here
                time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M")
                await update.message.reply_text(f"✅ One-time reminder set for {time_str} (Kyiv time)")

        elif command == "list":
            # Get reminders for this chat
            chat_reminders = self.get_reminders(chat_id)

            if not chat_reminders:
                await update.message.reply_text("You don't have any reminders set.")
                return

            # Format the list of reminders
            reminder_list = "📝 Your reminders:\n\n"
            now = datetime.datetime.now(KYIV_TZ)

            # Group reminders by status
            past_reminders = []
            upcoming_reminders = []
            recurring_reminders = []

            for r in chat_reminders:
                # Determine status based on next_execution time and frequency
                if not r.next_execution:
                    status = "⚠️ Unknown"
                elif r.frequency:
                    if r.frequency == "seconds":
                        status = "🔄 Testing (every 5s)"
                    else:
                        status = "🔁 Recurring"
                    recurring_reminders.append(r)
                elif r.next_execution <= now:
                    status = "✅ Completed"
                    past_reminders.append(r)
                else:
                    minutes_remaining = (r.next_execution - now).total_seconds() / 60
                    if minutes_remaining < 5:
                        status = "⏳ Soon (<5 min)"
                    else:
                        status = "⏰ Scheduled"
                    upcoming_reminders.append(r)

                # Format the time
                time_str = r.next_execution.strftime("%d.%m.%Y %H:%M") if r.next_execution else "Unknown"

                # Add to the appropriate section
                if r in upcoming_reminders:    
                    upcoming_reminders.remove(r)
                    upcoming_reminders.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Next: {time_str} Kyiv time)\n"))
                elif r in recurring_reminders:
                    recurring_reminders.remove(r)
                    recurring_reminders.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Next: {time_str} Kyiv time)\n"))
                elif r in past_reminders:
                    past_reminders.remove(r)
                    past_reminders.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Ran at: {time_str} Kyiv time)\n"))

            # Sort each group
            upcoming_reminders.sort(key=lambda x: x[0].next_execution or datetime.datetime.max)
            recurring_reminders.sort(key=lambda x: x[0].next_execution or datetime.datetime.max)
            past_reminders.sort(key=lambda x: x[0].next_execution or datetime.datetime.min, reverse=True)

            # Add upcoming reminders first
            if upcoming_reminders:
                reminder_list += "📅 UPCOMING:\n"
                for _, reminder_str in upcoming_reminders:
                    reminder_list += reminder_str
                reminder_list += "\n"

            # Add recurring reminders next
            if recurring_reminders:
                reminder_list += "🔁 RECURRING:\n"
                for _, reminder_str in recurring_reminders:
                    reminder_list += reminder_str
                reminder_list += "\n"

            # Add past reminders last
            if past_reminders:
                reminder_list += "✅ COMPLETED:\n"
                for _, reminder_str in past_reminders[:5]:  # Only show last 5 completed reminders
                    reminder_list += reminder_str
                if len(past_reminders) > 5:
                    reminder_list += f"...and {len(past_reminders) - 5} more\n"

            await update.message.reply_text(reminder_list)

        elif command == "delete":
            if len(context.args) < 2:
                await update.message.reply_text("Please specify a reminder ID to delete, or use 'all' to delete all reminders.")
                return

            # Check for "delete all" command
            if context.args[1].lower() == "all":
                # Get all reminders for this chat
                chat_reminders = self.get_reminders(chat_id)
                if not chat_reminders:
                    await update.message.reply_text("You don't have any reminders to delete.")
                    return
                
                # Delete all reminders
                count = len(chat_reminders)
                for reminder in chat_reminders[:]:  # Use a copy to avoid modification during iteration
                    self.remove_reminder(reminder)
                
                await update.message.reply_text(f"✅ All reminders deleted ({count} total).")
                return
            
            # Handle deleting a specific reminder by ID
            try:
                reminder_id = int(context.args[1])
                
                # Find the reminder by ID
                reminder_to_delete = next((r for r in self.reminders if r.reminder_id == reminder_id and r.chat_id == chat_id), None)

                if not reminder_to_delete:
                    await update.message.reply_text(f"Reminder ID {reminder_id} not found.")
                    return
                    
                # Delete the reminder
                self.remove_reminder(reminder_to_delete)
                await update.message.reply_text(f"✅ Reminder deleted.")
                
            except ValueError:
                await update.message.reply_text("Invalid reminder ID. Please provide a valid number or use 'all' to delete all reminders.")

        else:
            help_text = (
                "❌ Unknown command\n\n"
                "Available commands:\n"
                "/remind add <task> - Add a reminder\n"
                "/remind list - Show your reminders\n"
                "/remind delete <id> - Delete a reminder\n\n"
                "Type /remind for full usage instructions"
            )
            await update.message.reply_text(help_text)