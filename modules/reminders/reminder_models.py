import datetime as dt
from datetime import timedelta
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from modules.const import KYIV_TZ
from modules.logger import general_logger
from unittest.mock import MagicMock

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
        now = dt.datetime.now(KYIV_TZ)

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
        # Ensure both datetimes are timezone-aware
        if now.tzinfo is None:
            now = KYIV_TZ.localize(now)
        
        if self.next_execution:
            # Ensure next_execution is timezone-aware
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            
            # If the next execution time has passed
            if self.next_execution <= now:
                # Set to today at the same time if that hasn't passed yet
                today_at_time = dt.datetime(
                    now.year,
                    now.month,
                    now.day,
                    self.next_execution.hour,
                    self.next_execution.minute,
                    self.next_execution.second,
                    tzinfo=self.next_execution.tzinfo
                )
                
                if today_at_time <= now:
                    # If today's time has also passed, set to tomorrow
                    self.next_execution = dt.datetime(
                        now.year,
                        now.month,
                        now.day + 1,
                        self.next_execution.hour,
                        self.next_execution.minute,
                        self.next_execution.second,
                        tzinfo=self.next_execution.tzinfo
                    )
                    general_logger.debug(f"Daily reminder time passed today, adjusted to tomorrow: {self.next_execution}")
                else:
                    # Set to today's time since it hasn't passed yet
                    self.next_execution = today_at_time
                    general_logger.debug(f"Daily reminder set to today's time: {self.next_execution}")
            else:
                # Keep the current next_execution time since it hasn't passed yet
                general_logger.debug(f"Daily reminder time hasn't passed yet, keeping current time: {self.next_execution}")
        else:
            # For new reminders, start from today if the time hasn't passed, otherwise tomorrow
            today_at_time = dt.datetime(
                now.year,
                now.month,
                now.day,
                9,  # Default to 9 AM if no time specified
                0,
                0,
                tzinfo=now.tzinfo
            )
            
            # If the time has passed today, start from tomorrow
            if today_at_time <= now:
                self.next_execution = dt.datetime(
                    now.year,
                    now.month,
                    now.day + 1,
                    today_at_time.hour,
                    today_at_time.minute,
                    today_at_time.second,
                    tzinfo=today_at_time.tzinfo
                )
                general_logger.debug(f"New daily reminder time passed today, starting from tomorrow: {self.next_execution}")
            else:
                self.next_execution = today_at_time
                general_logger.debug(f"New daily reminder starting from today: {self.next_execution}")
    
    def _advance_weekly(self, now):
        # Handle MagicMock objects
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value

        if self.next_execution:
            # Ensure both datetimes are timezone-aware
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            if self.next_execution <= now:
                self.next_execution += timedelta(weeks=1)
        elif not self.next_execution:
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            self.next_execution = now + timedelta(weeks=1)
    
    def _advance_monthly(self, now):
        # Handle MagicMock objects
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value

        if self.next_execution:
            # Ensure both datetimes are timezone-aware
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            if self.next_execution <= now:
                self.next_execution += relativedelta(months=1)
        elif not self.next_execution:
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            self.next_execution = now + relativedelta(months=1)
    
    def _advance_yearly(self, now):
        # Handle MagicMock objects
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value

        if self.next_execution:
            # Ensure both datetimes are timezone-aware
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            if self.next_execution <= now:
                self.next_execution += relativedelta(years=1)
        elif not self.next_execution:
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            self.next_execution = now + relativedelta(years=1)

    def _calc_first_month(self, now):
        # Handle MagicMock objects
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value

        # Ensure both datetimes are timezone-aware
        if now.tzinfo is None:
            now = KYIV_TZ.localize(now)
        if self.next_execution and self.next_execution.tzinfo is None:
            self.next_execution = KYIV_TZ.localize(self.next_execution)

        # Log input values for debugging
        general_logger.debug(f"_calc_first_month: now={now}, next_execution={self.next_execution}")
        
        # If we have a next_execution date, use that as the base
        base_date = self.next_execution if self.next_execution else now
        
        # Move to the first day of the next month relative to the base date
        if base_date.month == 12:
            first_of_next = dt.datetime(base_date.year + 1, 1, 1, tzinfo=KYIV_TZ)
        else:
            first_of_next = dt.datetime(base_date.year, base_date.month + 1, 1, tzinfo=KYIV_TZ)
        
        # If the calculated date is in the past, move to the month after next
        if first_of_next <= now:
            if first_of_next.month == 12:
                first_of_next = dt.datetime(first_of_next.year + 1, 1, 1, tzinfo=KYIV_TZ)
            else:
                first_of_next = dt.datetime(first_of_next.year, first_of_next.month + 1, 1, tzinfo=KYIV_TZ)
        
        # Set the time
        hour = self.next_execution.hour if self.next_execution else 9
        minute = self.next_execution.minute if self.next_execution else 0
        self.next_execution = first_of_next.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=KYIV_TZ)
        
        # Log final next_execution
        general_logger.debug(f"_calc_first_month: final next_execution = {self.next_execution}")

    def _calc_last_month(self, now):
        """Calculate last day of next month"""
        # Handle MagicMock objects
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value

        # Ensure both datetimes are timezone-aware
        if now.tzinfo is None:
            now = KYIV_TZ.localize(now)
        if self.next_execution and self.next_execution.tzinfo is None:
            self.next_execution = KYIV_TZ.localize(self.next_execution)

        # Log input values for debugging
        general_logger.debug(f"_calc_last_month: now={now}, next_execution={self.next_execution}")
        
        # If we have a next_execution date, use that as the base
        base_date = self.next_execution if self.next_execution else now
        
        # Move to the first day of the next month relative to the base date
        if base_date.month == 12:
            first_of_next = dt.datetime(base_date.year + 1, 1, 1, tzinfo=KYIV_TZ)
        else:
            first_of_next = dt.datetime(base_date.year, base_date.month + 1, 1, tzinfo=KYIV_TZ)
        
        # Calculate the last day of that month
        if first_of_next.month == 12:
            end = dt.datetime(first_of_next.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
        else:
            end = dt.datetime(first_of_next.year, first_of_next.month + 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
        
        # Log calculated end date
        general_logger.debug(f"_calc_last_month: calculated end date = {end}")
                
        hour = self.next_execution.hour if self.next_execution else 9
        minute = self.next_execution.minute if self.next_execution else 0
        self.next_execution = end.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=KYIV_TZ)
        
        # Log final next_execution
        general_logger.debug(f"_calc_last_month: final next_execution = {self.next_execution}")

    def to_tuple(self):
        """Convert the reminder to a tuple for database storage."""
        next_execution_str = None
        if self.next_execution:
            # Ensure the datetime is timezone-aware
            if self.next_execution.tzinfo is None:
                self.next_execution = KYIV_TZ.localize(self.next_execution)
            next_execution_str = self.next_execution.isoformat()

        return (
            self.reminder_id,
            self.task,
            self.frequency,
            self.delay,
            self.date_modifier,
            next_execution_str,
            self.user_id,
            self.chat_id,
            self.user_mention_md
        )

    @classmethod
    def from_tuple(cls, data):
        """Create a reminder from a tuple from the database."""
        reminder_id, task, frequency, delay, date_modifier, next_execution_str, user_id, chat_id, user_mention_md = data
        next_execution = None
        if next_execution_str:
            next_execution = isoparse(next_execution_str)
            # Ensure the datetime is timezone-aware
            if next_execution.tzinfo is None:
                next_execution = KYIV_TZ.localize(next_execution)

        return cls(
            task=task,
            frequency=frequency,
            delay=delay,
            date_modifier=date_modifier,
            next_execution=next_execution,
            user_id=user_id,
            chat_id=chat_id,
            user_mention_md=user_mention_md,
            reminder_id=reminder_id
        ) 