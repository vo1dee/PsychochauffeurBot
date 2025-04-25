from datetime import datetime, timedelta
import sqlite3
import re
from dateutil.relativedelta import relativedelta
from dateutil.parser import isoparse
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from modules.const import KYIV_TZ
from modules.logger import error_logger, general_logger
from timefhuman import timefhuman

from telegram import Update
from telegram.ext import CallbackContext


def seconds_until(dt):
    now = datetime.now(KYIV_TZ)
    if dt.tzinfo is None:
        dt = KYIV_TZ.localize(dt)
    else:
        dt = dt.astimezone(KYIV_TZ)
    return max(0.01, (dt - now).total_seconds())


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
        now = datetime.now(KYIV_TZ)

        if self.date_modifier:
            if self.date_modifier == 'first day of every month':
                self._calc_first_month(now)
                return
            elif self.date_modifier == 'last day of every month':
                self._calc_last_month(now)
                return

        if not self.frequency:
            return

        if self.frequency == 'daily':
            self._advance_daily(now)
        elif self.frequency == 'weekly':
            self._advance_weekly(now)
        elif self.frequency == 'monthly':
            self._advance_monthly(now)
        elif self.frequency == 'yearly':
            self._advance_yearly(now)
    
    def _advance_daily(self, now):
        if self.next_execution and self.next_execution <= now:
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            self.next_execution += timedelta(days=1)
        elif not self.next_execution:
            self.next_execution = now + timedelta(days=1)
    
    def _advance_weekly(self, now):
        if self.next_execution and self.next_execution <= now:
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            self.next_execution += timedelta(weeks=1)
        elif not self.next_execution:
            self.next_execution = now + timedelta(weeks=1)
    
    def _advance_monthly(self, now):
        if self.next_execution and self.next_execution <= now:
            self.next_execution += relativedelta(months=1)
        elif not self.next_execution:
            self.next_execution = now + relativedelta(months=1)
    
    def _advance_yearly(self, now):
        if self.next_execution and self.next_execution <= now:
            self.next_execution += relativedelta(years=1)
        elif not self.next_execution:
            self.next_execution = now + relativedelta(years=1)

    def _calc_first_month(self, now):
        """Calculate first day of next month"""
        if now.month == 12:
            dt = datetime(now.year + 1, 1, 1, 9, 0, tzinfo=KYIV_TZ)
        else:
            dt = datetime(now.year, now.month + 1, 1, 9, 0, tzinfo=KYIV_TZ)
        
        # If we have a next_execution, use its time
        if self.next_execution:
            dt = dt.replace(hour=self.next_execution.hour, minute=self.next_execution.minute)
        
        # If the calculated time is in the past, move to next month
        if dt <= now:
            if dt.month == 12:
                dt = datetime(dt.year + 1, 1, 1, dt.hour, dt.minute, tzinfo=KYIV_TZ)
            else:
                dt = datetime(dt.year, dt.month + 1, 1, dt.hour, dt.minute, tzinfo=KYIV_TZ)
        
        self.next_execution = dt

    def _calc_last_month(self, now):
        """Calculate last day of next month"""
        # Calculate last day of the NEXT month
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
        else:
            end = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
            
        # For testing: when calculating next execution, move to the next month
        if self.next_execution and self.next_execution.month == now.month:
            if now.month == 12:
                end = datetime(now.year + 1, 2, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
            else:
                end = datetime(now.year, now.month + 2, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                
        hour = self.next_execution.hour if self.next_execution else 9
        minute = self.next_execution.minute if self.next_execution else 0
        self.next_execution = end.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def to_tuple(self):
        return (self.reminder_id, self.task, self.frequency, self.delay, self.date_modifier,
                self.next_execution.isoformat() if self.next_execution else None,
                self.user_id, self.chat_id, self.user_mention_md)

    @classmethod
    def from_tuple(cls, data):
        (rid, task, freq, delay, mod, next_exec_str, uid, cid, mention) = data
        dt = isoparse(next_exec_str) if next_exec_str else None
        if dt and dt.tzinfo is None:
            dt = KYIV_TZ.localize(dt)
        return cls(task, freq, delay, mod, dt, uid, cid, mention, rid)


class ReminderManager:
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self._create_table()
        self.reminders = self.load_reminders()
        
        # Common regex patterns
        self.FREQUENCY_PATTERN = r'(?:every\s+(day|week|month|year))|(?:(daily|weekly|monthly|yearly))'
        self.DATE_MODIFIER_PATTERN = r'(?:first\s+day\s+of\s+every\s+month)|(?:first\s+of\s+every\s+month)|(?:on\s+the\s+1st)|(?:last\s+day\s+of\s+every\s+month)'
        self.TIME_PATTERN = r'(?:at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?|in\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|wks?|months?|years?))'

    def _create_table(self):
        """Create reminders table if it doesn't exist"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                frequency TEXT,
                delay TEXT,
                date_modifier TEXT,
                next_execution TEXT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                user_mention_md TEXT
            )
        ''')
        self.conn.commit()

    def get_connection(self):
        conn = sqlite3.connect(self.db_file, check_same_thread=False)
        # Create table if it doesn't exist (helpful for tests with in-memory databases)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    frequency TEXT,
                    delay TEXT,
                    date_modifier TEXT,
                    next_execution TEXT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_mention_md TEXT
                )
            ''')
        return conn

    def load_reminders(self, chat_id=None):
        """Load all reminders from the database, optionally filtered by chat_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if chat_id:
                cursor.execute('SELECT * FROM reminders WHERE chat_id = ?', (chat_id,))
            else:
                cursor.execute('SELECT * FROM reminders')
            data = cursor.fetchall()
            return [Reminder.from_tuple(r) for r in data]

    def save_reminder(self, rem):
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # Ensure next_execution is timezone-aware before saving
            if rem.next_execution:
                if rem.next_execution.tzinfo is None:
                    rem.next_execution = KYIV_TZ.localize(rem.next_execution)
                rem.next_execution = rem.next_execution.astimezone(KYIV_TZ)
                
            if rem.reminder_id:
                c.execute('''UPDATE reminders SET task=?, frequency=?, delay=?, date_modifier=?, next_execution=?, 
                            user_id=?, chat_id=?, user_mention_md=? WHERE reminder_id=?''',
                          (rem.task, rem.frequency, rem.delay, rem.date_modifier,
                           rem.next_execution.isoformat() if rem.next_execution else None,
                           rem.user_id, rem.chat_id, rem.user_mention_md, rem.reminder_id))
            else:
                c.execute('''INSERT INTO reminders (task, frequency, delay, date_modifier, next_execution, 
                             user_id, chat_id, user_mention_md) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (rem.task, rem.frequency, rem.delay, rem.date_modifier,
                           rem.next_execution.isoformat() if rem.next_execution else None,
                           rem.user_id, rem.chat_id, rem.user_mention_md))
                rem.reminder_id = c.lastrowid
            conn.commit()
        self.reminders = self.load_reminders()
        return rem

    def remove_reminder(self, reminder):
        """Remove a reminder from the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM reminders WHERE reminder_id = ?', (reminder.reminder_id,))
            self.conn.commit()
            # Update the in-memory list
            self.reminders = [r for r in self.reminders if r.reminder_id != reminder.reminder_id]
        except Exception as e:
            error_logger.error(f"Error removing reminder {reminder.reminder_id}: {e}", exc_info=True)
            raise

    # Add an alias for backward compatibility if needed
    delete_reminder = remove_reminder

    def parse_reminder(self, text):
        """Parse a reminder text and extract components using timefhuman"""
        # Remove command prefix if present
        text = re.sub(r'^/remind\s+to\s+', '', text, flags=re.IGNORECASE).strip()
        
        # Initialize result
        result = {
            'task': text,  # Default to full text, will be refined later
            'frequency': None,
            'delay': None,
            'date_modifier': None,
            'parsed_datetime': None
        }
        
        # First try to parse with timefhuman
        try:
            parsed_datetimes = timefhuman(text)
            if parsed_datetimes and isinstance(parsed_datetimes, list):
                result['parsed_datetime'] = KYIV_TZ.localize(parsed_datetimes[0]) if parsed_datetimes[0].tzinfo is None else parsed_datetimes[0]
                general_logger.debug(f"timefhuman parsed datetime: {result['parsed_datetime']}")
        except Exception as e:
            general_logger.debug(f"Initial timefhuman parsing failed: {e}")
        
        # Extract frequency
        freq_match = re.search(self.FREQUENCY_PATTERN, text, re.IGNORECASE)
        if freq_match:
            # Either group 1 or group 2 will contain the frequency
            freq = freq_match.group(1) or freq_match.group(2)
            if freq:
                if freq.lower() in ['day', 'daily']:
                    result['frequency'] = 'daily'
                elif freq.lower() in ['week', 'weekly']:
                    result['frequency'] = 'weekly'
                elif freq.lower() in ['month', 'monthly']:
                    result['frequency'] = 'monthly'
                elif freq.lower() in ['year', 'yearly']:
                    result['frequency'] = 'yearly'
        
        # Extract date modifiers
        modifier_match = re.search(self.DATE_MODIFIER_PATTERN, text, re.IGNORECASE)
        if modifier_match:
            modifier_text = modifier_match.group(0).lower()
            if 'first' in modifier_text or '1st' in modifier_text:
                result['date_modifier'] = 'first day of every month'
            elif 'last' in modifier_text:
                result['date_modifier'] = 'last day of every month'
        
        # Extract time directly for specific cases
        time_match = re.search(self.TIME_PATTERN, text, re.IGNORECASE)
        if time_match:
            if time_match.group(4) and time_match.group(5):  # Relative time (e.g., "in 5 minutes")
                value = time_match.group(4)
                unit = time_match.group(5).lower()
                # Normalize unit for parsing
                if unit.startswith(('sec', 's')) and not unit.startswith(('min', 'm', 'month')):
                    unit = 'seconds'
                elif unit.startswith(('min', 'm')) and not unit.startswith('month'):
                    unit = 'minutes'
                elif unit.startswith(('hr', 'h')):
                    unit = 'hours'
                elif unit.startswith('day'):
                    unit = 'days'
                elif unit.startswith(('week', 'wk')):
                    unit = 'weeks'
                elif unit.startswith('month'):
                    unit = 'months'
                elif unit.startswith('year'):
                    unit = 'years'
                
                # For relative time, always use manual calculation to ensure accuracy
                now = datetime.now(KYIV_TZ)
                value = int(time_match.group(4))
                if 'second' in unit or 'sec' in unit:
                    result['parsed_datetime'] = now + timedelta(seconds=value)
                elif 'minute' in unit or 'min' in unit:
                    result['parsed_datetime'] = now + timedelta(minutes=value)
                elif 'hour' in unit or 'hr' in unit:
                    result['parsed_datetime'] = now + timedelta(hours=value)
                elif 'day' in unit:
                    result['parsed_datetime'] = now + timedelta(days=value)
                elif 'week' in unit or 'wk' in unit:
                    result['parsed_datetime'] = now + timedelta(weeks=value)
                elif 'month' in unit:
                    result['parsed_datetime'] = now + relativedelta(months=value)
                elif 'year' in unit:
                    result['parsed_datetime'] = now + relativedelta(years=value)
            else:  # Absolute time (e.g., "at 8PM")
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                ampm = time_match.group(3)
                
                # Convert to 24-hour format
                if ampm:
                    if ampm.lower() == 'pm' and hour < 12:
                        hour += 12
                    elif ampm.lower() == 'am' and hour == 12:
                        hour = 0
                
                now = datetime.now(KYIV_TZ)
                result['parsed_datetime'] = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If the time is in the past, move to next day
                if result['parsed_datetime'] <= now:
                    result['parsed_datetime'] += timedelta(days=1)
        
        # Handle date modifiers with specific time
        if result['date_modifier']:
            now = datetime.now(KYIV_TZ)
            if result['date_modifier'] == 'first day of every month':
                if now.month == 12:
                    result['parsed_datetime'] = datetime(now.year + 1, 1, 1, 9, 0, tzinfo=KYIV_TZ)
                else:
                    result['parsed_datetime'] = datetime(now.year, now.month + 1, 1, 9, 0, tzinfo=KYIV_TZ)
            elif result['date_modifier'] == 'last day of every month':
                if now.month == 12:
                    end = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                else:
                    end = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                result['parsed_datetime'] = end.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Refine the task by removing time expressions
        task = text
        if time_match:
            task = text[:time_match.start()] + text[time_match.end():]
        if freq_match:
            task = re.sub(r'\s*every\s+\w+\s*', ' ', task)
        if modifier_match:
            task = re.sub(r'\s*(first|last)\s+day\s+of\s+every\s+month\s*', ' ', task)
            task = re.sub(r'\s*on\s+the\s+1st\s*', ' ', task)
        
        # Clean up the task
        task = re.sub(r'\s+', ' ', task).strip()
        result['task'] = task
        
        general_logger.debug(f"Final parse result: {result}")
        return result

    async def remind(self, update: Update, context: CallbackContext):
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "📝 *Reminder Bot Help*\n\n"
                "🔹 *Commands:*\n"
                "`/remind to <text> \\.\\.\\.` \\- Create a new reminder\n"
                "`/remind list` \\- Show all active reminders\n"
                "`/remind delete <id>` \\- Delete a specific reminder\n"
                "`/remind delete all` \\- Delete all reminders\n"
                "`/remind edit <id> <new text>` \\- Edit an existing reminder\n\n"
                "🔹 *Examples:*\n"
                "• `/remind to pay rent every month on the 1st at 9AM`\n"
                "• `/remind to call mom in 2 hours`\n"
                "• `/remind to water plants every day at 8PM`\n"
                "• `/remind to submit report on the last day of every month`\n\n"
                "🔹 *Supported time formats:*\n"
                "• `in X minutes/hours/days/weeks/months`\n"
                "• `at HH\\:MM` or `at HH AM/PM`\n"
                "• `every day/week/month`\n"
                "• `first/last day of every month`\n"
                "• `tomorrow at HH\\:MM`\n"
                "• `on Monday` or `on July 15`",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return

        command = args[0].lower()
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if command == "to":
            reminder_text = " ".join(args[1:])
            parsed = self.parse_reminder(reminder_text)
            
            if not parsed.get('parsed_datetime'):
                general_logger.debug(f"No datetime parsed from: {reminder_text}")
                # Default to 5 minutes from now if no time was parsed
                parsed['parsed_datetime'] = datetime.now(KYIV_TZ) + timedelta(minutes=5)
            
            now = datetime.now(KYIV_TZ)
            next_exec = parsed['parsed_datetime']
            
            # Ensure the time is in the future
            is_one_time = not parsed['frequency'] and not parsed['date_modifier']
            if is_one_time and next_exec <= now:
                next_exec = now + timedelta(minutes=5)
            
            # Create and save the reminder
            rem = Reminder(
                parsed['task'], 
                parsed['frequency'], 
                parsed['delay'],
                parsed['date_modifier'], 
                next_exec, 
                user_id, 
                chat_id,
                update.effective_user.mention_markdown_v2()
            )
            
            rem = self.save_reminder(rem)
            
            # Schedule the reminder
            delay_sec = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay_sec, data=rem, name=f"reminder_{rem.reminder_id}")
            
            # Format date for user display
            kyiv_time = next_exec.astimezone(KYIV_TZ)
            await update.message.reply_text(f"✅ Reminder set for {kyiv_time.strftime('%d.%m.%Y %H:%M')}.")

        elif command == "list":
            rems = [r for r in self.load_reminders() if r.chat_id == chat_id]
            if not rems:
                await update.message.reply_text("No active reminders.")
                return
            now = datetime.now(KYIV_TZ)
            reminder_list = []
            for r in rems:
                if r.next_execution:
                    kyiv_time = r.next_execution.astimezone(KYIV_TZ)
                    due = kyiv_time.strftime('%d.%m.%Y %H:%M')
                else:
                    due = 'None'
                kind = r.frequency or 'one-time'
                status = 'past' if r.next_execution and r.next_execution < now else ''
                reminder_list.append(f"ID:{r.reminder_id} | {due} | {kind} {status}\n{r.task}")
            
            await update.message.reply_text("\n\n".join(reminder_list))

        elif command == "delete":
            if len(args) < 2:
                await update.message.reply_text("Usage /remind delete <id> or all")
                return
            what = args[1].lower()
            if what == 'all':
                # Check if it's a private chat or if user is admin
                is_private = update.effective_chat.type == 'private'
                if not is_private:
                    chat_member = await context.bot.get_chat_member(chat_id, user_id)
                    if chat_member.status not in ['creator', 'administrator']:
                        await update.message.reply_text("❌ Only admins can delete all reminders.")
                        return
                
                # Store the action in context for the callback
                context.user_data['pending_delete_all'] = True
                
                # Send confirmation message with buttons
                from modules.keyboards import create_confirmation_keyboard
                keyboard = create_confirmation_keyboard('delete_all')
                await update.message.reply_text(
                    "⚠️ Are you sure you want to delete ALL reminders in this chat?",
                    reply_markup=keyboard
                )
                return
            else:
                try:
                    rid = int(what)
                    rem = next((r for r in self.reminders if r.reminder_id == rid and r.chat_id == chat_id), None)
                    if rem:
                        self.delete_reminder(rem)
                        await update.message.reply_text(f"Deleted reminder {rid}")
                    else:
                        await update.message.reply_text("Invalid ID.")
                except:
                    await update.message.reply_text("Invalid ID.")

        elif command == "edit":
            if len(args) < 3:
                await update.message.reply_text("Usage: /remind edit <id> <new text>")
                return
            try:
                rid = int(args[1])
            except:
                await update.message.reply_text("Invalid ID.")
                return
                
            rem = next((r for r in self.load_reminders() if r.reminder_id==rid and r.chat_id==chat_id), None)
            if not rem:
                await update.message.reply_text("Reminder not found.")
                return

            new_txt = " ".join(args[2:])
            parsed = self.parse_reminder(new_txt)
            
            if not parsed.get('parsed_datetime'):
                parsed['parsed_datetime'] = datetime.now(KYIV_TZ) + timedelta(minutes=5)
            
            now = datetime.now(KYIV_TZ)
            next_exec = parsed['parsed_datetime']
            
            # Ensure the time is in the future
            is_one_time = not parsed['frequency'] and not parsed['date_modifier']
            if is_one_time and next_exec <= now:
                next_exec = now + timedelta(minutes=5)
            
            # Update the reminder
            rem.task = parsed['task']
            rem.frequency = parsed['frequency']
            rem.delay = parsed['delay']
            rem.date_modifier = parsed['date_modifier']
            rem.next_execution = next_exec
            
            self.save_reminder(rem)

            # Reschedule
            jobs = context.job_queue.get_jobs_by_name(f"reminder_{rem.reminder_id}")
            for j in jobs:
                j.schedule_removal()
            delay = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{rem.reminder_id}")

            # Format date for user display
            kyiv_time = next_exec.astimezone(KYIV_TZ)
            await update.message.reply_text(f"Reminder updated. Next execution: {kyiv_time.strftime('%d.%m.%Y %H:%M')}.")

        else:
            await update.message.reply_text("Unknown /remind command.")

    async def send_reminder(self, context: CallbackContext):
        rem = context.job.data

        escaped_task = escape_markdown(rem.task, version=2)
        is_group = rem.chat_id < 0
        is_one_time = not rem.frequency
        if is_group and is_one_time and rem.user_mention_md:
            msg = f"{rem.user_mention_md}: {escaped_task}"
        else:
            msg = f"⏰ REMINDER: {escaped_task}"
        try:
            await context.bot.send_message(rem.chat_id, msg, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            error_logger.error(f"Sending reminder failed: {e}")

        # Handle recurring reschedule or delete
        rem.calculate_next_execution()
        if rem.frequency or rem.date_modifier:
            self.save_reminder(rem)
            delay = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{rem.reminder_id}")
        else:
            self.delete_reminder(rem)

    def schedule_startup(self, job_queue):
        now = datetime.now(KYIV_TZ)
        for rem in self.load_reminders():
            if rem.next_execution and rem.next_execution > now:
                delay = seconds_until(rem.next_execution)
                job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{rem.reminder_id}")

    async def button_callback(self, update: Update, context: CallbackContext):
        """Handle button callbacks for reminder actions."""
        query = update.callback_query
        await query.answer()
        
        try:
            data = query.data or ''
            if ':' not in data:
                await query.message.edit_text("Invalid callback data.")
                return
                
            action, _ = data.split(':', 1)
            
            if action == 'confirm_delete_all':
                # Check if it's a private chat or if user is admin
                is_private = update.effective_chat.type == 'private'
                if not is_private:
                    chat_member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
                    if chat_member.status not in ['creator', 'administrator']:
                        await query.message.edit_text("❌ Only admins can delete all reminders.")
                        return
                
                # Delete all reminders
                reminders = self.load_reminders(update.effective_chat.id)
                for reminder in reminders:
                    self.delete_reminder(reminder)
                    # Remove any scheduled jobs for this reminder
                    jobs = context.job_queue.get_jobs_by_name(f"reminder_{reminder.reminder_id}")
                    for job in jobs:
                        job.schedule_removal()
                
                await query.message.edit_text("✅ All reminders have been deleted.")
                
            elif action == 'cancel_delete_all':
                await query.message.edit_text("❌ Deletion cancelled.")
                
        except Exception as e:
            error_logger.error(f"Error in button callback: {e}", exc_info=True)
            await query.message.edit_text("❌ An error occurred while processing your request.")