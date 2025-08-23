# Requirements Document

## Introduction

This document outlines the requirements for implementing a comprehensive leveling and achievement system for the Telegram group bot. The system will track user activity, assign experience points (XP), manage user levels, and unlock achievements based on specific behaviors and milestones. This gamification feature will enhance user engagement and create a more interactive group chat experience.

## Requirements

### Requirement 1: XP Assignment System

**User Story:** As a group chat member, I want to earn experience points for my activities so that I can progress and be recognized for my participation.

#### Acceptance Criteria

1. WHEN a user sends any message THEN the system SHALL award 1 XP to that user
2. WHEN a user shares a link (containing "http://" or "https://") THEN the system SHALL award 3 XP to that user
3. WHEN a user receives thanks (message mentions them with "@user" or reply to, and contains thank keywords(thanks, thank you, 10x, дякую, дяки, дякі, спасибі, спс, дяк і тд)) THEN the system SHALL award 5 XP to that user
4. WHEN XP is awarded THEN the system SHALL update the user's total XP in the database
5. WHEN XP is awarded THEN the system SHALL update relevant activity counters (messages_count, links_shared, thanks_received)

### Requirement 2: Level Progression System

**User Story:** As a group chat member, I want to level up automatically based on my accumulated XP so that I can see my progression over time.

#### Acceptance Criteria

1. WHEN a user's total XP reaches a level threshold THEN the system SHALL automatically increase their level
2. WHEN a user levels up THEN the system SHALL send a congratulatory message to the group chat mentionin their lvl achieved and promptin to /profile for more stats
3. WHEN calculating level thresholds THEN the system SHALL use the following progression: Level 1 (0 XP), Level 2 (50 XP), Level 3 (100 XP), Level 4 (200 XP), Level 5 (400 XP), continuing with exponential growth
4. WHEN a user's level changes THEN the system SHALL update their level in the database
5. WHEN checking for level ups THEN the system SHALL evaluate after each XP award
6. WHEN bot runs in existing chat THEN system automatically adjusted based on DB status, and SHALL send current lvl and base message when users chats

### Requirement 3: Achievement System

**User Story:** As a group chat member, I want to unlock achievements for reaching specific milestones so that my accomplishments are recognized and celebrated.

#### Acceptance Criteria
📈 Активність у чаті

WHEN a user sends their first message THEN the system SHALL unlock the "👶 Новачок" achievement

WHEN a user sends 100+ messages THEN the system SHALL unlock the "🐣 Молодий базіка" achievement

WHEN a user sends 500+ messages THEN the system SHALL unlock the "🗣️ Активний співрозмовник" achievement

WHEN a user sends 1,000+ messages THEN the system SHALL unlock the "💬 Голос чату" achievement

WHEN a user sends 5,000+ messages THEN the system SHALL unlock the "🪶 Писар" achievement

WHEN a user sends 10,000+ messages THEN the system SHALL unlock the "📜 Психошофьор" achievement

WHEN a user sends 20,000+ messages THEN the system SHALL unlock the "🏛️ Старійшина" achievement

WHEN a user sends 50,000+ messages THEN the system SHALL unlock the "👑 Володар чату" achievement

WHEN a user sends 100,000+ messages THEN the system SHALL unlock the "🌌 Легенда чату" achievement

WHEN a user sends 100+ messages in a single day THEN the system SHALL unlock the "⚡️ Денний марафон" achievement

WHEN a user is active for 7+ consecutive days THEN the system SHALL unlock the "📆 Без вихідних" achievement

WHEN a user stays active in the chat for 1+ year THEN the system SHALL unlock the "🎂 Чат-ветеран" achievement

WHEN a user sends the first message in the morning THEN the system SHALL unlock the "☀️ Жайворонок" achievement

WHEN a user sends the last message at night THEN the system SHALL unlock the "🌙 Сова" achievement

🔗 Лінки та медіа

WHEN a user shares 10+ photos THEN the system SHALL unlock the "📸 Фотолюбитель" achievement

WHEN a user shares 100+ photos THEN the system SHALL unlock the "🎞️ Фотопотік" achievement

WHEN a user shares 100+ Twitter links THEN the system SHALL unlock the "🐦 Твітерський" achievement

WHEN a user shares 10+ Steam links THEN the system SHALL unlock the "🎮 Гравець" achievement

WHEN a user shares 100+ memes THEN the system SHALL unlock the "😂 Мемолог" achievement

WHEN a user uploads their first video file THEN the system SHALL unlock the "🎥 Відеограф" achievement

WHEN a user shares 10+ music tracks THEN the system SHALL unlock the "🎶 Діджей чату" achievement

💬 Соціальні взаємодії

WHEN a user receives 100+ reactions THEN the system SHALL unlock the "🔥 Душа чату" achievement

WHEN a user makes their first reply THEN the system SHALL unlock the "↩️ Коментатор" achievement

