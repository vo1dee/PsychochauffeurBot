import sqlite3
from datetime import datetime, timedelta
import re
import os
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from modules.const import KYIV_TZ
from modules.logger import error_logger, general_logger
from timefhuman import timefhuman
import logging
from dateutil.tz import tzlocal

from telegram import Update, CallbackQuery
from telegram.ext import CallbackContext
from telegram.ext._jobqueue import JobQueue
from typing import Any, Optional, List, cast
from unittest.mock import MagicMock
from modules.reminders.reminder_models import Reminder
from modules.reminders.reminder_db import ReminderDB
from modules.reminders.reminder_parser import ReminderParser


def seconds_until(dt: datetime) -> float:
    now = datetime.now(KYIV_TZ)
    # Ensure dt is timezone-aware and in the same timezone as now
    if dt.tzinfo is None:
        dt = KYIV_TZ.localize(dt)
    else:
        dt = dt.astimezone(KYIV_TZ)
    general_logger.debug(f"seconds_until: now={now}, dt={dt}")
    return max(0.01, (dt - now).total_seconds())

class ReminderManager:
    db: ReminderDB
    reminders: List[Any]
    reminders_file: str
    def __init__(self, db_file: str = 'reminders.db') -> None:
        self.db = ReminderDB(db_file)
        self.reminders = self.db.load_reminders()
        self.reminders_file = os.path.join('data', 'reminders.json')

    async def initialize(self) -> bool:
        """Initialize the reminder manager."""
        # Load existing reminders
        self.reminders = self.db.load_reminders()
        general_logger.info("Reminder manager initialized successfully")
        return True

    async def stop(self) -> bool:
        """Clean up resources when stopping the reminder manager."""
        # Close database connection
        if hasattr(self.db, 'conn'):
            self.db.conn.close()
        general_logger.info("Reminder manager stopped successfully")
        return True

    def load_reminders(self, chat_id: Optional[int] = None) -> List[Any]:
        return self.db.load_reminders(chat_id)

    def save_reminder(self, rem: Any) -> Any:
        result = self.db.save_reminder(rem)
        self.reminders = self.db.load_reminders()
        return result

    def remove_reminder(self, reminder: Any) -> None:
        self.db.remove_reminder(reminder)
        self.reminders = self.db.load_reminders()

    # Add an alias for backward compatibility if needed
    delete_reminder = remove_reminder

    async def remind(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        args = getattr(context, 'args', []) or []
        user_id = None
        if getattr(update, 'effective_user', None) is not None and update.effective_user is not None:
            user_id = update.effective_user.id
        chat_id = None
        if getattr(update, 'effective_chat', None) is not None and update.effective_chat is not None:
            chat_id = update.effective_chat.id
        chat_type = 'private' if getattr(update, 'effective_chat', None) is not None and update.effective_chat is not None and update.effective_chat.type == 'private' else 'group'
        
        if not args:
            if getattr(update, 'message', None) is not None and update.message is not None:
                await update.message.reply_text(
                    "Usage: /remind <task> [time/frequency]\n"
                    "Examples:\n"
                    "- /remind to pay rent every month on the 1st at 9AM\n"
                    "- /remind to take medicine in 2 hours\n"
                    "- /remind to call mom tomorrow at 3PM\n"
                    "- /remind to water plants every day at 8AM"
                )
            return

        command = args[0].lower() if args else None
        
        if command == "list":
            rems = [r for r in self.load_reminders() if r.chat_id == chat_id]
            if not rems:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("No active reminders.")
                return
            s = ''
            now = datetime.now(KYIV_TZ)
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
            if getattr(update, 'message', None) is not None and update.message is not None:
                await update.message.reply_text(s)
            return
            
        elif command == "to":
            # Check user's reminder limit only when creating new reminders
            user_id = None
            if getattr(update, 'effective_user', None) is not None and update.effective_user is not None:
                user_id = update.effective_user.id
            user_reminders = [r for r in self.load_reminders(chat_id) if r.user_id == user_id]
            max_reminders = 5  # Assuming a default max_reminders_per_user
            
            if len(user_reminders) >= max_reminders:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text(f"You have reached the maximum limit of {max_reminders} reminders.")
                return
                
            # Check if recurring reminders are allowed
            allow_recurring = True
            max_recurring = 3  # Assuming a default max_recurring_reminders
            
            reminder_text = " ".join(args[1:])
            parsed = ReminderParser.parse_reminder(reminder_text)
            general_logger.info(f"[REMINDER_CREATE] User input: '{reminder_text}', Parsed: {parsed}")
            # derive next_execution
            now = datetime.now(KYIV_TZ)
            next_exec = None

            # Use parsed datetime from timefhuman if available
            if 'parsed_datetime' in parsed and parsed['parsed_datetime']:
                next_exec = parsed['parsed_datetime']
                logging.debug(f"Using parsed_datetime: {next_exec}")
                # Make sure it's in the future
                if next_exec <= now:
                    # If it's a time-of-day without specific date, move to tomorrow
                    if 'time' in parsed and parsed['time']:
                        # For daily reminders, always set to tomorrow if time has passed
                        if parsed.get('frequency') == 'daily':
                            next_exec = datetime(
                                now.year,
                                now.month,
                                now.day + 1,
                                next_exec.hour,
                                next_exec.minute,
                                next_exec.second,
                                tzinfo=next_exec.tzinfo
                            )
                            logging.debug(f"Daily reminder: Adjusted to tomorrow: {next_exec}")
                        else:
                            # For other cases, add 5 minutes to ensure it's in the future
                            next_exec = now + timedelta(minutes=5)
                            logging.debug(f"Non-daily reminder: Adjusted to 5 minutes from now: {next_exec}")
                    else:
                        next_exec = now + timedelta(minutes=5)
                        logging.debug(f"No time specified: Adjusted to 5 minutes from now: {next_exec}")
            
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
                        next_exec = now + timedelta(seconds=n)
                    elif unit_normalized == 'minute' or unit_normalized in ['min', 'm']:
                        next_exec = now + timedelta(minutes=n)
                    elif unit_normalized == 'hour' or unit_normalized in ['hr', 'h']:
                        next_exec = now + timedelta(hours=n)
                    elif unit_normalized == 'day' or unit_normalized == 'd':
                        next_exec = now + timedelta(days=n)
                    elif unit_normalized == 'week' or unit_normalized == 'w':
                        next_exec = now + timedelta(weeks=n)
                    elif unit_normalized == 'month':
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
                        last_day = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                    else:
                        last_day = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                    time_tuple = parsed.get('time')
                    hour, minute = time_tuple if time_tuple is not None else (10, 0)
                    next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                elif parsed['date_modifier'] == 'first day of every month':
                    general_logger.debug("Processing 'first day of every month' modifier")
                    # Calculate first day of next month
                    if now.month == 12:
                        first_day = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                    else:
                        first_day = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                    general_logger.debug(f"Calculated first_day: {first_day}")
                    
                    # Use the parsed time
                    time_tuple = parsed.get('time')
                    if time_tuple:
                        hour, minute = time_tuple
                        general_logger.debug(f"Using parsed time: {hour}:{minute}")
                    else:
                        hour, minute = 10, 0  # Default to 10 AM as mentioned in help text
                        general_logger.debug("No time specified, using default 10:00 AM")
                    
                    next_exec = first_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    general_logger.debug(f"Final next_exec calculation: {next_exec}")

                # If the calculated date is in the past, move to the next occurrence
                if next_exec <= now:
                    if parsed['date_modifier'] == 'first day of every month':
                        # Move to the first day of the month after next
                        if now.month == 12:
                            next_exec = datetime(now.year + 1, 2, 1, tzinfo=KYIV_TZ)
                        elif now.month == 11:
                            next_exec = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                        else:
                            next_exec = datetime(now.year, now.month + 2, 1, tzinfo=KYIV_TZ)
                        next_exec = next_exec.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    elif parsed['date_modifier'] == 'last day of every month':
                        # Move to the last day of the month after next
                        if now.month == 12:
                            next_exec = datetime(now.year + 1, 2, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                        elif now.month == 11:
                            next_exec = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                        else:
                            next_exec = datetime(now.year, now.month + 2, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                        next_exec = next_exec.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    general_logger.debug(f"Adjusted to next occurrence: {next_exec}")

            # If still no next_exec but we have time, use that for today or tomorrow
            if not next_exec and parsed.get('time'):
                general_logger.debug(f"Using time component from parsed result: {parsed.get('time')}")
                h, mnt = parsed['time']
                general_logger.debug(f"Using time component: {h}:{mnt}")
                tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
                
                # For recurring reminders, always start from tomorrow if the time has passed today
                if parsed.get('frequency') == 'daily' and tmp <= now:
                    tmp = datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                    general_logger.debug(f"Daily reminder time passed today, adjusted to tomorrow: {tmp}")
                # For one-time reminders, also move to tomorrow if time has passed
                elif not parsed.get('frequency') and tmp <= now:
                    tmp = datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                    general_logger.debug(f"Time is in the past, adjusted to tomorrow: {tmp}")
                next_exec = tmp

            # If parser couldn't determine a schedule, report error and exit
            if not next_exec:
                general_logger.error(f"Failed to parse reminder command: '{reminder_text}'")
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text(
                        f"Sorry, I couldn't understand your reminder: '{reminder_text}'.\n"
                        "Example: /remind to pay rent every month on the 1st at 9AM"
                    )
                return

            # For recurring reminders, ensure the time is set correctly
            if parsed.get('frequency') or parsed.get('date_modifier'):
                if parsed.get('time'):
                    hour, minute = parsed['time']
                    next_exec = next_exec.replace(hour=hour, minute=minute, second=0, microsecond=0)
                elif not parsed.get('time') and not parsed.get('delay'):
                    # For recurring reminders without specified time, use 10:00 AM
                    next_exec = next_exec.replace(hour=10, minute=0, second=0, microsecond=0)

            is_one_time = not parsed['frequency'] and not parsed['date_modifier']
            if is_one_time and next_exec <= now:
                general_logger.debug(f"One-time reminder in the past, adjusting to 5 minutes from now")
                next_exec = now + timedelta(minutes=5)

            # Ensure the result is timezone-aware
            if next_exec and next_exec.tzinfo is None:
                general_logger.warning(f"Naive datetime detected for next_exec ({next_exec}) for input '{reminder_text}'. Forcing KYIV_TZ.")
                next_exec = KYIV_TZ.localize(next_exec)
            general_logger.info(f"[REMINDER_SCHEDULE] Scheduling reminder for '{parsed['task']}' at {next_exec} (user input: '{reminder_text}')")

            # Guard update.effective_user before calling mention_markdown_v2
            user_mention_md = None
            if getattr(update, 'effective_user', None) is not None and update.effective_user is not None:
                user_mention_md = update.effective_user.mention_markdown_v2()

            if user_id is not None and chat_id is not None:
                rem = Reminder(
                    parsed['task'], parsed.get('frequency'), parsed.get('delay'),
                    parsed['date_modifier'], next_exec, user_id, chat_id, user_mention_md
                )
                rem = self.save_reminder(rem)

                if rem.next_execution is not None:
                    delay_sec = seconds_until(rem.next_execution)
                    if getattr(context, 'job_queue', None) is not None and context.job_queue is not None:
                        job_queue = cast('JobQueue[Any]', context.job_queue)
                        job_queue.run_once(self.send_reminder, delay_sec, data=rem, name=f"reminder_{rem.reminder_id}")
                else:
                    general_logger.error("JobQueue is not available. Cannot schedule reminder.")
                    if getattr(update, 'message', None) is not None and update.message is not None:
                        await update.message.reply_text("❌ Error occurred. This has been reported to the developer.")
                    return

                # Ensure the displayed time is in the KYIV_TZ timezone
                if next_exec.tzinfo is None:
                    next_exec = KYIV_TZ.localize(next_exec)
                kyiv_time = next_exec.astimezone(KYIV_TZ)
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text(f"✅ Reminder set for {kyiv_time.strftime('%d.%m.%Y %H:%M')}.")

        elif command == "delete":
            if len(args) < 2:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("Usage /remind delete <id> or all")
                return
            what = args[1].lower()
            if what == 'all':
                chat_rems = [r for r in self.reminders if r.chat_id == chat_id]
                for r in chat_rems: self.delete_reminder(r)
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("Deleted all reminders.")
            else:
                try:
                    rid = int(what)
                    rem_candidate: Optional[Reminder] = next((r for r in self.reminders if r.reminder_id == rid and r.chat_id == chat_id), None)
                    if rem_candidate is not None:
                        self.delete_reminder(rem_candidate)
                        if getattr(update, 'message', None) is not None and update.message is not None:
                            await update.message.reply_text(f"Deleted reminder {rid}")
                    else:
                        if getattr(update, 'message', None) is not None and update.message is not None:
                            await update.message.reply_text("Invalid ID.")
                except:
                    if getattr(update, 'message', None) is not None and update.message is not None:
                        await update.message.reply_text("Invalid ID.")

        elif command == "edit":
            if len(args) < 3:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("Usage: /remind edit <id> <new text>")
                return
            try:
                rid = int(args[1])
            except:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("Invalid ID.")
                return
            rem_edit: Optional[Reminder] = next((r for r in self.load_reminders() if r.reminder_id==rid and r.chat_id==chat_id), None)
            if rem_edit is None:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("Reminder not found.")
                return

            new_txt = " ".join(args[2:])
            parsed = ReminderParser.parse_reminder(new_txt)
            general_logger.info(f"[REMINDER_EDIT] User input: '{new_txt}', Parsed: {parsed}")
            now = datetime.now(KYIV_TZ)
            next_exec = None

            # Use parsed datetime from timefhuman if available
            if 'parsed_datetime' in parsed and parsed['parsed_datetime']:
                next_exec = parsed['parsed_datetime']
                logging.debug(f"Edit: Using parsed_datetime: {next_exec}")
                # Make sure it's in the future
                if next_exec <= now:
                    # If it's a time-of-day without specific date, move to tomorrow
                    if 'time' in parsed and parsed['time']:
                        # For daily reminders, always set to tomorrow if time has passed
                        if parsed.get('frequency') == 'daily':
                            next_exec = datetime(
                                now.year,
                                now.month,
                                now.day + 1,
                                next_exec.hour,
                                next_exec.minute,
                                next_exec.second,
                                tzinfo=next_exec.tzinfo
                            )
                            logging.debug(f"Daily reminder: Adjusted to tomorrow: {next_exec}")
                        else:
                            # For other cases, add 5 minutes to ensure it's in the future
                            next_exec = now + timedelta(minutes=5)
                            logging.debug(f"Non-daily reminder: Adjusted to 5 minutes from now: {next_exec}")
                    else:
                        next_exec = now + timedelta(minutes=5)
                        logging.debug(f"No time specified: Adjusted to 5 minutes from now: {next_exec}")
                        
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
                        next_exec = now + timedelta(seconds=n)
                    elif unit_normalized == 'minute' or unit_normalized in ['min', 'm']:
                        next_exec = now + timedelta(minutes=n)
                    elif unit_normalized == 'hour' or unit_normalized in ['hr', 'h']:
                        next_exec = now + timedelta(hours=n)
                    elif unit_normalized == 'day' or unit_normalized == 'd':
                        # Ensure now has timezone info
                        general_logger.debug(f"Edit: Adding {n} days to now: {now}")
                        if now.tzinfo is None:
                            now = KYIV_TZ.localize(now)
                        # Use timedelta to add days to the timezone-aware datetime
                        next_exec = now + timedelta(days=n)
                        general_logger.debug(f"Edit: Result after adding {n} days: {next_exec}")
                    elif unit_normalized == 'week' or unit_normalized == 'w':
                        next_exec = now + timedelta(weeks=n)
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
                        last_day = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                    else:
                        last_day = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                    time_tuple = parsed.get('time')
                    hour, minute = time_tuple if time_tuple is not None else (10, 0)
                    next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                elif parsed['date_modifier'] == 'first day of every month':
                    # Calculate the first day of the next month
                    if now.month == 12:
                        first_day = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                    else:
                        first_day = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                    
                    # Use the parsed time
                    time_tuple = parsed.get('time')
                    if time_tuple:
                        hour, minute = time_tuple
                        general_logger.debug(f"Using parsed time: {hour}:{minute}")
                    else:
                        hour, minute = 10, 0  # Default to 10 AM as mentioned in help text
                        general_logger.debug("No time specified, using default 10:00 AM")
                    
                    next_exec = first_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    general_logger.debug(f"Final next_exec calculation: {next_exec}")

                # If the calculated date is in the past, move to the next occurrence
                if next_exec <= now:
                    if parsed['date_modifier'] == 'first day of every month':
                        # Move to the first day of the month after next
                        if now.month == 12:
                            next_exec = datetime(now.year + 1, 2, 1, tzinfo=KYIV_TZ)
                        elif now.month == 11:
                            next_exec = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                        else:
                            next_exec = datetime(now.year, now.month + 2, 1, tzinfo=KYIV_TZ)
                        next_exec = next_exec.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    elif parsed['date_modifier'] == 'last day of every month':
                        # Move to the last day of the month after next
                        if now.month == 12:
                            next_exec = datetime(now.year + 1, 2, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                        elif now.month == 11:
                            next_exec = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                        else:
                            next_exec = datetime(now.year, now.month + 2, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
                        next_exec = next_exec.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    general_logger.debug(f"Adjusted to next occurrence: {next_exec}")

            if not next_exec and parsed.get('time'):
                h, mnt = parsed['time']
                logging.debug(f"Edit: Using time component: {h}:{mnt}")
                tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
                
                # For recurring reminders, always start from tomorrow if the time has passed today
                if parsed.get('frequency') == 'daily' and tmp <= now:
                    tmp = datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                    general_logger.debug(f"Daily reminder time passed today, adjusted to tomorrow: {tmp}")
                # For one-time reminders, also move to tomorrow if time has passed
                elif not parsed.get('frequency') and tmp <= now:
                    tmp = datetime(
                        tmp.year,
                        tmp.month,
                        tmp.day + 1,
                        tmp.hour,
                        tmp.minute,
                        tmp.second,
                        tzinfo=tmp.tzinfo
                    )
                    general_logger.debug(f"Time is in the past, adjusted to tomorrow: {tmp}")
                next_exec = tmp

            if not next_exec:
                logging.debug("Edit: No time information extracted, using default (tomorrow 9 AM)")
                tmp = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if tmp <= now:
                    # Create a new datetime object with the same time but 1 day later
                    tmp = datetime(
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
                next_exec = now + timedelta(minutes=5)

            rem_edit.task = parsed['task']
            rem_edit.frequency = parsed['frequency']
            rem_edit.delay = parsed['delay']
            rem_edit.date_modifier = parsed['date_modifier']
            rem_edit.next_execution = next_exec
            self.save_reminder(rem_edit)

            # reschedule
            jobs: list[Any] = []
            if getattr(context, 'job_queue', None) is not None and context.job_queue is not None:
                job_queue = cast('JobQueue[Any]', context.job_queue)
                jobs = list(job_queue.get_jobs_by_name(f"reminder_{rem_edit.reminder_id}"))
            if jobs:
                for j in jobs:
                    j.schedule_removal()
            if rem_edit.next_execution is not None:
                delay = seconds_until(rem_edit.next_execution)
                if getattr(context, 'job_queue', None) is not None and context.job_queue is not None:
                    job_queue = cast('JobQueue[Any]', context.job_queue)
                    job_queue.run_once(self.send_reminder, delay, data=rem_edit, name=f"reminder_{rem_edit.reminder_id}")
            else:
                general_logger.error("JobQueue is not available. Cannot schedule reminder.")
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text("❌ Error occurred. This has been reported to the developer.")
                return

            # Ensure the displayed time is in the KYIV_TZ timezone
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
            kyiv_time = next_exec.astimezone(KYIV_TZ)
            if getattr(update, 'message', None) is not None and update.message is not None:
                await update.message.reply_text(f"Reminder updated. Next execution: {kyiv_time.strftime('%d.%m.%Y %H:%M')}.")

            # Ensure the result is timezone-aware
            if next_exec and next_exec.tzinfo is None:
                general_logger.warning(f"Naive datetime detected for next_exec ({next_exec}) for input '{new_txt}'. Forcing KYIV_TZ.")
                next_exec = KYIV_TZ.localize(next_exec)
            general_logger.info(f"[REMINDER_EDIT_SCHEDULE] Scheduling edited reminder for '{parsed['task']}' at {next_exec} (user input: '{new_txt}')")

        else:
            # Handle cases where users don't use the "to" keyword
            # Treat the entire args as a potential reminder task
            if args:
                reminder_text = " ".join(args)
                # Check if it looks like a simple task without time specification
                if len(args) <= 3 and not any(word in reminder_text.lower() for word in ['in', 'at', 'every', 'tomorrow', 'today']):
                    if getattr(update, 'message', None) is not None and update.message is not None:
                        await update.message.reply_text(
                            f"⚠️ Did you mean to set a reminder for '{reminder_text}'?\n\n"
                            "Please use the correct format:\n"
                            "• `/remind to {task}` - for immediate reminder (5 min default)\n"
                            "• `/remind to {task} in {time}` - for delayed reminder\n"
                            "• `/remind to {task} at {time}` - for specific time\n"
                            "• `/remind to {task} every {frequency}` - for recurring\n\n"
                            "Examples:\n"
                            "• `/remind to check email in 1 hour`\n"
                            "• `/remind to call mom at 3PM`\n"
                            "• `/remind to take medicine every day at 8AM`"
                        )
                else:
                    # Try to parse it as a reminder anyway
                    parsed = ReminderParser.parse_reminder(reminder_text)
                    # Check if parsing succeeded
                    task_val = parsed.get('task')
                    if not task_val or not isinstance(task_val, str) or not task_val.strip():
                        if getattr(update, 'message', None) is not None and update.message is not None:
                            await update.message.reply_text(
                                f"❌ Couldn't understand the reminder format.\n\n"
                                "Correct usage:\n"
                                "• `/remind to {task}` followed by time/frequency\n"
                                "• `/remind list` to see all reminders\n"
                                "• `/remind delete {id}` to remove a reminder\n\n"
                                "Example: `/remind to pay rent every month on the 1st at 9AM`"
                            )
                        return
                    
                    # Continue with reminder creation as if "to" was used
                    # [Rest of the reminder creation logic would go here]
                    if getattr(update, 'message', None) is not None and update.message is not None:
                        await update.message.reply_text(
                            f"⚠️ I'll try to create a reminder, but please use `/remind to {reminder_text}` format next time.\n\n"
                            "Setting reminder for: {parsed['task']}"
                        )
            else:
                if getattr(update, 'message', None) is not None and update.message is not None:
                    await update.message.reply_text(
                        "❌ Please specify a reminder command.\n\n"
                        "Available commands:\n"
                        "• `/remind to {task}` - create a reminder\n"
                        "• `/remind list` - view all reminders\n"
                        "• `/remind delete {id}` - delete a reminder"
                    )

    async def send_reminder(self, context: CallbackContext[Any, Any, Any, Any]) -> None:
        rem = getattr(context.job, 'data', None)
        if rem is None:
            return

        escaped_task = escape_markdown(rem.task, version=2)
        is_group = getattr(rem, 'chat_id', 0) < 0
        is_one_time = not getattr(rem, 'frequency', None)
        if is_group and is_one_time and getattr(rem, 'user_mention_md', None):
            msg = f"{rem.user_mention_md}: {escaped_task}"
        else:
            msg = f"⏰ REMINDER: {escaped_task}"
        try:
            await context.bot.send_message(rem.chat_id, msg, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            error_logger.error(f"Sending reminder failed: {e}")

        # handle recurring reschedule or delete
        rem.calculate_next_execution()
        if getattr(rem, 'frequency', None) or getattr(rem, 'date_modifier', None):
            self.save_reminder(rem)
            if rem.next_execution is not None:
                delay = seconds_until(rem.next_execution)
                general_logger.info(f"[REMINDER_RECUR] Rescheduling recurring reminder (id={getattr(rem, 'reminder_id', '?')}, task='{getattr(rem, 'task', '?')}') for next execution at {getattr(rem, 'next_execution', '?')}")
                if getattr(context, 'job_queue', None) is not None and context.job_queue is not None:
                    job_queue = cast('JobQueue[Any]', context.job_queue)
                    job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{getattr(rem, 'reminder_id', '?')}")
            else:
                general_logger.error("JobQueue is not available. Cannot schedule reminder.")
                await context.bot.send_message(rem.chat_id, "❌ Reminder scheduling is not available. Please contact the administrator.")
                return
        else:
            self.delete_reminder(rem)

    def schedule_startup(self, job_queue: Any) -> None:
        if job_queue is None:
            general_logger.warning("JobQueue is None, cannot schedule startup reminders.")
            return
        
        now = datetime.now(KYIV_TZ)
        for rem in self.load_reminders():
            if getattr(rem, 'next_execution', None) and rem.next_execution is not None and rem.next_execution > now:
                delay = seconds_until(rem.next_execution)
                job_queue.run_once(self.send_reminder, delay, data=rem, name=f"reminder_{getattr(rem, 'reminder_id', '?')}")

    async def button_callback(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle button callbacks for reminder actions."""
        query = getattr(update, 'callback_query', None)
        if query is None:
            return
        await query.answer()
        
        try:
            data = getattr(query, 'data', '') or ''
            if ':' not in data:
                if getattr(query, 'message', None) is not None and query.message is not None:
                    await query.message.edit_text("Invalid callback data.")
                return
                
            action, _ = data.split(':', 1)
            
            if action == 'confirm_delete_all':
                # Check if it's a private chat or if user is admin
                is_private = getattr(update, 'effective_chat', None) is not None and update.effective_chat is not None and update.effective_chat.type == 'private'
                if not is_private:
                    chat_id = None
                    if getattr(update, 'effective_chat', None) is not None and update.effective_chat is not None:
                        chat_id = update.effective_chat.id
                    user_id = None
                    if getattr(update, 'effective_user', None) is not None and update.effective_user is not None:
                        user_id = update.effective_user.id
                    chat_member = await context.bot.get_chat_member(chat_id, user_id)
                    if getattr(chat_member, 'status', None) not in ['creator', 'administrator']:
                        if getattr(query, 'message', None) is not None and query.message is not None:
                            await query.message.edit_text("❌ Only admins can delete all reminders.")
                        return
                
                # Delete all reminders
                chat_id = None
                if getattr(update, 'effective_chat', None) is not None and update.effective_chat is not None:
                    chat_id = update.effective_chat.id
                user_id = None
                if getattr(update, 'effective_user', None) is not None and update.effective_user is not None:
                    user_id = update.effective_user.id
                reminders = self.load_reminders(chat_id) if chat_id is not None else self.load_reminders()
                for reminder in reminders:
                    self.delete_reminder(reminder)
                    # Remove any scheduled jobs for this reminder
                    if getattr(context, 'job_queue', None) is not None and context.job_queue is not None:
                        job_queue = cast('JobQueue[Any]', context.job_queue)
                        jobs = job_queue.get_jobs_by_name(f"reminder_{getattr(reminder, 'reminder_id', '?')}")
                        for job in jobs:
                            job.schedule_removal()
                    else:
                        general_logger.warning("JobQueue not available, cannot remove scheduled jobs.")
                
                if getattr(query, 'message', None) is not None and query.message is not None:
                    await query.message.edit_text("✅ All reminders have been deleted.")
                
            elif action == 'cancel_delete_all':
                if getattr(query, 'message', None) is not None and query.message is not None:
                    await query.message.edit_text("❌ Deletion cancelled.")
                
        except Exception as e:
            error_logger.error(f"Error in button callback: {e}", exc_info=True)
            if getattr(query, 'message', None) is not None and query.message is not None:
                await query.message.edit_text("❌ An error occurred while processing your request.")

    async def list_reminders(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """List all active reminders in a visually appealing format."""
        chat_id = None
        if getattr(update, 'effective_chat', None) is not None and update.effective_chat is not None:
            chat_id = update.effective_chat.id
        user_reminders = [r for r in self.reminders if getattr(r, 'chat_id', None) == chat_id]

        if not user_reminders:
            if getattr(update, 'message', None) is not None and update.message is not None:
                await update.message.reply_text(
                    "🌟 *No Active Reminders* 🌟\n\n"
                    "Looks like you're all caught up! Create a new reminder with `/remind to`",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            return

        # Prepare a formatted list of reminders
        reminder_list = "🕰️ *Your Active Reminders* 🕰️\n\n"
        for reminder in user_reminders:
            # Format next execution time
            next_exec = getattr(reminder, 'next_execution', None)
            next_exec_str = next_exec.strftime('%d %b %Y at %I:%M %p') if next_exec else 'N/A'
            
            # Add frequency info
            freq = getattr(reminder, 'frequency', None)
            freq_str = str(freq) if freq is not None else ''
            icon = {
                'daily': '🔁',
                'weekly': '📅',
                'monthly': '📆',
                'yearly': '🗓️'
            }.get(freq_str, '⏰')

            reminder_list += (
                f"*ID:* `{getattr(reminder, 'reminder_id', '?')}`\n"
                f"{icon} *Task:* `{getattr(reminder, 'task', '?')}`\n"
                f" *Next Reminder:* `{next_exec_str}`\n"
                f"{'📆 *Frequency:* `' + freq_str.capitalize() + '`' if freq_str else ''}\n\n"
            )

        reminder_list += "Use `/remind delete <id>` to remove a specific reminder."

        if getattr(update, 'message', None) is not None and update.message is not None:
            await update.message.reply_text(
                reminder_list,
                parse_mode=ParseMode.MARKDOWN_V2
            )