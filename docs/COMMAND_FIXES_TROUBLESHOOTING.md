# Command Fixes Troubleshooting Guide

This guide provides specific troubleshooting procedures for the enhanced `/analyze` and `/flares` commands after the command fixes implementation.

## Quick Reference

### Command Status Check
```bash
# Check if enhanced commands are working
python -c "
from modules.enhanced_analyze_command import enhanced_analyze
from modules.enhanced_flares_command import enhanced_flares
print('Enhanced commands loaded successfully')
"

# Test date parser functionality
python -c "
from modules.utils import DateParser
test_dates = ['15-01-2024', '2024-01-15', '15/01/2024']
for date_str in test_dates:
    try:
        parsed = DateParser.parse_date(date_str)
        print(f'{date_str} -> {parsed}')
    except Exception as e:
        print(f'{date_str} -> ERROR: {e}')
"
```

### Log Analysis for Command Issues
```bash
# Check for command-specific errors
grep -i "analyze\|flares" logs/error.log | tail -20

# Monitor command execution in real-time
tail -f logs/general.log | grep -E "(analyze|flares|enhanced)"

# Check diagnostic logs
grep "command_diagnostics\|enhanced_diagnostics" logs/general.log | tail -10
```

## Analyze Command Issues

### Issue 1: Date Format Not Recognized

#### Symptoms
- Error message: "❌ Помилка в форматі дати"
- Command fails with date parsing errors
- Previously working date formats now fail

#### Diagnostic Steps
```bash
# Test date parser directly
python -c "
from modules.utils import DateParser
import traceback

test_cases = [
    '15-01-2024',    # DD-MM-YYYY
    '2024-01-15',    # YYYY-MM-DD  
    '15/01/2024',    # DD/MM/YYYY
    '32-01-2024',    # Invalid day
    '15-13-2024',    # Invalid month
    '15-01-24'       # 2-digit year
]

for date_str in test_cases:
    try:
        result = DateParser.parse_date(date_str)
        print(f'✅ {date_str} -> {result}')
    except Exception as e:
        print(f'❌ {date_str} -> {e}')
        traceback.print_exc()
"
```

#### Solutions

**Solution 1: Verify Date Parser Implementation**
```bash
# Check if DateParser class exists and is properly imported
python -c "
from modules.utils import DateParser
print('Available methods:', [method for method in dir(DateParser) if not method.startswith('_')])
print('DATE_FORMATS:', getattr(DateParser, 'DATE_FORMATS', 'Not found'))
"
```

**Solution 2: Test Date Format Patterns**
```python
# Add to modules/utils.py if missing
from datetime import datetime

class DateParser:
    DATE_FORMATS = [
        ('%Y-%m-%d', 'YYYY-MM-DD'),
        ('%d-%m-%Y', 'DD-MM-YYYY'),
        ('%d/%m/%Y', 'DD/MM/YYYY'),
    ]
    
    @staticmethod
    def parse_date(date_str: str):
        for fmt, description in DateParser.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        supported_formats = [desc for _, desc in DateParser.DATE_FORMATS]
        raise ValueError(f"Invalid date format. Supported: {', '.join(supported_formats)}")
```

**Solution 3: Check Enhanced Command Integration**
```bash
# Verify enhanced commands are being used
python -c "
from modules.enhanced_analyze_command import enhanced_analyze_command
import inspect
print('Enhanced analyze command signature:')
print(inspect.signature(enhanced_analyze_command))
"
```

### Issue 2: Database Connection Failures

#### Symptoms
- Error message: "❌ Виникла проблема з підключенням до бази даних"
- Commands timeout or fail to retrieve messages
- Database connection errors in logs

