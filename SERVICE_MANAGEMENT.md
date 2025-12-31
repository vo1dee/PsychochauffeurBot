# Bot Service Management Guide

The PsychoChauffeur bot is now set up as a systemd service that runs in the background.

## Quick Commands

### Using the helper script (recommended):
```bash
cd /root/psychochauffeurbot
./scripts/bot_service.sh start    # Start the bot
./scripts/bot_service.sh stop     # Stop the bot
./scripts/bot_service.sh restart   # Restart the bot
./scripts/bot_service.sh status    # Check status
./scripts/bot_service.sh logs      # View live logs
./scripts/bot_service.sh enable    # Enable auto-start on boot
./scripts/bot_service.sh disable   # Disable auto-start on boot
```

### Using systemctl directly:
```bash
sudo systemctl start psychochauffeur-bot      # Start
sudo systemctl stop psychochauffeur-bot       # Stop
sudo systemctl restart psychochauffeur-bot    # Restart
sudo systemctl status psychochauffeur-bot     # Status
sudo journalctl -u psychochauffeur-bot -f     # Live logs
sudo systemctl enable psychochauffeur-bot     # Enable on boot
sudo systemctl disable psychochauffeur-bot    # Disable on boot
```

## Service Details

- **Service Name**: `psychochauffeur-bot`
- **Service File**: `/etc/systemd/system/psychochauffeur-bot.service`
- **Working Directory**: `/root/psychochauffeurbot`
- **Python**: Uses venv at `/root/psychochauffeurbot/venv/bin/python3`
- **Auto-restart**: Enabled (restarts automatically if it crashes)
- **Auto-start on boot**: Enabled (starts when system boots)

## Starting the Bot

To start the bot service:
```bash
./scripts/bot_service.sh start
```

Or:
```bash
sudo systemctl start psychochauffeur-bot
```

## Checking Status

```bash
./scripts/bot_service.sh status
```

You should see:
- `Active: active (running)` - Bot is running
- `Active: inactive (dead)` - Bot is stopped

## Viewing Logs

### Live logs (follow):
```bash
./scripts/bot_service.sh logs
```

### Last 100 lines:
```bash
sudo journalctl -u psychochauffeur-bot -n 100
```

### Logs since boot:
```bash
sudo journalctl -u psychochauffeur-bot -b
```

### Logs for today:
```bash
sudo journalctl -u psychochauffeur-bot --since today
```

## Troubleshooting

### Service won't start
1. Check logs: `sudo journalctl -u psychochauffeur-bot -n 50`
2. Verify Docker is running: `docker ps | grep postgres`
3. Check .env file exists: `ls -la /root/psychochauffeurbot/.env`
4. Verify Python venv: `ls -la /root/psychochauffeurbot/venv/bin/python3`

### Service keeps restarting
1. Check logs for errors: `sudo journalctl -u psychochauffeur-bot -n 100`
2. Verify database connection
3. Check TELEGRAM_BOT_TOKEN in .env

### Service is running but bot doesn't respond
1. Check bot logs: `sudo journalctl -u psychochauffeur-bot -f`
2. Verify bot token is correct
3. Check network connectivity

## Service Configuration

The service file is located at:
- `/etc/systemd/system/psychochauffeur-bot.service`

To edit it:
```bash
sudo nano /etc/systemd/system/psychochauffeur-bot.service
sudo systemctl daemon-reload  # Reload after editing
```

## Notes

- The service automatically restarts if it crashes (RestartSec=10)
- Logs are sent to systemd journal (view with `journalctl`)
- The service waits for Docker and network to be ready before starting
- Environment variables are loaded from `/root/psychochauffeurbot/.env`
