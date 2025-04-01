import sqlite3
import datetime
import pytz
import re
import os
import openai
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
        
        # Handle recurring frequencies first
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
            
            # First, load the latest reminders from the database
            self.reminders = self.load_reminders()
            
            # Process reminders that need to be sent
            reminders_to_send = []
            for reminder in self.reminders:
                if reminder.next_execution:
                    # Ensure timezone is set
                    if reminder.next_execution.tzinfo is None:
                        reminder.next_execution = KYIV_TZ.localize(reminder.next_execution)
                    
                    # Check if it's time to send
                    if reminder.next_execution <= now:
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
                        reminder.calculate_next_execution()
                        self.update_reminder(reminder)
                        
                        # Special case for seconds frequency - reschedule immediately
                        if reminder.frequency == "seconds" and context.job_queue:
                            job = context.job_queue.run_once(
                                self.send_reminder, 
                                when=5,  # Fixed 5 seconds interval for testing
                                data=reminder
                            )
                    else:
                        # One-time reminder, remove it
                        self.remove_reminder(reminder)
                except Exception as e:
                    error_logger.error(f"Error processing reminder {reminder.reminder_id}: {e}")
        
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
                    # No URLs, send regular messager message
                    await context.bot.send_message(sage(
                        chat_id=reminder.chat_id,         chat_id=reminder.chat_id, 
                        text=f"⏰ REMINDER: {task_text}""⏰ REMINDER: {task_text}"
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
            UPDATE remindersUPDATE reminders
            SET task = ?, frequency = ?, delay = ?, date_modifier = ?, next_execution = ?, user_id = ?, chat_id = ? ?, date_modifier = ?, next_execution = ?, user_id = ?, chat_id = ?
            WHERE reminder_id = ?
        ''', (reminder.task, reminder.frequency, reminder.delay, reminder.date_modifier, reminder.next_execution.isoformat() if isinstance(reminder.next_execution, datetime.datetime) else None, reminder.user_id, reminder.chat_id, reminder.reminder_id))eminder.frequency, reminder.delay, reminder.date_modifier, reminder.next_execution.isoformat() if isinstance(reminder.next_execution, datetime.datetime) else None, reminder.user_id, reminder.chat_id, reminder.reminder_id))
        self.conn.commit()

    def parse_natural_language_date(self, text):
        openai.api_key = os.getenv("OPENAI_API_KEY") # Ensure API key is set in environment variables.
        prompt = f"Convert the following natural language date/time to ISO 8601 format: {text}"
        try:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=50
            )
            iso_date = response.choices[0].text.strip()
            return datetime.datetime.fromisoformat(iso_date).astimezone(KYIV_TZ)    iso_date = response.choices[0].text.strip()
        except Exception as e:turn datetime.datetime.fromisoformat(iso_date).astimezone(KYIV_TZ)
            error_logger.error(f"Error parsing date with OpenAI: {e}", exc_info=True)
            return None
            
    async def remind(self, update, context):
        """
        Handle the /remind command to create, list, or delete reminders.
        Handle the /remind command to create, list, or delete reminders.
        Usage:
        /remind add <task> [frequency] [delay] - Add a new reminder
        /remind list - List all reminders for this chatay] - Add a new reminder
        /remind delete <id> - Delete a reminder by ID
        """
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not context.args:
            help_text = (
                "📅 Reminder Commands:\n\n"(
                "/remind add <task> - Add a one-time reminder\n"         "📅 Reminder Commands:\n\n"
                "/remind add <task> daily - Add a daily reminder\n"
                "/remind add <task> weekly - Add a weekly reminder\n"
                "/remind add <task> monthly - Add a monthly reminder\n"
                "/remind add <task> every 5 seconds - Add a quick repeating reminder\n"
                "/remind list - Show your reminders\n"
                "/remind delete <id> - Delete a reminder\n\n"
                "Time formats supported:\n"
                "• in X seconds (e.g., in 5 seconds)\n"
                "• in X minutes (e.g., in 30 minutes)\n" 
                "• in X hours (e.g., in 2 hours)\n"
                "• in X days (e.g., in 3 days)\n"
                "• in X months (e.g., in 1 month)\n"
                "• at HH:MM (e.g., at 16:30)\n"
                "• every 5 seconds (special testing mode)\n\n"
                "Examples:\n"
                "/remind add Buy milk in 2 hours\n"
                "/remind add Take a break in 30 minutes\n"
                "/remind add Team meeting every Monday at 10:00\n"H:MM (e.g., at 16:30)\n"
                "/remind add Pay rent on first day of every month\n"
                "/remind add Play Wordle (https://www.nytimes.com/games/wordle) everyday at 16:20\n"
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
            delay = None# Extract the reminder text from args
            date_modifier = None
            
            # Parse frequency and timing from the text
            if "every day" in reminder_text or "daily" in reminder_text or "everyday" in reminder_text:
                frequency = "daily"
            elif "every week" in reminder_text or "weekly" in reminder_text:
                frequency = "weekly"
            elif "every month" in reminder_text or "monthly" in reminder_text:
                frequency = "monthly"
            elif "every second" in reminder_text or "every seconds" in reminder_text:
                frequency = "seconds"
                
            # Initialize date_modifier
            date_modifier = None
            
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
                "on the 1st day of every month"
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
            time_pattern = re.compile(r'(in\s+(\d+)\s+(?:second|minute|hour|day|month)s?)')
            time_match = time_pattern.search(reminder_text)e
            if time_match:    specific_time = target_time
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
                                # This creates a job that runs every 5 secondsing info)
                                context.job_queue.run_repeating(onds?', '', reminder_text).strip()
                                    callback=test_reminder_callback,
                                    interval=5,  # Every 5 secondsth run_repeating, which is designed for this
                                    first=1,     # Start after 1 secondntext.job_queue:
                                    data=task_only    # This creates a job that runs every 5 seconds
                                )
                            
                            # Confirm to user - don't store in database since it's just a test feature
                            await update.message.reply_text(f"⚠️ TEST MODE: '{task_only}' reminder will repeat every 5 seconds")
                            return
                        
                        # Normal "in X seconds" case (one-time)
                        # Override next_execution calculation just a test feature
                        now = datetime.datetime.now(KYIV_TZ)    await update.message.reply_text(f"⚠️ TEST MODE: '{task_only}' reminder will repeat every 5 seconds")
                        next_execution = now + datetime.timedelta(seconds=seconds)
                        
                        # Create reminder object with direct execution time
                        reminder = Reminder(
                            task=reminder_text,atetime.now(KYIV_TZ)
                            frequency=None,  # One-time remindertimedelta(seconds=seconds)
                            delay=delay,
                            date_modifier=date_modifier,ject with direct execution time
                            next_execution=next_execution,(
                            user_id=user_id,   task=reminder_text,
                            chat_id=chat_id    frequency=None,  # One-time reminder
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
                        time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M:%S")  when=seconds,  # Use seconds directly for scheduling
                        await update.message.reply_text(f"✅ Reminder set for {time_str} (Kyiv time)")
                        return
                    except (ValueError, IndexError):            
                        pass  # Continue with normal processing if parsing fails
            
            elif "in 1 hour" in reminder_text:
                delay = "in 1 hour"
            elif "in 1 day" in reminder_text:ror):
                delay = "in 1 day"inue with normal processing if parsing fails
            elif "in 1 month" in reminder_text:
                delay = "in 1 month"
                
            # This section was replaced with more comprehensive pattern matching above
                
            # Calculate next execution time
            now = datetime.datetime.now(KYIV_TZ)
            
            # Use specific time if it was captured, otherwise default to 5 minutes
            if specific_time:
                next_execution = specific_time
                print(f"Using specific time: {next_execution}")
            else:
                next_execution = now + datetime.timedelta(minutes=5)  # Default to 5 minutes
            
            # Override next_execution with date_modifier calculation if set
            if date_modifier == "last day of every month":
                print(f"Date modifier is 'last day of every month'")
                now = datetime.datetime.now(KYIV_TZ)
                print(f"Current date: {now}")
                
                # Calculate the last day of the current month
                current_month = now.month
                current_year = now.year
                
                # First day of next month
                if current_month == 12:
                    next_month_year = current_year + 1
                    next_month = 1
                else:
                    next_month_year = current_year
                    next_month = current_month + 1
                
                first_of_next_month = datetime.datetime(
                    year=next_month_year,
                    month=next_month,
                    day=1,
                    tzinfo=KYIV_TZ
                )
                print(f"First day of next month: {first_of_next_month}")
                
                # Last day of current month is one day before first of next month
                last_day_of_current_month = first_of_next_month - datetime.timedelta(days=1)
                print(f"Last day of current month: {last_day_of_current_month}")
                
                # If current day is already the last day of month, move to next month
                if now.day == last_day_of_current_month.day:
                    print("Today is already the last day of month, calculating for next month")
                    # Calculate first day of month after next
                    if next_month == 12:
                        month_after_next_year = next_month_year + 1
                        month_after_next = 1
                    else:
                        month_after_next_year = next_month_year
                        month_after_next = next_month + 1
                    
                    first_of_month_after_next = datetime.datetime(
                        year=month_after_next_year,
                        month=month_after_next,
                        day=1,
                        tzinfo=KYIV_TZ
                    )
                    # Last day of next month
                    target_day = first_of_month_after_next - datetime.timedelta(days=1)
                else:
                    print("Using last day of current month")
                    target_day = last_day_of_current_month
                
                print(f"Target day before time adjustment: {target_day}")
                
                # Use specified time if provided, otherwise default to 9:00 AM
                # Create a completely new datetime with explicit timezone to avoid tzinfo issues
                if specified_hour is not None and specified_minute is not None:
                    next_execution = datetime.datetime(
                        year=target_day.year,
                        month=target_day.month,
                        day=target_day.day,
                        hour=specified_hour,
                        minute=specified_minute,
                        second=0,
                        microsecond=0,
                        tzinfo=KYIV_TZ  # Use KYIV_TZ explicitly
                    )
                    print(f"Using specified time with explicit timezone: {next_execution}")
                else:
                    next_execution = datetime.datetime(
                        year=target_day.year,
                        month=target_day.month,
                        day=target_day.day,
                        hour=9,
                        minute=0,
                        second=0,
                        microsecond=0,
                        tzinfo=KYIV_TZ  # Use KYIV_TZ explicitly
                    )
                    print(f"Using default time with explicit timezone: {next_execution}")
                
                print(f"Final last day of month calculation: {next_execution}")
                
            # Ensure the timezone is set
            if next_execution.tzinfo is None:    print(f"Using default time with explicit timezone: {next_execution}")
                next_execution = KYIV_TZ.localize(next_execution)
            
            # Create reminder object
            reminder = Reminder(
                task=reminder_text,
                frequency=frequency,ze(next_execution)
                delay=delay,
                date_modifier=date_modifier,
                next_execution=next_execution,
                user_id=user_id,t,
                chat_id=chat_id
            )
            
            # Calculate actual next execution time based on parameters
            reminder.calculate_next_execution()
            
            # Add to database
            self.add_reminder(reminder)
            
            # Schedule the reminder
            if context.job_queue:
                context.job_queue.run_once(
                    self.send_reminder, )
                    when=reminder.next_execution, 
                    data=remindere the reminder
                )
            
            # Print actual reminder execution time for debugging
            print(f"Final reminder next_execution: {reminder.next_execution}")
            
            # For last day of month, we'll calculate the correct day and month explicitly
            if date_modifier == "last day of every month":
                # Calculate the last day of current month correctly
                now = datetime.datetime.now(KYIV_TZ)
                if now.month == 12:
                    next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                else:
                    next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                last_day = next_month - datetime.timedelta(days=1)
                
                # Get the correct month name and day
                month_name = last_day.strftime("%B")
                day = last_day.day
                
                # Format time only
                time_str = reminder.next_execution.strftime("%H:%M")
                
                # Use explicit formatting to avoid timezone confusion
                await update.message.reply_text(
                    f"✅ Reminder set for the last day of {month_name} ({day}.{last_day.month}.{last_day.year} {time_str} Kyiv time)\n"
                    f"Will repeat monthly on the last day of each month."
                )
            elif date_modifier == "first day of every month":
                # Calculate the first day of next month correctly
                now = datetime.datetime.now(KYIV_TZ)
                if now.month == 12:
                    next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                else:
                    next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                
                # Get the correct month name
                month_name = next_month.strftime("%B")
                
                # Format time for display
                time_str = reminder.next_execution.strftime("%H:%M")
                
                await update.message.reply_text(
                    f"✅ Reminder set for the first day of {month_name} (1.{next_month.month}.{next_month.year} {time_str} Kyiv time)\n"
                    f"Will repeat monthly on the first day of each month."
                )
            elif frequency:
                # Calculate formatted time string here
                time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M")ay of {month_name} (1.{next_month.month}.{next_month.year} {time_str} Kyiv time)\n"
                await update.message.reply_text(monthly on the first day of each month."
                    f"✅ Recurring reminder set for {time_str} (Kyiv time)\n")
                    f"Frequency: {frequency}"
                )
            else:time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M")
                # Calculate formatted time string here
                time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M")or {time_str} (Kyiv time)\n"
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
            upcoming_reminders = []nder_list = "📝 Your reminders:\n\n"
            recurring_reminders = []
            
            for r in chat_reminders:
                # Determine status based on next_execution time and frequencyreminders = []
                if not r.next_execution:ers = []
                    status = "⚠️ Unknown"
                elif r.frequency:
                    if r.frequency == "seconds":
                        status = "🔄 Testing (every 5s)"y
                    else:
                        status = "🔁 Recurring"   status = "⚠️ Unknown"
                    recurring_reminders.append(r)lif r.frequency:
                elif r.next_execution <= now:
                    status = "✅ Completed"
                    past_reminders.append(r)
                else:            status = "🔁 Recurring"
                    minutes_remaining = (r.next_execution - now).total_seconds() / 60eminders.append(r)
                    if minutes_remaining < 5:now:
                        status = "⏳ Soon (<5 min)"
                    else:        past_reminders.append(r)
                        status = "⏰ Scheduled"
                    upcoming_reminders.append(r)
                
                # Format the time
                time_str = r.next_execution.strftime("%d.%m.%Y %H:%M") if r.next_execution else "Unknown"
                
                # Add to the appropriate section
                if r in upcoming_reminders:    
                    upcoming_reminders.remove(r)
                    upcoming_reminders.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Next: {time_str} Kyiv time)\n"))xt_execution.strftime("%d.%m.%Y %H:%M") if r.next_execution else "Unknown"
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
            if upcoming_reminders:a x: x[0].next_execution or datetime.datetime.max)
                reminder_list += "📅 UPCOMING:\n"ambda x: x[0].next_execution or datetime.datetime.max)
                for _, reminder_str in upcoming_reminders:: x[0].next_execution or datetime.datetime.min, reverse=True)
                    reminder_list += reminder_str
                reminder_list += "\n"
            
            # Add recurring reminders next
            if recurring_reminders:minder_str in upcoming_reminders:
                reminder_list += "🔁 RECURRING:\n"str
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
                await update.message.reply_text("Please specify a reminder ID to delete.")
                return
                
            try:
                reminder_id = int(context.args[1])
                
                # Find the reminder by ID
                reminder_to_delete = next((r for r in self.reminders if r.reminder_id == reminder_id and r.chat_id == chat_id), None)

                if not reminder_to_delete:
                    await update.message.reply_text(f"Reminder ID {reminder_id} not found.")text.args[1])
                    return
                    
                # Delete the reminder
                self.remove_reminder(reminder_to_delete)
                await update.message.reply_text(f"✅ Reminder deleted.")
                
            except ValueError:
                await update.message.reply_text("Invalid reminder ID. Please provide a valid number.")
        
        else:
            await update.message.reply_text("Unknown command. Use /remind add, /remind list, or /remind delete.")