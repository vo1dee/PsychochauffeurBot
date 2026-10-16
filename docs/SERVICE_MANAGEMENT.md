# Bot Service Management Guide

Production runs on the Oracle OCI host under Docker Compose (`docker-compose.prod.yml`) and
deploys automatically from `main` via `.github/workflows/deploy.yml` → `scripts/deploy_oci.sh`.
See [OCI_DEPLOYMENT.md](OCI_DEPLOYMENT.md) for setup and deployment details.

There is no `psychochauffeur-bot.service` systemd unit anymore; `systemctl` / `journalctl`
commands for it will fail with "Unit psychochauffeur-bot.service not found".

## Quick Commands

Run these on the OCI host from `~/psychochauffeurbot`:

```bash
cd ~/psychochauffeurbot

./restart_bot.sh                                                                  # Restart / pick up .env changes
docker compose -f docker-compose.prod.yml stop bot                                # Stop
IMAGE_TAG=$(cat .last_good_tag) docker compose -f docker-compose.prod.yml up -d bot  # Start
docker compose -f docker-compose.prod.yml ps                                      # Status (bot + postgres)
docker compose -f docker-compose.prod.yml logs -f bot                             # Live logs
```

`./restart_bot.sh` recreates the `bot` container using the image tag in `.last_good_tag`
(the tag `scripts/deploy_oci.sh` last deployed successfully), so changes to `.env` are re-read.

Always pass `IMAGE_TAG=$(cat .last_good_tag)` when starting the bot by hand; without it Compose
falls back to the `latest` image tag.

## Service Details

- **Compose file**: `~/psychochauffeurbot/docker-compose.prod.yml`
- **Services**: `bot` (image `ghcr.io/vo1dee/psychochauffeurbot:${IMAGE_TAG}`) and `postgres`
- **Deployed tag**: `~/psychochauffeurbot/.last_good_tag`
- **Environment**: `~/psychochauffeurbot/.env` (untracked; loaded via `env_file`)
- **Auto-restart / start on boot**: `restart: unless-stopped` — containers come back after a
  crash or a reboot unless they were stopped explicitly

## Checking Status

```bash
docker compose -f docker-compose.prod.yml ps bot
```

`STATUS` shows `Up …` when the bot is running. A `Restarting` status means it is crash-looping;
check the logs.

## Viewing Logs

```bash
# Live logs (follow)
docker compose -f docker-compose.prod.yml logs -f bot

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 bot

# Last 24 hours
docker compose -f docker-compose.prod.yml logs --since 24h bot
```

Application log files are also written to `~/psychochauffeurbot/logs/` (bind-mounted into the
container).

## Troubleshooting

### Bot won't start
1. Check logs: `docker compose -f docker-compose.prod.yml logs --tail=50 bot`
2. Check postgres is healthy: `docker compose -f docker-compose.prod.yml ps postgres`
3. Check the .env file exists: `ls -la ~/psychochauffeurbot/.env`
4. Check the deployed tag: `cat ~/psychochauffeurbot/.last_good_tag`

### Bot keeps restarting
1. Check logs for errors: `docker compose -f docker-compose.prod.yml logs --tail=100 bot`
2. Verify database connection
3. Check `TELEGRAM_BOT_TOKEN` in `.env`, then `./restart_bot.sh`

### Bot is running but doesn't respond
1. Follow bot logs: `docker compose -f docker-compose.prod.yml logs -f bot`
2. Verify the bot token is correct
3. Check network connectivity

## Changing Configuration

- **Environment variables**: edit `~/psychochauffeurbot/.env`, then run `./restart_bot.sh`.
- **Container definition** (volumes, logging, services): change `docker-compose.prod.yml` in
  the repository and merge to `main`; the deploy workflow applies it.
- **Deploying a specific image by hand**: `IMAGE_TAG=sha-abc1234 ./scripts/deploy_oci.sh`
  (rolls back to the previous tag automatically if the new one fails to stay up).
