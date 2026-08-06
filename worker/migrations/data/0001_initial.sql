CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    chat_type TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT,
    username TEXT,
    is_bot INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    internal_message_id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id),
    user_id INTEGER REFERENCES users(user_id),
    timestamp TEXT NOT NULL,
    text TEXT,
    is_command INTEGER NOT NULL DEFAULT 0,
    command_name TEXT,
    is_gpt_reply INTEGER NOT NULL DEFAULT 0,
    replied_to_message_id INTEGER,
    gpt_context_message_ids TEXT,
    raw_telegram_message TEXT,
    UNIQUE(chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp ON messages(chat_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_command ON messages(chat_id, is_command);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(text, content='messages', content_rowid='internal_message_id');
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, text) VALUES (new.internal_message_id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.internal_message_id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF text ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.internal_message_id, old.text);
  INSERT INTO messages_fts(rowid, text) VALUES (new.internal_message_id, new.text);
END;

CREATE TABLE IF NOT EXISTS analysis_cache (
    chat_id INTEGER NOT NULL,
    time_period TEXT NOT NULL,
    message_content_hash TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, time_period, message_content_hash)
);

CREATE TABLE IF NOT EXISTS bot_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    user_id INTEGER,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bot_events_type_chat_ts ON bot_events(event_type, chat_id, timestamp);
