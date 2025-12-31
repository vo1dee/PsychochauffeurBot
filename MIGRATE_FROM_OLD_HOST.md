# Migrate Database from Old Host to New Machine

This guide shows you how to extract 167,639 messages from the old host and migrate them to your new machine.

## Option 1: Direct Migration (Recommended - if you can connect from new machine to old host)

If your new machine can connect to the old host's database:

```bash
# On NEW machine, run the migration script
cd ~/psychochauffeurbot
source venv/bin/activate
python3 scripts/migrate_to_docker_db.py
```

The script will:
1. Ask for old host connection details
2. Connect to both databases
3. Show statistics
4. Migrate all data directly

**Old host details:**
- Host: `instance-20241026-1717` (or its IP address)
- Port: `5432`
- Database: `telegram_bot`
- User: `postgres`
- Password: `psychochauffeur`

## Option 2: Backup & Restore (if direct connection not possible)

### Step 1: Create backup on OLD host

```bash
# SSH to old host
ssh ubuntu@instance-20241026-1717

# On old host, create backup
cd ~/psychochauffeurbot
PGPASSWORD=psychochauffeur pg_dump -h localhost -U postgres -d telegram_bot -Fc -f telegram_bot_backup.dump

# Check backup size (should be ~50-100MB)
ls -lh telegram_bot_backup.dump
```

### Step 2: Transfer backup to NEW machine

```bash
# From NEW machine, copy backup from old host
scp ubuntu@instance-20241026-1717:~/psychochauffeurbot/telegram_bot_backup.dump ./

# Or if you're on old host, copy it to new machine
# scp telegram_bot_backup.dump user@new-machine:~/psychochauffeurbot/
```

### Step 3: Restore on NEW machine

```bash
# On NEW machine
cd ~/psychochauffeurbot
source venv/bin/activate

# Restore backup
PGPASSWORD=psychochauffeur pg_restore -h localhost -U postgres -d telegram_bot -c --if-exists telegram_bot_backup.dump
```

### Step 4: Verify migration

```bash
# Check message count
source venv/bin/activate && python3 scripts/count_all_messages.py
```

You should see **167,639 messages**!

## Option 3: Using the shell script

I've created a helper script:

```bash
# Make it executable
chmod +x scripts/migrate_from_old_host.sh

# Run it (replace OLD_HOST_IP with actual IP or hostname)
./scripts/migrate_from_old_host.sh OLD_HOST_IP
```

## Troubleshooting

### "pg_dump: command not found"
Install PostgreSQL client tools:
```bash
sudo apt-get update
sudo apt-get install postgresql-client
```

### "Connection refused"
- Check if PostgreSQL is running on old host: `sudo systemctl status postgresql`
- Check firewall rules
- Verify PostgreSQL allows remote connections in `/etc/postgresql/*/main/pg_hba.conf`

### "Permission denied"
- Make sure you have read access to database
- Check PostgreSQL user permissions

### "Database already exists"
The restore will skip existing data due to `ON CONFLICT` clauses, so it's safe to run multiple times.

## Expected Results

After migration, you should have:
- **167,639 total messages**
- **Date range**: 2023-12-30 to 2025-12-30
- **Table size**: ~124 MB
- All chats and users migrated

Run the count script to verify:
```bash
source venv/bin/activate && python3 scripts/count_all_messages.py
```
