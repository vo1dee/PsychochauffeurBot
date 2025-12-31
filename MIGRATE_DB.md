# Database Migration Guide

## Problem
When you start using Docker for the database, it creates a **fresh, empty database** in a Docker volume. Your old database with existing messages is separate and not being used.

## Solutions

### Option 1: Migrate Data to Docker Database (Recommended)

This copies all your old messages to the Docker database:

```bash
# Run the migration script
python scripts/migrate_to_docker_db.py
```

The script will:
1. Ask for your old database connection details
2. Check if it can connect to both databases
3. Show you statistics (how many messages, date range)
4. Migrate all data (chats, users, messages) to Docker database

### Option 2: Use Your Old Database Instead

If you prefer to keep using your old database (not Docker), update your `.env` file:

```env
# Point to your old database instead of Docker
DB_HOST=your_old_db_host
DB_PORT=your_old_db_port
DB_NAME=your_old_db_name
DB_USER=your_old_db_user
DB_PASSWORD=your_old_db_password
```

Then stop Docker database:
```bash
docker-compose down
```

### Option 3: Manual Backup & Restore

If you prefer to do it manually:

```bash
# 1. Backup your old database
pg_dump -Fc -h OLD_HOST -U OLD_USER -d OLD_DB_NAME > backup.dump

# 2. Restore to Docker database
pg_restore -d postgresql://postgres:psychochauffeur@localhost:5432/telegram_bot -c backup.dump
```

## Finding Your Old Database

If you're not sure where your old database is:

1. **Check if PostgreSQL is running locally:**
   ```bash
   sudo systemctl status postgresql
   # or
   ps aux | grep postgres
   ```

2. **Check connection details in your old `.env` or config files**

3. **Check Docker volumes (if it was in Docker before):**
   ```bash
   docker volume ls
   docker volume inspect VOLUME_NAME
   ```

## Verify Migration

After migration, check that messages are there:

```bash
# Connect to Docker database
docker-compose exec postgres psql -U postgres -d telegram_bot

# Check message count
SELECT COUNT(*) FROM messages;

# Check date range
SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM messages;
```

Then test in your bot:
```
/analyze last 10 days
```

## Troubleshooting

### "Cannot connect to old database"
- Check if PostgreSQL is running: `sudo systemctl status postgresql`
- Verify connection details (host, port, user, password)
- Check firewall settings

### "Docker database connection failed"
- Make sure Docker database is running: `docker-compose ps`
- Check if port 5432 is available: `netstat -tuln | grep 5432`
- Verify Docker database is healthy: `docker-compose exec postgres pg_isready`

### "Migration is slow"
- This is normal for large databases
- The script shows progress
- Be patient, it processes messages in batches

## Important Notes

- **Backup first!** Always backup your old database before migration
- The migration uses `ON CONFLICT DO NOTHING` so it won't duplicate existing messages
- Docker database password is: `psychochauffeur` (as set in docker-compose.yml)
- Docker database is accessible at: `localhost:5432`
