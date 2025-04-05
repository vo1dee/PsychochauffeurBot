import re
from datetime import datetime

def parse_reminder(text):
    """Parse free-text reminder instructions, return dict with components."""
    text_lower = text.lower()
    result = {
        'task': text,
        'frequency': None,
        'date_modifier': None,
        'time': None,
        'delay': None
    }
    txt = text.lower()

    # Delay (now handle min/m/hr/second/sec etc.)
    delay_match = re.search(r"in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|months?)", txt)
    if delay_match:
        amount = int(delay_match.group(1))
        unit = delay_match.group(2)
        norm_unit = {
            's':'second', 'sec':'second', 'secs':'second', 'seconds':'second',
            'm':'minute','min':'minute','mins':'minute','minutes':'minute',
            'h':'hour','hr':'hour','hrs':'hour','hours':'hour',
            'day':'day','days':'day','month':'month','months':'month'
        }.get(unit.strip(), unit.strip())
        result['delay'] = f"in {amount} {norm_unit}"



    # Delay: e.g., in 5 minutes
    m_delay = re.search(r'in\s+(\d+)\s+(second|minute|hour|day|month)s?', text_lower)
    if m_delay:
        amount, unit = int(m_delay.group(1)), m_delay.group(2)
        result['delay'] = f"in {amount} {unit}"

    # 'tomorrow' → delay 1 day
    if 'tomorrow' in text_lower:
        now = datetime.now()
        result['time'] = (9,0)  # default 9AM next day
        result['delay'] = None
        result['date_modifier'] = None
        result['frequency'] = None  # one-off

    # Specific time e.g. at 15:30
    m_time = re.search(r'at\s+(\d{1,2}):(\d{2})', text_lower)
    if m_time:
        result['time'] = int(m_time.group(1)), int(m_time.group(2))

    # Frequency:
    if any(word in text_lower for word in ['every day', 'daily', 'everyday']):
        result['frequency'] = "daily"
    elif any(word in text_lower for word in ['every week', 'weekly']):
        result['frequency'] = "weekly"
    elif any(word in text_lower for word in ['every month', 'monthly']):
        result['frequency'] = "monthly"
    elif 'every second' in text_lower:
        result['frequency'] = "seconds"

    # "every N days/weeks/months"
    match = re.search(r'every\s+(\d+)\s+(day|week|month)s?', text_lower)
    if match:
        n, period = int(match.group(1)), match.group(2)
        result['frequency'] = f"every {n} {period}s"  # You can implement more logic on this later

    # "every <weekday>"
    weekdays = {'monday','tuesday','wednesday','thursday','friday','saturday','sunday'}
    for day in weekdays:
        if f'every {day}' in text_lower:
            result['frequency'] = f"weekly_{day}"

    # Date modifiers
    last_day_patterns = [
        'last day of every month', 'last day of month', 'on the last day of every month'
    ]
    first_day_patterns = [
        'first day of every month', 'first of every month', 'on the first day of every month'
    ]
    if any(p in text_lower for p in last_day_patterns):
        result['date_modifier'] = 'last day of every month'
        result['frequency'] = 'monthly'
    elif any(p in text_lower for p in first_day_patterns):
        result['date_modifier'] = 'first day of every month'
        result['frequency'] = 'monthly'

    return result
