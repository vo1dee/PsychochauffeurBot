# Weather Web App (Mini App) demo

A small Telegram Mini App that shows weather in a page opened inside Telegram.
It is served by the existing Cloudflare worker (`worker/`), so it gets HTTPS for free.

## What it shows

- Greeting from `Telegram.WebApp.initDataUnsafe.user`, platform.
- Light/dark theme: follows Telegram's theme inside the app and the system setting in a browser.
- City search + current weather and 3-day forecast (Open-Meteo, no API key).
- Telegram `MainButton` ("Закрити") and haptic feedback.
- "🔐 Перевірка initData" section: the page sends `initData` to `POST /webapp/verify`,
  and the worker checks its HMAC signature with the bot token. This is how a real Mini App
  must authenticate users. Never trust `initDataUnsafe` on the server.

## Pieces

| Part | File |
|------|------|
| Page (`GET /webapp`) and verification (`POST /webapp/verify`) | `worker/src/webapp.ts` |
| Routing hook | `worker/src/index.ts` |
| `/webapp` bot command | `modules/handlers/webapp_command.py` |

## Setup

1. **Deploy the worker.** CI deploys it on pushes to `main` that touch `worker/`; or run
   `cd worker && npx wrangler deploy` manually. The page is then at
   `https://psychochauffeur-d1-api.<your-subdomain>.workers.dev/webapp`.
2. **(Optional) enable server-side verification:**
   `cd worker && npx wrangler secret put TELEGRAM_BOT_TOKEN`
3. **Bot env:** set `WEBAPP_URL` to the page URL above in `~/psychochauffeurbot/.env` on the host,
   then run `./restart_bot.sh` there (it recreates the container so `.env` is re-read).
4. **Try it:** send `/webapp` to the bot in a private chat and tap "🌤 Відкрити погоду".

### Groups

Telegram rejects `web_app` inline buttons in groups. To open the app from a group:

1. In BotFather run `/newapp` and choose the bot. Set the URL to `WEBAPP_URL` and pick a short name, e.g. `weather`.
2. Set `WEBAPP_SHORT_NAME=weather` in the bot env.

`/webapp` in a group then sends a `https://t.me/<bot>/weather` link that opens the app inside Telegram.
Without a short name it links to the bot's private chat instead.

You can also attach the app to the chat **menu button** via BotFather (`/mybots` → Bot Settings → Menu Button).

## Saved locations

`/weather` and the Mini App share one saved city per user, stored in D1 (`user_locations`,
migration `worker/migrations/data/0004_user_locations.sql`):

- **Home city** (`chat_id = 0`) is updated by every successful `/weather <city>` and by
  "Зберегти …" in the Mini App. The Mini App opens on it.
- **Group override**: `/weather <city>` in a group also remembers that city for you in that group.
- `/weather` with no city uses the group override, then the home city.

The bot reaches D1 through the Worker API (`D1_API_URL` / `D1_API_TOKEN`, see
`modules/user_locations.py`); when D1 is not configured or fails it falls back to
`data/user_locations.csv`. The Mini App uses `POST /webapp/location` and
`POST /webapp/location/save`, authenticated by verified `initData` (needs the
`TELEGRAM_BOT_TOKEN` worker secret).

### Importing the old CSV

1. Copy the old file into the deployment's `data/` folder (mounted into the container), e.g.
   `scp old-host:~/psychochauffeurbot/data/user_locations.csv ~/psychochauffeurbot/data/user_locations_old.csv`
2. Preview, then import (safe to re-run; it never overwrites a city saved more recently):
   ```bash
   cd ~/psychochauffeurbot
   docker compose -f docker-compose.prod.yml exec bot python scripts/import_user_locations.py data/user_locations_old.csv --dry-run
   docker compose -f docker-compose.prod.yml exec bot python scripts/import_user_locations.py data/user_locations_old.csv
   ```
