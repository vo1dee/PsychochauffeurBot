CREATE TABLE IF NOT EXISTS chats (
    chat_id TEXT PRIMARY KEY,
    chat_type TEXT NOT NULL DEFAULT 'private',
    chat_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO chats (chat_id, chat_type, chat_name) VALUES ('global', 'global', 'Global Configuration');

CREATE TABLE IF NOT EXISTS config_values (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL DEFAULT 'global',
    module TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, module, key)
);
CREATE INDEX IF NOT EXISTS idx_config_values_chat_module ON config_values(chat_id, module);

CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_backups_chat ON backups(chat_id);

CREATE TABLE IF NOT EXISTS config_audit (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL,
    module TEXT NOT NULL,
    key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    actor_id TEXT,
    actor_username TEXT,
    source TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_config_audit_chat ON config_audit(chat_id, created_at);
