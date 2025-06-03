# Database & Analysis Guide

## Recent Changes

### Database Schema Updates
- Added new tables and columns for message analysis
- Implemented timezone-aware timestamp handling (KYIV_TZ)
- Added user statistics tracking

### Analysis Features
- Added comprehensive message analysis functions:
  - `get_messages_for_chat_today`: Get today's messages
  - `get_last_n_messages_in_chat`: Get last N messages
  - `get_messages_for_chat_last_n_days`: Get messages from last N days
  - `get_messages_for_chat_date_period`: Get messages in date range
  - `get_messages_for_chat_single_date`: Get messages for specific date
  - `get_user_chat_stats`: Get user statistics

## Database Migration Guide

### 1. Backup Your Database
```bash
# For SQLite
cp your_database.db your_database.db.backup

# For PostgreSQL
pg_dump -U your_user your_database > backup.sql
```

### 2. Update Schema
```sql
-- Add timezone column if not exists
ALTER TABLE messages ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'Europe/Kyiv';

-- Add user statistics columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_messages INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_message_timestamp TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_message_timestamp TIMESTAMP WITH TIME ZONE;

-- Create index for faster message queries
CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user_chat ON messages(user_id, chat_id);
```

### 3. Update Existing Data
```sql
-- Update timezone for existing messages
UPDATE messages SET timezone = 'Europe/Kyiv' WHERE timezone IS NULL;

-- Update user statistics
UPDATE users u
SET total_messages = (
    SELECT COUNT(*) 
    FROM messages m 
    WHERE m.user_id = u.user_id
),
last_message_timestamp = (
    SELECT MAX(timestamp) 
    FROM messages m 
    WHERE m.user_id = u.user_id
),
first_message_timestamp = (
    SELECT MIN(timestamp) 
    FROM messages m 
    WHERE m.user_id = u.user_id
);
```

## Analysis Commands Cheatsheet

### Basic Analysis
| Command | Description | Example |
|---------|-------------|---------|
| `/analyze` | Analyze today's messages | `/analyze` |
| `/mystats` | Show your message statistics | `/mystats` |

### Advanced Analysis
| Command | Description | Example |
|---------|-------------|---------|
| `/analyze last N messages` | Analyze last N messages | `/analyze last 50 messages` |
| `/analyze last N days` | Analyze messages from last N days | `/analyze last 7 days` |
| `/analyze period YYYY-MM-DD YYYY-MM-DD` | Analyze messages in date range | `/analyze period 2024-01-01 2024-01-31` |
| `/analyze date YYYY-MM-DD` | Analyze messages for specific date | `/analyze date 2024-01-15` |

## User Statistics Details

The `/mystats` command shows:
- Total messages sent
- Messages in the last 7 days
- Most active hour
- Command usage statistics
- First message date

## Database Queries Reference

### Get Today's Messages
```sql
SELECT m.timestamp, u.username, m.text
FROM messages m
JOIN users u ON m.user_id = u.user_id
WHERE m.chat_id = $1
AND DATE(m.timestamp AT TIME ZONE m.timezone) = CURRENT_DATE
ORDER BY m.timestamp;
```

### Get Last N Messages
```sql
SELECT m.timestamp, u.username, m.text
FROM messages m
JOIN users u ON m.user_id = u.user_id
WHERE m.chat_id = $1
ORDER BY m.timestamp DESC
LIMIT $2;
```

### Get User Statistics
```sql
SELECT 
    COUNT(*) as total_messages,
    COUNT(CASE WHEN timestamp > NOW() - INTERVAL '7 days' THEN 1 END) as messages_last_week,
    EXTRACT(HOUR FROM timestamp AT TIME ZONE timezone) as hour,
    COUNT(*) as hour_count
FROM messages
WHERE chat_id = $1 AND user_id = $2
GROUP BY EXTRACT(HOUR FROM timestamp AT TIME ZONE timezone)
ORDER BY hour_count DESC
LIMIT 1;
```

## Troubleshooting

### Common Issues

1. **Timezone Issues**
   - Check if messages have correct timezone
   - Verify KYIV_TZ constant is set correctly
   - Run timezone update query if needed

2. **Missing Statistics**
   - Run user statistics update query
   - Check if indexes are created
   - Verify user and message tables are properly linked

3. **Slow Queries**
   - Ensure indexes are created
   - Check if timezone conversion is optimized
   - Monitor query execution time

### Maintenance Queries

```sql
-- Check for messages without timezone
SELECT COUNT(*) FROM messages WHERE timezone IS NULL;

-- Check for users without statistics
SELECT user_id FROM users 
WHERE total_messages IS NULL 
   OR last_message_timestamp IS NULL 
   OR first_message_timestamp IS NULL;

-- Rebuild statistics for specific user
UPDATE users u
SET total_messages = (
    SELECT COUNT(*) FROM messages m WHERE m.user_id = u.user_id
)
WHERE user_id = $1;
``` 