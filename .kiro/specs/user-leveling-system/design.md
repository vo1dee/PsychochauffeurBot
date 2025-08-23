# Design Document

## Overview

The User Leveling System is designed as a comprehensive gamification module that integrates seamlessly with the existing PsychoChauffeur Telegram bot architecture. The system will track user activities, assign experience points (XP), manage level progression, and unlock achievements to enhance user engagement in group chats.

The design follows the existing service-oriented architecture pattern used throughout the bot, implementing the ServiceInterface for proper lifecycle management and integration with the ServiceRegistry. The system will be event-driven, processing messages in real-time while maintaining high performance through efficient database operations and caching strategies.

## Architecture

### High-Level Architecture

```mermaid
graph TB
    A[Message Handler] --> B[Leveling Service]
    B --> C[XP Calculator]
    B --> D[Level Manager]
    B --> E[Achievement Engine]
    B --> F[Database Layer]
    
    C --> G[Activity Detectors]
    G --> H[Message Detector]
    G --> I[Link Detector]
    G --> J[Thank You Detector]ÍÍ
    
    E --> K[Achievement Definitions]
    E --> L[Achievement Checker]
    
    F --> M[User Stats Repository]
    F --> N[Achievement Repository]
    
    B --> O[Notification Service]
    O --> P[Level Up Messages]
    O --> Q[Achievement Messages]
```

### Service Integration

The leveling system will integrate with the existing bot architecture through:

1. **ServiceRegistry Integration**: Registered as a singleton service with proper initialization and shutdown lifecycle
2. **Message Handler Integration**: Hooks into the existing message processing pipeline without disrupting current functionality
3. **Database Integration**: Extends the existing Database class with new tables and operations
4. **Configuration Integration**: Uses the existing ConfigManager for system settings and feature toggles

### Data Flow

1. **Message Reception**: Messages are intercepted by the existing message handler
2. **Activity Analysis**: The leveling service analyzes message content for XP-worthy activities
3. **XP Calculation**: Points are calculated based on activity type and user context
4. **Database Update**: User stats and XP are updated atomically
5. **Level Check**: System checks if user has reached a new level threshold
6. **Achievement Check**: System evaluates if any achievements should be unlocked
7. **Notification**: Level ups and achievements trigger celebration messages

## Components and Interfaces

### Core Service: UserLevelingService

```python
class UserLevelingService(ServiceInterface):
    """Main service orchestrating the leveling system."""
    
    async def initialize(self) -> None
    async def shutdown(self) -> None
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
    async def get_user_profile(self, user_id: int, chat_id: int) -> UserProfile
    async def get_leaderboard(self, chat_id: int, limit: int = 10) -> List[UserProfile]
```

### XP Calculation Engine

```python
class XPCalculator:
    """Calculates experience points for different activities."""
    
    def calculate_message_xp(self, message: Message) -> int
    def calculate_link_xp(self, message: Message) -> int
    def calculate_thanks_xp(self, message: Message, mentioned_users: List[int]) -> Dict[int, int]
    def detect_links(self, text: str) -> List[str]
    def detect_thanks(self, message: Message) -> List[int]
```

### Level Management

```python
class LevelManager:
    """Manages level calculations and thresholds."""
    
    def calculate_level(self, total_xp: int) -> int
    def get_level_threshold(self, level: int) -> int
    def get_next_level_progress(self, current_xp: int, current_level: int) -> Tuple[int, int]
    def check_level_up(self, old_xp: int, new_xp: int) -> Optional[int]
```

### Achievement System

```python
class AchievementEngine:
    """Manages achievement definitions and checking."""
    
    def check_achievements(self, user_stats: UserStats) -> List[Achievement]
    def is_achievement_unlocked(self, user_id: int, achievement_id: str) -> bool
    def unlock_achievement(self, user_id: int, achievement: Achievement) -> None
```

### Database Repositories

```python
class UserStatsRepository:
    """Database operations for user statistics."""
    
    async def get_user_stats(self, user_id: int, chat_id: int) -> Optional[UserStats]
    async def update_user_stats(self, user_stats: UserStats) -> None
    async def create_user_stats(self, user_id: int, chat_id: int) -> UserStats
    async def get_leaderboard(self, chat_id: int, limit: int) -> List[UserStats]

class AchievementRepository:
    """Database operations for achievements."""
    
    async def get_user_achievements(self, user_id: int, chat_id: int) -> List[UserAchievement]
    async def save_achievement(self, user_achievement: UserAchievement) -> None
    async def has_achievement(self, user_id: int, achievement_id: str) -> bool
```

### Activity Detectors

```python
class ActivityDetector:
    """Base class for activity detection."""
    
    def detect(self, message: Message) -> bool
    def calculate_xp(self, message: Message) -> int

class LinkDetector(ActivityDetector):
    """Detects link sharing activities."""

class ThankYouDetector(ActivityDetector):
    """Detects gratitude expressions with user mentions."""
```

## Data Models

### User Statistics Model

```python
@dataclass
class UserStats:
    user_id: int
    chat_id: int
    username: Optional[str]
    xp: int = 0
    level: int = 1
    messages_count: int = 0
    links_shared: int = 0
    thanks_received: int = 0
    created_at: datetime
    updated_at: datetime
```

### Achievement Models

