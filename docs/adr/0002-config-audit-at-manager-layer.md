# Config changes are audited at the manager layer, not in handlers

Every config write path (Telegram UI, web UI, system migrations/restores) goes
through the config_v2 manager, which appends to a `config_audit` table in the same
SQLite database: timestamp, chat_id, module, key, old value, new value, actor id,
actor username, source (`telegram` / `web` / `system`). Write paths must supply an
actor. The ledger is write-only for now — nothing in the bot reads it back.

Auditing in the Telegram handler was rejected because it would be blind to web and
system writes, so the ledger could never answer "who changed this?" definitively.
The web UI has no authentication, so its changes are attributable only as
`source="web"`.
