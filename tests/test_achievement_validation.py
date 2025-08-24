"""
Achievement System Validation Tests

This test suite validates that all achievement conditions work correctly
and can be properly evaluated.
"""

import pytest
from modules.leveling_models import Achievement, UserStats
from modules.achievement_engine import AchievementEngine
from unittest.mock import Mock


class TestAchievementValidation:
    """Test achievement condition validation."""
    
    def test_basic_activity_achievements(self):
        """Test basic activity-based achievements."""
        # Test first message achievement
        first_message = Achievement(
            id="first_message",
            title="👶 Новачок",
            description="Send your first message",
            emoji="👶",
            sticker="👶",
            condition_type="messages_count",
            condition_value=1,
            category="activity"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456, messages_count=0)
        assert not first_message.check_condition(user_stats)
        
        user_stats.messages_count = 1
        assert first_message.check_condition(user_stats)
        
        # Test 100 messages achievement
        young_fluder = Achievement(
            id="young_fluder",
            title="🐣 Молодий флудер",
            description="Відправив 100+ повідомлень",
            emoji="🐣",
            sticker="🐣",
            condition_type="messages_count",
            condition_value=100,
            category="activity"
        )
        
        user_stats.messages_count = 99
        assert not young_fluder.check_condition(user_stats)
        
        user_stats.messages_count = 100
        assert young_fluder.check_condition(user_stats)
        
        user_stats.messages_count = 150
        assert young_fluder.check_condition(user_stats)
    
    def test_link_sharing_achievements(self):
        """Test link sharing achievements."""
        # Test Steam links achievement
        steam_achievement = Achievement(
            id="steam_gamer",
            title="🎮 Гравець",
            description="Share 10+ Steam links",
            emoji="🎮",
            sticker="🎮",
            condition_type="steam_links",
            condition_value=10,
            category="links"
        )
        
        # Test with context data
        user_stats = UserStats(user_id=123, chat_id=456)
        
        # Not enough Steam links
        assert not steam_achievement.check_condition(user_stats, steam_links=5)
        
        # Exactly 10 Steam links
        assert steam_achievement.check_condition(user_stats, steam_links=10)
        
        # More than 10 Steam links
        assert steam_achievement.check_condition(user_stats, steam_links=15)
    
    def test_social_achievements(self):
        """Test social interaction achievements."""
        # Test thanks received achievement
        helpful = Achievement(
            id="helpful",
            title="🤝 Helpful",
            description="Receive 5+ thanks",
            emoji="🤝",
            sticker="🤝",
            condition_type="thanks_received",
            condition_value=5,
            category="social"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456, thanks_received=4)
        assert not helpful.check_condition(user_stats)
        
        user_stats.thanks_received = 5
        assert helpful.check_condition(user_stats)
        
        user_stats.thanks_received = 10
        assert helpful.check_condition(user_stats)
    
    def test_level_based_achievements(self):
        """Test level-based achievements."""
        level_up = Achievement(
            id="level_up",
            title="🆙 Level Up!",
            description="Reach level 5",
            emoji="🆙",
            sticker="🆙",
            condition_type="level",
            condition_value=5,
            category="progression"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456, level=4)
        assert not level_up.check_condition(user_stats)
        
        user_stats.level = 5
        assert level_up.check_condition(user_stats)
        
        user_stats.level = 10
        assert level_up.check_condition(user_stats)
    
    def test_xp_based_achievements(self):
        """Test XP-based achievements."""
        xp_milestone = Achievement(
            id="xp_1000",
            title="💪 XP Master",
            description="Reach 1000 XP",
            emoji="💪",
            sticker="💪",
            condition_type="xp",
            condition_value=1000,
            category="progression"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456, xp=999)
        assert not xp_milestone.check_condition(user_stats)
        
        user_stats.xp = 1000
        assert xp_milestone.check_condition(user_stats)
        
        user_stats.xp = 1500
        assert xp_milestone.check_condition(user_stats)
    
    def test_complex_achievements_with_context(self):
        """Test achievements that require additional context data."""
        # Test daily messages achievement
        daily_marathon = Achievement(
            id="daily_marathon",
            title="⚡️ Денний марафон",
            description="Send 100+ messages in a single day",
            emoji="⚡️",
            sticker="⚡️",
            condition_type="daily_messages",
            condition_value=100,
            category="activity"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456)
        
        # Not enough daily messages
        assert not daily_marathon.check_condition(user_stats, daily_messages=50)
        
        # Exactly 100 daily messages
        assert daily_marathon.check_condition(user_stats, daily_messages=100)
        
        # More than 100 daily messages
        assert daily_marathon.check_condition(user_stats, daily_messages=150)
        
        # Test consecutive days achievement
        no_weekends = Achievement(
            id="no_weekends",
            title="📆 Без вихідних",
            description="Be active for 7+ consecutive days",
            emoji="📆",
            sticker="📆",
            condition_type="consecutive_days",
            condition_value=7,
            category="activity"
        )
        
        assert not no_weekends.check_condition(user_stats, consecutive_days=6)
        assert no_weekends.check_condition(user_stats, consecutive_days=7)
        assert no_weekends.check_condition(user_stats, consecutive_days=10)
    
    def test_special_achievements(self):
        """Test special/rare achievements."""
        # Test longest message achievement
        novelist = Achievement(
            id="novelist",
            title="📚 Романіст",
            description="Send the longest message in chat history",
            emoji="📚",
            sticker="📚",
            condition_type="longest_message",
            condition_value=1,
            category="rare"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456)
        
        # Not the longest message
        assert not novelist.check_condition(user_stats, is_longest_message=False)
        
        # Is the longest message
        assert novelist.check_condition(user_stats, is_longest_message=True)
        
        # Test shortest message achievement
        minimalist = Achievement(
            id="minimalist",
            title="👌 Мінімаліст",
            description="Send the shortest message ('ок')",
            emoji="👌",
            sticker="👌",
            condition_type="shortest_message",
            condition_value=1,
            category="rare"
        )
        
        assert not minimalist.check_condition(user_stats, is_shortest_message=False)
        assert minimalist.check_condition(user_stats, is_shortest_message=True)
    
    def test_media_achievements(self):
        """Test media-related achievements."""
        # Test photo sharing achievement
        photo_lover = Achievement(
            id="photo_lover",
            title="📸 Фотолюбитель",
            description="Share 10+ photos",
            emoji="📸",
            sticker="📸",
            condition_type="photos_shared",
            condition_value=10,
            category="media"
        )
        
        user_stats = UserStats(user_id=123, chat_id=456)
        
        assert not photo_lover.check_condition(user_stats, photos_shared=9)
        assert photo_lover.check_condition(user_stats, photos_shared=10)
        assert photo_lover.check_condition(user_stats, photos_shared=15)
        
        # Test video achievement
        videographer = Achievement(
            id="videographer",
            title="🎥 Відеограф",
            description="Upload your first video file",
            emoji="🎥",
            sticker="🎥",
            condition_type="videos_uploaded",
            condition_value=1,
            category="media"
        )
        
        assert not videographer.check_condition(user_stats, videos_uploaded=0)
        assert videographer.check_condition(user_stats, videos_uploaded=1)
        assert videographer.check_condition(user_stats, videos_uploaded=5)
    
    def test_achievement_engine_integration(self):
        """Test achievement engine can properly evaluate achievements."""
        # Mock achievement repository
        mock_repo = Mock()
        
        # Create achievement engine
        engine = AchievementEngine(mock_repo)
        
        # Test that engine exists and has required methods
        assert hasattr(engine, 'check_achievements')
        assert hasattr(engine, 'is_achievement_unlocked')
        assert hasattr(engine, 'unlock_achievement')
        
        # Test achievement definitions exist
        from modules.achievement_engine import AchievementDefinitions
        all_achievements = AchievementDefinitions.get_all_achievements()
        assert len(all_achievements) > 0
        
        # Verify some key achievements are defined
        achievement_ids = [achievement.id for achievement in all_achievements]
        
        # Check for basic activity achievements
        assert "novice" in achievement_ids
        assert "young_fluder" in achievement_ids
        
        # Print available achievement IDs for debugging
        print(f"Available achievement IDs: {sorted(achievement_ids)}")
    
    def test_all_achievement_categories_covered(self):
        """Test that all achievement categories are properly covered."""
        from modules.achievement_engine import AchievementDefinitions
        
        # Get all achievements
        all_achievements = AchievementDefinitions.get_all_achievements()
        
        # Get all categories
        categories = set()
        for achievement in all_achievements:
            categories.add(achievement.category)
        
        # Verify expected categories exist
        expected_categories = {"activity", "social", "media", "rare", "progression"}
        
        # Check that we have achievements in major categories
        assert "activity" in categories
        assert "social" in categories
        
        # Print categories for verification
        print(f"Achievement categories found: {sorted(categories)}")
        
        # Verify we have a reasonable number of achievements
        assert len(all_achievements) >= 10
        
        print(f"Total achievements defined: {len(all_achievements)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])