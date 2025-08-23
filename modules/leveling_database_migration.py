"""
Database migration for the user leveling system.

This module contains the SQL schema and migration logic for the leveling system tables.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# SQL for creating leveling system tables
LEVELING_TABLES_SQL = """
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

-- Performance indexes for user_chat_stats
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_xp ON user_chat_stats(chat_id, xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_level ON user_chat_stats(chat_id, level DESC);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_activity ON user_chat_stats(last_activity);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_user_lookup ON user_chat_stats(user_id);

-- Performance indexes for user_achievements
CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id, chat_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_achievement ON user_achievements(achievement_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_unlocked ON user_achievements(unlocked_at);

-- Performance indexes for achievements
CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements(category);
CREATE INDEX IF NOT EXISTS idx_achievements_condition ON achievements(condition_type, condition_value);
"""

# Achievement definitions to be inserted
ACHIEVEMENT_DEFINITIONS = [
    # Activity achievements
    ("newcomer", "👶 Новачок", "Відправив своє перше повідомлення", "👶", "messages_count", 1, "activity"),
    ("young_fluder", "🐣 Молодий флудер", "Відправив 100+ повідомлень", "🐣", "messages_count", 100, "activity"),
    ("active_talker", "🗣️ Активний співрозмовник", "Відправив 500+ повідомлень", "🗣️", "messages_count", 500, "activity"),
    ("chat_voice", "💬 Голос чату", "Відправив 1,000+ повідомлень", "💬", "messages_count", 1000, "activity"),
    ("scribe", "🪶 Писар", "Відправив 5,000+ повідомлень", "🪶", "messages_count", 5000, "activity"),
    ("psychochauffeur", "🚗 Психошофьор", "Відправив 10,000+ повідомлень", "📜", "messages_count", 10000, "activity"),
    ("elder", "🏛️ Старійшина", "Відправив 20,000+ повідомлень", "🏛️", "messages_count", 20000, "activity"),
    ("chat_lord", "👑 Володар чату", "Відправив 50,000+ повідомлень", "👑", "messages_count", 50000, "activity"),
    ("chat_legend", "🌌 Легенда чату", "Відправив 100,000+ повідомлень", "🌌", "messages_count", 100000, "activity"),
    
    # Daily activity achievements
    ("daily_marathon", "⚡️ Денний марафон", "Відправив 100+ повідомлень за день", "⚡️", "daily_messages", 100, "activity"),
    ("no_weekends", "📆 Без вихідних", "Активний 7+ днів поспіль", "📆", "consecutive_days", 7, "activity"),
    ("chat_veteran", "🎂 Чат-ветеран", "Активний в чаті 1+ рік", "🎂", "days_active", 365, "activity"),
    ("early_bird", "☀️ Жайворонок", "Відправив перше повідомлення вранці", "☀️", "first_morning_message", 1, "activity"),
    ("night_owl", "🌙 Сова", "Відправив останнє повідомлення вночі", "🌙", "last_night_message", 1, "activity"),
    
    # Media and links achievements
    ("photo_lover", "📸 Фотолюбитель", "Поділився 10+ фото", "📸", "photos_shared", 10, "media"),
    ("photo_stream", "🎞️ Фотопотік", "Поділився 100+ фото", "🎞️", "photos_shared", 100, "media"),
    ("twitter_fan", "🐦 Твітерський", "Поділився 100+ посиланнями Twitter", "🐦", "twitter_links", 100, "media"),
    ("gamer", "🎮 Гравець", "Поділився 10+ посиланнями Steam", "🎮", "steam_links", 10, "media"),
    ("meme_lord", "😂 Мемолог", "Поділився 100+ мемами", "😂", "memes_shared", 100, "media"),
    ("videographer", "🎥 Відеограф", "Завантажив перше відео", "🎥", "videos_uploaded", 1, "media"),
    ("chat_dj", "🎶 Діджей чату", "Поділився 10+ музичними треками", "🎶", "music_shared", 10, "media"),
    
    # Social achievements
    ("soul_of_chat", "🔥 Душа чату", "Отримав 100+ реакцій", "🔥", "reactions_received", 100, "social"),
    ("commenter", "↩️ Коментатор", "Зробив першу відповідь", "↩️", "replies_made", 1, "social"),
    ("voice_of_people", "📊 Голос народу", "Створив перше опитування", "📊", "polls_created", 1, "social"),
    ("emotional", "😄 Емоційний", "Відправив перший емодзі", "😄", "emojis_sent", 1, "social"),
    ("helpful", "🤝 Helpful", "Отримав 5+ подяк", "🤝", "thanks_received", 5, "social"),
    ("polite", "🙏 Чемний", "Отримав 100+ подяк", "🙏", "thanks_received", 100, "social"),
    
    # Rare/fun achievements
    ("novelist", "📚 Романіст", "Відправив найдовше повідомлення в історії чату", "📚", "longest_message", 1, "rare"),
    ("minimalist", "👌 Мінімаліст", "Відправив найкоротше повідомлення ('ок')", "👌", "shortest_message", 1, "rare"),
    ("laugher", "🤣 Сміхун", "Відправив 100+ 'лол'/'ахаха' повідомлень", "🤣", "laugh_messages", 100, "rare"),
    ("tagger", "📣 Тегер", "Згадав інших користувачів 50+ разів", "📣", "mentions_made", 50, "rare"),
    ("sticker_master", "🖼️ Стікермайстер", "Відправив перший стікер", "🖼️", "stickers_sent", 1, "rare"),
    ("solo_concert", "🧑‍🎤 Сольний концерт", "Відправив 3+ повідомлення поспіль без відповідей", "🧑‍🎤", "consecutive_messages", 3, "rare"),
    ("rebel", "🤬 Бунтар", "Відправив перше лайливе слово", "🤬", "swear_words", 1, "rare"),
    
    # Level achievements
    ("level_up", "🆙 Level Up!", "Досяг 5-го рівня", "🆙", "level", 5, "progression"),
]

ACHIEVEMENT_INSERT_SQL = """
INSERT INTO achievements (id, title, description, emoji, condition_type, condition_value, category)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    emoji = EXCLUDED.emoji,
    condition_type = EXCLUDED.condition_type,
    condition_value = EXCLUDED.condition_value,
    category = EXCLUDED.category;
"""

async def run_leveling_migration(connection) -> None:
    """
    Run the leveling system database migration.
    
    Args:
        connection: Database connection object
    """
    try:
        logger.info("Starting leveling system database migration...")
        
        # Create tables and indexes
        await connection.execute(LEVELING_TABLES_SQL)
        logger.info("Leveling system tables and indexes created successfully")
        
        # Insert achievement definitions
        for achievement_data in ACHIEVEMENT_DEFINITIONS:
            await connection.execute(ACHIEVEMENT_INSERT_SQL, *achievement_data)
        
        logger.info(f"Inserted {len(ACHIEVEMENT_DEFINITIONS)} achievement definitions")
        logger.info("Leveling system database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to run leveling system migration: {e}")
        raise

def get_migration_sql() -> str:
    """Get the complete migration SQL for the leveling system."""
    return LEVELING_TABLES_SQL