-- Database initialization script for PsychochauffeurBot
-- This script creates all necessary tables and indexes

-- Create extensions (required for text search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create chats table
CREATE TABLE IF NOT EXISTS chats (
    chat_id BIGINT PRIMARY KEY,
    chat_type VARCHAR(50) NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT,
    username TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    internal_message_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL REFERENCES chats(chat_id),
    user_id BIGINT REFERENCES users(user_id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    text TEXT,
    is_command BOOLEAN DEFAULT FALSE,
    command_name VARCHAR(255),
    is_gpt_reply BOOLEAN DEFAULT FALSE,
    replied_to_message_id BIGINT,
    gpt_context_message_ids JSONB,
    raw_telegram_message JSONB,
    UNIQUE(chat_id, message_id)
);

-- Create analysis_cache table
CREATE TABLE IF NOT EXISTS analysis_cache (
    chat_id BIGINT NOT NULL,
    time_period TEXT NOT NULL,
    message_content_hash TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (chat_id, time_period, message_content_hash)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_is_command ON messages(is_command);
CREATE INDEX IF NOT EXISTS idx_messages_is_gpt_reply ON messages(is_gpt_reply);

-- Text search indexes for /count command optimization
CREATE INDEX IF NOT EXISTS idx_messages_text_gin ON messages USING GIN(text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_messages_text_search ON messages USING GIN(to_tsvector('english', text));

-- Composite index for faster chat-specific text searches
CREATE INDEX IF NOT EXISTS idx_messages_chat_text ON messages(chat_id) WHERE text IS NOT NULL;

-- Leveling System Tables
-- Chat-specific user statistics
CREATE TABLE IF NOT EXISTS user_chat_stats (
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    messages_count INTEGER DEFAULT 0,
    links_shared INTEGER DEFAULT 0,
    thanks_received INTEGER DEFAULT 0,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, chat_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
);

-- Achievement definitions
CREATE TABLE IF NOT EXISTS achievements (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    emoji VARCHAR(10) NOT NULL,
    condition_type VARCHAR(50) NOT NULL,
    condition_value INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User achievements (per chat)
CREATE TABLE IF NOT EXISTS user_achievements (
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    achievement_id VARCHAR(50) NOT NULL,
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, chat_id, achievement_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE
);

-- Performance indexes for leveling system
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_xp ON user_chat_stats(chat_id, xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_level ON user_chat_stats(chat_id, level DESC);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_activity ON user_chat_stats(last_activity);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_user_lookup ON user_chat_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id, chat_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_achievement ON user_achievements(achievement_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_unlocked ON user_achievements(unlocked_at);
CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements(category);
CREATE INDEX IF NOT EXISTS idx_achievements_condition ON achievements(condition_type, condition_value);