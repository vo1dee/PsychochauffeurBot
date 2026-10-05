#!/usr/bin/env bash
# One-time preparation of an Oracle OCI host (Ubuntu or Oracle Linux) for the bot.
# Run as the deploy user (the one GitHub Actions will SSH in as), with sudo rights:
#   curl -fsSL https://raw.githubusercontent.com/vo1dee/PsychochauffeurBot/main/scripts/oci_bootstrap.sh | bash
# or, after cloning:  ./scripts/oci_bootstrap.sh
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/psychochauffeurbot}"
REPO_URL="${REPO_URL:-https://github.com/vo1dee/PsychochauffeurBot.git}"

echo "==> Host: $(uname -m), $(. /etc/os-release && echo "$PRETTY_NAME")"

if ! command -v docker >/dev/null; then
  echo "==> Installing Docker Engine + compose plugin"
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# sqlite3 lets you inspect D1 snapshots / config.db on the host.
if command -v apt-get >/dev/null; then
  sudo apt-get update -y && sudo apt-get install -y git sqlite3
else
  sudo dnf install -y git sqlite
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# Runtime state directories mounted into the container (owned by UID 1000 = image user).
mkdir -p logs downloads data/backups data/d1-backups config/global config/private config/group config/backups config/archive
[[ -e cookies.txt ]] || touch cookies.txt
sudo chown -R 1000:1000 logs downloads data config/global config/private config/group config/backups config/archive cookies.txt

if [[ ! -f .env ]]; then
  cat > .env <<'ENV'
# Fill in and keep this file only on the host (chmod 600). Never commit it.
TELEGRAM_BOT_TOKEN=
OPENROUTER_API_KEY=
OPENWEATHER_API_KEY=
DISCORD_WEBHOOK_URL=
ERROR_CHANNEL_ID=
SPEECHMATICS_API_KEY=
NASA_API_KEY=
YTDL_SERVICE_API_KEY=
REPORT_CHAT_ID=
REPORT_THREAD_ID=
REPORT_ALLOWED_USER_ID=

DB_NAME=telegram_bot
DB_USER=postgres
DB_PASSWORD=change-me-to-a-long-random-string

D1_API_URL=
D1_API_TOKEN=
D1_DUAL_WRITE=true
D1_DUAL_WRITE_REQUIRED=false
ENV
  chmod 600 .env
  echo "==> Created $APP_DIR/.env template; fill it in before the first deploy."
fi

# Daily Postgres dump (14 days retained) at 03:17 host time.
CRON_LINE="17 3 * * * cd $APP_DIR && docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -Fc telegram_bot > data/backups/telegram_bot-\$(date +\\%F).dump && find data/backups -name '*.dump' -mtime +14 -delete"
( crontab -l 2>/dev/null | grep -v 'pg_dump -U postgres -Fc telegram_bot' ; echo "$CRON_LINE" ) | crontab -

echo "==> Done. Log out and back in (docker group), fill in .env, then follow docs/OCI_DEPLOYMENT.md."