```python
@dataclass
class Achievement:
    id: str
    title: str
    description: str
    emoji: str
    condition_type: str
    condition_value: int
    category: str

@dataclass
class UserAchievement:
    user_id: int
    chat_id: int
    achievement_id: str
    unlocked_at: datetime
```

### User Profile (Response Model)

```python
@dataclass
class UserProfile:
    user_id: int
    username: Optional[str]
    level: int
    xp: int
    next_level_xp: int
    progress_percentage: float
    achievements: List[Achievement]
    stats: Dict[str, int]
    rank: Optional[int] = None
```

## Database Schema

### Enhanced Users Table

The existing users table will be extended with leveling-specific fields:

```sql
-- Add leveling columns to existing users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS messages_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS links_shared INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS thanks_received INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW();
```

### New Tables

```sql
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
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
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
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_xp ON user_chat_stats(chat_id, xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_level ON user_chat_stats(chat_id, level DESC);
CREATE INDEX IF NOT EXISTS idx_user_chat_stats_activity ON user_chat_stats(last_activity);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id, chat_id);
```

## Integration Points

### Message Handler Integration

The leveling system will integrate with the existing message handling pipeline:

```python
# In modules/message_handler.py - add leveling processing
async def handle_message_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... existing message logging code ...
    
    # Add leveling system processing
    try:
        leveling_service = context.bot_data.get('service_registry').get_service('user_leveling_service')
        await leveling_service.process_message(update, context)
    except Exception as e:
        error_logger.error(f"Error in leveling system: {e}")
        # Don't interrupt normal message processing
```

### Command Integration

New commands will be registered through the existing CommandRegistry:

```python
# Profile command
self.register_command(CommandInfo(
    name="profile",
    description="Show your level, XP, and achievements",
    category=CommandCategory.UTILITY,
    handler_func=profile_command,
    usage="/profile [@username]",
    examples=["/profile", "/profile @john"]
))

# Leaderboard command
self.register_command(CommandInfo(
    name="leaderboard",
    description="Show chat leaderboard",
    category=CommandCategory.UTILITY,
    handler_func=leaderboard_command,
    aliases=["top", "rank"],
    usage="/leaderboard [limit]",
    examples=["/leaderboard", "/leaderboard 20"]
))
```

### Service Registry Integration

```python
# In application initialization
service_registry.register_singleton(
    'user_leveling_service',
    UserLevelingService,
    dependencies=['database', 'config_manager']
)
```

## Error Handling

### Database Error Handling

- **Connection Failures**: Use existing database retry mechanisms
- **Transaction Failures**: Implement atomic operations for XP updates
- **Constraint Violations**: Handle duplicate achievement unlocks gracefully

### Message Processing Errors

- **Invalid Message Data**: Skip processing without affecting other handlers
- **XP Calculation Errors**: Log errors and use default values
- **Achievement Check Failures**: Continue with XP updates even if achievement checking fails

### Performance Safeguards

- **Rate Limiting**: Prevent XP farming through rapid message sending
- **Batch Processing**: Group database updates for high-activity periods
- **Caching**: Cache user stats and achievement status for frequently active users

## Testing Strategy

### Unit Tests

- **XP Calculation**: Test all activity detection and XP calculation logic
- **Level Management**: Verify level threshold calculations and progression
- **Achievement Engine**: Test achievement condition checking and unlocking
- **Database Operations**: Test all repository methods with various scenarios

### Integration Tests

- **Message Processing**: Test end-to-end message processing with XP updates
- **Command Handlers**: Test profile and leaderboard commands
- **Database Integration**: Test with real database operations
- **Service Integration**: Test integration with existing bot services

### Performance Tests

- **High Message Volume**: Test system behavior under high message loads
- **Database Performance**: Measure query performance with large datasets
- **Memory Usage**: Monitor memory consumption during extended operation
- **Concurrent Users**: Test system behavior with multiple simultaneous users

### Test Data

- **Achievement Definitions**: Predefined test achievements for validation
- **User Scenarios**: Various user activity patterns for testing
- **Edge Cases**: Boundary conditions for XP and level calculations
- **Error Scenarios**: Simulated failures for error handling validation

## Configuration

### System Configuration

```yaml
leveling_system:
  enabled: true
  xp_rates:
    message: 1
    link: 3
    thanks: 5
  level_formula: "exponential"  # or "linear"
  level_base_xp: 50
  level_multiplier: 2.0
  rate_limiting:
    enabled: true
    max_xp_per_minute: 10
  notifications:
    level_up: true
    achievements: true
    celebration_emoji: true
  cache:
    user_stats_ttl: 300  # 5 minutes
    achievement_cache_ttl: 3600  # 1 hour
```

### Achievement Configuration

```yaml
achievements:
  chatterbox:
    title: "Chatterbox"
    emoji: "📬"
    condition: "messages >= 100"
    category: "activity"
  linker:
    title: "Linker"
    emoji: "🌐"
    condition: "links_shared >= 10"
    category: "sharing"
  helpful:
    title: "Helpful"
    emoji: "🤝"
    condition: "thanks_received >= 5"
    category: "social"
  level_up:
    title: "Level Up!"
    emoji: "🆙"
    condition: "level >= 5"
    category: "progression"
```

This design ensures the leveling system integrates seamlessly with the existing bot architecture while providing a robust, scalable, and engaging user experience.