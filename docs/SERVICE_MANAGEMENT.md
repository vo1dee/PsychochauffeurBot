# Bot Service Management Guide

Production runs on Oracle OCI with Docker Compose and deploys automatically from
`main` (`.github/workflows/deploy.yml` → `scripts/deploy_oci.sh`). See
[OCI_DEPLOYMENT.md](OCI_DEPLOYMENT.md) for setup. The bot is the `bot` service in
`docker-compose.prod.yml`; there is no systemd unit (`psychochauffeur-bot.service`
no longer exists, so `systemctl` / `journalctl` commands will not work).

Run every command below from the deployment directory, `~/psychochauffeurbot`
(not its `worker/` subfolder).

## Quick Commands

```bash
cd ~/psychochauffeurbot
./restart_bot.sh                                                                     # Restart / pick up .env changes
docker compose -f docker-compose.prod.yml stop bot                                   # Stop
IMAGE_TAG=$(cat .last_good_tag) docker compose -f docker-compose.prod.yml up -d bot  # Start
docker compose -f docker-compose.prod.yml ps bot                                     # Status
docker compose -f docker-compose.prod.yml logs -f bot                                # Live logs
```

`./restart_bot.sh` recreates the `bot` container with the image tag recorded in
`.last_good_tag` (the last tag `scripts/deploy_oci.sh` deployed successfully), so
edits to `.env` take effect.

## Service Details

- **Compose file**: `~/psychochauffeurbot/docker-compose.prod.yml`
- **Services**: `bot` (image `ghcr.io/vo1dee/psychochauffeurbot:${IMAGE_TAG}`) and `postgres`
- **Environment**: loaded from `~/psychochauffeurbot/.env`
- **Auto-restart**: `restart: unless-stopped` (restarts on crash and after reboot,
  unless it was stopped explicitly)

## Checking Status

```bash
docker compose -f docker-compose.prod.yml ps
```

The `bot` row should show `running` (or `Up`).

## Viewing Logs

### Live logs (follow):
```bash
docker compose -f docker-compose.prod.yml logs -f bot
```

### Last 100 lines:
```bash
docker compose -f docker-compose.prod.yml logs --tail=100 bot
```

### Logs for the last day:
```bash
docker compose -f docker-compose.prod.yml logs --since 24h bot
```

Application log files are also written to `~/psychochauffeurbot/logs/`.

## Troubleshooting

### Bot won't start
1. Check logs: `docker compose -f docker-compose.prod.yml logs --tail=50 bot`
2. Verify Postgres is healthy: `docker compose -f docker-compose.prod.yml ps postgres`
3. Check .env file exists: `ls -la ~/psychochauffeurbot/.env`
4. Check the tag being started: `cat ~/psychochauffeurbot/.last_good_tag`

### Bot keeps restarting
1. Check logs for errors: `docker compose -f docker-compose.prod.yml logs --tail=100 bot`
2. Verify database connection
3. Check TELEGRAM_BOT_TOKEN in .env

### Bot is running but doesn't respond
1. Check bot logs: `docker compose -f docker-compose.prod.yml logs -f bot`
2. Verify bot token is correct
3. Check network connectivity
