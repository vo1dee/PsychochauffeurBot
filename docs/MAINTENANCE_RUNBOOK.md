# PsychoChauffeur Bot - Maintenance and Operations Runbook

This runbook provides comprehensive guidance for maintaining, troubleshooting, and operating the PsychoChauffeur Bot in production environments.

## Table of Contents
1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Monitoring and Alerts](#monitoring-and-alerts)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Maintenance Procedures](#maintenance-procedures)
6. [Emergency Procedures](#emergency-procedures)
7. [Performance Optimization](#performance-optimization)
8. [Security Operations](#security-operations)

## System Overview

### Architecture Components
- **Main Application**: `main.py` - Core bot logic and message handling
- **Database Layer**: PostgreSQL with asyncpg connection pooling
- **Configuration System**: Hierarchical config management (global/chat/user)
- **External Services**: OpenAI GPT, Weather APIs, Video downloaders
- **Monitoring**: Performance monitoring and error tracking
- **Logging**: Structured logging with multiple handlers

### Key Dependencies
- Python 3.10+
- PostgreSQL 12+
- Redis (optional, for caching)
- External APIs (OpenAI, Weather services)

### File Structure
```
├── main.py                 # Main application entry point
├── modules/               # Core functionality modules
├── config/               # Configuration management
├── tests/                # Test suites
├── scripts/              # Utility and maintenance scripts
├── docs/                 # Documentation
└── logs/                 # Application logs
```

## Daily Operations

### Morning Checklist (5 minutes)
1. **Check System Health**
   ```bash
   python scripts/health_check.py
   ```

2. **Review Error Logs**
   ```bash
   tail -n 100 logs/error.log | grep -E "(ERROR|CRITICAL)"
   ```

3. **Monitor Resource Usage**
   ```bash
   python scripts/simple_performance_test.py --quick
   ```

4. **Verify External Services**
   - OpenAI API status
   - Weather service availability
   - Database connectivity

### Weekly Tasks (30 minutes)
1. **Database Maintenance**
   ```bash
   python scripts/migrate_db.py --check
   python scripts/truncate_tables.py --old-data
   ```

2. **Log Rotation and Cleanup**
   ```bash
   find logs/ -name "*.log" -mtime +7 -delete
   ```

3. **Performance Review**
   ```bash
   python scripts/simple_performance_test.py --full-report
   ```

4. **Security Scan**
   ```bash
   python scripts/security_audit.py --quick-scan
   ```

### Monthly Tasks (2 hours)
1. **Comprehensive Security Audit**
   ```bash
   python scripts/security_audit.py
   ```

2. **Full Performance Analysis**
   ```bash
   python scripts/performance_testing.py
   ```

3. **Database Optimization**
   ```bash
   python scripts/migrate_db.py --optimize
   ```

4. **Configuration Review**
   - Review and update global configurations
   - Clean up unused chat configurations
   - Validate API keys and tokens

## Monitoring and Alerts

### Key Metrics to Monitor

#### System Health Metrics
- **CPU Usage**: Should stay below 70%
- **Memory Usage**: Should stay below 80%
- **Disk Space**: Should have at least 20% free
- **Database Connections**: Monitor pool utilization

#### Application Metrics
- **Response Time**: 95th percentile should be < 2 seconds
- **Error Rate**: Should be < 1%
- **Message Processing Rate**: Monitor throughput
- **External API Response Times**: Track service dependencies

#### Business Metrics
- **Active Users**: Daily/weekly active user counts
- **Command Usage**: Most popular commands and features
- **Error Categories**: Types of errors occurring

### Alert Thresholds

#### Critical Alerts (Immediate Response Required)
- Application down/unresponsive
- Database connection failures
- Memory usage > 90%
- Error rate > 5%
- External API failures > 50%

#### Warning Alerts (Response Within 1 Hour)
- CPU usage > 80%
- Memory usage > 80%
- Response time > 5 seconds
- Error rate > 2%
- Disk space < 30%

#### Info Alerts (Daily Review)
- High command usage
- New error patterns
- Performance degradation trends

### Monitoring Commands
```bash
# Check application status
python scripts/health_check.py

# Monitor real-time logs
tail -f logs/general.log

# Check database status
python -c "from modules.database import Database; import asyncio; asyncio.run(Database.get_database_stats())"

# Monitor performance
python scripts/simple_performance_test.py --monitor
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Bot Not Responding
**Symptoms**: No response to commands, webhook timeouts
**Diagnosis**:
```bash
# Check if process is running
ps aux | grep python | grep main.py

# Check logs for errors
tail -n 50 logs/error.log

# Test bot token
python -c "from telegram import Bot; import asyncio; bot = Bot('YOUR_TOKEN'); print(asyncio.run(bot.get_me()))"
```

**Solutions**:
- Restart the application
- Check network connectivity
- Verify bot token validity
- Check Telegram API status

#### 2. Database Connection Issues
**Symptoms**: Database errors in logs, data not persisting
**Diagnosis**:
```bash
# Test database connection
python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://user:pass@host/db'))"

# Check database logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

**Solutions**:
- Restart database service
- Check connection parameters
- Verify database user permissions
- Check disk space on database server

#### 3. High Memory Usage
**Symptoms**: Memory alerts, slow performance, OOM errors
**Diagnosis**:
```bash
# Check memory usage
python scripts/simple_performance_test.py --memory-profile

# Monitor memory in real-time
watch -n 5 'ps aux | grep python | grep main.py'
```

**Solutions**:
- Restart application to clear memory leaks
- Review recent code changes
- Check for memory-intensive operations
- Implement garbage collection tuning

#### 4. External API Failures
**Symptoms**: GPT/Weather commands failing, API error messages
**Diagnosis**:
```bash
# Test OpenAI API
python -c "import openai; openai.api_key='YOUR_KEY'; print(openai.Model.list())"

# Test weather API
curl "http://api.openweathermap.org/data/2.5/weather?q=London&appid=YOUR_KEY"
```

**Solutions**:
- Check API key validity
- Verify API quotas and limits
- Implement fallback mechanisms
- Contact API provider if needed

#### 5. Performance Degradation
**Symptoms**: Slow response times, timeouts, high CPU usage
**Diagnosis**:
```bash
# Run performance analysis
python scripts/performance_testing.py

# Check database query performance
python scripts/migrate_db.py --analyze-queries
```

**Solutions**:
- Optimize database queries
- Implement caching strategies
- Review recent code changes
- Scale resources if needed

### Error Code Reference

#### Database Errors
- `DB001`: Connection timeout - Check database availability
- `DB002`: Query timeout - Optimize slow queries
- `DB003`: Connection pool exhausted - Increase pool size
- `DB004`: Deadlock detected - Review transaction logic

#### API Errors
- `API001`: Rate limit exceeded - Implement backoff strategy
- `API002`: Authentication failed - Check API keys
- `API003`: Service unavailable - Implement fallback
- `API004`: Quota exceeded - Monitor usage limits

#### Application Errors
- `APP001`: Configuration error - Validate config files
- `APP002`: Module import error - Check dependencies
- `APP003`: Permission denied - Check file permissions
- `APP004`: Resource exhausted - Scale resources

## Maintenance Procedures

### Application Updates

#### 1. Pre-Update Checklist
- [ ] Backup database
- [ ] Review changelog
- [ ] Test in staging environment
- [ ] Schedule maintenance window
- [ ] Notify users if needed

#### 2. Update Process
```bash
# 1. Stop the application
sudo systemctl stop psychochauffeur-bot

# 2. Backup current version
cp -r /opt/psychochauffeur-bot /opt/psychochauffeur-bot.backup

# 3. Pull latest changes
cd /opt/psychochauffeur-bot
git pull origin main

# 4. Update dependencies
pip install -r requirements.txt

# 5. Run database migrations
python scripts/migrate_db.py

# 6. Run tests
python -m pytest tests/ -v

# 7. Start the application
sudo systemctl start psychochauffeur-bot

# 8. Verify functionality
python scripts/health_check.py
```

#### 3. Rollback Process
```bash
# 1. Stop the application
sudo systemctl stop psychochauffeur-bot

# 2. Restore backup
rm -rf /opt/psychochauffeur-bot
mv /opt/psychochauffeur-bot.backup /opt/psychochauffeur-bot

# 3. Restore database if needed
# (Follow database backup restoration procedure)

# 4. Start the application
sudo systemctl start psychochauffeur-bot
```

### Database Maintenance

#### Regular Maintenance Tasks
```bash
# Vacuum and analyze tables
python scripts/migrate_db.py --vacuum

# Update table statistics
python scripts/migrate_db.py --analyze

# Check for index usage
python scripts/migrate_db.py --index-analysis

# Clean up old data
python scripts/truncate_tables.py --older-than 30d
```

#### Backup Procedures
```bash
# Daily backup
pg_dump psychochauffeur_bot > backup_$(date +%Y%m%d).sql

# Weekly full backup with compression
pg_dump -Fc psychochauffeur_bot > backup_weekly_$(date +%Y%m%d).dump

# Verify backup integrity
pg_restore --list backup_weekly_$(date +%Y%m%d).dump
```

### Log Management

#### Log Rotation Configuration
```bash
# /etc/logrotate.d/psychochauffeur-bot
/opt/psychochauffeur-bot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 psychochauffeur psychochauffeur
    postrotate
        systemctl reload psychochauffeur-bot
    endscript
}
```

#### Log Analysis
```bash
# Find error patterns
grep -E "(ERROR|CRITICAL)" logs/*.log | sort | uniq -c | sort -nr

# Monitor specific user issues
grep "user_id:12345" logs/chat.log

# Analyze performance issues
grep "slow_query" logs/general.log | tail -20
```

## Emergency Procedures

### Service Outage Response

#### Immediate Actions (0-5 minutes)
1. **Assess Impact**
   - Check if bot is completely down or partially functional
   - Identify affected users/chats
   - Determine root cause category

2. **Initial Response**
   ```bash
   # Quick restart attempt
   sudo systemctl restart psychochauffeur-bot
   
   # Check immediate status
   python scripts/health_check.py
   ```

3. **Communication**
   - Post status update in monitoring channel
   - Notify stakeholders if widespread impact

#### Investigation Phase (5-15 minutes)
1. **Gather Information**
   ```bash
   # Check recent logs
   tail -n 200 logs/error.log
   
   # Check system resources
   top -p $(pgrep -f main.py)
   
   # Check database status
   python -c "from modules.database import Database; import asyncio; print(asyncio.run(Database.get_database_stats()))"
   ```

2. **Identify Root Cause**
   - Review recent changes
   - Check external service status
   - Analyze error patterns

#### Resolution Phase (15+ minutes)
1. **Apply Fix**
   - Implement immediate workaround if available
   - Apply permanent fix if identified
   - Consider rollback if recent deployment caused issue

2. **Verify Resolution**
   ```bash
   # Test core functionality
   python scripts/health_check.py --comprehensive
   
   # Monitor for 10 minutes
   watch -n 30 'python scripts/health_check.py'
   ```

3. **Post-Incident**
   - Document incident and resolution
   - Update monitoring/alerting if needed
   - Schedule post-mortem if significant impact

### Data Recovery Procedures

#### Database Recovery
```bash
# Restore from latest backup
pg_restore -d psychochauffeur_bot backup_latest.dump

# Restore specific tables
pg_restore -d psychochauffeur_bot -t messages backup_latest.dump

# Point-in-time recovery (if WAL archiving enabled)
pg_restore -d psychochauffeur_bot -T "2025-07-16 10:00:00" backup_base.dump
```

#### Configuration Recovery
```bash
# Restore configuration from backup
cp config_backup/global_config.json config/global/global_config.json

# Regenerate default configurations
python scripts/generate_global_config.py --reset
```

## Performance Optimization

### Database Optimization

#### Query Optimization
```sql
-- Identify slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats 
WHERE schemaname = 'public' 
ORDER BY n_distinct DESC;
```

#### Index Management
```bash
# Analyze index usage
python scripts/migrate_db.py --index-analysis

# Create missing indexes
python scripts/migrate_db.py --create-indexes

# Remove unused indexes
python scripts/migrate_db.py --cleanup-indexes
```

### Application Optimization

#### Memory Optimization
```python
# Monitor memory usage
import gc
import psutil

def monitor_memory():
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"RSS: {memory_info.rss / 1024 / 1024:.1f}MB")
    print(f"VMS: {memory_info.vms / 1024 / 1024:.1f}MB")
    print(f"GC objects: {len(gc.get_objects())}")
```

#### Caching Strategies
```python
# Implement Redis caching
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(key: str, data: dict, ttl: int = 3600):
    redis_client.setex(key, ttl, json.dumps(data))

def get_cached_result(key: str) -> dict:
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None
```

## Security Operations

### Security Monitoring

#### Daily Security Checks
```bash
# Check for failed authentication attempts
grep "authentication failed" logs/*.log | wc -l

# Monitor suspicious activity
grep -E "(injection|exploit|attack)" logs/*.log

# Check file integrity
find . -name "*.py" -newer /tmp/last_check -ls
```

#### Security Incident Response
1. **Immediate Actions**
   - Isolate affected systems
   - Preserve evidence
   - Assess impact scope

2. **Investigation**
   - Analyze logs for attack vectors
   - Check for data compromise
   - Identify affected users

3. **Remediation**
   - Apply security patches
   - Update access controls
   - Notify affected parties if required

### Access Control Management

#### User Access Review
```bash
# Review admin users
python -c "from modules.user_management import get_admin_users; print(get_admin_users())"

# Check API key usage
grep "api_key" logs/*.log | grep -v "SUCCESS" | tail -20
```

#### Security Hardening
```bash
# Update file permissions
find . -name "*.py" -exec chmod 644 {} \;
find . -name "*.sh" -exec chmod 755 {} \;

# Secure configuration files
chmod 600 config/private/*
chmod 600 .env
```

## Contact Information

### Escalation Matrix
- **Level 1**: On-call engineer (immediate response)
- **Level 2**: Senior engineer (within 1 hour)
- **Level 3**: Engineering manager (within 4 hours)
- **Level 4**: CTO (critical incidents only)

### External Contacts
- **Telegram Support**: @BotSupport
- **OpenAI Support**: platform.openai.com/support
- **Database Vendor**: [Database support contact]
- **Hosting Provider**: [Cloud provider support]

---

*This runbook should be reviewed and updated monthly to ensure accuracy and completeness.*