#### Diagnostic Steps
```bash
# Test database connectivity
python -c "
import asyncio
from modules.database import Database

async def test_db():
    try:
        # Test basic connection
        await Database.initialize()
        print('✅ Database initialization successful')
        
        # Test health check if available
        if hasattr(Database, 'health_check'):
            health = await Database.health_check()
            print(f'✅ Database health check: {health}')
        
        # Test message retrieval
        from modules.database import get_messages_for_chat_today
        messages = await get_messages_for_chat_today(-1001234567890)  # Test chat ID
        print(f'✅ Message retrieval test: {len(messages)} messages')
        
    except Exception as e:
        print(f'❌ Database test failed: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test_db())
"
```

#### Solutions

**Solution 1: Check Database Configuration**
```bash
# Verify database environment variables
python -c "
import os
db_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
for var in db_vars:
    value = os.getenv(var)
    print(f'{var}: {\"SET\" if value else \"MISSING\"}')
"
```

**Solution 2: Test Connection Pool**
```bash
# Check connection pool status
python -c "
import asyncio
from modules.database import Database

async def check_pool():
    try:
        pool = await Database.get_pool()
        print(f'Pool size: {pool.get_size()}')
        print(f'Pool max size: {pool.get_max_size()}')
        print(f'Pool min size: {pool.get_min_size()}')
    except Exception as e:
        print(f'Pool check failed: {e}')

asyncio.run(check_pool())
"
```

**Solution 3: Enable Database Retry Logic**
```python
# Verify retry logic is implemented in enhanced commands
# Check modules/enhanced_analyze_command.py for:
async def _parse_command_arguments(self, args, chat_id, username):
    # Should include retry logic for database operations
    try:
        messages = await get_messages_for_chat_today(chat_id)
    except Exception as e:
        # Retry logic should be here
        await asyncio.sleep(1)
        messages = await get_messages_for_chat_today(chat_id)
```

### Issue 3: GPT API Failures

#### Symptoms
- Error message: "❌ Сервіс аналізу тимчасово недоступний"
- Analysis completes but returns empty results
- API timeout errors in logs

#### Diagnostic Steps
```bash
# Test GPT API connectivity
python -c "
import asyncio
from modules.gpt import generate_response
from unittest.mock import MagicMock

async def test_gpt():
    # Create mock update and context
    update = MagicMock()
    context = MagicMock()
    
    try:
        result = await generate_response(
            update, 
            context, 
            response_type='analyze',
            message_text_override='Test message for analysis',
            return_text=True
        )
        print(f'✅ GPT API test successful: {len(result) if result else 0} characters')
    except Exception as e:
        print(f'❌ GPT API test failed: {e}')

asyncio.run(test_gpt())
"
```

#### Solutions

**Solution 1: Check API Configuration**
```bash
# Verify OpenAI/OpenRouter API key
python -c "
import os
api_key = os.getenv('OPENAI_API_KEY') or os.getenv('OPENROUTER_API_KEY')
if api_key:
    print(f'API key configured: {api_key[:10]}...{api_key[-4:]}')
else:
    print('❌ No API key found')
"
```

**Solution 2: Test API Call Tracking**
```bash
# Check if API call tracking is working
python -c "
from modules.command_diagnostics import track_api_call
import asyncio

async def test_tracking():
    async with track_api_call('openrouter', '/chat/completions', 'POST') as tracker:
        print('✅ API call tracking initialized')
        tracker.set_status_code(200)
        print('✅ API call tracking completed')

asyncio.run(test_tracking())
"
```

## Flares Command Issues

### Issue 4: Screenshot Generation Failures

#### Symptoms
- Error message: "❌ Не вдалося створити знімок сонячних спалахів"
- Command hangs during screenshot generation
- wkhtmltoimage errors in logs

#### Diagnostic Steps
```bash
# Test wkhtmltoimage availability
which wkhtmltoimage
wkhtmltoimage --version

# Test screenshot manager
python -c "
from modules.utils import ScreenshotManager
import asyncio

async def test_screenshot():
    manager = ScreenshotManager()
    
    # Test tool availability
    available = manager._check_wkhtmltoimage_availability()
    print(f'wkhtmltoimage available: {available}')
    
    # Test directory creation
    try:
        await manager.ensure_screenshot_directory()
        print('✅ Screenshot directory check passed')
    except Exception as e:
        print(f'❌ Directory check failed: {e}')
    
    # Test status info
    status = manager.get_screenshot_status_info()
    print(f'Status info: {status}')

asyncio.run(test_screenshot())
"
```

