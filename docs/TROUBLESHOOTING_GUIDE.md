# PsychoChauffeur Bot - Troubleshooting Guide

This guide provides step-by-step troubleshooting procedures for common issues encountered with the PsychoChauffeur Bot.

## Quick Diagnostic Commands

### System Health Check
```bash
# Comprehensive health check
python scripts/health_check.py

# Quick status check
python scripts/smoke_tests.py

# Performance check
python scripts/simple_performance_test.py --quick
```

### Log Analysis
```bash
# View recent errors
tail -n 50 logs/error.log

# Search for specific issues
grep -i "error\|exception\|failed" logs/general.log | tail -20

# Monitor real-time logs
tail -f logs/general.log
```

## Common Issues and Solutions

### 1. Bot Not Responding to Commands

#### Symptoms
- Commands receive no response
- Bot appears offline
- Webhook timeouts

#### Diagnostic Steps
```bash
# 1. Check if bot process is running
ps aux | grep -E "python.*main.py"

# 2. Check bot token validity
python -c "
from telegram import Bot
import asyncio
from modules.const import Config
bot = Bot(Config.TELEGRAM_BOT_TOKEN)
try:
    result = asyncio.run(bot.get_me())
    print(f'Bot is valid: {result.username}')
except Exception as e:
    print(f'Bot token error: {e}')
"

# 3. Check network connectivity
curl -s https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe

# 4. Check recent error logs
tail -n 100 logs/error.log | grep -E "(ERROR|CRITICAL)"
```

#### Solutions

**Solution 1: Restart the Bot**
```bash
# If running as systemd service
sudo systemctl restart psychochauffeur-bot
sudo systemctl status psychochauffeur-bot

# If running manually
pkill -f "python.*main.py"
python main.py
```

**Solution 2: Fix Configuration Issues**
```bash
# Check environment variables
python -c "
import os
required_vars = ['TELEGRAM_BOT_TOKEN', 'DB_HOST', 'DB_NAME']
for var in required_vars:
    value = os.getenv(var)
    print(f'{var}: {\"SET\" if value else \"MISSING\"}')
"

# Validate configuration
python -c "
from config.config_manager import ConfigManager
import asyncio
cm = ConfigManager()
try:
    asyncio.run(cm.initialize())
    print('Configuration is valid')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

**Solution 3: Check External Dependencies**
```bash
# Test database connection
python -c "
from modules.database import Database
import asyncio
try:
    asyncio.run(Database.initialize())
    print('Database connection successful')
except Exception as e:
    print(f'Database error: {e}')
"

# Test OpenAI API
python -c "
import openai
from modules.const import Config
openai.api_key = Config.OPENAI_API_KEY
try:
    models = openai.Model.list()
    print('OpenAI API connection successful')
except Exception as e:
    print(f'OpenAI API error: {e}')
"
```

### 2. Database Connection Issues

#### Symptoms
- Database connection errors in logs
- Data not persisting
- Timeout errors

#### Diagnostic Steps
```bash
# 1. Check database service status
sudo systemctl status postgresql

# 2. Test direct connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT version();"

# 3. Check connection pool status
python -c "
from modules.database import Database
import asyncio
try:
    stats = asyncio.run(Database.get_database_stats())
    print(f'Connection stats: {stats}')
except Exception as e:
    print(f'Database stats error: {e}')
"

# 4. Check database logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

#### Solutions

**Solution 1: Restart Database Service**
```bash
sudo systemctl restart postgresql
sudo systemctl status postgresql
```

**Solution 2: Fix Connection Parameters**
```bash
# Check .env file
cat .env | grep -E "DB_|DATABASE_"

# Test with correct parameters
python -c "
import asyncpg
import asyncio
import os

async def test_connection():
    try:
        conn = await asyncpg.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'telegram_bot'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '')
        )
        await conn.close()
        print('Database connection successful')
    except Exception as e:
        print(f'Connection failed: {e}')

asyncio.run(test_connection())
"
```

**Solution 3: Database Recovery**
```bash
# Check database disk space
df -h /var/lib/postgresql/

# Check for corrupted tables
python scripts/migrate_db.py --check-integrity

# Repair if needed
python scripts/migrate_db.py --repair
```

### 3. High Memory Usage

#### Symptoms
- Memory usage alerts
- Slow performance
- Out of memory errors

#### Diagnostic Steps
```bash
# 1. Check current memory usage
python -c "
import psutil
process = psutil.Process()
memory_info = process.memory_info()
print(f'RSS: {memory_info.rss / 1024 / 1024:.1f}MB')
print(f'VMS: {memory_info.vms / 1024 / 1024:.1f}MB')
print(f'Memory percent: {process.memory_percent():.1f}%')
"

# 2. Monitor memory over time
python scripts/simple_performance_test.py --memory-profile

# 3. Check for memory leaks
python -c "
import gc
import sys
print(f'Objects in memory: {len(gc.get_objects())}')
print(f'Reference count: {sys.gettotalrefcount()}')
gc.collect()
print(f'After GC: {len(gc.get_objects())}')
"
```

#### Solutions

