"""
Unit tests for the achievement system engine.

Tests achievement definitions, condition checking, unlocking logic,
and all achievement types defined in the requirements.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any

from modules.achievement_engine import AchievementEngine, AchievementDefinitions
from modules.leveling_models import Achievement, UserStats, UserAchievement
from modules.repositories import AchievementRepository


class TestAchievementDefinitions:
    """Test achievement definitions and their properties."""
    
    def test_get_all_achievements_returns_complete_list(self):
        """Test that all achievements are returned."""
        achievements = AchievementDefinitions.get_all_achievements()
        
        # Should have achievements from all categories
        assert len(achievements) > 0
        
        # Check that we have achievements from each category
        categories = {ach.category for ach in achievements}
        expected_categories = {'activity', 'media', 'social', 'rare', 'level'}
        assert expected_categories.issubset(categories)
    
    def test_activity_achievements_structure(self):
        """Test activity achievements have correct structure."""
        achievements = AchievementDefinitions._get_activity_achievements()
        
        # Check specific achievements from requirements
        achievement_ids = {ach.id for ach in achievements}
        
        expected_achievements = {
            'novice', 'young_chatter', 'active_talker', 'chat_voice',
            'scribe', 'psycho_chauffeur', 'elder', 'chat_lord', 'chat_legend',
            'daily_marathon', 'no_weekends', 'chat_veteran', 'early_bird', 'night_owl'
        }
        
        assert expected_achievements.issubset(achievement_ids)
        
        # Check message count achievements have correct thresholds
        novice = next(ach for ach in achievements if ach.id == 'novice')
        assert novice.condition_value == 1
        assert novice.condition_type == 'messages_count'
        assert novice.emoji == '👶'
        
        young_chatter = next(ach for ach in achievements if ach.id == 'young_chatter')
        assert young_chatter.condition_value == 100
        assert young_chatter.condition_type == 'messages_count'
    
    def test_media_achievements_structure(self):
        """Test media achievements have correct structure."""
        achievements = AchievementDefinitions._get_media_achievements()
        
        achievement_ids = {ach.id for ach in achievements}
        expected_achievements = {
            'photo_lover', 'photo_stream', 'twitter_user', 'gamer',
            'meme_lord', 'videographer', 'chat_dj'
        }
        
        assert expected_achievements.issubset(achievement_ids)
        
        # Check specific achievement properties
        photo_lover = next(ach for ach in achievements if ach.id == 'photo_lover')
        assert photo_lover.condition_type == 'photos_shared'
        assert photo_lover.condition_value == 10
        assert photo_lover.category == 'media'
    
    def test_social_achievements_structure(self):
        """Test social achievements have correct structure."""
        achievements = AchievementDefinitions._get_social_achievements()
        
        achievement_ids = {ach.id for ach in achievements}
        expected_achievements = {
            'soul_of_chat', 'commenter', 'voice_of_people', 'emotional',
            'helpful', 'polite'
        }
        
        assert expected_achievements.issubset(achievement_ids)
        
        # Check thanks-based achievements
        helpful = next(ach for ach in achievements if ach.id == 'helpful')
        assert helpful.condition_type == 'thanks_received'
        assert helpful.condition_value == 5
        
        polite = next(ach for ach in achievements if ach.id == 'polite')
        assert polite.condition_type == 'thanks_received'
        assert polite.condition_value == 100
    
    def test_rare_achievements_structure(self):
        """Test rare achievements have correct structure."""
        achievements = AchievementDefinitions._get_rare_achievements()
        
        achievement_ids = {ach.id for ach in achievements}
        expected_achievements = {
            'novelist', 'minimalist', 'laugher', 'tagger',
            'sticker_master', 'solo_concert', 'rebel'
        }
        
        assert expected_achievements.issubset(achievement_ids)
        
        # Check specific rare achievements
        minimalist = next(ach for ach in achievements if ach.id == 'minimalist')
        assert minimalist.condition_type == 'shortest_message'
        assert minimalist.condition_value == 1
    
    def test_level_achievements_structure(self):
        """Test level achievements have correct structure."""
        achievements = AchievementDefinitions._get_level_achievements()
        
        level_up = next(ach for ach in achievements if ach.id == 'level_up')
        assert level_up.condition_type == 'level'
        assert level_up.condition_value == 5
        assert level_up.emoji == '🆙'
    
    def test_all_achievements_have_required_fields(self):
        """Test that all achievements have required fields."""
        achievements = AchievementDefinitions.get_all_achievements()
        
        for achievement in achievements:
            assert achievement.id
            assert achievement.title
            assert achievement.description
            assert achievement.emoji
            assert achievement.sticker
            assert achievement.condition_type
            assert achievement.condition_value >= 0
            assert achievement.category
            assert isinstance(achievement.created_at, datetime)


class TestAchievementEngine:
    """Test the achievement engine functionality."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock achievement repository."""
        return AsyncMock(spec=AchievementRepository)
    
    @pytest.fixture
    def achievement_engine(self, mock_repository):
        """Create an achievement engine with mocked repository."""
        return AchievementEngine(mock_repository)
    
    @pytest.fixture
    def sample_user_stats(self):
        """Create sample user statistics."""
        return UserStats(
            user_id=12345,
            chat_id=67890,
            xp=150,
            level=2,
            messages_count=50,
            links_shared=5,
            thanks_received=3
        )
    
    @pytest.fixture
    def sample_achievements(self):
        """Create sample achievements for testing."""
        return [
            Achievement(
                id="test_messages_100",
                title="Test 100 Messages",
                description="Send 100 messages",
                emoji="📝",
                sticker="📝",
                condition_type="messages_count",
                condition_value=100,
                category="test"
            ),
            Achievement(
                id="test_thanks_5",
                title="Test 5 Thanks",
                description="Receive 5 thanks",
                emoji="🙏",
                sticker="🙏",
                condition_type="thanks_received",
                condition_value=5,
                category="test"
            ),
            Achievement(
                id="test_level_3",
                title="Test Level 3",
                description="Reach level 3",
                emoji="⬆️",
                sticker="⬆️",
                condition_type="level",
                condition_value=3,
                category="test"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_initialize_achievement_definitions(self, achievement_engine, mock_repository):
        """Test initialization of achievement definitions."""
        mock_repository.save_achievement = AsyncMock()
        
        await achievement_engine.initialize_achievement_definitions()
        
        # Should save all achievements
        assert mock_repository.save_achievement.call_count > 0
        
        # Verify some specific achievements were saved
        saved_achievement_ids = []
        for call in mock_repository.save_achievement.call_args_list:
            achievement = call[0][0]
            saved_achievement_ids.append(achievement.id)
        
        assert 'novice' in saved_achievement_ids
        assert 'helpful' in saved_achievement_ids
        assert 'level_up' in saved_achievement_ids
    
    @pytest.mark.asyncio
    async def test_get_all_achievements_with_caching(self, achievement_engine, mock_repository, sample_achievements):
        """Test getting all achievements with caching."""
        mock_repository.get_all_achievements.return_value = sample_achievements
        
        # First call should hit the repository
        result1 = await achievement_engine.get_all_achievements()
        assert result1 == sample_achievements
        assert mock_repository.get_all_achievements.call_count == 1
        
        # Second call should use cache
        result2 = await achievement_engine.get_all_achievements()
        assert result2 == sample_achievements
        assert mock_repository.get_all_achievements.call_count == 1  # Still 1
    
    @pytest.mark.asyncio
    async def test_get_achievement_by_id(self, achievement_engine, mock_repository, sample_achievements):
        """Test getting achievement by ID."""
        mock_repository.get_all_achievements.return_value = sample_achievements
        
        # Get existing achievement
        result = await achievement_engine.get_achievement_by_id("test_messages_100")
        assert result is not None
        assert result.id == "test_messages_100"
        
        # Get non-existing achievement
        result = await achievement_engine.get_achievement_by_id("non_existing")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_achievements_basic_conditions(self, achievement_engine, mock_repository, sample_achievements, sample_user_stats):
        """Test checking achievements with basic conditions."""
        mock_repository.get_all_achievements.return_value = sample_achievements
        mock_repository.get_user_achievements.return_value = []  # No achievements unlocked yet
        
        # User has 50 messages, 3 thanks, level 2
        # Should not unlock messages_100 or level_3, but should unlock thanks_5
        sample_user_stats.thanks_received = 5
        
        result = await achievement_engine.check_achievements(12345, 67890, sample_user_stats)
        
        # Should return the thanks achievement
        assert len(result) == 1
        assert result[0].id == "test_thanks_5"
    
    @pytest.mark.asyncio
    async def test_check_achievements_with_unlocked_achievements(self, achievement_engine, mock_repository, sample_achievements, sample_user_stats):
        """Test that already unlocked achievements are not returned."""
        mock_repository.get_all_achievements.return_value = sample_achievements
        
        # User already has the thanks achievement
        existing_achievements = [
            UserAchievement(12345, 67890, "test_thanks_5")
        ]
        mock_repository.get_user_achievements.return_value = existing_achievements
        
        sample_user_stats.thanks_received = 5
        
        result = await achievement_engine.check_achievements(12345, 67890, sample_user_stats)
        
        # Should not return the already unlocked achievement
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_check_achievements_with_context_data(self, achievement_engine, mock_repository, sample_user_stats):
        """Test checking achievements with context data for complex conditions."""
        # Create achievement that requires context data
        complex_achievement = Achievement(
            id="test_daily_messages",
            title="Daily Messages",
            description="Send 50 messages in one day",
            emoji="📅",
            sticker="📅",
            condition_type="daily_messages",
            condition_value=50,
            category="test"
        )
        
        mock_repository.get_all_achievements.return_value = [complex_achievement]
        mock_repository.get_user_achievements.return_value = []
        
        context_data = {"daily_messages": 60}
        
        result = await achievement_engine.check_achievements(12345, 67890, sample_user_stats, context_data)
        
        assert len(result) == 1
        assert result[0].id == "test_daily_messages"
    
    @pytest.mark.asyncio
    async def test_unlock_achievement(self, achievement_engine, mock_repository, sample_achievements):
        """Test unlocking a single achievement."""
        mock_repository.has_achievement.return_value = False
        mock_repository.unlock_achievement = AsyncMock()
        
        achievement = sample_achievements[0]
        
        result = await achievement_engine.unlock_achievement(12345, 67890, achievement)
        
        assert result.user_id == 12345
        assert result.chat_id == 67890
        assert result.achievement_id == achievement.id
        assert isinstance(result.unlocked_at, datetime)
        
        mock_repository.unlock_achievement.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unlock_achievement_already_unlocked(self, achievement_engine, mock_repository, sample_achievements):
        """Test unlocking an already unlocked achievement."""
        mock_repository.has_achievement.return_value = True
        mock_repository.unlock_achievement = AsyncMock()
        
        achievement = sample_achievements[0]
        
        result = await achievement_engine.unlock_achievement(12345, 67890, achievement)
        
        # Should still return a UserAchievement but not call unlock
        assert result.achievement_id == achievement.id
        mock_repository.unlock_achievement.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_unlock_achievements_bulk(self, achievement_engine, mock_repository, sample_achievements):
        """Test unlocking multiple achievements."""
        mock_repository.has_achievement.return_value = False
        mock_repository.bulk_unlock_achievements = AsyncMock()
        
        achievements = sample_achievements[:2]
        
        result = await achievement_engine.unlock_achievements(12345, 67890, achievements)
        
        assert len(result) == 2
        assert all(ua.user_id == 12345 for ua in result)
        assert all(ua.chat_id == 67890 for ua in result)
        
        mock_repository.bulk_unlock_achievements.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_is_achievement_unlocked(self, achievement_engine, mock_repository):
        """Test checking if achievement is unlocked."""
        mock_repository.has_achievement.return_value = True
        
        result = await achievement_engine.is_achievement_unlocked(12345, 67890, "test_achievement")
        
        assert result is True
        mock_repository.has_achievement.assert_called_once_with(12345, 67890, "test_achievement")
    
    @pytest.mark.asyncio
    async def test_get_user_achievements(self, achievement_engine, mock_repository, sample_achievements):
        """Test getting user achievements."""
        achievement_data = [(UserAchievement(12345, 67890, "test_1"), sample_achievements[0])]
        mock_repository.get_user_achievements_with_details.return_value = achievement_data
        
        result = await achievement_engine.get_user_achievements(12345, 67890)
        
        assert len(result) == 1
        assert result[0] == sample_achievements[0]
    
    @pytest.mark.asyncio
    async def test_get_achievements_by_category(self, achievement_engine, mock_repository, sample_achievements):
        """Test getting achievements by category."""
        test_achievements = [ach for ach in sample_achievements if ach.category == "test"]
        mock_repository.get_achievements_by_category.return_value = test_achievements
        
        result = await achievement_engine.get_achievements_by_category("test")
        
        assert result == test_achievements
        mock_repository.get_achievements_by_category.assert_called_once_with("test")
    
    def test_create_context_data_basic(self, achievement_engine):
        """Test creating context data with basic parameters."""
        context = achievement_engine.create_context_data(
            daily_messages=50,
            consecutive_days=7,
            is_photo=True,
            is_reply=True,
            mentions_count=2
        )
        
        assert context['daily_messages'] == 50
        assert context['consecutive_days'] == 7
        assert context['photos_shared'] == 1
        assert context['replies_made'] == 1
        assert context['mentions_made'] == 2
    
    def test_create_context_data_with_message_analysis(self, achievement_engine):
        """Test creating context data with message content analysis."""
        context = achievement_engine.create_context_data(
            message_text="лол это очень смешно ахаха",
            is_sticker=True
        )
        
        assert context['laugh_messages'] == 1
        assert context['stickers_sent'] == 1
    
    def test_analyze_message_content_laugh_detection(self, achievement_engine):
        """Test message content analysis for laugh detection."""
        test_cases = [
            ("лол це смішно", {'laugh_messages': 1}),
            ("ахаха це смішно", {'laugh_messages': 1}),
            ("хахахаха", {'laugh_messages': 1}),
            ("звичайне повідомлення", {}),
            ("😂😂😂", {'laugh_messages': 1}),
        ]
        
        for message, expected in test_cases:
            result = achievement_engine._analyze_message_content(message)
            for key, value in expected.items():
                assert result.get(key) == value
    
    def test_analyze_message_content_shortest_message(self, achievement_engine):
        """Test detection of shortest message."""
        test_cases = [
            ("ок", {'is_shortest_message': True}),
            ("ok", {'is_shortest_message': True}),
            ("OK", {'is_shortest_message': True}),
            ("окей", {}),
            ("okay", {}),
        ]
        
        for message, expected in test_cases:
            result = achievement_engine._analyze_message_content(message)
            for key, value in expected.items():
                assert result.get(key) == value
    
    def test_analyze_message_content_link_detection(self, achievement_engine):
        """Test detection of specific link types."""
        test_cases = [
            ("Check this out: https://twitter.com/user/status/123", {'twitter_links': 1}),
            ("Steam game: https://store.steampowered.com/app/123", {'steam_links': 1}),
            ("Multiple links: twitter.com and x.com", {'twitter_links': 2}),
            ("Regular link: https://google.com", {}),
        ]
        
        for message, expected in test_cases:
            result = achievement_engine._analyze_message_content(message)
            for key, value in expected.items():
                assert result.get(key) == value
    
    def test_analyze_message_content_swear_detection(self, achievement_engine):
        """Test detection of swear words."""
        # Note: This is a simplified test - in production you'd want more sophisticated detection
        test_cases = [
            ("блять, це погано", {'swear_words': 1}),
            ("fuck this", {'swear_words': 1}),
            ("звичайне повідомлення", {}),
        ]
        
        for message, expected in test_cases:
            result = achievement_engine._analyze_message_content(message)
            for key, value in expected.items():
                assert result.get(key) == value
    
    @pytest.mark.asyncio
    async def test_get_achievement_progress_unlocked(self, achievement_engine, mock_repository, sample_achievements, sample_user_stats):
        """Test getting progress for an unlocked achievement."""
        mock_repository.get_all_achievements.return_value = sample_achievements
        mock_repository.has_achievement.return_value = True
        
        result = await achievement_engine.get_achievement_progress(12345, 67890, sample_user_stats, "test_thanks_5")
        
        assert result is not None
        assert result['unlocked'] is True
        assert result['percentage'] == 100.0
        assert result['progress'] == 5
        assert result['target'] == 5
    
    @pytest.mark.asyncio
    async def test_get_achievement_progress_in_progress(self, achievement_engine, mock_repository, sample_achievements, sample_user_stats):
        """Test getting progress for an achievement in progress."""
        mock_repository.get_all_achievements.return_value = sample_achievements
        mock_repository.has_achievement.return_value = False
        
        # User has 50 messages, target is 100
        result = await achievement_engine.get_achievement_progress(12345, 67890, sample_user_stats, "test_messages_100")
        
        assert result is not None
        assert result['unlocked'] is False
        assert result['percentage'] == 50.0
        assert result['progress'] == 50
        assert result['target'] == 100
    
    @pytest.mark.asyncio
    async def test_get_achievement_progress_not_found(self, achievement_engine, mock_repository, sample_user_stats):
        """Test getting progress for non-existent achievement."""
        mock_repository.get_all_achievements.return_value = []
        
        result = await achievement_engine.get_achievement_progress(12345, 67890, sample_user_stats, "non_existent")
        
        assert result is None
    
    def test_get_current_value_for_condition(self, achievement_engine, sample_user_stats):
        """Test getting current values for different condition types."""
        test_cases = [
            ("messages_count", 50),
            ("links_shared", 5),
            ("thanks_received", 3),
            ("level", 2),
            ("xp", 150),
            ("unknown_condition", 0),
        ]
        
        for condition_type, expected_value in test_cases:
            result = achievement_engine._get_current_value_for_condition(sample_user_stats, condition_type)
            assert result == expected_value


class TestAchievementConditionChecking:
    """Test achievement condition checking logic."""
    
    @pytest.fixture
    def sample_user_stats(self):
        """Create sample user statistics."""
        return UserStats(
            user_id=12345,
            chat_id=67890,
            xp=250,
            level=3,
            messages_count=150,
            links_shared=8,
            thanks_received=12
        )
    
    def test_basic_condition_checking(self, sample_user_stats):
        """Test basic condition checking for different types."""
        # Messages count achievement
        messages_achievement = Achievement(
            id="test_messages",
            title="Test Messages",
            description="Send messages",
            emoji="📝",
            sticker="📝",
            condition_type="messages_count",
            condition_value=100,
            category="test"
        )
        
        assert messages_achievement.check_condition(sample_user_stats) is True
        
        # Higher threshold should fail
        messages_achievement.condition_value = 200
        assert messages_achievement.check_condition(sample_user_stats) is False
    
    def test_thanks_condition_checking(self, sample_user_stats):
        """Test thanks-based condition checking."""
        thanks_achievement = Achievement(
            id="test_thanks",
            title="Test Thanks",
            description="Receive thanks",
            emoji="🙏",
            sticker="🙏",
            condition_type="thanks_received",
            condition_value=10,
            category="test"
        )
        
        assert thanks_achievement.check_condition(sample_user_stats) is True
        
        thanks_achievement.condition_value = 15
        assert thanks_achievement.check_condition(sample_user_stats) is False
    
    def test_level_condition_checking(self, sample_user_stats):
        """Test level-based condition checking."""
        level_achievement = Achievement(
            id="test_level",
            title="Test Level",
            description="Reach level",
            emoji="⬆️",
            sticker="⬆️",
            condition_type="level",
            condition_value=3,
            category="test"
        )
        
        assert level_achievement.check_condition(sample_user_stats) is True
        
        level_achievement.condition_value = 5
        assert level_achievement.check_condition(sample_user_stats) is False
    
    def test_xp_condition_checking(self, sample_user_stats):
        """Test XP-based condition checking."""
        xp_achievement = Achievement(
            id="test_xp",
            title="Test XP",
            description="Earn XP",
            emoji="⭐",
            sticker="⭐",
            condition_type="xp",
            condition_value=200,
            category="test"
        )
        
        assert xp_achievement.check_condition(sample_user_stats) is True
        
        xp_achievement.condition_value = 300
        assert xp_achievement.check_condition(sample_user_stats) is False
    
    def test_complex_condition_checking(self, sample_user_stats):
        """Test complex condition checking with context data."""
        daily_achievement = Achievement(
            id="test_daily",
            title="Daily Achievement",
            description="Daily activity",
            emoji="📅",
            sticker="📅",
            condition_type="daily_messages",
            condition_value=50,
            category="test"
        )
        
        # Without context data, should fail
        assert daily_achievement.check_condition(sample_user_stats) is False
        
        # With sufficient context data, should pass
        context_data = {"daily_messages": 60}
        assert daily_achievement.check_condition(sample_user_stats, **context_data) is True
        
        # With insufficient context data, should fail
        context_data = {"daily_messages": 40}
        assert daily_achievement.check_condition(sample_user_stats, **context_data) is False
    
    def test_boolean_condition_checking(self, sample_user_stats):
        """Test boolean-based condition checking."""
        morning_achievement = Achievement(
            id="test_morning",
            title="Morning Achievement",
            description="First morning message",
            emoji="☀️",
            sticker="☀️",
            condition_type="first_morning_message",
            condition_value=1,
            category="test"
        )
        
        # Should fail without context
        assert morning_achievement.check_condition(sample_user_stats) is False
        
        # Should pass with positive context
        context_data = {"is_first_morning_message": True}
        assert morning_achievement.check_condition(sample_user_stats, **context_data) is True
        
        # Should fail with negative context
        context_data = {"is_first_morning_message": False}
        assert morning_achievement.check_condition(sample_user_stats, **context_data) is False


class TestAchievementEngineErrorHandling:
    """Test error handling in the achievement engine."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository that can raise exceptions."""
        return AsyncMock(spec=AchievementRepository)
    
    @pytest.fixture
    def achievement_engine(self, mock_repository):
        """Create an achievement engine with mocked repository."""
        return AchievementEngine(mock_repository)
    
    @pytest.fixture
    def sample_user_stats(self):
        """Create sample user statistics."""
        return UserStats(
            user_id=12345,
            chat_id=67890,
            xp=100,
            level=2,
            messages_count=50,
            links_shared=5,
            thanks_received=3
        )
    
    @pytest.mark.asyncio
    async def test_check_achievements_handles_repository_error(self, achievement_engine, mock_repository, sample_user_stats):
        """Test that check_achievements handles repository errors gracefully."""
        mock_repository.get_all_achievements.side_effect = Exception("Database error")
        
        result = await achievement_engine.check_achievements(12345, 67890, sample_user_stats)
        
        # Should return empty list on error
        assert result == []
    
    @pytest.mark.asyncio
    async def test_unlock_achievement_handles_error(self, achievement_engine, mock_repository):
        """Test that unlock_achievement handles errors properly."""
        mock_repository.has_achievement.side_effect = Exception("Database error")
        
        achievement = Achievement(
            id="test",
            title="Test",
            description="Test",
            emoji="🧪",
            sticker="🧪",
            condition_type="messages_count",
            condition_value=1,
            category="test"
        )
        
        with pytest.raises(Exception):
            await achievement_engine.unlock_achievement(12345, 67890, achievement)
    
    @pytest.mark.asyncio
    async def test_unlock_achievements_handles_partial_failure(self, achievement_engine, mock_repository):
        """Test that unlock_achievements handles partial failures."""
        # First call succeeds, second fails
        mock_repository.has_achievement.side_effect = [False, Exception("Database error")]
        
        achievements = [
            Achievement(
                id="test1",
                title="Test 1",
                description="Test 1",
                emoji="🧪",
                sticker="🧪",
                condition_type="messages_count",
                condition_value=1,
                category="test"
            ),
            Achievement(
                id="test2",
                title="Test 2",
                description="Test 2",
                emoji="🧪",
                sticker="🧪",
                condition_type="messages_count",
                condition_value=1,
                category="test"
            )
        ]
        
        result = await achievement_engine.unlock_achievements(12345, 67890, achievements)
        
        # Should return empty list on error
        assert result == []
    
    @pytest.mark.asyncio
    async def test_is_achievement_unlocked_handles_error(self, achievement_engine, mock_repository):
        """Test that is_achievement_unlocked handles errors gracefully."""
        mock_repository.has_achievement.side_effect = Exception("Database error")
        
        result = await achievement_engine.is_achievement_unlocked(12345, 67890, "test")
        
        # Should return False on error
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_user_achievements_handles_error(self, achievement_engine, mock_repository):
        """Test that get_user_achievements handles errors gracefully."""
        mock_repository.get_user_achievements_with_details.side_effect = Exception("Database error")
        
        result = await achievement_engine.get_user_achievements(12345, 67890)
        
        # Should return empty list on error
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_achievements_by_category_handles_error(self, achievement_engine, mock_repository):
        """Test that get_achievements_by_category handles errors gracefully."""
        mock_repository.get_achievements_by_category.side_effect = Exception("Database error")
        
        result = await achievement_engine.get_achievements_by_category("test")
        
        # Should return empty list on error
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_achievement_progress_handles_error(self, achievement_engine, mock_repository, sample_user_stats):
        """Test that get_achievement_progress handles errors gracefully."""
        mock_repository.get_all_achievements.side_effect = Exception("Database error")
        
        result = await achievement_engine.get_achievement_progress(12345, 67890, sample_user_stats, "test")
        
        # Should return None on error
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])