# Oracle OCI Deployment & CI/CD

Production runs on an Oracle OCI VM with Docker Compose (`docker-compose.prod.yml`):
the bot image from GHCR plus a local PostgreSQL. Cloudflare D1 receives copies of
every write (`D1_DUAL_WRITE=true`), so D1 doubles as an off-host backup.

Every push to `main` runs `.github/workflows/deploy.yml`:

| Job | What it does |
| --- | --- |
| Checks | syntax check, fatal flake8 errors, `import main` (blocking) |
| Test suite | full pytest run, **non-blocking** until existing failures are fixed |
| Build image | multi-arch (amd64 + arm64) image → `ghcr.io/vo1dee/psychochauffeurbot:sha-<7>` and `:latest` |
| Deploy D1 Worker | only when `worker/**` changed: D1 migrations + `wrangler deploy` |
| Deploy to OCI | uploads `docker-compose.prod.yml`, runs `scripts/deploy_oci.sh` over SSH; rolls back to `.last_good_tag` if the bot doesn't stay up for 60 s |

Pull requests run Checks, Test suite and an image build (not pushed), without deploying.

## 1. Check the OCI host

```bash
# On the host
uname -m                    # aarch64 = Ampere (ARM), x86_64 = AMD/Intel; both are supported
curl -s ifconfig.me         # public IP -> OCI_HOST
sudo ss -tlnp | grep ':22'  # sshd is listening
# From your laptop
nc -vz <PUBLIC_IP> 22
```

If port 22 isn't reachable, add an ingress rule (TCP 22) to the instance's VCN
Security List / NSG. Oracle Linux and Ubuntu images on OCI also ship restrictive
iptables rules: check `sudo iptables -L INPUT -n --line-numbers`.

## 2. Bootstrap the host (once)

```bash
git clone https://github.com/vo1dee/PsychochauffeurBot.git ~/psychochauffeurbot
~/psychochauffeurbot/scripts/oci_bootstrap.sh
# log out/in so the docker group applies, then fill in secrets:
nano ~/psychochauffeurbot/.env
```

The bootstrap installs Docker and creates the state directories mounted into the
container (`logs`, `downloads`, `data`, `config/{global,private,group,backups,archive}`,
`cookies.txt`, all owned by UID 1000, the image user). It also writes a `.env`
template and installs a daily `pg_dump` cron job into `data/backups/` (14 days kept).
Copy your YouTube/Instagram `cookies.txt` into place if you have one.

## 3. GitHub configuration

Create a deploy key pair (`ssh-keygen -t ed25519 -f oci_deploy -N ''`), append
`oci_deploy.pub` to `~/.ssh/authorized_keys` on the host, then add these repository
secrets (preferably on a `production` environment):

| Secret | Value |
| --- | --- |
| `OCI_HOST` | public IP / DNS of the VM |
| `OCI_USER` | SSH user (`ubuntu` or `opc`) |
| `OCI_SSH_KEY` | contents of `oci_deploy` (private key) |
| `OCI_KNOWN_HOSTS` | output of `ssh-keyscan <OCI_HOST>` (recommended; otherwise trust-on-first-use) |
| `OCI_SSH_PORT` | optional, default 22 |
| `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` | token with Workers + D1 edit, for the Worker job |
| `DISCORD_WEBHOOK_URL` | optional, notified on failed deploys |

Bot secrets (`TELEGRAM_BOT_TOKEN`, `DB_PASSWORD`, `D1_API_TOKEN`, ...) live **only**
in the host's `.env`.

The deploy job logs the host into GHCR with the workflow's short-lived token, so
private images work without a stored PAT. For manual pulls on the host outside CI,
either make the package public or run `docker login ghcr.io` with a `read:packages` PAT.

## 4. Restore the database from D1 (once)

```bash
cd ~/psychochauffeurbot
docker compose -f docker-compose.prod.yml up -d postgres

# Export both D1 databases to data/d1-backups/*.sql (Node in a throwaway container)
TS=$(date -u +%Y%m%dT%H%M%SZ)
docker run --rm -v "$PWD":/w -w /w/worker \
  -e CLOUDFLARE_API_TOKEN -e CLOUDFLARE_ACCOUNT_ID node:22 sh -c "
    npm ci --silent &&
    npx wrangler d1 export psychochauffeur-data   --remote --output ../data/d1-backups/data-$TS.sql --skip-confirmation &&
    npx wrangler d1 export psychochauffeur-config --remote --output ../data/d1-backups/config-$TS.sql --skip-confirmation"

# Load into Postgres + data/config.db using the bot image
docker compose -f docker-compose.prod.yml run --rm --no-deps bot \
  python scripts/restore_d1_to_postgres.py \
    --data-snapshot data/d1-backups/data-$TS.sql \
    --config-snapshot data/d1-backups/config-$TS.sql
```

(`export CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=...` first.) The script
creates the schema with the bot's own DDL, inserts with `ON CONFLICT DO NOTHING`
(safe to re-run), advances sequences, and prints D1 and Postgres row counts per
table. It exits non-zero if Postgres has fewer rows than D1.

Before the first deploy the `:latest` image may not exist yet. Run the workflow once
(Actions → Deploy → Run workflow), or push to `main`, and then do the restore.
The bot will start on an empty schema in the meantime, which is harmless because
restored rows are merged in.

Known gaps:
- `chat_recap_settings` is mirrored to D1 since migration `0003`. Exports taken before that
  have no recap table, so chats that used `/recap on` must re-enable it after such a restore.
- The D1 config database holds the one-time import from `migrate_to_d1.py`, not live config changes.
- Per-chat JSON configs under `config/private|group` were only on the old host; they
  regenerate from `config/global/global_config.json` defaults.

## 5. Day-to-day

```bash
cd ~/psychochauffeurbot
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f bot
docker compose -f docker-compose.prod.yml restart bot
```

**Rollback:** Actions → Deploy → Run workflow with `image_tag` set to a previous
`sha-xxxxxxx`, or on the host: `IMAGE_TAG=sha-xxxxxxx ./scripts/deploy_oci.sh`.

**Backups:** daily `pg_dump` in `data/backups/`. Off-host copies come from D1, via
`scripts/export_d1_backups.py` or the export command above. Restore a dump with
`docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U postgres -d telegram_bot -c --if-exists < data/backups/<file>.dump`.

**No public SSH?** Register a self-hosted GitHub runner on the host and replace the
SSH steps of the `deploy` job with `bash scripts/deploy_oci.sh` run locally.
