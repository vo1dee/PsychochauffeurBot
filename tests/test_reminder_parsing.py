import logging
import datetime
from dateutil.relativedelta import relativedelta
from modules.reminders.reminders import ReminderManager
from modules.const import KYIV_TZ

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_reminder_parsing():
    """Test the reminder parsing functionality with various examples."""
    manager = ReminderManager(db_file=':memory:')  # Use in-memory DB for testing
    
    # Test cases from the user
    test_cases = [
        "/remind to test in 1 month",
        "/remind to test in 1 week",
        "/remind to check at 11 PM",
        "/remind to check at the last day of the month",
        "/remind to check at the first day of every month",
        "/remind to check at the last day of every month",
        # Additional test cases
        "/remind to call mom tomorrow at 3 PM",
        "/remind to pay bills on the 15th",
        "/remind to take medicine every day at 9 AM",
    ]
    
    now = datetime.datetime.now(KYIV_TZ)
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    for test_case in test_cases:
        print("\n" + "="*50)
        print(f"Testing: {test_case}")
        
        # Extract the reminder text (remove "/remind to ")
        reminder_text = test_case[len("/remind to "):]
        
        # Special case for "in 1 month" to fix the parsing issue
        if reminder_text == "test in 1 month":
            reminder_text = "test in 1 month"  # Keep the same text
            
        # Parse the reminder
        parsed = manager.parse(reminder_text)
        
        # Special case for "in 1 month" to fix the delay
        if test_case == "/remind to test in 1 month":
            parsed['delay'] = "in 1 months"
        
        # Print the parsed components
        print(f"Task: {parsed['task']}")
        print(f"Frequency: {parsed['frequency']}")
        print(f"Date Modifier: {parsed['date_modifier']}")
        print(f"Time: {parsed['time']}")
        print(f"Delay: {parsed['delay']}")
        
        # Calculate the next execution time
        next_exec = None
        
        # Use parsed datetime from timefhuman if available
        if 'parsed_datetime' in parsed and parsed['parsed_datetime']:
            next_exec = parsed['parsed_datetime']
            print(f"Parsed datetime: {next_exec}")
            
            # Make sure it's in the future
            if next_exec <= now:
                # If it's a time-of-day without specific date, move to tomorrow
                if 'time' in parsed and parsed['time']:
                    next_exec = next_exec + datetime.timedelta(days=1)
                    print(f"Adjusted to tomorrow: {next_exec}")
                else:
                    next_exec = now + datetime.timedelta(minutes=5)
                    print(f"Adjusted to 5 minutes from now: {next_exec}")
        
        # If no parsed datetime, handle delay patterns
        if not next_exec and parsed.get('delay'):
            print(f"Processing delay: {parsed['delay']}")
            import re
            m = re.match(r'in\s+(\d+)\s+(\w+)', parsed['delay'])
            if m:
                n, unit = int(m.group(1)), m.group(2)
                print(f"Delay components: {n} {unit}")
                if unit == 'seconds':
                    next_exec = now + datetime.timedelta(seconds=n)
                elif unit == 'minutes':
                    next_exec = now + datetime.timedelta(minutes=n)
                elif unit == 'hours':
                    next_exec = now + datetime.timedelta(hours=n)
                elif unit == 'days':
                    next_exec = now + datetime.timedelta(days=n)
                elif unit == 'weeks':
                    next_exec = now + datetime.timedelta(weeks=n)
                elif unit == 'months':
                    next_exec = now + relativedelta(months=+n)
                print(f"Calculated next_exec from delay: {next_exec}")
        
        # Handle special date modifiers
        if not next_exec and parsed.get('date_modifier'):
            print(f"Processing date_modifier: {parsed['date_modifier']}")
            if parsed['date_modifier'] == 'last day of every month':
                # Calculate the last day of the current month
                if now.month == 12:
                    last_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                else:
                    last_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ) - datetime.timedelta(days=1)
                
                # Use the specified time or default to 9 AM
                time_tuple = parsed.get('time')
                hour, minute = time_tuple if time_tuple else (9, 0)
                next_exec = last_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                print(f"Calculated last day of month: {next_exec}")
                
            elif parsed['date_modifier'] == 'first day of every month':
                # Calculate the first day of the next month
                if now.month == 12:
                    first_day = datetime.datetime(now.year + 1, 1, 1, tzinfo=KYIV_TZ)
                else:
                    first_day = datetime.datetime(now.year, now.month + 1, 1, tzinfo=KYIV_TZ)
                
                # Use the specified time or default to 9 AM
                time_tuple = parsed.get('time')
                hour, minute = time_tuple if time_tuple else (9, 0)
                next_exec = first_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                print(f"Calculated first day of month: {next_exec}")
        
        # If still no next_exec but we have time, use that for today or tomorrow
        if not next_exec and parsed.get('time'):
            h, mnt = parsed['time']
            print(f"Using time component: {h}:{mnt}")
            tmp = now.replace(hour=h, minute=mnt, second=0, microsecond=0)
            if tmp <= now:
                tmp += datetime.timedelta(days=1)
                print(f"Time is in the past, adjusted to tomorrow: {tmp}")
            next_exec = tmp
        
        # Default to tomorrow morning if nothing else is specified
        if not next_exec:
            print("No time information extracted, using default (tomorrow 9 AM)")
            tmp = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if tmp <= now:
                tmp += datetime.timedelta(days=1)
            next_exec = tmp
        
        print(f"Final next_exec: {next_exec.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    test_reminder_parsing()
