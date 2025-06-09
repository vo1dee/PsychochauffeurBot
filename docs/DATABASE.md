# Database System Documentation

## Overview
The bot now uses PostgreSQL for message storage, replacing the previous logging system. This provides better data organization, querying capabilities, and scalability.

## Recent Changes
1. **Database Migration**
   - Implemented PostgreSQL database integration
   - Created three main tables: `chats`, `users`, and `messages`
   - Migrated existing chat logs to the new database structure
   - Added support for storing message metadata (commands, GPT replies, etc.)

2. **New Features**
   - Structured message storage with relationships between chats, users, and messages
   - Support for different chat types (private, group, channel)
   - Message metadata tracking (commands, timestamps, etc.)
   - Efficient querying capabilities

## Database Schema

### Tables

#### `chats`
```sql
CREATE TABLE chats (
    chat_id BIGINT PRIMARY KEY,
    chat_type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### `users`
```sql
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    first_name VARCHAR(255),
    username VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### `messages`
```sql
CREATE TABLE messages (
    message_id BIGINT,
    chat_id BIGINT REFERENCES chats(chat_id),
    user_id BIGINT REFERENCES users(user_id),
    timestamp TIMESTAMP WITH TIME ZONE,
    text TEXT,
    is_command BOOLEAN DEFAULT FALSE,
    command_name VARCHAR(255),
    is_gpt_reply BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, message_id)
);
```

## Database Cheat Sheet

### Basic Queries

#### Count Messages
```sql
-- Total messages
SELECT COUNT(*) FROM messages;

-- Messages per chat
SELECT c.chat_id, c.title, COUNT(*) as message_count 
FROM messages m 
JOIN chats c ON m.chat_id = c.chat_id 
GROUP BY c.chat_id, c.title;
```

#### Recent Messages
```sql
-- Latest 10 messages
SELECT m.timestamp, c.title, u.username, m.text 
FROM messages m 
JOIN chats c ON m.chat_id = c.chat_id 
JOIN users u ON m.user_id = u.user_id 
ORDER BY m.timestamp DESC 
LIMIT 10;
```

#### User Activity
```sql
-- Messages per user
SELECT u.username, COUNT(*) as message_count 
FROM messages m 
JOIN users u ON m.user_id = u.user_id 
GROUP BY u.username 
ORDER BY message_count DESC;
```

#### Command Usage
```sql
-- Most used commands
SELECT command_name, COUNT(*) as usage_count 
FROM messages 
WHERE is_command = true 
GROUP BY command_name 
ORDER BY usage_count DESC;
```

### Advanced Queries

#### Message Statistics
```sql
-- Messages per hour
SELECT 
    EXTRACT(HOUR FROM timestamp) as hour,
    COUNT(*) as message_count
FROM messages
GROUP BY hour
ORDER BY hour;
```

#### Chat Activity
```sql
-- Most active chats
SELECT 
    c.title,
    COUNT(*) as message_count,
    COUNT(DISTINCT m.user_id) as unique_users
FROM messages m
JOIN chats c ON m.chat_id = c.chat_id
GROUP BY c.title
ORDER BY message_count DESC;
```

#### User Engagement
```sql
-- User engagement by chat
SELECT 
    c.title as chat_name,
    u.username,
    COUNT(*) as message_count,
    MIN(m.timestamp) as first_message,
    MAX(m.timestamp) as last_message
FROM messages m
JOIN chats c ON m.chat_id = c.chat_id
JOIN users u ON m.user_id = u.user_id
GROUP BY c.title, u.username
ORDER BY message_count DESC;
```

## Maintenance

### Backup
```bash
# Create a backup
pg_dump -d telegram_bot > backup.sql

# Restore from backup
psql -d telegram_bot < backup.sql
```

### Monitoring
```sql
-- Check table sizes
SELECT 
    relname as table_name,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

## Troubleshooting

### Common Issues

1. **Connection Issues**
   - Check if PostgreSQL is running: `ps aux | grep postgres`
   - Verify database exists: `psql -l`
   - Check connection settings in `.env`

2. **Performance Issues**
   - Monitor table sizes
   - Check for missing indexes
   - Analyze query performance with `EXPLAIN ANALYZE`

### Useful Commands

```bash
# Connect to database
psql -d telegram_bot

# List all tables
\dt

# Describe table structure
\d table_name

# Show table contents
SELECT * FROM table_name LIMIT 5;
```

## Future Improvements

1. **Planned Features**
   - Message search functionality
   - Advanced analytics
   - Automated backups
   - Performance optimizations

2. **Potential Enhancements**
   - Message categories/tags
   - User roles and permissions
   - Message reactions tracking
   - Media message support

## Contributing

When making changes to the database:
1. Always backup before making changes
2. Test changes in a development environment
3. Document schema changes
4. Update this documentation

## Support

For database-related issues:
1. Check the logs in `logs/database.log`
2. Review recent changes in the migration scripts
3. Consult the PostgreSQL documentation
4. Contact the development team 