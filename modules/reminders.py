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
        """Convert reminder to tuple for database storage"""
        return (
            self.reminder_id, 
            self.task, 
            self.frequency, 
            self.delay, 
            self.date_modifier, 
            self.next_execution.isoformat() if isinstance(self.next_execution, datetime.datetime) else None, 
            self.user_id, 
            self.chat_id
        )

    @classmethod
    def from_tuple(cls, data):
        """Create reminder from database tuple"""
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
                chat_id INTEGER
            )
        ''')
        self.conn.commit()

    def add_reminder(self, reminder):
        """Add a reminder to the database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (task, frequency, delay, date_modifier, next_execution, user_id, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', reminder.to_tuple()[1:])  # Skip reminder_id
        self.conn.commit()
        reminder.reminder_id = cursor.lastrowid
        self.reminders.append(reminder)
        return reminder

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

    async def check_reminders(self, context: CallbackContext):
        """Periodic check for due reminders"""
        try:
            if context is None:
                return

            now = datetime.datetime.now(KYIV_TZ)
            error_logger.info(f"Checking reminders at {now.isoformat()}")

            # Load the latest reminders
            self.reminders = self.load_reminders()
            error_logger.info(f"Loaded {len(self.reminders)} reminders from database")

            # Find reminders that are due
            reminders_to_send = []
            for reminder in self.reminders:
                if reminder.next_execution:
                    # Ensure timezone is set
                    if reminder.next_execution.tzinfo is None:
                        reminder.next_execution = KYIV_TZ.localize(reminder.next_execution)

                    # Check if it's time to send
                    if reminder.next_execution <= now:
                        error_logger.info(f"Reminder {reminder.reminder_id} is due: '{reminder.task}'")
                        reminders_to_send.append(reminder)

            # Process due reminders
            for reminder in reminders_to_send:
                try:
                    # Set up context with reminder data
                    mock_context = context
                    mock_context.job = type('MockJob', (), {'data': reminder})
                    
                    # Send the reminder
                    await self.send_reminder(mock_context)

                    # Handle recurring reminders
                    if reminder.frequency:
                        old_time = reminder.next_execution
                        reminder.calculate_next_execution()
                        error_logger.info(f"Updated reminder {reminder.reminder_id} from {old_time.isoformat()} to {reminder.next_execution.isoformat()}")
                        self.update_reminder(reminder)

                        # Special case for seconds frequency - reschedule immediately
                        if reminder.frequency == "seconds" and context.job_queue:
                            context.job_queue.run_once(
                                self.send_reminder, 
                                when=5,  # Fixed 5 seconds interval for testing
                                data=reminder
                            )
                    else:
                        # One-time reminder, remove it
                        error_logger.info(f"Removing one-time reminder {reminder.reminder_id}")
                        self.remove_reminder(reminder)
                except Exception as e:
                    error_logger.error(f"Error processing reminder {reminder.reminder_id}: {e}", exc_info=True)

        except Exception as e:
            error_logger.error(f"Error in check_reminders: {e}", exc_info=True)

    async def send_reminder(self, context: CallbackContext):
        """Send a reminder message"""
        try:
            if not context or not context.job or not context.job.data:
                error_logger.error("Invalid context in send_reminder")
                return

            reminder = context.job.data

            # Check for URLs in the reminder text
            url_pattern = r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            has_urls = bool(re.search(url_pattern, reminder.task))

            # Send the reminder message
            await context.bot.send_message(
                chat_id=reminder.chat_id, 
                text=f"⏰ REMINDER: {reminder.task}",
                parse_mode=None,  # Let Telegram auto-format
                disable_web_page_preview=not has_urls  # Allow preview only if there are URLs
            )

        except Exception as e:
            error_logger.error(f"Error in send_reminder: {e}", exc_info=True)

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
            # Show help text
            help_text = (
                "📅 Reminder Commands:\n\n"
                "/remind add <task> - Add a one-time reminder\n"
                "/remind add <task> daily - Add a daily reminder\n"
                "/remind add <task> weekly - Add a weekly reminder\n"
                "/remind add <task> monthly - Add a monthly reminder\n"
                "/remind add <task> every first day of month - First-of-month reminder\n"
                "/remind add <task> on last day of month - End-of-month reminder\n"
                "/remind list - Show your reminders\n"
                "/remind delete <id> - Delete a specific reminder\n"
                "/remind delete all - Delete all your reminders\n\n"
                "Time formats supported:\n"
                "• in X minutes/hours/days (e.g., in 30 minutes)\n" 
                "• at HH:MM (e.g., at 16:30)\n"
                "• daily/weekly/monthly\n"
                "• first/last day of month\n\n"
                "Examples:\n"
                "/remind add Buy milk in 2 hours\n"
                "/remind add Team meeting every Monday at 10:00\n"
                "/remind add Pay rent on first day of every month\n"
                "/remind add Pay bills on last day of month"
            )
            await update.message.reply_text(help_text)
            return

        command = context.args[0].lower()

        if command == "add":
            if len(context.args) < 2:
                await update.message.reply_text("Please specify a task for your reminder.")
                return

            # Extract the reminder text
            reminder_text = " ".join(context.args[1:])
            
            # Parse reminder parameters
            parsed = self.parse_reminder(reminder_text)
            task = parsed['task']
            frequency = parsed['frequency']
            date_modifier = parsed['date_modifier']
            time_tuple = parsed['time']
            delay = parsed['delay']
            
            # Calculate next execution time
            now = datetime.datetime.now(KYIV_TZ)
            
            # Start with default time (5 minutes from now)
            next_execution = now + datetime.timedelta(minutes=5)
            
            # Apply specific time if provided
            if time_tuple:
                hour, minute = time_tuple
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If time is in the past, move to next day
                if target_time <= now and not date_modifier:
                    target_time += datetime.timedelta(days=1)
                    
                next_execution = target_time
                
            # Apply delay if provided
            if delay:
                match = re.search(r'in\s+(\d+)\s+(second|minute|hour|day|month)', delay)
                if match:
                    amount = int(match.group(1))
                    unit = match.group(2)
                    
                    if unit == 'second':
                        next_execution = now + datetime.timedelta(seconds=amount)
                    elif unit == 'minute':
                        next_execution = now + datetime.timedelta(minutes=amount)
                    elif unit == 'hour':
                        next_execution = now + datetime.timedelta(hours=amount)
                    elif unit == 'day':
                        next_execution = now + datetime.timedelta(days=amount)
                    elif unit == 'month':
                        next_execution = now + datetime.timedelta(days=amount*30)  # approximate
            
            # Create the reminder object
            reminder = Reminder(
                task=task,
                frequency=frequency,
                delay=delay,
                date_modifier=date_modifier,
                next_execution=next_execution,
                user_id=user_id,
                chat_id=chat_id
            )
            
            # Calculate actual next execution time
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
            
            # Prepare confirmation message
            time_str = reminder.next_execution.strftime("%d.%m.%Y %H:%M")
            
            if date_modifier == "first day of every month":
                month_name = reminder.next_execution.strftime("%B")
                await update.message.reply_text(
                    f"✅ Reminder set for the first day of {month_name} ({time_str} Kyiv time)\n"
                    f"Will repeat monthly on the first day of each month."
                )
            elif date_modifier == "last day of every month":
                month_name = reminder.next_execution.strftime("%B")
                await update.message.reply_text(
                    f"✅ Reminder set for the last day of {month_name} ({time_str} Kyiv time)\n"
                    f"Will repeat monthly on the last day of each month."
                )
            elif frequency:
                await update.message.reply_text(
                    f"✅ Recurring reminder set for {time_str} (Kyiv time)\n"
                    f"Frequency: {frequency}"
                )
            else:
                await update.message.reply_text(f"✅ One-time reminder set for {time_str} (Kyiv time)")

        elif command == "list":
            # Get reminders for this chat
            chat_reminders = self.get_reminders(chat_id)

            if not chat_reminders:
                await update.message.reply_text("You don't have any reminders set.")
                return

            # Format the list of reminders
            now = datetime.datetime.now(KYIV_TZ)
            upcoming = []
            recurring = []
            past = []

            for r in chat_reminders:
                time_str = r.next_execution.strftime("%d.%m.%Y %H:%M") if r.next_execution else "Unknown"
                
                if r.frequency:
                    status = "🔄 Testing" if r.frequency == "seconds" else "🔁 Recurring"
                    recurring.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Next: {time_str})\n"))
                elif not r.next_execution or r.next_execution <= now:
                    status = "✅ Completed"
                    past.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, Ran: {time_str})\n"))
                else:
                    minutes_left = (r.next_execution - now).total_seconds() / 60
                    status = "⏳ Soon" if minutes_left < 5 else "⏰ Scheduled"
                    upcoming.append((r, f"ID: {r.reminder_id} - {r.task} ({status}, At: {time_str})\n"))
            
            # Sort each category
            upcoming.sort(key=lambda x: x[0].next_execution or datetime.datetime.max)
            recurring.sort(key=lambda x: x[0].next_execution or datetime.datetime.max)
            past.sort(key=lambda x: x[0].next_execution or datetime.datetime.min, reverse=True)
            
            # Build the message
            result = "📝 Your reminders:\n\n"
            
            if upcoming:
                result += "📅 UPCOMING:\n"
                result += "".join([item[1] for item in upcoming])
                result += "\n"
                
            if recurring:
                result += "🔁 RECURRING:\n"
                result += "".join([item[1] for item in recurring])
                result += "\n"
                
            if past:
                result += "✅ COMPLETED:\n"
                result += "".join([item[1] for item in past[:5]])
                if len(past) > 5:
                    result += f"...and {len(past) - 5} more\n"
                
            await update.message.reply_text(result)

        elif command == "delete":
            if len(context.args) < 2:
                await update.message.reply_text("Please specify a reminder ID to delete, or use 'all'.")
                return

            # Check for "delete all" command
            if context.args[1].lower() == "all":
                chat_reminders = self.get_reminders(chat_id)
                if not chat_reminders:
                    await update.message.reply_text("You don't have any reminders to delete.")
                    return
                
                count = len(chat_reminders)
                for reminder in chat_reminders[:]:
                    self.remove_reminder(reminder)
                
                await update.message.reply_text(f"✅ All reminders deleted ({count} total).")
                return
            
            # Delete specific reminder
            try:
                reminder_id = int(context.args[1])
                reminder_to_delete = next((r for r in self.reminders 
                                          if r.reminder_id == reminder_id and r.chat_id == chat_id), None)

                if not reminder_to_delete:
                    await update.message.reply_text(f"Reminder ID {reminder_id} not found.")
                    return
                    
                self.remove_reminder(reminder_to_delete)
                await update.message.reply_text(f"✅ Reminder deleted.")
                
            except ValueError:
                await update.message.reply_text("Invalid reminder ID. Please provide a valid number or use 'all'.")

        else:
            await update.message.reply_text(
                "❌ Unknown command\n\n"
                "Available commands:\n"
                "/remind add <task> - Add a reminder\n"
                "/remind list - Show your reminders\n"
                "/remind delete <id> - Delete a reminder\n\n"
                "Type /remind for full usage instructions"
            )

    def schedule_reminders(self, bot, job_queue):
        """Schedule all loaded reminders"""
        now = datetime.datetime.now(KYIV_TZ)
        for reminder in self.reminders:
            if reminder.next_execution > now:
                job_queue.run_once(
                    self.send_reminder,
                    when=reminder.next_execution,
                    data=reminder
                )
                print(f"Scheduled reminder {reminder.reminder_id} for {reminder.next_execution}")
            else:
                print(f"Reminder {reminder.reminder_id} is in the past. Skipping.")