# 🐳 Docker Setup Guide for PsychochauffeurBot

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# 1. Start the database
./start.sh

# 2. Start the bot
source .venv/bin/activate && python main.py
```

### Option 2: Manual Docker Setup

```bash
# Start PostgreSQL database
docker-compose up -d postgres

# Wait for it to be ready, then start your bot
source .venv/bin/activate && python main.py
```

### Option 3: Full Docker Setup (Bot + Database)

```bash
# Enable the bot service in docker-compose.yml by uncommenting it, then:
docker-compose up --build
```

## 📋 What Gets Created Automatically

When you run `docker-compose up`, the following happens automatically:

✅ **PostgreSQL Database**
- Container: `postgres:15`
- Database: `telegram_bot`
- User: `postgres` with password `psychochauffeur`
- Port: `5432` (mapped to host)

✅ **Database Schema** (via `init-db.sql`)
- All necessary tables for your bot
- Proper indexes and constraints
- Text search extensions

✅ **Health Checks**
- Database readiness verification
- Automatic retry logic

## 🔧 Configuration

### Environment Variables (.env)

Your `.env` file is already configured with:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=telegram_bot
DB_USER=postgres
DB_PASSWORD=psychochauffeur

# Your bot tokens and API keys are already set
```

### Docker Configuration

The `docker-compose.yml` includes:
- Automatic database initialization
- Health checks
- Volume persistence
- Proper networking

## 🛠️ Management Commands

### Database Operations

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d telegram_bot

# View tables
docker-compose exec postgres psql -U postgres -d telegram_bot -c "\dt"

# View database logs
docker-compose logs postgres

# Backup database
docker-compose exec postgres pg_dump -U postgres telegram_bot > backup.sql

# Restore database
docker-compose exec -T postgres psql -U postgres -d telegram_bot < backup.sql
```

### Container Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f

# Remove everything (including data)
docker-compose down -v
```

## 🔍 Troubleshooting

### Database Connection Issues

1. **Check if PostgreSQL is running:**
   ```bash
   docker-compose ps
   ```

2. **Check database health:**
   ```bash
   docker-compose exec postgres pg_isready -U postgres -d telegram_bot
   ```

3. **View database logs:**
   ```bash
   docker-compose logs postgres
   ```

### Port Conflicts

If port 5432 is already in use:

1. **Stop local PostgreSQL:**
   ```bash
   brew services stop postgresql@15
   ```

2. **Or change Docker port mapping in docker-compose.yml:**
   ```yaml
   ports:
     - "5433:5432"  # Use port 5433 instead
   ```
   
   Then update your `.env`:
   ```env
   DB_PORT=5433
   ```

### Reset Everything

To start fresh:

```bash
# Stop and remove everything
docker-compose down -v

# Start again
docker-compose up -d postgres
```

## 📁 File Structure

```
.
├── docker-compose.yml    # Docker services configuration
├── init-db.sql          # Database initialization script
├── Dockerfile           # Bot container configuration
├── start.sh             # Automated startup script
├── .env                 # Environment variables
├── requirements.txt     # Python dependencies
└── main.py              # Bot application
```

## 🎯 Enable Full Docker Mode

To run both database and bot in Docker:

1. **Edit docker-compose.yml** and uncomment the bot service:

```yaml
  bot:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DB_HOST=postgres
    volumes:
      - .:/app
    restart: unless-stopped
```

2. **Start everything:**
```bash
docker-compose up --build
```

## 🚀 Production Deployment

For production, consider:

1. **Use Docker secrets** for sensitive data
2. **Set up proper backups** for the database
3. **Use environment-specific configurations**
4. **Set up monitoring and logging**
5. **Use a reverse proxy** if needed

Example production docker-compose:

```yaml
services:
  postgres:
    # ... existing config ...
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    
  bot:
    # ... bot config ...
    restart: always
    depends_on:
      postgres:
        condition: service_healthy

secrets:
  db_password:
    file: ./secrets/db_password.txt
```