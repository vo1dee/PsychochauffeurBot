"""
Data models for the user leveling system.

This module contains all the data classes and models used by the leveling system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from modules.types import UserId, ChatId, Timestamp


@dataclass
class UserStats:
    """
    User statistics model for the leveling system.
    
    Represents a user's progress and activity in a specific chat.
    """
    user_id: UserId
    chat_id: ChatId
    xp: int = 0
    level: int = 1
    messages_count: int = 0
    links_shared: int = 0
    thanks_received: int = 0
    last_activity: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Set default timestamps if not provided."""
        now = datetime.utcnow()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if self.last_activity is None:
            self.last_activity = now
    
    def add_xp(self, amount: int) -> None:
        """Add XP to the user's total."""
        self.xp += amount
        self.updated_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def increment_messages(self) -> None:
        """Increment the message count."""
        self.messages_count += 1
        self.updated_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def increment_links(self) -> None:
        """Increment the links shared count."""
        self.links_shared += 1
        self.updated_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def increment_thanks(self) -> None:
        """Increment the thanks received count."""
        self.thanks_received += 1
        self.updated_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def update_level(self, new_level: int) -> None:
        """Update the user's level."""
        self.level = new_level
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'xp': self.xp,
            'level': self.level,
            'messages_count': self.messages_count,
            'links_shared': self.links_shared,
            'thanks_received': self.thanks_received,
            'last_activity': self.last_activity,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserStats':
        """Create UserStats from dictionary."""
        return cls(
            user_id=data['user_id'],
            chat_id=data['chat_id'],
            xp=data.get('xp', 0),
            level=data.get('level', 1),
            messages_count=data.get('messages_count', 0),
            links_shared=data.get('links_shared', 0),
            thanks_received=data.get('thanks_received', 0),
            last_activity=data.get('last_activity'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )


@dataclass
class Achievement:
    """
    Achievement definition model.
    
    Represents an achievement that users can unlock.
    """
    id: str
    title: str
    description: str
    emoji: str
    sticker: str
    condition_type: str
    condition_value: int
    category: str
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Set default timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'emoji': self.emoji,
            'sticker': self.sticker,
            'condition_type': self.condition_type,
            'condition_value': self.condition_value,
            'category': self.category,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Achievement':
        """Create Achievement from dictionary."""
        return cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            emoji=data['emoji'],
            condition_type=data['condition_type'],
            condition_value=data['condition_value'],
            category=data['category'],
            created_at=data.get('created_at')
        )
    
    def check_condition(self, user_stats: UserStats, **kwargs) -> bool:
        """
        Check if the achievement condition is met.
        
        Args:
            user_stats: User statistics to check against
            **kwargs: Additional context data for complex conditions
            
        Returns:
            True if the achievement should be unlocked
        """
        if self.condition_type == "messages_count":
            return user_stats.messages_count >= self.condition_value
        elif self.condition_type == "links_shared":
            return user_stats.links_shared >= self.condition_value
        elif self.condition_type == "thanks_received":
            return user_stats.thanks_received >= self.condition_value
        elif self.condition_type == "level":
            return user_stats.level >= self.condition_value
        elif self.condition_type == "xp":
            return user_stats.xp >= self.condition_value
        
        # For complex conditions that require additional data
        elif self.condition_type == "daily_messages":
            return kwargs.get('daily_messages', 0) >= self.condition_value
        elif self.condition_type == "consecutive_days":
            return kwargs.get('consecutive_days', 0) >= self.condition_value
        elif self.condition_type == "days_active":
            return kwargs.get('days_active', 0) >= self.condition_value
        elif self.condition_type == "first_morning_message":
            return kwargs.get('is_first_morning_message', False)
        elif self.condition_type == "last_night_message":
            return kwargs.get('is_last_night_message', False)
        elif self.condition_type == "photos_shared":
            return kwargs.get('photos_shared', 0) >= self.condition_value
        elif self.condition_type == "twitter_links":
            return kwargs.get('twitter_links', 0) >= self.condition_value
        elif self.condition_type == "steam_links":
            return kwargs.get('steam_links', 0) >= self.condition_value
        elif self.condition_type == "memes_shared":
            return kwargs.get('memes_shared', 0) >= self.condition_value
        elif self.condition_type == "videos_uploaded":
            return kwargs.get('videos_uploaded', 0) >= self.condition_value
        elif self.condition_type == "music_shared":
            return kwargs.get('music_shared', 0) >= self.condition_value
        elif self.condition_type == "reactions_received":
            return kwargs.get('reactions_received', 0) >= self.condition_value
        elif self.condition_type == "replies_made":
            return kwargs.get('replies_made', 0) >= self.condition_value
        elif self.condition_type == "polls_created":
            return kwargs.get('polls_created', 0) >= self.condition_value
        elif self.condition_type == "emojis_sent":
            return kwargs.get('emojis_sent', 0) >= self.condition_value
        elif self.condition_type == "longest_message":
            return kwargs.get('is_longest_message', False)
        elif self.condition_type == "shortest_message":
            return kwargs.get('is_shortest_message', False)
        elif self.condition_type == "laugh_messages":
            return kwargs.get('laugh_messages', 0) >= self.condition_value
        elif self.condition_type == "mentions_made":
            return kwargs.get('mentions_made', 0) >= self.condition_value
        elif self.condition_type == "stickers_sent":
            return kwargs.get('stickers_sent', 0) >= self.condition_value
        elif self.condition_type == "consecutive_messages":
            return kwargs.get('consecutive_messages', 0) >= self.condition_value
        elif self.condition_type == "swear_words":
            return kwargs.get('swear_words', 0) >= self.condition_value
        
        return False


