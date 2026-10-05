-- Mirror of PostgreSQL chat_recap_settings (per-chat daily /recap toggle and state).
CREATE TABLE IF NOT EXISTS chat_recap_settings (
    chat_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    send_time TEXT NOT NULL DEFAULT '09:30',
    last_sent_date TEXT,
    last_pinned_message_id INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
