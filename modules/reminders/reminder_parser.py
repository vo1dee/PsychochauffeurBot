import re
from modules.logger import general_logger
import timefhuman
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from modules.const import KYIV_TZ
from dateutil.parser import parse as date_parse

class ReminderParser:
    FREQUENCY_PATTERN = r'(?:every\s+(day|week|month|year))|(?:(daily|weekly|monthly|yearly))'
    DATE_MODIFIER_PATTERN = r'(?:on\s+the\s+(?:first|1st|last)\s+day\s+of\s+every\s+month)|(?:first\s+day\s+of\s+every\s+month)|(?:first\s+of\s+every\s+month)|(?:every\s+month\s+on\s+the\s+(?:1st|first))|(?:on\s+the\s+(?:1st|first))|(?:on\s+the\s+1st\s+at)|(?:on\s+the\s+first\s+at)|(?:on\s+the\s+1st)|(?:on\s+the\s+first)'
    TIME_PATTERN = r'(?:at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?|in\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|wks?|months?|years?))'
    SPECIFIC_DATE_PATTERN = r'on\s+(\d{1,2})\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)'

    @classmethod
    def parse_reminder(cls, text):
        """Parse a reminder text and extract components using timefhuman"""
        text = re.sub(r'^/remind\s+to\s+', '', text, flags=re.IGNORECASE).strip()
        general_logger.debug(f"Parsing reminder text: {text}")
        
        result = {
            'task': text,
            'frequency': None,
            'delay': None,
            'date_modifier': None,
            'parsed_datetime': None,
            'time': None
        }

        # Extract frequency first
        freq_match = re.search(cls.FREQUENCY_PATTERN, text, re.IGNORECASE)
        if freq_match:
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
            general_logger.debug(f"Extracted frequency: {result['frequency']}")

        # Extract date modifier
        modifier_match = re.search(cls.DATE_MODIFIER_PATTERN, text, re.IGNORECASE)
        if modifier_match:
            modifier_text = modifier_match.group(0).lower()
            general_logger.debug(f"Found date modifier text: {modifier_text}")
            if 'first' in modifier_text or '1st' in modifier_text:
                result['date_modifier'] = 'first day of every month'
                if not result['frequency']:  # Only set if not already set
                    result['frequency'] = 'monthly'
                
                # Calculate first day of next month
                now = datetime.now(KYIV_TZ)
                if now.month == 12:
                    first_day = datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                else:
                    first_day = datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                
                # Use the parsed time or default to 9 AM
                time_tuple = result.get('time')
                hour, minute = time_tuple if time_tuple else (9, 0)
                result['parsed_datetime'] = first_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                general_logger.debug(f"Set first day of month reminder for: {result['parsed_datetime']}")
                
            elif 'last' in modifier_text:
                result['date_modifier'] = 'last day of every month'
                if not result['frequency']:  # Only set if not already set
                    result['frequency'] = 'monthly'
            general_logger.debug(f"Extracted date modifier: {result['date_modifier']}")
            general_logger.debug(f"Updated frequency: {result['frequency']}")

        # Extract time
        time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3)
            if ampm:
                if ampm.lower() == 'pm' and hour < 12:
                    hour += 12
                elif ampm.lower() == 'am' and hour == 12:
                    hour = 0
            result['time'] = (hour, minute)
            general_logger.debug(f"Extracted time: {hour}:{minute}")

            # For daily reminders, check if the time has passed today
            if result.get('frequency') == 'daily':
                now = datetime.now(KYIV_TZ)
                today_at_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if today_at_time <= now:
                    # Time has passed today, set for tomorrow
                    tomorrow_at_time = (now + timedelta(days=1)).replace(
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0
                    )
                    result['parsed_datetime'] = tomorrow_at_time
                    general_logger.debug(f"Daily reminder time passed today, setting for tomorrow: {tomorrow_at_time}")
                else:
                    # Time hasn't passed yet today, set for today
                    result['parsed_datetime'] = today_at_time
                    general_logger.debug(f"Daily reminder time hasn't passed today, setting for today: {today_at_time}")

        # Extract delay
        delay_match = re.search(r'in\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|wks?|months?|years?)', text, re.IGNORECASE)
        if delay_match:
            result['delay'] = delay_match.group(0)
            general_logger.debug(f"Extracted delay: {result['delay']}")
            
            # Handle relative time delays directly
            n = int(delay_match.group(1))
            unit = delay_match.group(2).lower().rstrip('s')
            now = datetime.now(KYIV_TZ)
            
            if unit in ['second', 'sec']:
                result['parsed_datetime'] = now + timedelta(seconds=n)
            elif unit in ['minute', 'min']:
                result['parsed_datetime'] = now + timedelta(minutes=n)
            elif unit in ['hour', 'hr']:
                result['parsed_datetime'] = now + timedelta(hours=n)
            elif unit == 'day':
                result['parsed_datetime'] = now + timedelta(days=n)
            elif unit == 'week':
                result['parsed_datetime'] = now + timedelta(weeks=n)
            elif unit == 'month':
                result['parsed_datetime'] = now + relativedelta(months=+n)
            elif unit == 'year':
                result['parsed_datetime'] = now + relativedelta(years=+n)
            
            general_logger.debug(f"Calculated relative time: {result['parsed_datetime']}")

        # Handle specific dates (e.g., "on 15 July")
        specific_date_match = re.search(cls.SPECIFIC_DATE_PATTERN, text, re.IGNORECASE)
        if specific_date_match and not result['parsed_datetime']:
            try:
                date_str = specific_date_match.group(0)
                parsed_date = date_parse(date_str, fuzzy=True)
                if result['time']:
                    hour, minute = result['time']
                else:
                    hour, minute = 10, 0
                parsed_date = parsed_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if not parsed_date.tzinfo:
                    parsed_date = parsed_date.replace(tzinfo=KYIV_TZ)
                result['parsed_datetime'] = parsed_date
                general_logger.debug(f"Parsed specific date: {parsed_date}")
            except Exception as e:
                general_logger.error(f"Error parsing specific date: {e}")

        # Extract task by removing time-related parts
        task = text
        
        # Remove time specifications
        if time_match:
            task = task[:time_match.start()].strip()
        
        # Remove frequency specifications
        if freq_match:
            task = re.sub(r'\s*every\s+\w+\s*', ' ', task)
            task = re.sub(r'\s*(?:daily|weekly|monthly|yearly)\s*', ' ', task)
            # Also remove "on Monday" etc. for weekly reminders
            task = re.sub(r'\s*on\s+\w+\s*', ' ', task)
        
        # Remove date modifiers
        if modifier_match:
            task = task[:modifier_match.start()].strip()
        
        # Remove delay specifications
        if delay_match:
            task = task[:delay_match.start()].strip()
        
        # Remove specific date specifications
        if specific_date_match:
            task = task[:specific_date_match.start()].strip()
        
        # Clean up the task text
        task = re.sub(r'\s+', ' ', task).strip()
        task = re.sub(r'^remind\s+me\s+to\s+', '', task, flags=re.IGNORECASE).strip()
        
        # If task is empty after cleaning, use the original text up to the first time indicator
        if not task:
            task = text.split(' on the ')[0].split(' every ')[0].split(' at ')[0].split(' in ')[0].strip()
        
        result['task'] = task

        # Try to parse with timefhuman if we don't have a parsed datetime yet
        if not result['parsed_datetime']:
            try:
                parsed_dates = timefhuman.timefhuman(text)
                if parsed_dates:
                    parsed_datetime = parsed_dates[0]
                    if not parsed_datetime.tzinfo:
                        parsed_datetime = parsed_datetime.replace(tzinfo=KYIV_TZ)
                    
                    # Validate the parsed datetime
                    now = datetime.now(KYIV_TZ)
                    if parsed_datetime <= now:
                        # If it's a time-of-day without specific date, move to tomorrow
                        if 'tomorrow' in text.lower() or 'at' in text.lower():
                            parsed_datetime = parsed_datetime + timedelta(days=1)
                        else:
                            # For other cases, add 5 minutes to ensure it's in the future
                            parsed_datetime = now + timedelta(minutes=5)
                    result['parsed_datetime'] = parsed_datetime
            except Exception as e:
                general_logger.error(f"Error parsing with timefhuman: {e}")

        general_logger.debug(f"Final parse result: {result}")
        return result

    parse = parse_reminder 