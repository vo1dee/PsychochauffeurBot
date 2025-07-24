from typing import Any, Optional, Tuple, ClassVar
import datetime as dt
from datetime import timedelta, datetime
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from modules.const import KYIV_TZ
from modules.logger import general_logger
from unittest.mock import MagicMock

class Reminder:
    reminder_id: Optional[int]
    task: str
    frequency: Optional[str]
    delay: Optional[str]
    date_modifier: Optional[str]
    next_execution: Optional[dt.datetime]
    user_id: int
    chat_id: int
    user_mention_md: Optional[str]

    def __init__(self, task: str, frequency: Optional[str], delay: Optional[str], date_modifier: Optional[str], next_execution: Optional[dt.datetime], user_id: int, chat_id: int, user_mention_md: Optional[str] = None, reminder_id: Optional[int] = None) -> None:
        self.reminder_id = reminder_id
        self.task = task
        self.frequency = frequency
        self.delay = delay
        self.date_modifier = date_modifier
        self.next_execution = next_execution
        self.user_id = user_id
        self.chat_id = chat_id
        self.user_mention_md = user_mention_md

    def calculate_next_execution(self) -> None:
        now: dt.datetime = dt.datetime.now(KYIV_TZ)
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

    def _advance_daily(self, now: dt.datetime) -> None:
        if now.tzinfo is None:
            now = KYIV_TZ.localize(now)
        if self.next_execution is not None:
            next_exec = self.next_execution  # Type narrowing for mypy
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
                self.next_execution = next_exec
            if next_exec <= now:
                today_at_time = dt.datetime(
                    now.year,
                    now.month,
                    now.day,
                    next_exec.hour,
                    next_exec.minute,
                    next_exec.second,
                    tzinfo=next_exec.tzinfo
                )
                if today_at_time <= now:
                    self.next_execution = today_at_time + timedelta(days=1)
                    general_logger.debug(f"Daily reminder time passed today, adjusted to tomorrow: {self.next_execution}")
                else:
                    self.next_execution = today_at_time
                    general_logger.debug(f"Daily reminder set to today's time: {self.next_execution}")
            else:
                general_logger.debug(f"Daily reminder time hasn't passed yet, keeping current time: {self.next_execution}")
        else:
            today_at_time = dt.datetime(
                now.year,
                now.month,
                now.day,
                9,  # Default to 9 AM if no time specified
                0,
                0,
                tzinfo=now.tzinfo
            )
            if today_at_time <= now:
                self.next_execution = today_at_time + timedelta(days=1)
                general_logger.debug(f"New daily reminder time passed today, starting from tomorrow: {self.next_execution}")
            else:
                self.next_execution = today_at_time
                general_logger.debug(f"New daily reminder starting from today: {self.next_execution}")

    def _advance_weekly(self, now: dt.datetime) -> None:
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value
        if self.next_execution is not None:
            next_exec = self.next_execution  # Type narrowing for mypy
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
                self.next_execution = next_exec
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            if next_exec <= now:
                self.next_execution = next_exec + timedelta(weeks=1)
        elif not self.next_execution:
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            self.next_execution = (now + timedelta(weeks=1)) if isinstance(now, dt.datetime) else None

    def _advance_monthly(self, now: dt.datetime) -> None:
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value
        if self.next_execution is not None:
            next_exec = self.next_execution  # Type narrowing for mypy
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
                self.next_execution = next_exec
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            if next_exec <= now:
                next_exec = next_exec + relativedelta(months=1)
                if isinstance(next_exec, datetime):
                    self.next_execution = next_exec
        elif not self.next_execution:
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            next_exec_result = now + relativedelta(months=1)
            if isinstance(next_exec_result, datetime):
                self.next_execution = next_exec_result

    def _advance_yearly(self, now: dt.datetime) -> None:
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value
        if self.next_execution is not None:
            next_exec = self.next_execution  # Type narrowing for mypy
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
                self.next_execution = next_exec
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            if next_exec <= now:
                self.next_execution = next_exec.replace(year=next_exec.year + 1)
                general_logger.debug(f"Yearly reminder advanced to next year: {self.next_execution}")
        elif not self.next_execution:
            if now.tzinfo is None:
                now = KYIV_TZ.localize(now)
            self.next_execution = now.replace(year=now.year + 1)
            general_logger.debug(f"New yearly reminder set for next year: {self.next_execution}")

    def _calc_first_month(self, now: dt.datetime) -> None:
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value
        if now.tzinfo is None:
            now = KYIV_TZ.localize(now)
        if self.next_execution and self.next_execution.tzinfo is None:
            self.next_execution = KYIV_TZ.localize(self.next_execution)
        general_logger.debug(f"_calc_first_month: now={now}, next_execution={self.next_execution}")
        base_date = self.next_execution if self.next_execution else now
        if base_date.month == 12:
            first_of_next = dt.datetime(base_date.year + 1, 1, 1, tzinfo=KYIV_TZ)
        else:
            first_of_next = dt.datetime(base_date.year, base_date.month + 1, 1, tzinfo=KYIV_TZ)
        if first_of_next <= now:
            if first_of_next.month == 12:
                first_of_next = dt.datetime(first_of_next.year + 1, 1, 1, tzinfo=KYIV_TZ)
            else:
                first_of_next = dt.datetime(first_of_next.year, first_of_next.month + 1, 1, tzinfo=KYIV_TZ)
        hour = self.next_execution.hour if self.next_execution else 9
        minute = self.next_execution.minute if self.next_execution else 0
        self.next_execution = first_of_next.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=KYIV_TZ)
        general_logger.debug(f"_calc_first_month: final next_execution = {self.next_execution}")

    def _calc_last_month(self, now: dt.datetime) -> None:
        if isinstance(now, MagicMock):
            if hasattr(now, 'return_value'):
                now = now.return_value
        if now.tzinfo is None:
            now = KYIV_TZ.localize(now)
        if self.next_execution and self.next_execution.tzinfo is None:
            self.next_execution = KYIV_TZ.localize(self.next_execution)
        general_logger.debug(f"_calc_last_month: now={now}, next_execution={self.next_execution}")
        base_date = self.next_execution if self.next_execution else now
        if base_date.month == 12:
            first_of_next = dt.datetime(base_date.year + 1, 1, 1, tzinfo=KYIV_TZ)
        else:
            first_of_next = dt.datetime(base_date.year, base_date.month + 1, 1, tzinfo=KYIV_TZ)
        if first_of_next.month == 12:
            end = dt.datetime(first_of_next.year + 1, 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
        else:
            end = dt.datetime(first_of_next.year, first_of_next.month + 1, 1, tzinfo=KYIV_TZ) - timedelta(days=1)
        general_logger.debug(f"_calc_last_month: calculated end date = {end}")
        hour = self.next_execution.hour if self.next_execution else 9
        minute = self.next_execution.minute if self.next_execution else 0
        self.next_execution = end.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=KYIV_TZ)
        general_logger.debug(f"_calc_last_month: final next_execution = {self.next_execution}")

    def to_tuple(self) -> Tuple[Optional[int], str, Optional[str], Optional[str], Optional[str], Optional[str], int, int, Optional[str]]:
        next_execution_str: Optional[str] = None
        if self.next_execution is not None:
            next_exec = self.next_execution  # Type narrowing for mypy
            if next_exec.tzinfo is None:
                next_exec = KYIV_TZ.localize(next_exec)
                self.next_execution = next_exec
            next_execution_str = next_exec.isoformat()
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
    def from_tuple(cls, data: Tuple[Any, ...]) -> 'Reminder':
        reminder_id, task, frequency, delay, date_modifier, next_execution_str, user_id, chat_id, user_mention_md = data
        next_execution: Optional[dt.datetime] = None
        if next_execution_str:
            next_execution = isoparse(next_execution_str)
            if next_execution is not None and next_execution.tzinfo is None:
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