@dataclass
class UserAchievement:
    """
    User achievement model.
    
    Represents an achievement that has been unlocked by a user in a specific chat.
    """
    user_id: UserId
    chat_id: ChatId
    achievement_id: str
    unlocked_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Set default timestamp if not provided."""
        if self.unlocked_at is None:
            self.unlocked_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'achievement_id': self.achievement_id,
            'unlocked_at': self.unlocked_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserAchievement':
        """Create UserAchievement from dictionary."""
        return cls(
            user_id=data['user_id'],
            chat_id=data['chat_id'],
            achievement_id=data['achievement_id'],
            unlocked_at=data.get('unlocked_at')
        )


@dataclass
class UserProfile:
    """
    User profile response model.
    
    Represents a complete user profile with stats, level, and achievements.
    """
    user_id: UserId
    username: Optional[str]
    level: int
    xp: int
    next_level_xp: int
    progress_percentage: float
    achievements: List[Achievement] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    rank: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'level': self.level,
            'xp': self.xp,
            'next_level_xp': self.next_level_xp,
            'progress_percentage': self.progress_percentage,
            'achievements': [achievement.to_dict() for achievement in self.achievements],
            'stats': self.stats,
            'rank': self.rank
        }
    
    @classmethod
    def from_user_stats(
        cls,
        user_stats: UserStats,
        username: Optional[str],
        next_level_xp: int,
        progress_percentage: float,
        achievements: List[Achievement],
        rank: Optional[int] = None
    ) -> 'UserProfile':
        """Create UserProfile from UserStats and additional data."""
        return cls(
            user_id=user_stats.user_id,
            username=username,
            level=user_stats.level,
            xp=user_stats.xp,
            next_level_xp=next_level_xp,
            progress_percentage=progress_percentage,
            achievements=achievements,
            stats={
                'messages_count': user_stats.messages_count,
                'links_shared': user_stats.links_shared,
                'thanks_received': user_stats.thanks_received
            },
            rank=rank
        )


@dataclass
class LevelUpResult:
    """
    Result of a level up check.
    
    Contains information about whether a level up occurred and the new level.
    """
    leveled_up: bool
    old_level: int
    new_level: int
    xp_for_next_level: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'leveled_up': self.leveled_up,
            'old_level': self.old_level,
            'new_level': self.new_level,
            'xp_for_next_level': self.xp_for_next_level
        }


@dataclass
class XPGainResult:
    """
    Result of XP calculation and awarding.
    
    Contains information about XP gained and any level changes.
    """
    xp_gained: int
    total_xp: int
    level_up_result: Optional[LevelUpResult] = None
    achievements_unlocked: List[Achievement] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'xp_gained': self.xp_gained,
            'total_xp': self.total_xp,
            'level_up_result': self.level_up_result.to_dict() if self.level_up_result else None,
            'achievements_unlocked': [achievement.to_dict() for achievement in self.achievements_unlocked]
        }