**Solution 1: Restart Application**
```bash
# Graceful restart
sudo systemctl restart psychochauffeur-bot

# Force restart if needed
pkill -9 -f "python.*main.py"
python main.py
```

**Solution 2: Memory Optimization**
```bash
# Enable garbage collection debugging
python -c "
import gc
gc.set_debug(gc.DEBUG_STATS)
gc.collect()
"

# Check for circular references
python -c "
import gc
import collections
counter = collections.Counter()
for obj in gc.get_objects():
    counter[type(obj).__name__] += 1
for obj_type, count in counter.most_common(10):
    print(f'{obj_type}: {count}')
"
```

**Solution 3: Configuration Tuning**
```python
# Add to main.py or configuration
import gc
import os

# Tune garbage collection
gc.set_threshold(700, 10, 10)

# Set memory limits
import resource
resource.setrlimit(resource.RLIMIT_AS, (1024*1024*1024, 1024*1024*1024))  # 1GB limit
```

### 4. External API Failures

#### Symptoms
- GPT commands not working
- Weather commands failing
- Video download errors

#### Diagnostic Steps
```bash
# 1. Test OpenAI API
python -c "
import openai
from modules.const import Config
openai.api_key = Config.OPENAI_API_KEY
try:
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': 'test'}],
        max_tokens=10
    )
    print('OpenAI API working')
except Exception as e:
    print(f'OpenAI API error: {e}')
"

# 2. Test Weather API
curl -s "http://api.openweathermap.org/data/2.5/weather?q=London&appid=$WEATHER_API_KEY"

# 3. Test video download
python -c "
from modules.video_downloader import VideoDownloader
import asyncio
vd = VideoDownloader()
try:
    result = asyncio.run(vd.test_connection())
    print(f'Video downloader: {result}')
except Exception as e:
    print(f'Video downloader error: {e}')
"
```

#### Solutions

**Solution 1: Check API Keys**
```bash
# Verify API keys are set
python -c "
import os
apis = {
    'OpenAI': os.getenv('OPENAI_API_KEY'),
    'Weather': os.getenv('WEATHER_API_KEY'),
    'Telegram': os.getenv('TELEGRAM_BOT_TOKEN')
}
for name, key in apis.items():
    status = 'SET' if key and len(key) > 10 else 'MISSING/INVALID'
    print(f'{name}: {status}')
"

# Update API keys if needed
echo "OPENAI_API_KEY=your_new_key" >> .env
```

**Solution 2: Implement Fallback Mechanisms**
```python
# Add to modules/gpt.py
async def gpt_with_fallback(prompt: str):
    try:
        return await openai_request(prompt)
    except openai.RateLimitError:
        await asyncio.sleep(60)  # Wait and retry
        return await openai_request(prompt)
    except openai.APIError:
        return "Sorry, AI service is temporarily unavailable."
```

**Solution 3: Monitor API Usage**
```bash
# Check API usage patterns
grep "openai\|weather\|video" logs/general.log | tail -50

# Monitor rate limits
grep -i "rate.limit\|quota" logs/error.log
```

### 5. Performance Issues

#### Symptoms
- Slow response times
- High CPU usage
- Timeouts

#### Diagnostic Steps
```bash
# 1. Run performance test
python scripts/simple_performance_test.py

# 2. Check CPU usage
top -p $(pgrep -f "python.*main.py")

# 3. Profile slow operations
python -c "
import cProfile
import pstats
from modules.gpt import gpt_response
# Profile specific functions
"

# 4. Check database performance
python scripts/migrate_db.py --analyze-performance
```

#### Solutions

**Solution 1: Database Optimization**
```bash
# Analyze slow queries
python -c "
import asyncio
from modules.database import Database

async def analyze_queries():
    async with Database.get_connection() as conn:
        slow_queries = await conn.fetch('''
            SELECT query, mean_time, calls 
            FROM pg_stat_statements 
            WHERE mean_time > 1000 
            ORDER BY mean_time DESC 
            LIMIT 10
        ''')
        for query in slow_queries:
            print(f'Query: {query[\"query\"][:100]}...')
            print(f'Mean time: {query[\"mean_time\"]:.2f}ms')
            print(f'Calls: {query[\"calls\"]}')
            print('---')

asyncio.run(analyze_queries())
"

# Create missing indexes
python scripts/migrate_db.py --create-indexes
```

**Solution 2: Code Optimization**
```python
# Add async optimizations
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Use thread pool for CPU-intensive tasks
executor = ThreadPoolExecutor(max_workers=4)

async def cpu_intensive_task():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, blocking_function)
```

**Solution 3: Caching Implementation**
```python
# Add caching to frequently accessed data
from functools import lru_cache
import asyncio

@lru_cache(maxsize=128)
def cached_function(param):
    # Expensive operation
    return result

# Async caching
cache = {}
async def async_cached_function(param):
    if param in cache:
        return cache[param]
    result = await expensive_async_operation(param)
    cache[param] = result
    return result
```

### 6. Configuration Issues

#### Symptoms
- Bot behaving unexpectedly
- Features not working
- Permission errors

