# Weather Web App (Mini App) demo

A small Telegram Mini App that shows weather in a page opened inside Telegram.
It is served by the existing Cloudflare worker (`worker/`), so it gets HTTPS for free.

## What it shows

- Greeting from `Telegram.WebApp.initDataUnsafe.user`, Telegram theme colours, platform.
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
3. **Bot env:** set `WEBAPP_URL` to the page URL above and restart the bot.
4. **Try it:** send `/webapp` to the bot in a private chat and tap "🌤 Відкрити погоду".

### Groups

Telegram rejects `web_app` inline buttons in groups. To open the app from a group:

1. In BotFather run `/newapp` and choose the bot. Set the URL to `WEBAPP_URL` and pick a short name, e.g. `weather`.
2. Set `WEBAPP_SHORT_NAME=weather` in the bot env.

`/webapp` in a group then sends a `https://t.me/<bot>/weather` link that opens the app inside Telegram.
Without a short name it links to the bot's private chat instead.

You can also attach the app to the chat **menu button** via BotFather (`/mybots` → Bot Settings → Menu Button).
