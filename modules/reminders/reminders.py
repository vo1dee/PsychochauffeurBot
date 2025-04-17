import sqlite3
import datetime
import re
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from modules.const import KYIV_TZ
from modules.logger import error_logger, general_logger
from timefhuman import timefhuman
import logging

from telegram import Update
from telegram.ext import CallbackContext

def seconds_until(dt):
    now = datetime.datetime.now(KYIV_TZ)
    # Ensure dt is timezone-aware and in the same timezone as now
    if dt.tzinfo is None:
        dt = KYIV_TZ.localize(dt)
    else:
        dt = dt.astimezone(KYIV_TZ)
    general_logger.debug(f"seconds_until: now={now}, dt={dt}")
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
        now = datetime.datetime.now(KYIV_TZ)

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
            if self.next_execution and self.next_execution <= now:
                # For daily reminders, create a new datetime with the same time but 1 day later
                if self.next_execution.tzinfo is None:
                    self.next_execution = KYIV_TZ.localize(self.next_execution)
                self.next_execution = datetime.datetime(
                    self.next_execution.year,
                    self.next_execution.month,
                    self.next_execution.day + 1,
                    self.next_execution.hour,
                    self.next_execution.minute,
                    self.next_execution.second,
                    tzinfo=self.next_execution.tzinfo
                )
            elif not self.next_execution:
                # Create a new datetime with the same time but 1 day later
                if now.tzinfo is None:
                    now = KYIV_TZ.localize(now)
                self.next_execution = datetime.datetime(
                    now.year,
                    now.month,
                    now.day + 1,
                    now.hour,
                    now.minute,
                    now.second,
                    tzinfo=now.tzinfo
                )

        elif self.frequency == 'weekly':
            if self.next_execution and self.next_execution <= now:
                # For weekly reminders, create a new datetime with the same time but 7 days later
                if self.next_execution.tzinfo is None:
                    self.next_execution = KYIV_TZ.localize(self.next_execution)
                self.next_execution = datetime.datetime(
                    self.next_execution.year,
                    self.next_execution.month,
                    self.next_execution.day + 7,
                    self.next_execution.hour,
                    self.next_execution.minute,
                    self.next_execution.second,
                    tzinfo=self.next_execution.tzinfo
                )
            elif not self.next_execution:
                # Create a new datetime with the same time but 7 days later
                if now.tzinfo is None:
                    now = KYIV_TZ.localize(now)
                self.next_execution = datetime.datetime(
                    now.year,
                    now.month,
                    now.day + 7,
                    now.hour,
                    now.minute,
                    now.second,
                    tzinfo=now.tzinfo
                )

        elif self.frequency == 'monthly':
            if self.next_execution and self.next_execution <= now:
                self.next_execution += relativedelta(months=1)
            elif not self.next_execution:
                self.next_execution = now + relativedelta(months=1)

        elif self.frequency == 'seconds':
            self.next_execution = now + datetime.timedelta(seconds=5)
        elif self.frequency == 'yearly':
            # For yearly reminders, advance by one year
            if self.next_execution and self.next_execution <= now:
                self.next_execution += relativedelta(years=1)
            elif not self.next_execution:
                self.next_execution = now + relativedelta(years=1)

    def _calc_first_month(self, now):
        if now.month == 12:
            dt = datetime.datetime(now.year + 1, 1, 1, 9, 0, tzinfo=KYIV_TZ)
        else:
            dt = datetime.datetime(now.year, now.month + 1, 1, 9, 0, tzinfo=KYIV_TZ)
        if self.next_execution:
            dt = dt.replace(hour=self.next_execution.hour, minute=self.next_execution.minute)
        self.next_execution = dt

    def _calc_last_month(self, now):
        # Calculate last day of the NEXT month
        if now.month == 12:
            end = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
        else:
            end = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
            
        # For testing: when calculating next execution, move to the next month
        if self.next_execution and self.next_execution.month == now.month:
            if now.month == 12:
                end = datetime.datetime(now.year + 1, 2, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
            else:
                end = datetime.datetime(now.year, now.month + 2, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                
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
        if dt:
            # Ensure dt is timezone-aware
            if dt.tzinfo is None:
                dt = KYIV_TZ.localize(dt)
            else:
                # If it's already timezone-aware, convert it to KYIV_TZ
                dt = dt.astimezone(KYIV_TZ)
            general_logger.debug(f"Loaded reminder with next_execution: {dt}")
        return cls(task, freq, delay, mod, dt, uid, cid, mention, rid)


class ReminderManager:
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self._create_table()
        self.reminders = self.load_reminders()

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
                # Convert to KYIV_TZ timezone
                rem.next_execution = rem.next_execution.astimezone(KYIV_TZ)
                general_logger.debug(f"Saving reminder with next_execution: {rem.next_execution}")
                
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

    def extract_task_and_time(self, text):
        """
        Process the reminder text to separate time-related expressions from the actual task.
        Return both the clean task text and the extracted time text.
        """
        # Look for the last occurrence of time-related patterns
        delay_pattern = re.search(r'(.*?)\s+in\s+\d+\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|months?|month)\s*$', text, re.IGNORECASE)
        
        if delay_pattern:
            # Take everything before the last "in X units" as the task
            task = delay_pattern.group(1).strip()
            time_expr = text[len(task):].strip()
            logging.debug(f"Delay pattern found - Task: '{task}', Time: '{time_expr}'")
            return task, time_expr

        # Special case for first/last day of month patterns
        first_day_pattern = re.search(r'(.*?)(?:at the first|on the first|on first|first of|first day of|at the first day of)(?:.*)', text, re.IGNORECASE)
        if first_day_pattern and first_day_pattern.group(1).strip():
            task = first_day_pattern.group(1).strip()
            time_expr = text[len(task):].strip()
            return task, time_expr
            
        last_day_pattern = re.search(r'(.*?)(?:at the last|on the last|on last|last day of|at the last day of)(?:.*)', text, re.IGNORECASE)
        if last_day_pattern and last_day_pattern.group(1).strip():
            task = last_day_pattern.group(1).strip()
            time_expr = text[len(task):].strip()
            return task, time_expr
            
        # Special case for "tomorrow" patterns
        tomorrow_pattern = re.search(r'(.*?)\btomorrow\b(?:.*)', text, re.IGNORECASE)
        if tomorrow_pattern and tomorrow_pattern.group(1).strip():
            task = tomorrow_pattern.group(1).strip()
            time_expr = text[len(task):].strip()
            return task, time_expr
        
        # Time-related patterns - use regex with word boundaries to avoid partial matches
        time_patterns = [
            r'\bevery day\b', r'\bdaily\b', r'\beveryday\b',
            r'\bevery week\b', r'\bweekly\b',
            r'\bevery month\b', r'\bmonthly\b',
            r'\bevery year\b', r'\byearly\b',
            r'\bevery year\b', r'\byearly\b',
            r'\bevery second\b',
            r'\bin \d+ (seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|months?|month)\b',
            r'\bat \d{1,2}:\d{2}\b',
            r'\bat \d{1,2}\s*(am|pm)\b',  # at 11 PM
            # support month/day dates e.g. at Sep 27
            r'\b(?:at|on) [A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?\b',
            r'\btomorrow at\b', r'\btomorrow\b', r'\bnext week\b', r'\bnext month\b',
            r'\bon [a-zA-Z]+ \d+\b', r'\bon [a-zA-Z]+\b',  # On Monday, On July 15
            r'\bthe (first|last) day of (the|every) month\b',
            r'\b(first|last) day of (the|every) month\b',
        ]
        
        # Try to find the task and time by looking for time patterns
        task = text
        time_expr = ""
        
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = match.start()
                # If we find a time pattern, assume everything before it is the task
                potential_task = text[:start].strip()
                if potential_task:
                    task = potential_task
                time_expr = text[start:].strip()
                break
        
        return task, time_expr

    def parse(self, text):
        """Parse reminder text using timefhuman for date/time extraction"""
        # Extract task and time expression
        task, time_expr = self.extract_task_and_time(text)
        r = {'task': task, 'frequency': None, 'date_modifier': None, 'time': None, 'delay': None}
        
        # Extract frequency patterns
        txt_lower = text.lower()
        
        # Log the input for debugging
        logging.debug(f"Parsing reminder: '{text}'")
        logging.debug(f"Extracted task: '{task}', time expression: '{time_expr}'")
        
        # Extract frequency patterns
        if any(pattern in txt_lower for pattern in ["every day", "daily", "everyday"]):
            r['frequency'] = 'daily'
        elif any(pattern in txt_lower for pattern in ["every week", "weekly"]):
            r['frequency'] = 'weekly'
        elif any(pattern in txt_lower for pattern in ["every month", "monthly"]):
            r['frequency'] = 'monthly'
        elif "every second" in txt_lower:
            r['frequency'] = 'seconds'
        elif any(pattern in txt_lower for pattern in ["every year", "yearly"]):
            r['frequency'] = 'yearly'
            
        # Extract special date modifiers
        if any(pattern in txt_lower for pattern in ['last day of every month', 'last day of month', 'the last day of the month']):
            r['date_modifier'] = 'last day of every month'
            r['frequency'] = 'monthly'
        elif any(pattern in txt_lower for pattern in ['first day of every month', 'first of every month', 'the first day of the month']):
            r['date_modifier'] = 'first day of every month' 
            r['frequency'] = 'monthly'
            
        # Extract delay information (in X minutes/hours/days/weeks/months)
        delay_match = re.search(r"in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|months?|month)", txt_lower)
        if delay_match:
            amt = int(delay_match.group(1))
            unit = delay_match.group(2).strip()
            
            # Determine the normalized unit
            if unit in ['s', 'sec', 'secs', 'second', 'seconds']:
                norm = 'second'
            elif unit in ['m', 'min', 'mins', 'minute', 'minutes']:
                norm = 'minute'
            elif unit in ['h', 'hr', 'hrs', 'hour', 'hours']:
                norm = 'hour'
            elif unit in ['d', 'day', 'days']:
                norm = 'day'
            elif unit in ['w', 'week', 'weeks']:
                norm = 'week'
            elif unit in ['month', 'months']:
                norm = 'month'
            else:
                norm = unit  # Fallback
            # Always use plural for the unit in the delay string
            if norm == 'second': norm_display = 'seconds'
            elif norm == 'minute': norm_display = 'minutes'
            elif norm == 'hour': norm_display = 'hours'
            elif norm == 'day': norm_display = 'days'
            elif norm == 'week': norm_display = 'weeks'
            elif norm == 'month': norm_display = 'months'
            else: norm_display = norm + 's'  # Fallback
            r['delay'] = f"in {amt} {norm_display}"
            logging.debug(f"Extracted delay: {r['delay']}")
            
        # Extract time information using timefhuman if there's a time expression
        parsed_time = None
        # Clean up the time expression: remove frequency words and leading "at"/"on"
        if time_expr:
            # Strip frequency tokens from start of time_expr
            if r['frequency']:
                freq = r['frequency']
                freq_patterns = {
                    'daily': r'^(every\s+day|daily|everyday)',
                    'weekly': r'^(every\s+week|weekly)',
                    'monthly': r'^(every\s+month|monthly)',
                    'yearly': r'^(every\s+year|yearly)',
                    'seconds': r'^(every\s+second)'
                }
                pat = freq_patterns.get(freq)
                if pat:
                    time_expr = re.sub(pat, '', time_expr, flags=re.IGNORECASE).strip()
            # Strip leading "at" or "on"
            time_expr = re.sub(r'^(?:at|on)\s+', '', time_expr, flags=re.IGNORECASE).strip()
            # If time_expr is a bare HH:MM, extract it directly
            m_bare = re.match(r'^(\d{1,2}):(\d{2})$', time_expr)
            if m_bare:
                r['time'] = (int(m_bare.group(1)), int(m_bare.group(2)))
            try:
                # Try parsing with timefhuman
                parsed_time_result = timefhuman(time_expr)
                logging.debug(f"timefhuman parsed result: {parsed_time_result}")
                
                # Handle case where timefhuman returns a list
                if isinstance(parsed_time_result, list) and parsed_time_result:
                    parsed_time = parsed_time_result[0]  # Take the first result
                else:
                    parsed_time = parsed_time_result
                
                # If we got a valid time object, extract hour/minute for 'time' key
                if parsed_time:
                    # Add handling for "morning" specifically
                    if 'morning' in time_expr.lower():
                        # Override the time to 9 AM if it was early morning (before 8 AM)
                        if parsed_time.hour < 8:
                            parsed_time = parsed_time.replace(hour=9, minute=0)
                            r['time'] = (9, 0)  # Also update the time tuple
                            logging.debug(f"Adjusted 'morning' time to 9 AM: {parsed_time}")
                    
                    # --- Extract H:M from original expression BEFORE conversion ---
                    original_hour_minute = None
                    time_match_hm = re.search(r'\bat\s+(\d{1,2}):(\d{2})\b', time_expr, re.IGNORECASE)
                    time_match_ampm = re.search(r'\bat\s+(\d{1,2})\s*(am|pm)\b', time_expr, re.IGNORECASE)
                    if time_match_hm:
                        original_hour_minute = (int(time_match_hm.group(1)), int(time_match_hm.group(2)))
                    elif time_match_ampm:
                        hour = int(time_match_ampm.group(1))
                        am_pm = time_match_ampm.group(2).lower()
                        if am_pm == 'pm' and hour < 12: hour += 12
                        if am_pm == 'am' and hour == 12: hour = 0
                        original_hour_minute = (hour, 0)
                        
                    if original_hour_minute:
                        r['time'] = original_hour_minute # Store the originally specified H:M
                        logging.debug(f"Extracted time tuple (from input): {r['time']}")
                    # --- End H:M extraction ---

                    # Now perform the timezone conversion for the full datetime object
                    if parsed_time.tzinfo is None:
                        # ASSUMPTION REVISED: Naive datetime from timefhuman likely represents the intended LOCAL time.
                        # Localize directly to KYIV_TZ.
                        logging.debug(f"timefhuman returned naive: {parsed_time}. Assuming KYIV_TZ wall time.")
                        parsed_time = KYIV_TZ.localize(parsed_time)
                    else:
                        # If timefhuman returned an *aware* object (e.g., maybe it returns UTC for absolute dates?),
                        # convert it to KYIV_TZ.
                        logging.debug(f"timefhuman returned aware: {parsed_time}. Converting to KYIV.")
                        parsed_time = parsed_time.astimezone(KYIV_TZ)

                    logging.debug(f"Timezone-adjusted parsed time (should be KYIV): {parsed_time}")
                    r['parsed_datetime'] = parsed_time



                    # Keep the logic for extracting 'time' tuple if needed, operating on the now-correct parsed_time
                    if 'at' in time_expr.lower() or any(t in time_expr.lower() for t in ['tomorrow', 'next', 'on']):
                        r['time'] = (parsed_time.hour, parsed_time.minute)
                        logging.debug(f"Extracted time: {r['time']}")
                        
                    # For future time calculations, we'll use the full datetime
                    r['parsed_datetime'] = parsed_time
                    logging.debug(f"Parsed datetime: {r['parsed_datetime']}")
            except Exception as e:
                logging.debug(f"timefhuman parsing failed: {str(e)}")
                # Fallback to regex parsing for specific time formats 
                time_match = re.search(r'at\s+(\d{1,2}):(\d{2})', time_expr.lower())
                if time_match:
                    r['time'] = (int(time_match.group(1)), int(time_match.group(2)))
                    logging.debug(f"Regex extracted time: {r['time']}")
                else:
                    # Try to match "at XX PM/AM" format
                    am_pm_match = re.search(r'at\s+(\d{1,2})(?:\s*|\:00)?\s*(am|pm)', time_expr.lower())
                    if am_pm_match:
                        hour = int(am_pm_match.group(1))
                        if am_pm_match.group(2) == 'pm' and hour < 12:
                            hour += 12
                        elif am_pm_match.group(2) == 'am' and hour == 12:
                            hour = 0
                        r['time'] = (hour, 0)
                        logging.debug(f"AM/PM regex extracted time: {r['time']}")
            
        return r

    async def remind(self, update: Update, context: CallbackContext):
        args = context.args or []
        if not args:
            await update.message.reply_text("/remind to <text> ... | list | delete ID/all | edit ID <text>")
            return

        command = args[0].lower()
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if command == "to":
            reminder_text = " ".join(args[1:])
            parsed = self.parse(reminder_text)
            # derive next_execution
            now = datetime.datetime.now(KYIV_TZ)
            next_exec = None

            # Use parsed datetime from timefhuman if available
            if 'parsed_datetime' in parsed and parsed['parsed_datetime']:
                next_exec = parsed['parsed_datetime']
                logging.debug(f"Using parsed_datetime: {next_exec}")
                # Make sure it's in the future
                if next_exec <= now:
                    # If it's a time-of-day without specific date, move to tomorrow
                    if 'time' in parsed and parsed['time']:
                        # Create a new datetime object with the same time but 1 day later
                        next_exec = datetime.datetime(
                            next_exec.year,
                            next_exec.month,
                            next_exec.day + 1,
                            next_exec.hour,
                            next_exec.minute,
                            next_exec.second,
                            tzinfo=next_exec.tzinfo
                        )
                        logging.debug(f"Adjusted to tomorrow: {next_exec}")
                    else:
                        next_exec = now + datetime.timedelta(minutes=5)
                        logging.debug(f"Adjusted to 5 minutes from now: {next_exec}")
            
            # If no parsed datetime, handle delay patterns
            if not next_exec and parsed.get('delay'):
                logging.debug(f"Processing delay: {parsed['delay']}")
                m = re.match(r'in\s+(\d+)\s+(\w+)', parsed['delay'])
                if m:
                    n, unit = int(m.group(1)), m.group(2)
                    logging.debug(f"Delay components: {n} {unit}")
                    
                    # Normalize the unit to handle variations
                    unit_normalized = unit.rstrip('s')  # Remove trailing 's' to handle plural forms
                    
                    # Special case for "month" to ensure it's not confused with "minute"
                    if unit.strip() == 'month' or unit.strip() == 'months':
                        unit_normalized = 'month'
                    
                    # Ensure now is timezone-aware
                    if now.tzinfo is None:
                        now = KYIV_TZ.localize(now)
                    
                    if unit_normalized == 'second' or unit_normalized in ['sec', 's']:
                        next_exec = now + datetime.timedelta(seconds=n)
                    elif unit_normalized == 'minute' or unit_normalized in ['min', 'm']:
                        next_exec = now + datetime.timedelta(minutes=n)
                    elif unit_normalized == 'hour' or unit_normalized in ['hr', 'h']:
                        next_exec = now + datetime.timedelta(hours=n)
                    elif unit_normalized == 'day' or unit_normalized == 'd':
                        # Ensure now has timezone info
                        general_logger.debug(f"Adding {n} days to now: {now}")
                        if now.tzinfo is None:
                            now = KYIV_TZ.localize(now)
                        # Use timedelta to add days to the timezone-aware datetime
                        next_exec = now + datetime.timedelta(days=n)
                        general_logger.debug(f"Result after adding {n} days: {next_exec}")

                    elif unit_normalized == 'week' or unit_normalized == 'w':
                        # Ensure now has timezone info
                        if now.tzinfo is None:
                            now = KYIV_TZ.localize(now)
                        # Use timedelta to add weeks to the timezone-aware datetime
                        next_exec = now + datetime.timedelta(weeks=n)
                    elif unit_normalized == 'month':
                        # Ensure now has timezone info
                        if now.tzinfo is None:
                            now = KYIV_TZ.localize(now)
                        # Use relativedelta to add months to the timezone-aware datetime
                        next_exec = now + relativedelta(months=+n)
                    
                    # Ensure the result is timezone-aware
                    if next_exec.tzinfo is None:
                        next_exec = KYIV_TZ.localize(next_exec)
                    
                    logging.debug(f"Calculated next_exec from delay: {next_exec}")

            # Handle special date modifiers
            if not next_exec and parsed.get('date_modifier'):
                logging.debug(f"Processing date_modifier: {parsed['date_modifier']}")
                if parsed['date_modifier'] == 'last day of every month':
                    # Calculate the last day of the current month
                    if now.month == 12:
                        last_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                        time_tuple = parsed.get('time')
                        hour, minute = time_tuple if time_tuple is not None else (9, 0)
                        next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    else:
                        last_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                        time_tuple = parsed.get('time')
                        hour, minute = time_tuple if time_tuple is not None else (9, 0)
                        next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                elif parsed['date_modifier'] == 'first day of every month':
                    # Calculate first day of next month
                    if now.month == 12:
                        first_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                    else:
                        first_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                    
                    # Use the specified time or default to 9 AM
                    time_tuple = parsed.get('time')
                    hour, minute = time_tuple if time_tuple is not None else (9, 0)
                    next_exec = first_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    logging.debug(f"Calculated first day of month: {next_exec}")

            # If still no next_exec but we have time, use that for today or tomorrow
            if not next_exec and parsed.get('time'):
                h, mnt = parsed['time']
                logging.debug(f"Using time component: {h}:{mnt}")
                tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
                if tmp <= now:
                    # Create a new datetime object with the same time but 1 day later
                    tmp = datetime.datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                    logging.debug(f"Time is in the past, adjusted to tomorrow: {tmp}")
                next_exec = tmp

            # If parser couldn't determine a schedule, report error and exit
            if not next_exec:
                error_logger.error(f"Failed to parse reminder command: '{reminder_text}'")
                await update.message.reply_text(
                    f"Sorry, I couldn't understand your reminder: '{reminder_text}'.\n"
                    "Example: /remind to pay rent every month on the 1st at 9AM"
                )
                return

            is_one_time = not parsed['frequency'] and not parsed['date_modifier']
            if is_one_time and next_exec <= now:
                next_exec = now + datetime.timedelta(minutes=5)

            rem = Reminder(parsed['task'], parsed['frequency'], parsed['delay'],
                           parsed['date_modifier'], next_exec, user_id, chat_id,
                           update.effective_user.mention_markdown_v2())
            rem = self.save_reminder(rem)

            delay_sec = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay_sec, data=rem, name=f"reminder_{rem.reminder_id}")

            # Ensure the displayed time is in the KYIV_TZ timezone
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
            kyiv_time = next_exec.astimezone(KYIV_TZ)
            await update.message.reply_text(f"✅ Reminder set for {kyiv_time.strftime('%d.%m.%Y %H:%M')}.")

        elif command == "list":
            rems = [r for r in self.load_reminders() if r.chat_id == chat_id]
            if not rems:
                await update.message.reply_text("No active reminders.")
                return
            s = ''
            now = datetime.datetime.now(KYIV_TZ)
            for r in rems:
                # Ensure the displayed time is in the KYIV_TZ timezone
                if r.next_execution:
                    if r.next_execution.tzinfo is None:
                        next_exec = KYIV_TZ.localize(r.next_execution)
                    else:
                        next_exec = r.next_execution
                    kyiv_time = next_exec.astimezone(KYIV_TZ)
                    due = kyiv_time.strftime('%d.%m.%Y %H:%M')
                else:
                    due = 'None'
                kind = r.frequency or 'one-time'
                status = 'past' if r.next_execution and r.next_execution < now else ''
                s += f"ID:{r.reminder_id} | {due} | {kind} {status}\n{r.task}\n\n"
            await update.message.reply_text(s)

        elif command == "delete":
            if len(args) < 2:
                await update.message.reply_text("Usage /remind delete <id> or all")
                return
            what = args[1].lower()
            if what == 'all':
                chat_rems = [r for r in self.reminders if r.chat_id == chat_id]
                for r in chat_rems: self.delete_reminder(r)
                await update.message.reply_text("Deleted all reminders.")
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
            parsed = self.parse(new_txt)
            now = datetime.datetime.now(KYIV_TZ)
            next_exec = None

            # Use parsed datetime from timefhuman if available
            if 'parsed_datetime' in parsed and parsed['parsed_datetime']:
                next_exec = parsed['parsed_datetime']
                logging.debug(f"Edit: Using parsed_datetime: {next_exec}")
                # Make sure it's in the future
                if next_exec <= now:
                    # If it's a time-of-day without specific date, move to tomorrow
                    if 'time' in parsed and parsed['time']:
                        # Create a new datetime object with the same time but 1 day later
                        next_exec = datetime.datetime(
                            next_exec.year,
                            next_exec.month,
                            next_exec.day + 1,
                            next_exec.hour,
                            next_exec.minute,
                            next_exec.second,
                            tzinfo=next_exec.tzinfo
                        )
                        logging.debug(f"Edit: Adjusted to tomorrow: {next_exec}")
                    else:
                        next_exec = now + datetime.timedelta(minutes=5)
                        logging.debug(f"Edit: Adjusted to 5 minutes from now: {next_exec}")
                        
            # Process delay pattern if no datetime from timefhuman
            if not next_exec and parsed.get('delay'):
                logging.debug(f"Edit: Processing delay: {parsed['delay']}")
                m = re.match(r'in\s+(\d+)\s+(\w+)', parsed['delay'])
                if m:
                    n, unit = int(m.group(1)), m.group(2)
                    logging.debug(f"Edit: Delay components: {n} {unit}")
                    
                    # Normalize the unit to handle variations
                    unit_normalized = unit.rstrip('s')  # Remove trailing 's' to handle plural forms
                    
                    # Special case for "month" to ensure it's not confused with "minute"
                    if unit.strip() == 'month' or unit.strip() == 'months':
                        unit_normalized = 'month'
                    
                    # Ensure now is timezone-aware
                    if now.tzinfo is None:
                        now = KYIV_TZ.localize(now)
                    
                    if unit_normalized == 'second' or unit_normalized in ['sec', 's']:
                        next_exec = now + datetime.timedelta(seconds=n)
                    elif unit_normalized == 'minute' or unit_normalized in ['min', 'm']:
                        next_exec = now + datetime.timedelta(minutes=n)
                    elif unit_normalized == 'hour' or unit_normalized in ['hr', 'h']:
                        next_exec = now + datetime.timedelta(hours=n)
                    elif unit_normalized == 'day' or unit_normalized == 'd':
                        # Ensure now has timezone info
                        general_logger.debug(f"Edit: Adding {n} days to now: {now}")
                        if now.tzinfo is None:
                            now = KYIV_TZ.localize(now)
                        # Use timedelta to add days to the timezone-aware datetime
                        next_exec = now + datetime.timedelta(days=n)
                        general_logger.debug(f"Edit: Result after adding {n} days: {next_exec}")
                    elif unit_normalized == 'week' or unit_normalized == 'w':
                        next_exec = now + datetime.timedelta(weeks=n)
                    elif unit_normalized == 'month':
                        next_exec = now + relativedelta(months=+n)
                    
                    # Ensure the result is timezone-aware
                    if next_exec.tzinfo is None:
                        next_exec = KYIV_TZ.localize(next_exec)
                    
                    logging.debug(f"Edit: Calculated next_exec from delay: {next_exec}")

            # Handle special date modifiers
            if not next_exec and parsed.get('date_modifier'):
                logging.debug(f"Edit: Processing date_modifier: {parsed['date_modifier']}")
                if parsed['date_modifier'] == 'last day of every month':
                    # Calculate the last day of the current month
                    if now.month == 12:
                        last_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                        time_tuple = parsed.get('time')
                        hour, minute = time_tuple if time_tuple is not None else (9, 0)
                        next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    else:
                        last_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                        time_tuple = parsed.get('time')
                        hour, minute = time_tuple if time_tuple is not None else (9, 0)
                        next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                elif parsed['date_modifier'] == 'first day of every month':
                    # Calculate the first day of the next month
                    if now.month == 12:
                        first_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                    else:
                        first_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                    
                    # Use the specified time or default to 9 AM
                    time_tuple = parsed.get('time')
                    hour, minute = time_tuple if time_tuple is not None else (9, 0)
                    next_exec = first_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    logging.debug(f"Edit: Calculated first day of month: {next_exec}")

            if not next_exec and parsed.get('time'):
                h, mnt = parsed['time']
                logging.debug(f"Edit: Using time component: {h}:{mnt}")
                tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
                if tmp <= now:
                    # Create a new datetime object with the same time but 1 day later
                    tmp = datetime.datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                    logging.debug(f"Edit: Time is in the past, adjusted to tomorrow: {tmp}")
                next_exec = tmp

            if not next_exec:
                logging.debug("Edit: No time information extracted, using default (tomorrow 9 AM)")
                tmp = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if tmp <= now:
                    # Create a new datetime object with the same time but 1 day later
                    tmp = datetime.datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                next_exec = tmp

            is_one_time = not parsed['frequency'] and not parsed['date_modifier']
            if is_one_time and next_exec <= now:
                next_exec = now + datetime.timedelta(minutes=5)

            rem.task = parsed['task']
            rem.frequency = parsed['frequency']
            rem.delay = parsed['delay']
            rem.date_modifier = parsed['date_modifier']
            rem.next_execution = next_exec
            self.save_reminder(rem)

            # reschedule
            jobs = context.job_queue.get_jobs_by_name(f"reminder_{rem.reminder_id}")
            for j in jobs:
                j.schedule_removal()
            delay = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{rem.reminder_id}")

            # Ensure the displayed time is in the KYIV_TZ timezone
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
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

        # handle recurring reschedule or delete
        rem.calculate_next_execution()
        if rem.frequency or rem.date_modifier:
            self.save_reminder(rem)
            delay = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{rem.reminder_id}")
        else:
            self.delete_reminder(rem)

    def schedule_startup(self, job_queue):
        now = datetime.datetime.now(KYIV_TZ)
        for rem in self.load_reminders():
            if rem.next_execution and rem.next_execution > now:
                delay = seconds_until(rem.next_execution)
                job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{rem.reminder_id}")