#### Solutions

**Solution 1: Install wkhtmltoimage**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install wkhtmltopdf

# macOS
brew install wkhtmltopdf

# Verify installation
wkhtmltoimage --version
```

**Solution 2: Check File Permissions**
```bash
# Check screenshot directory permissions
ls -la python-web-screenshots/
mkdir -p python-web-screenshots
chmod 755 python-web-screenshots

# Test file creation
touch python-web-screenshots/test.txt
rm python-web-screenshots/test.txt
```

**Solution 3: Test Screenshot Generation Manually**
```bash
# Test wkhtmltoimage directly
wkhtmltoimage \
  --width 1200 \
  --height 800 \
  --javascript-delay 3000 \
  "https://api.meteoagent.com/flares" \
  test_screenshot.png

# Check if file was created
ls -la test_screenshot.png
rm test_screenshot.png
```

### Issue 5: Screenshot Freshness Issues

#### Symptoms
- Always generates new screenshots even when fresh ones exist
- Incorrect age calculation for screenshots
- Freshness threshold not working

#### Diagnostic Steps
```bash
# Check screenshot files and timestamps
ls -la python-web-screenshots/

# Test freshness calculation
python -c "
from modules.utils import ScreenshotManager
from datetime import datetime, timedelta
import os

manager = ScreenshotManager()

# Check if screenshot exists
screenshot_path = 'python-web-screenshots/flares_screenshot.png'
if os.path.exists(screenshot_path):
    file_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path))
    age_hours = (datetime.now() - file_time).total_seconds() / 3600
    is_fresh = age_hours < manager.FRESHNESS_THRESHOLD_HOURS
    
    print(f'Screenshot exists: True')
    print(f'File time: {file_time}')
    print(f'Age: {age_hours:.1f} hours')
    print(f'Threshold: {manager.FRESHNESS_THRESHOLD_HOURS} hours')
    print(f'Is fresh: {is_fresh}')
else:
    print('Screenshot does not exist')
"
```

#### Solutions

**Solution 1: Verify Freshness Threshold**
```python
# Check ScreenshotManager configuration
class ScreenshotManager:
    FRESHNESS_THRESHOLD_HOURS = 6  # Should be 6 hours
    
    async def validate_screenshot_freshness(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(path))
        age_hours = (datetime.now() - file_time).total_seconds() / 3600
        return age_hours < self.FRESHNESS_THRESHOLD_HOURS
```

**Solution 2: Test Timezone Handling**
```bash
# Check timezone configuration
python -c "
from modules.const import KYIV_TZ
from datetime import datetime
import os

print(f'KYIV_TZ: {KYIV_TZ}')
print(f'Current time (local): {datetime.now()}')
print(f'Current time (Kyiv): {datetime.now(KYIV_TZ)}')

# Test file timestamp handling
screenshot_path = 'python-web-screenshots/flares_screenshot.png'
if os.path.exists(screenshot_path):
    file_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path))
    file_time_kyiv = file_time.astimezone(KYIV_TZ)
    print(f'File time (local): {file_time}')
    print(f'File time (Kyiv): {file_time_kyiv}')
"
```

## Performance Issues

### Issue 6: Slow Command Response

#### Symptoms
- Commands take longer than 30 seconds to respond
- Timeout errors from Telegram
- High CPU or memory usage during command execution

#### Diagnostic Steps
```bash
# Monitor command performance
python -c "
import asyncio
import time
from modules.enhanced_analyze_command import enhanced_analyze_command
from unittest.mock import MagicMock