#### Diagnostic Steps
```bash
# 1. Validate configuration
python -c "
from config.config_manager import ConfigManager
import asyncio
import json

async def check_config():
    cm = ConfigManager()
    await cm.initialize()
    
    # Check global config
    global_config = await cm._load_global_config()
    print('Global config loaded successfully')
    
    # Check template
    template = await cm._load_template()
    print('Template loaded successfully')
    
    # Validate structure
    required_keys = ['config_modules', 'default_settings']
    for key in required_keys:
        if key not in global_config:
            print(f'Missing key: {key}')
        else:
            print(f'Key {key}: OK')

asyncio.run(check_config())
"

# 2. Check file permissions
ls -la config/
ls -la config/global/
ls -la .env
```

#### Solutions

**Solution 1: Reset Configuration**
```bash
# Backup current config
cp -r config/ config_backup_$(date +%Y%m%d)/

# Regenerate default configuration
python scripts/generate_global_config.py --reset

# Restore custom settings
python scripts/migrate_configs.py --merge config_backup_*/
```

**Solution 2: Fix Permissions**
```bash
# Set correct permissions
chmod 644 config/global/*.json
chmod 600 .env
chmod 755 config/
chown -R $USER:$USER config/
```

**Solution 3: Validate JSON Files**
```bash
# Check JSON syntax
python -c "
import json
import os

config_files = [
    'config/global/global_config.json',
    'config/global/system_defaults.json'
]

for file_path in config_files:
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                json.load(f)
            print(f'{file_path}: Valid JSON')
        except json.JSONDecodeError as e:
            print(f'{file_path}: Invalid JSON - {e}')
    else:
        print(f'{file_path}: File not found')
"
```

## Advanced Troubleshooting

### Debug Mode Activation
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py

# Or modify logging configuration
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Run specific operations
"
```

### Memory Profiling
```python
# Install memory profiler
pip install memory-profiler

# Profile specific functions
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Your code here
    pass

# Run with: python -m memory_profiler your_script.py
```

### Network Debugging
```bash
# Monitor network connections
netstat -tulpn | grep python

# Check DNS resolution
nslookup api.telegram.org
nslookup api.openai.com

# Test connectivity
telnet api.telegram.org 443
```

### Database Debugging
```sql
-- Check active connections
SELECT * FROM pg_stat_activity WHERE datname = 'telegram_bot';

-- Check locks
SELECT * FROM pg_locks WHERE NOT granted;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Emergency Procedures

### Complete System Recovery
```bash
# 1. Stop all services
sudo systemctl stop psychochauffeur-bot

# 2. Backup current state
tar -czf emergency_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    config/ logs/ .env

# 3. Restore from known good backup
# (Follow backup restoration procedures)

# 4. Start services
sudo systemctl start psychochauffeur-bot

# 5. Verify functionality
python scripts/health_check.py --comprehensive
```

### Data Recovery
```bash
# Database recovery
pg_restore -d telegram_bot backup_latest.dump

# Configuration recovery
cp config_backup/global_config.json config/global/

# Log analysis for data loss
grep -E "DELETE|DROP|TRUNCATE" logs/*.log
```

## Prevention Strategies

### Monitoring Setup
```bash
# Set up log monitoring
tail -f logs/error.log | grep -E "(ERROR|CRITICAL)" | \
while read line; do
    echo "ALERT: $line" | mail -s "Bot Error Alert" admin@example.com
done

# Resource monitoring
while true; do
    python scripts/simple_performance_test.py --quick >> monitoring.log
    sleep 300  # Check every 5 minutes
done
```

### Automated Health Checks
```bash
# Add to crontab
# */5 * * * * /path/to/health_check.sh

#!/bin/bash
# health_check.sh
cd /opt/psychochauffeur-bot
if ! python scripts/health_check.py --quiet; then
    echo "Health check failed at $(date)" | \
    mail -s "Bot Health Alert" admin@example.com
fi
```

### Backup Automation
```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
pg_dump telegram_bot > /backups/db_backup_$DATE.sql
tar -czf /backups/config_backup_$DATE.tar.gz config/
find /backups -name "*.sql" -mtime +7 -delete
find /backups -name "*.tar.gz" -mtime +7 -delete
```

## Getting Help

### Log Collection for Support
```bash
# Collect relevant logs
mkdir support_logs_$(date +%Y%m%d)
cp logs/error.log support_logs_*/
cp logs/general.log support_logs_*/
python scripts/health_check.py > support_logs_*/health_check.txt
python scripts/simple_performance_test.py > support_logs_*/performance.txt
tar -czf support_logs_$(date +%Y%m%d).tar.gz support_logs_*/
```

### Information to Include in Support Requests
1. **System Information**
   - Operating system and version
   - Python version
   - Bot version/commit hash

2. **Error Details**
   - Exact error messages
   - Steps to reproduce
   - When the issue started

3. **Environment**
   - Configuration changes
   - Recent updates
   - External service status

4. **Logs**
   - Relevant log excerpts
   - Health check output
   - Performance test results

---

*This troubleshooting guide should be updated as new issues are discovered and resolved.*