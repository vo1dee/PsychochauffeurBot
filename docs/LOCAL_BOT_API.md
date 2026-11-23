# Local Telegram Bot API server

The bot can talk to a self-hosted [`telegram-bot-api`](https://github.com/tdlib/telegram-bot-api)
server (image `aiogram/telegram-bot-api`) instead of Telegram's cloud Bot API.

What it gives us:

- **Uploads up to 2000 MB** (cloud: 50 MB). Limits come from `modules/telegram_files.py`.
- Files are sent as `file://` paths, so a 2 GB video never has to fit in the bot's RAM.
- `getFile` has no 20 MB limit; downloaded files are read from the shared volume.
- It doesn't go through Telegram's public Bot API servers. The bot outage of 2026-11-20
  (`getMe` hanging for one bot ID) happened on those servers.

## How it is wired

`docker-compose.prod.yml`:

| Service | Role |
| --- | --- |
| `telegram-bot-api` | The server, profile `local-bot-api`, 384 MB memory cap, no published port. |
| `media-cleanup` | Always on. Every 10 min deletes files > 50 MB older than 30 min and everything older than 6 h in `downloads/`; in the Bot API volume, files > 50 MB after 30 min and the rest after 2 h (only per-bot subfolders, never its database). |

Both the bot and the server mount `./downloads` at `/app/downloads` and `./data/music`
at `/app/data/music` (where `/song` saves audio), so a path the bot sends means the same
file inside the server. Any new directory the bot sends files from needs the same mount,
or the server answers `Can't find real file path`. The bot mounts the server's work dir
`bot_api_data` read-only at the same path, for `getFile` results.

The bot switches to local mode when `TELEGRAM_API_BASE_URL` is set
(`modules/bot_application.py`): `base_url`, `base_file_url` and `local_mode=True`.

## Enabling (one-time cutover)

1. Get `api_id` / `api_hash` at <https://my.telegram.org> → API development tools.
2. On the host, add to `~/psychochauffeurbot/.env`:

   ```
   COMPOSE_PROFILES=local-bot-api
   TELEGRAM_API_ID=...
   TELEGRAM_API_HASH=...
   ```

3. Start the server (the bot keeps using the cloud API for now):

   ```bash
   cd ~/psychochauffeurbot && IMAGE_TAG=$(cat .last_good_tag) docker compose -f docker-compose.prod.yml up -d telegram-bot-api
   ```

4. Log the bot out of the cloud API. **After this the cloud API refuses the bot for
   10 minutes**, so only do it while the cloud API is answering and you're ready to switch:

   ```bash
   source <(grep ^TELEGRAM_BOT_TOKEN= .env) && curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/logOut"
   ```

5. Add `TELEGRAM_API_BASE_URL=http://telegram-bot-api:8081` to `.env` and recreate the bot:

   ```bash
   IMAGE_TAG=$(cat .last_good_tag) docker compose -f docker-compose.prod.yml up -d bot
   ```

   The log should show `Using local Telegram Bot API server at http://telegram-bot-api:8081`.

## Switching back to the cloud API

1. Close the bot on the local server, then wait about 10 minutes before the cloud API accepts it again:

   ```bash
   source <(grep ^TELEGRAM_BOT_TOKEN= .env) && docker compose -f docker-compose.prod.yml exec bot \
     python -c "import httpx,os; print(httpx.post(f'http://telegram-bot-api:8081/bot{os.environ[\"TELEGRAM_BOT_TOKEN\"]}/close').text)"
   ```

2. Remove `TELEGRAM_API_BASE_URL` from `.env` and recreate the bot (`up -d bot`).
   Upload limits drop back to 50 MB automatically.
3. Optionally drop `COMPOSE_PROFILES=local-bot-api` and `docker compose ... stop telegram-bot-api`.

Updates that arrive during a switch can be lost; switch at a quiet time.
