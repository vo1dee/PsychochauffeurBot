import sqlite3
from modules.reminders.reminder_models import Reminder
from modules.const import KYIV_TZ
from modules.logger import error_logger, general_logger

class ReminderDB:
    def __init__(self, db_file='reminders.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self._create_table()

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
                general_logger.debug(f"Saving reminder with next_execution: {rem.next_execution}")
            if rem.reminder_id:
                c.execute('''UPDATE reminders SET task=?, frequency=?, delay=?, date_modifier=?, next_execution=?, \
                            user_id=?, chat_id=?, user_mention_md=? WHERE reminder_id=?''',
                          (rem.task, rem.frequency, rem.delay, rem.date_modifier,
                           rem.next_execution.isoformat() if rem.next_execution else None,
                           rem.user_id, rem.chat_id, rem.user_mention_md, rem.reminder_id))
            else:
                c.execute('''INSERT INTO reminders (task, frequency, delay, date_modifier, next_execution, \
                             user_id, chat_id, user_mention_md) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (rem.task, rem.frequency, rem.delay, rem.date_modifier,
                           rem.next_execution.isoformat() if rem.next_execution else None,
                           rem.user_id, rem.chat_id, rem.user_mention_md))
                rem.reminder_id = c.lastrowid
            conn.commit()
        return rem

    def remove_reminder(self, reminder):
        """Remove a reminder from the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM reminders WHERE reminder_id = ?', (reminder.reminder_id,))
            self.conn.commit()
        except Exception as e:
            error_logger.error(f"Error removing reminder {reminder.reminder_id}: {e}", exc_info=True)
            raise

    # Add an alias for backward compatibility if needed
    delete_reminder = remove_reminder 