async def performance_test():
    # Create mock objects
    update = MagicMock()
    update.effective_chat.id = -1001234567890
    update.effective_user.id = 123456789
    update.effective_user.username = 'testuser'
    update.message = MagicMock()
    
    context = MagicMock()
    context.args = ['last', '10', 'messages']
    
    # Time the command execution
    start_time = time.time()
    try:
        await enhanced_analyze_command(update, context)
        end_time = time.time()
        print(f'✅ Command completed in {end_time - start_time:.2f} seconds')
    except Exception as e:
        end_time = time.time()
        print(f'❌ Command failed after {end_time - start_time:.2f} seconds: {e}')

asyncio.run(performance_test())
"
```

#### Solutions

**Solution 1: Enable Performance Monitoring**
```bash
# Check if performance metrics are being logged
grep "performance_metric\|command_milestone" logs/general.log | tail -10

# Enable debug logging for performance analysis
export LOG_LEVEL=DEBUG
python main.py
```

**Solution 2: Optimize Database Queries**
```sql
-- Check for slow queries in PostgreSQL
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements 
WHERE mean_time > 1000 
ORDER BY mean_time DESC 
LIMIT 10;

-- Create indexes if missing
CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp ON messages(chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date(timestamp));
```

**Solution 3: Implement Caching**
```python
# Verify caching is enabled in configuration
from modules.config.config_manager import config_manager
import asyncio

async def check_cache_config():
    cache_cfg = config_manager.get_analysis_cache_config()
    print(f"Cache enabled: {cache_cfg['enabled']}")
    print(f"Cache TTL: {cache_cfg['ttl']} seconds")

asyncio.run(check_cache_config())
```

## Configuration Issues

### Issue 7: Command Configuration Validation Failures

#### Symptoms
- Error message: "❌ Конфігурація команди містить помилки"
- Commands fail before execution
- Configuration validation errors in logs

#### Diagnostic Steps
```bash
# Test configuration validation
python -c "
import asyncio
from modules.command_diagnostics import validate_command_configuration

async def test_config():
    for command in ['analyze', 'flares']:
        try:
            result = await validate_command_configuration(command)
            print(f'{command} config: {result}')
        except Exception as e:
            print(f'{command} config error: {e}')

asyncio.run(test_config())
"
```

#### Solutions

**Solution 1: Check Configuration Files**
```bash
# Verify configuration files exist
ls -la config/global/
ls -la config/modules/

# Validate JSON syntax
python -c "
import json
import os

config_files = [
    'config/global/global_config.json',
    'config/modules/gpt_config.json',
    'config/modules/screenshot_config.json'
]

for file_path in config_files:
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                json.load(f)
            print(f'✅ {file_path}: Valid JSON')
        except json.JSONDecodeError as e:
            print(f'❌ {file_path}: Invalid JSON - {e}')
    else:
        print(f'⚠️ {file_path}: File not found')
"
```

**Solution 2: Reset Configuration**
```bash
# Backup current configuration
cp -r config/ config_backup_$(date +%Y%m%d)/

# Regenerate default configuration
python scripts/generate_global_config.py --reset

# Restart the bot
sudo systemctl restart psychochauffeur-bot
```

## Emergency Recovery Procedures

### Complete Command System Recovery

```bash
# 1. Stop the bot
sudo systemctl stop psychochauffeur-bot

# 2. Backup current state
tar -czf command_fixes_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    modules/enhanced_*.py \
    modules/utils.py \
    modules/command_*.py \
    config/ \
    logs/

# 3. Verify enhanced command files
python -c "
import os
required_files = [
    'modules/enhanced_analyze_command.py',
    'modules/enhanced_flares_command.py',
    'modules/command_diagnostics.py',
    'modules/enhanced_error_diagnostics.py',
    'modules/command_help_messages.py'
]

for file_path in required_files:
    if os.path.exists(file_path):
        print(f'✅ {file_path}')
    else:
        print(f'❌ {file_path} - MISSING')
"

