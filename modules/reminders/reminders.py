import sqlite3
import datetime
import re
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from modules.const import KYIV_TZ
from modules.logger import error_logger
from telegram import Update
from telegram.ext import CallbackContext

def seconds_until(dt):
    now = datetime.datetime.now(KYIV_TZ)
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
                self.next_execution += datetime.timedelta(days=1)
            elif not self.next_execution:
                self.next_execution = now + datetime.timedelta(days=1)

        elif self.frequency == 'weekly':
            if self.next_execution and self.next_execution <= now:
                self.next_execution += datetime.timedelta(days=7)
            elif not self.next_execution:
                self.next_execution = now + datetime.timedelta(days=7)

        elif self.frequency == 'monthly':
            if self.next_execution and self.next_execution <= now:
                self.next_execution += relativedelta(months=1)
            elif not self.next_execution:
                self.next_execution = now + relativedelta(months=1)

        elif self.frequency == 'seconds':
            self.next_execution = now + datetime.timedelta(seconds=5)

    def _calc_first_month(self, now):
        if now.month == 12:
            dt = datetime.datetime(now.year + 1, 1, 1, 9, 0, tzinfo=KYIV_TZ)
        else:
            dt = datetime.datetime(now.year, now.month + 1, 1, 9, 0, tzinfo=KYIV_TZ)
        if self.next_execution:
            dt = dt.replace(hour=self.next_execution.hour, minute=self.next_execution.minute)
        self.next_execution = dt

    def _calc_last_month(self, now):
        if now.month == 12:
            end = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
        else:
            end = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
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
        self.conn = sqlite3.connect(self.db_file)
        self._create_table()  # Note: changed to _create_table (private method)
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
        return sqlite3.connect(self.db_file, check_same_thread=False)

    def load_reminders(self, chat_id=None):
        """Load all reminders from the database, optionally filtered by chat_id"""
        cursor = self.conn.cursor()
        if chat_id:
            cursor.execute('SELECT * FROM reminders WHERE chat_id = ?', (chat_id,))
        else:
            cursor.execute('SELECT * FROM reminders')
        data = cursor.fetchall()
        return [Reminder.from_tuple(r) for r in data]

    def save_reminder(self, rem):
        with self.get_connection() as conn:
            c = conn.cursor()
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

    def parse(self, text):
        r = {'task': text, 'frequency': None, 'date_modifier': None, 'time': None, 'delay': None}
        txt = text.lower()
        m = re.search(r"in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|months?)", txt)
        if m:
            amt = int(m.group(1))
            unit = m.group(2)
            norm = {'s':'second','sec':'second','secs':'second','seconds':'second',
                    'm':'minute','min':'minute','mins':'minute','minutes':'minute',
                    'h':'hour','hr':'hour','hrs':'hour','hours':'hour',
                    'day':'day','days':'day','month':'month','months':'month'}.get(unit, unit)
            r['delay'] = f"in {amt} {norm}"
        t = re.search(r'at\s+(\d{1,2}):(\d{2})', txt)
        if t:
            r['time'] = (int(t.group(1)), int(t.group(2)))
        if "every day" in txt or "daily" in txt or "everyday" in txt: r['frequency'] = 'daily'
        elif "every week" in txt or "weekly" in txt: r['frequency'] = 'weekly'
        elif "every month" in txt or "monthly" in txt: r['frequency'] = 'monthly'
        elif "every second" in txt: r['frequency'] = 'seconds'
        if 'last day of every month' in txt or 'last day of month' in txt:
            r['date_modifier'] = 'last day of every month'; r['frequency']='monthly'
        if 'first day of every month' in txt or 'first of every month' in txt:
            r['date_modifier'] = 'first day of every month'; r['frequency']='monthly'
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

            delay = parsed.get('delay')
            if delay:
                m = re.match(r'in\s+(\d+)\s+(\w+)', delay)
                if m:
                    n, unit = int(m.group(1)), m.group(2)
                    if unit == 'second':
                        next_exec = now + datetime.timedelta(seconds=n)
                    elif unit == 'minute':
                        next_exec = now + datetime.timedelta(minutes=n)
                    elif unit == 'hour':
                        next_exec = now + datetime.timedelta(hours=n)
                    elif unit == 'day':
                        next_exec = now + datetime.timedelta(days=n)
                    elif unit == 'month':
                        next_exec = now + relativedelta(months=+n)

            if not next_exec and parsed.get('time'):
                h, mnt = parsed['time']
                tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
                if tmp <= now:
                    tmp += datetime.timedelta(days=1)
                next_exec = tmp

            if not next_exec:
                tmp = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if tmp <= now:
                    tmp += datetime.timedelta(days=1)
                next_exec = tmp

            is_one_time = not parsed['frequency'] and not parsed['date_modifier']
            if is_one_time and next_exec <= now:
                next_exec = now + datetime.timedelta(minutes=5)

            rem = Reminder(parsed['task'], parsed['frequency'], parsed['delay'],
                           parsed['date_modifier'], next_exec, user_id, chat_id,
                           update.effective_user.mention_markdown_v2())
            rem = self.save_reminder(rem)

            delay_sec = seconds_until(rem.next_execution)
            context.job_queue.run_once(self.send_reminder, delay_sec, data=rem, name=f"reminder_{rem.reminder_id}")

            await update.message.reply_text(f"✅ Reminder set for {next_exec.strftime('%d.%m.%Y %H:%M')}.")

        elif command == "list":
            rems = [r for r in self.load_reminders() if r.chat_id == chat_id]
            if not rems:
                await update.message.reply_text("No active reminders.")
                return
            s = ''
            now = datetime.datetime.now(KYIV_TZ)
            for r in rems:
                due = r.next_execution.strftime('%d.%m.%Y %H:%M') if r.next_execution else 'None'
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

            delay = parsed.get('delay')
            if delay:
                m = re.match(r'in\s+(\d+)\s+(\w+)', delay)
                if m:
                    n, unit = int(m.group(1)), m.group(2)
                    if unit == 'second':
                        next_exec = now + datetime.timedelta(seconds=n)
                    elif unit == 'minute':
                        next_exec = now + datetime.timedelta(minutes=n)
                    elif unit == 'hour':
                        next_exec = now + datetime.timedelta(hours=n)
                    elif unit == 'day':
                        next_exec = now + datetime.timedelta(days=n)
                    elif unit == 'month':
                        next_exec = now + relativedelta(months=+n)

            if not next_exec and parsed.get('time'):
                h, mnt = parsed['time']
                tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
                if tmp <= now:
                    tmp += datetime.timedelta(days=1)
                next_exec = tmp

            if not next_exec:
                tmp = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if tmp <= now:
                    tmp += datetime.timedelta(days=1)
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

            await update.message.reply_text("Reminder updated.")

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
