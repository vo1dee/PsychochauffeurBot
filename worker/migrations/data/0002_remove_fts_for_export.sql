-- Wrangler cannot export a D1 database that contains an FTS5 virtual table.
-- The application does not currently query messages_fts, so remove this derived
-- index to retain portable local SQL/SQLite backups. Message source data remains
-- in the messages table.
DROP TRIGGER IF EXISTS messages_ai;
DROP TRIGGER IF EXISTS messages_ad;
DROP TRIGGER IF EXISTS messages_au;
DROP TABLE IF EXISTS messages_fts;

CREATE INDEX IF NOT EXISTS idx_messages_chat_text ON messages(chat_id, text);