# 4. Test imports
python -c "
try:
    from modules.enhanced_analyze_command import enhanced_analyze_command
    from modules.enhanced_flares_command import enhanced_flares_command
    from modules.utils import DateParser, ScreenshotManager
    from modules.command_help_messages import CommandHelpMessages
    print('✅ All enhanced command imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
"

# 5. Start the bot
sudo systemctl start psychochauffeur-bot

# 6. Verify functionality
python -c "
import asyncio
from modules.utils import DateParser

# Test date parsing
test_dates = ['15-01-2024', '2024-01-15', '15/01/2024']
for date_str in test_dates:
    try:
        result = DateParser.parse_date(date_str)
        print(f'✅ {date_str} -> {result}')
    except Exception as e:
        print(f'❌ {date_str} -> {e}')
"
```

### Rollback Procedure

If the enhanced commands are causing issues, you can temporarily disable them:

```bash
# 1. Create fallback command handlers
cp modules/handlers/gpt_commands.py modules/handlers/gpt_commands_backup.py

# 2. Modify handler registration to use original commands
# Edit modules/handler_registry.py to use original analyze_command instead of enhanced_analyze_command

# 3. Restart the bot
sudo systemctl restart psychochauffeur-bot

# 4. Monitor for stability
tail -f logs/general.log | grep -E "(analyze|flares)"
```

## Prevention and Monitoring

### Automated Health Checks

```bash
# Create health check script for command fixes
cat > scripts/command_fixes_health_check.py << 'EOF'
#!/usr/bin/env python3
"""Health check script for command fixes functionality."""

import asyncio
import sys
from datetime import datetime

async def check_enhanced_commands():
    """Check if enhanced commands are working properly."""
    try:
        # Test imports
        from modules.enhanced_analyze_command import enhanced_analyze_command
        from modules.enhanced_flares_command import enhanced_flares_command
        from modules.utils import DateParser, ScreenshotManager
        from modules.command_help_messages import CommandHelpMessages
        
        # Test date parser
        test_date = DateParser.parse_date('15-01-2024')
        
        # Test screenshot manager
        manager = ScreenshotManager()
        tool_available = manager._check_wkhtmltoimage_availability()
        
        print(f"✅ Enhanced commands health check passed at {datetime.now()}")
        print(f"   - Date parser working: {test_date}")
        print(f"   - Screenshot tool available: {tool_available}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced commands health check failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(check_enhanced_commands())
    sys.exit(0 if success else 1)
EOF

chmod +x scripts/command_fixes_health_check.py

# Add to crontab for regular monitoring
# */15 * * * * /path/to/scripts/command_fixes_health_check.py >> /var/log/command_fixes_health.log 2>&1
```

### Log Monitoring Setup

```bash
# Monitor for command-specific errors
tail -f logs/error.log | grep -E "(analyze|flares|DateParser|ScreenshotManager)" | \
while read line; do
    echo "COMMAND ERROR: $line" | mail -s "Command Fixes Alert" admin@example.com
done &

# Monitor performance metrics
grep "command_performance_metric" logs/general.log | tail -20
```

## Getting Support

### Information to Collect for Support

When reporting issues with the enhanced commands, please collect:

1. **Command Details**
   - Exact command used
   - Expected vs actual behavior
   - Error messages received

2. **System Information**
   ```bash
   # Collect system info
   python --version
   which wkhtmltoimage
   wkhtmltoimage --version
   df -h python-web-screenshots/
   ```

3. **Log Excerpts**
   ```bash
   # Collect relevant logs
   grep -A5 -B5 "enhanced_analyze\|enhanced_flares" logs/error.log | tail -50
   grep "command_diagnostics" logs/general.log | tail -20
   ```

4. **Configuration Status**
   ```bash
   # Check configuration
   python scripts/command_fixes_health_check.py
   ls -la config/global/
   ```

### Contact Information

- **Primary Contact**: @vo1dee
- **Issue Tracking**: GitHub repository issues
- **Emergency**: Use the emergency recovery procedures above

---

*This troubleshooting guide is specific to the command fixes implementation and should be used alongside the main troubleshooting guide.*