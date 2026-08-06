# Cloudflare D1 Migration Runbook

This project uses two D1 databases: `psychochauffeur-data` for messages and
events, and `psychochauffeur-config` for configuration. They must remain
separate because both legacy stores have a different `chats` table.

## Provision and deploy

1. Install Worker dependencies: `npm --prefix worker install`.
2. Create both databases with `cd worker && npx wrangler d1 create <name>`.
3. Replace the two placeholder IDs in `worker/wrangler.jsonc` with the returned IDs.
4. Apply migrations for each binding:
   `cd worker && npx wrangler d1 migrations apply DATA_DB --remote`
   and `cd worker && npx wrangler d1 migrations apply CONFIG_DB --remote`.
5. Set `D1_API_TOKEN` interactively with Wrangler, deploy the Worker, and place
   its URL/token in the bot host's untracked environment file.

## Migrate and cut over

1. Generate imports with `python scripts/migrate_to_d1.py`; inspect its manifest.
2. Import each generated SQL file using `wrangler d1 execute ... --remote --file`.
3. Enable `D1_DUAL_WRITE=true` on the bot. Set `D1_DUAL_WRITE_REQUIRED=true`
   only after initial reconciliation is clean.
4. Compare row counts and sampled messages/configuration before migrating the
   remaining read-only PostgreSQL query callers to typed Worker endpoints.

## Local backups and development

Run `python scripts/export_d1_backups.py` daily from the bot host after Wrangler
authentication is configured. It produces ignored SQL exports and SQLite files in
`data/d1-backups`; query a snapshot with `sqlite3 <snapshot>.sqlite3`.

The data migrations remove the unused FTS5 virtual table because Wrangler cannot
export a D1 database containing virtual tables. The primary `messages` data and
ordinary query indexes are retained.

For local development, put `D1_API_TOKEN=<local secret>` in `worker/.dev.vars`,
run `npm --prefix worker run dev`, and point `D1_API_URL` at that local endpoint.