WHEN a user creates their first poll THEN the system SHALL unlock the "📊 Голос народу" achievement

WHEN a user sends their first emoji THEN the system SHALL unlock the "😄 Емоційний" achievement

WHEN a user receives 5+ thanks THEN the system SHALL unlock the "🤝 Helpful" achievement

WHEN a user receives 100+ thanks THEN the system SHALL unlock the "🙏 Чемний" achievement

🎯 Рідкісні / фанові

WHEN a user sends the longest message in chat history THEN the system SHALL unlock the "📚 Романіст" achievement

WHEN a user sends the shortest message ("ок") THEN the system SHALL unlock the "👌 Мінімаліст" achievement

WHEN a user sends 100+ "лол"/"ахаха" messages THEN the system SHALL unlock the "🤣 Сміхун" achievement

WHEN a user mentions another user 50+ times THEN the system SHALL unlock the "📣 Тегер" achievement

WHEN a user sends their first sticker THEN the system SHALL unlock the "🖼️ Стікермайстер" achievement

WHEN a user sends 3+ consecutive messages without replies THEN the system SHALL unlock the "🧑‍🎤 Сольний концерт" achievement

WHEN a user sends their first swear word THEN the system SHALL unlock the "🤬 Бунтар" achievement

🆙 Рівні

WHEN a user reaches level 5 THEN the system SHALL unlock the "🆙 Level Up!" achievement

🎉 Системні правила

WHEN an achievement is unlocked THEN the system SHALL send a celebration message to the group chat

WHEN an achievement is unlocked THEN the system SHALL store the achievement record with timestamp

WHEN checking for achievements THEN the system SHALL prevent duplicate awards for the same achievement

### Requirement 4: Thank You Detection System

**User Story:** As a group chat member, I want to be recognized when others thank me so that helpful behavior is rewarded.

#### Acceptance Criteria

1. WHEN a message contains a user mention (@username) or reply to AND thank keywords THEN the system SHALL identify it as a thank you message
2. WHEN detecting thank keywords THEN the system SHALL recognize: "thanks", "thank you", "дякую", "תודה", and similar variations 10x, дякую, дяки, дякі, спасибі, спс, дяк і тд
3. WHEN a thank you is detected THEN the system SHALL award XP to the mentioned or replied to user, not the sender
4. WHEN processing thank messages THEN the system SHALL handle multiple mentions in a single message
5. WHEN processing thank messages THEN the system SHALL not be case-insensitive for keyword matching

### Requirement 5: User Profile Display

**User Story:** As a group chat member, I want to view my current level, XP, and achievements so that I can track my progress.

#### Acceptance Criteria

1. WHEN a user sends the "/profile" command THEN the system SHALL display their current stats
2. WHEN displaying profile THEN the system SHALL show: username, level, current XP, and earned achievements
3. WHEN displaying achievements THEN the system SHALL show achievement emojis in a readable format
4. WHEN a user has no achievements THEN the system SHALL display an appropriate message or closest achievment to earn
5. WHEN the profile command is used THEN the system SHALL respond in the same chat where the command was issued

### Requirement 6: Data Persistence

**User Story:** As a system administrator, I want user progress and achievements to be permanently stored so that data is not lost between bot restarts.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL create the required database tables if they don't exist
2. WHEN user data is updated THEN the system SHALL persist changes to the SQLite database
3. WHEN storing user data THEN the system SHALL use the users table with fields: user_id, username, xp, level, messages_count, links_shared, thanks_received
4. WHEN storing achievements THEN the system SHALL use the achievements table with fields: id, user_id, title, emoji, awarded_at
5. WHEN the bot restarts THEN the system SHALL maintain all user progress and achievement data

### Requirement 7: Message Processing Integration

**User Story:** As a system administrator, I want the leveling system to integrate seamlessly with the existing bot message handling so that it works automatically without disrupting other features.

#### Acceptance Criteria

1. WHEN any message is received in the group THEN the system SHALL process it for XP and achievement evaluation
2. WHEN processing messages THEN the system SHALL not interfere with existing bot functionality
3. WHEN the system encounters errors THEN it SHALL log them without crashing the bot
4. WHEN processing messages THEN the system SHALL handle new users automatically by creating database records
5. WHEN the system is disabled THEN existing bot functionality SHALL continue to work normally
6. WHEN use current data in the tables, to reevbaluate /profile and achievments 

### Requirement 8: Performance and Scalability

**User Story:** As a system administrator, I want the leveling system to perform efficiently so that it doesn't slow down the bot or consume excessive resources.

#### Acceptance Criteria

1. WHEN processing messages THEN the system SHALL complete XP calculations within 100ms
2. WHEN checking for achievements THEN the system SHALL use efficient database queries
3. WHEN storing data THEN the system SHALL use database transactions to ensure consistency
4. WHEN the group has many active users THEN the system SHALL maintain responsive performance
5. WHEN database operations fail THEN the system SHALL handle errors gracefully and retry if appropriate