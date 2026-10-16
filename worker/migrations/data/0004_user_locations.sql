-- Saved /weather cities, shared by the bot and the Mini App.
-- chat_id = 0 is the user's home city; any other chat_id is a per-group override.
CREATE TABLE IF NOT EXISTS user_locations (
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL DEFAULT 0,
    city TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, chat_id)
);
