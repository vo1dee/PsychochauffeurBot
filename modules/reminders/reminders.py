import sqlite3
import datetime
from datetime import datetime, timedelta
import re
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
from unittest.mock import MagicMock
from modules.reminders.reminder_models import Reminder
from modules.reminders.reminder_db import ReminderDB
from modules.reminders.reminder_parser import ReminderParser

def seconds_until(dt):
    now = datetime.now(KYIV_TZ)
    # Ensure dt is timezone-aware and in the same timezone as now
    if dt.tzinfo is None:
        dt = KYIV_TZ.localize(dt)
    else:
        dt = dt.astimezone(KYIV_TZ)
    general_logger.debug(f"seconds_until: now={now}, dt={dt}")
    return max(0.01, (dt - now).total_seconds())

class ReminderManager:
    def __init__(self, db_file='reminders.db'):
        self.db = ReminderDB(db_file)
        self.reminders = self.db.load_reminders()
        # No need to define regex patterns here; use ReminderParser

    def load_reminders(self, chat_id=None):
        return self.db.load_reminders(chat_id)

    def save_reminder(self, rem):
        result = self.db.save_reminder(rem)
        self.reminders = self.db.load_reminders()
        return result

    def remove_reminder(self, reminder):
        self.db.remove_reminder(reminder)
        self.reminders = self.db.load_reminders()

    # Add an alias for backward compatibility if needed
    delete_reminder = remove_reminder

    async def remind(self, update: Update, context: CallbackContext):
        args = context.args or []
        if not args:
            help_text = (
                '📝 *Reminder Bot Help*\n\n'
                '🕰️ *Reminder Bot \\- Your Personal Assistant* 🚨\n\n'
                '*How to Use:*\n'
                '• Create Reminders: `/remind to <task> \\[details\\]`\n'
                '• List Reminders: `/remind list`\n'
                '• Delete Reminders: `/remind delete <id>` or `/remind delete all`\n'
                '• Edit Reminders: `/remind edit <id> <new text>`\n\n'
                '🌟 *Example Reminders:*\n'
                '• Time\\-based: `/remind to pay rent every month on the 1st at 9AM`\n'
                '• Relative Time: `/remind to call mom in 2 hours`\n'
                '• Daily Tasks: `/remind to water plants every day at 8PM`\n'
                '• Monthly Tasks: `/remind to submit report on the last day of every month`\n\n'
                '🕒 *Supported Date Formats:*\n'
                '• `on 15 July` \\(defaults to 10 AM\\)\n'
                '• `on 15/07` \\(defaults to 10 AM this year\\)\n'
                '• `on 15\\.07\\.2025` \\(specific date and year\\)\n'
                '• `in 2 hours` \\(relative time\\)\n\n'
                '💡 *Pro Tip:* Reminders default to 10 AM if no time is specified\\!\n'
                '🔹 *Supported time formats:*\n'
                '• `in X minutes/hours/days/weeks/months`\n'
                '• `at HH:MM` or `at HH AM/PM`\n'
                '• `every day/week/month at HH:MM`\n'
            )
            await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)
            return

        command = args[0].lower()
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if command == "to":
            reminder_text = " ".join(args[1:])
            parsed = ReminderParser.parse(reminder_text)
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
            parsed = ReminderParser.parse(new_txt)
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

    async def list_reminders(self, update: Update, context: CallbackContext):
        """List all active reminders in a visually appealing format."""
        chat_id = update.effective_chat.id
        user_reminders = [r for r in self.reminders if r.chat_id == chat_id]

        if not user_reminders:
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
            next_exec = reminder.next_execution.strftime('%d %b %Y at %I:%M %p')
            
            # Add frequency info
            freq_emoji = {
                'daily': '🔁',
                'weekly': '📅',
                'monthly': '📆',
                'yearly': '🗓️'
            }.get(reminder.frequency, '⏰')

            reminder_list += (
                f"*ID:* `{reminder.reminder_id}`\n"
                f"{freq_emoji} *Task:* `{reminder.task}`\n"
                f"🕒 *Next Reminder:* `{next_exec}`\n"
                f"{'📆 *Frequency:* `' + reminder.frequency.capitalize() + '`' if reminder.frequency else ''}\n\n"
            )

        reminder_list += "Use `/remind delete <id>` to remove a specific reminder."

        await update.message.reply_text(
            reminder_list,
            parse_mode=ParseMode.MARKDOWN_V2
        )