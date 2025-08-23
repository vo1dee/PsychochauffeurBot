"""
Integration tests for the leveling system repositories.

These tests verify the database repository layer functionality including
CRUD operations, transactions, and error handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

from modules.repositories import UserStatsRepository, AchievementRepository, LevelingRepository
from modules.leveling_models import UserStats, Achievement, UserAchievement, UserProfile
from modules.database import Database


@pytest.fixture
def user_stats_repo():
    """Fixture for UserStatsRepository."""
    return UserStatsRepository()


@pytest.fixture
def achievement_repo():
    """Fixture for AchievementRepository."""
    return AchievementRepository()


@pytest.fixture
def leveling_repo():
    """Fixture for LevelingRepository."""
    return LevelingRepository()


@pytest.fixture
def sample_user_stats():
    """Fixture for sample user statistics."""
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
def sample_achievement():
    """Fixture for sample achievement."""
    return Achievement(
        id="test_achievement",
        title="Test Achievement",
        description="A test achievement",
        emoji="🏆",
        sticker="",
        condition_type="messages_count",
        condition_value=10,
        category="test"
    )


@pytest.fixture
def sample_user_achievement():
    """Fixture for sample user achievement."""
    return UserAchievement(
        user_id=12345,
        chat_id=67890,
        achievement_id="test_achievement"
    )


class TestUserStatsRepository:
    """Test cases for UserStatsRepository."""
    
    @pytest.mark.asyncio
    async def test_create_user_stats(self, user_stats_repo: UserStatsRepository):
        """Test creating new user statistics."""
        user_id = 11111
        chat_id = 22222
        
        try:
            # Create prerequisite user and chat records
            await self._create_test_user_and_chat(user_id, chat_id)
            
            # Create user stats
            user_stats = await user_stats_repo.create_user_stats(user_id, chat_id)
            
            # Verify creation
            assert user_stats.user_id == user_id
            assert user_stats.chat_id == chat_id
            assert user_stats.xp == 0
            assert user_stats.level == 1
            assert user_stats.messages_count == 0
            assert user_stats.links_shared == 0
            assert user_stats.thanks_received == 0
            assert user_stats.created_at is not None
            assert user_stats.updated_at is not None
            assert user_stats.last_activity is not None
            
        finally:
            # Clean up
            await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
            await self._cleanup_test_user_and_chat(user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_get_user_stats_existing(self, user_stats_repo: UserStatsRepository, sample_user_stats: UserStats):
        """Test getting existing user statistics."""
        # Create prerequisite user and chat records
        await self._create_test_user_and_chat(sample_user_stats.user_id, sample_user_stats.chat_id)
        
        # Create user stats first
        await user_stats_repo.create_user_stats(sample_user_stats.user_id, sample_user_stats.chat_id)
        await user_stats_repo.update_user_stats(sample_user_stats)
        
        # Get user stats
        retrieved_stats = await user_stats_repo.get_user_stats(sample_user_stats.user_id, sample_user_stats.chat_id)
        
        # Verify retrieval
        assert retrieved_stats is not None
        assert retrieved_stats.user_id == sample_user_stats.user_id
        assert retrieved_stats.chat_id == sample_user_stats.chat_id
        assert retrieved_stats.xp == sample_user_stats.xp
        assert retrieved_stats.level == sample_user_stats.level
        assert retrieved_stats.messages_count == sample_user_stats.messages_count
        assert retrieved_stats.links_shared == sample_user_stats.links_shared
        assert retrieved_stats.thanks_received == sample_user_stats.thanks_received
        
        # Clean up
        await self._cleanup_user_stats(user_stats_repo, sample_user_stats.user_id, sample_user_stats.chat_id)
        await self._cleanup_test_user_and_chat(sample_user_stats.user_id, sample_user_stats.chat_id)
    
    @pytest.mark.asyncio
    async def test_get_user_stats_nonexistent(self, user_stats_repo: UserStatsRepository):
        """Test getting non-existent user statistics."""
        user_id = 99999
        chat_id = 88888
        
        # Try to get non-existent user stats
        user_stats = await user_stats_repo.get_user_stats(user_id, chat_id)
        
        # Verify it returns None
        assert user_stats is None
    
    @pytest.mark.asyncio
    async def test_update_user_stats(self, user_stats_repo: UserStatsRepository, sample_user_stats: UserStats):
        """Test updating user statistics."""
        # Create user stats first
        await user_stats_repo.create_user_stats(sample_user_stats.user_id, sample_user_stats.chat_id)
        
        # Update stats
        sample_user_stats.xp = 200
        sample_user_stats.level = 3
        sample_user_stats.messages_count = 75
        await user_stats_repo.update_user_stats(sample_user_stats)
        
        # Verify update
        updated_stats = await user_stats_repo.get_user_stats(sample_user_stats.user_id, sample_user_stats.chat_id)
        assert updated_stats.xp == 200
        assert updated_stats.level == 3
        assert updated_stats.messages_count == 75
        
        # Clean up
        await self._cleanup_user_stats(user_stats_repo, sample_user_stats.user_id, sample_user_stats.chat_id)
    
    @pytest.mark.asyncio
    async def test_get_or_create_user_stats_new(self, user_stats_repo: UserStatsRepository):
        """Test get_or_create with new user."""
        user_id = 33333
        chat_id = 44444
        
        # Get or create (should create)
        user_stats = await user_stats_repo.get_or_create_user_stats(user_id, chat_id)
        
        # Verify creation
        assert user_stats.user_id == user_id
        assert user_stats.chat_id == chat_id
        assert user_stats.xp == 0
        assert user_stats.level == 1
        
        # Clean up
        await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_get_or_create_user_stats_existing(self, user_stats_repo: UserStatsRepository, sample_user_stats: UserStats):
        """Test get_or_create with existing user."""
        # Create user stats first
        await user_stats_repo.create_user_stats(sample_user_stats.user_id, sample_user_stats.chat_id)
        await user_stats_repo.update_user_stats(sample_user_stats)
        
        # Get or create (should get existing)
        user_stats = await user_stats_repo.get_or_create_user_stats(sample_user_stats.user_id, sample_user_stats.chat_id)
        
        # Verify it got existing data
        assert user_stats.xp == sample_user_stats.xp
        assert user_stats.level == sample_user_stats.level
        assert user_stats.messages_count == sample_user_stats.messages_count
        
        # Clean up
        await self._cleanup_user_stats(user_stats_repo, sample_user_stats.user_id, sample_user_stats.chat_id)
    
    @pytest.mark.asyncio
    async def test_get_leaderboard(self, user_stats_repo: UserStatsRepository):
        """Test getting leaderboard."""
        chat_id = 55555
        
        # Create multiple users with different XP
        users_data = [
            (10001, 300, 3),
            (10002, 150, 2),
            (10003, 500, 5),
            (10004, 75, 1)
        ]
        
        created_users = []
        for user_id, xp, level in users_data:
            user_stats = await user_stats_repo.create_user_stats(user_id, chat_id)
            user_stats.xp = xp
            user_stats.level = level
            await user_stats_repo.update_user_stats(user_stats)
            created_users.append((user_id, chat_id))
        
        # Get leaderboard
        leaderboard = await user_stats_repo.get_leaderboard(chat_id, limit=3)
        
        # Verify order (should be sorted by XP descending)
        assert len(leaderboard) == 3
        assert leaderboard[0].user_id == 10003  # 500 XP
        assert leaderboard[1].user_id == 10001  # 300 XP
        assert leaderboard[2].user_id == 10002  # 150 XP
        
        # Clean up
        for user_id, chat_id in created_users:
            await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_get_user_rank(self, user_stats_repo: UserStatsRepository):
        """Test getting user rank."""
        chat_id = 66666
        
        # Create multiple users with different XP
        users_data = [
            (20001, 300),
            (20002, 150),
            (20003, 500),
            (20004, 75)
        ]
        
        created_users = []
        for user_id, xp in users_data:
            user_stats = await user_stats_repo.create_user_stats(user_id, chat_id)
            user_stats.xp = xp
            await user_stats_repo.update_user_stats(user_stats)
            created_users.append((user_id, chat_id))
        
        # Get ranks
        rank_20003 = await user_stats_repo.get_user_rank(20003, chat_id)  # 500 XP - should be rank 1
        rank_20001 = await user_stats_repo.get_user_rank(20001, chat_id)  # 300 XP - should be rank 2
        rank_20004 = await user_stats_repo.get_user_rank(20004, chat_id)  # 75 XP - should be rank 4
        
        # Verify ranks
        assert rank_20003 == 1
        assert rank_20001 == 2
        assert rank_20004 == 4
        
        # Clean up
        for user_id, chat_id in created_users:
            await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_get_active_users(self, user_stats_repo: UserStatsRepository):
        """Test getting active users."""
        chat_id = 77777
        now = datetime.now(pytz.utc)
        
        # Create users with different activity times
        users_data = [
            (30001, now - timedelta(days=1)),  # Active 1 day ago
            (30002, now - timedelta(days=5)),  # Active 5 days ago
            (30003, now - timedelta(days=10)), # Active 10 days ago
            (30004, now - timedelta(hours=2))  # Active 2 hours ago
        ]
        
        created_users = []
        for user_id, last_activity in users_data:
            user_stats = await user_stats_repo.create_user_stats(user_id, chat_id)
            user_stats.last_activity = last_activity
            await user_stats_repo.update_user_stats(user_stats)
            created_users.append((user_id, chat_id))
        
        # Get active users (within 7 days)
        active_users = await user_stats_repo.get_active_users(chat_id, days=7)
        
        # Verify only users active within 7 days are returned
        active_user_ids = [user.user_id for user in active_users]
        assert 30001 in active_user_ids  # 1 day ago
        assert 30002 in active_user_ids  # 5 days ago
        assert 30004 in active_user_ids  # 2 hours ago
        assert 30003 not in active_user_ids  # 10 days ago
        
        # Clean up
        for user_id, chat_id in created_users:
            await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_bulk_update_user_stats(self, user_stats_repo: UserStatsRepository):
        """Test bulk updating user statistics."""
        chat_id = 88888
        
        # Create multiple users
        user_ids = [40001, 40002, 40003]
        user_stats_list = []
        
        for user_id in user_ids:
            user_stats = await user_stats_repo.create_user_stats(user_id, chat_id)
            user_stats.xp = user_id  # Use user_id as XP for easy verification
            user_stats.messages_count = 10
            user_stats_list.append(user_stats)
        
        # Bulk update
        await user_stats_repo.bulk_update_user_stats(user_stats_list)
        
        # Verify updates
        for user_id in user_ids:
            updated_stats = await user_stats_repo.get_user_stats(user_id, chat_id)
            assert updated_stats.xp == user_id
            assert updated_stats.messages_count == 10
        
        # Clean up
        for user_id in user_ids:
            await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
    
    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, user_stats_repo: UserStatsRepository):
        """Test transaction context manager."""
        user_id = 50001
        chat_id = 99999
        
        # Test successful transaction
        async with user_stats_repo.transaction() as conn:
            await conn.execute("""
                INSERT INTO user_chat_stats (user_id, chat_id, xp, level)
                VALUES ($1, $2, $3, $4)
            """, user_id, chat_id, 100, 2)
        
        # Verify data was committed
        user_stats = await user_stats_repo.get_user_stats(user_id, chat_id)
        assert user_stats is not None
        assert user_stats.xp == 100
        assert user_stats.level == 2
        
        # Clean up
        await self._cleanup_user_stats(user_stats_repo, user_id, chat_id)
    
    async def _create_test_user_and_chat(self, user_id: int, chat_id: int):
        """Helper method to create test user and chat records."""
        from modules.database import Database
        manager = Database.get_connection_manager()
        async with manager.get_connection() as conn:
            # Create test user
            await conn.execute("""
                INSERT INTO users (user_id, first_name, last_name, username, is_bot)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id, "Test", "User", f"testuser{user_id}", False)
            
            # Create test chat
            await conn.execute("""
                INSERT INTO chats (chat_id, chat_type, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO NOTHING
            """, chat_id, "group", f"Test Chat {chat_id}")
    
    async def _cleanup_test_user_and_chat(self, user_id: int, chat_id: int):
        """Helper method to clean up test user and chat records."""
        from modules.database import Database
        manager = Database.get_connection_manager()
        async with manager.get_connection() as conn:
            await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM chats WHERE chat_id = $1", chat_id)
    
    async def _cleanup_user_stats(self, repo: UserStatsRepository, user_id: int, chat_id: int):
        """Helper method to clean up test data."""
        async with repo._connection_manager.get_connection() as conn:
            await conn.execute("DELETE FROM user_chat_stats WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)


class TestAchievementRepository:
    """Test cases for AchievementRepository."""
    
    @pytest.mark.asyncio
    async def test_save_and_get_achievement(self, achievement_repo: AchievementRepository, sample_achievement: Achievement):
        """Test saving and getting achievement."""
        # Save achievement
        await achievement_repo.save_achievement(sample_achievement)
        
        # Get achievement
        retrieved_achievement = await achievement_repo.get_achievement(sample_achievement.id)
        
        # Verify retrieval
        assert retrieved_achievement is not None
        assert retrieved_achievement.id == sample_achievement.id
        assert retrieved_achievement.title == sample_achievement.title
        assert retrieved_achievement.description == sample_achievement.description
        assert retrieved_achievement.emoji == sample_achievement.emoji
        assert retrieved_achievement.condition_type == sample_achievement.condition_type
        assert retrieved_achievement.condition_value == sample_achievement.condition_value
        assert retrieved_achievement.category == sample_achievement.category
        
        # Clean up
        await self._cleanup_achievement(achievement_repo, sample_achievement.id)
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_achievement(self, achievement_repo: AchievementRepository):
        """Test getting non-existent achievement."""
        achievement = await achievement_repo.get_achievement("nonexistent_achievement")
        assert achievement is None
    
    @pytest.mark.asyncio
    async def test_get_all_achievements(self, achievement_repo: AchievementRepository):
        """Test getting all achievements."""
        # Create test achievements
        achievements = [
            Achievement("test_1", "Test 1", "Description 1", "🏆", "", "messages_count", 10, "test"),
            Achievement("test_2", "Test 2", "Description 2", "🎯", "", "xp", 100, "test"),
            Achievement("test_3", "Test 3", "Description 3", "⭐", "", "level", 5, "progression")
        ]
        
        for achievement in achievements:
            await achievement_repo.save_achievement(achievement)
        
        # Get all achievements
        all_achievements = await achievement_repo.get_all_achievements()
        
        # Verify we have at least our test achievements
        test_achievement_ids = [a.id for a in all_achievements if a.id.startswith("test_")]
        assert "test_1" in test_achievement_ids
        assert "test_2" in test_achievement_ids
        assert "test_3" in test_achievement_ids
        
        # Clean up
        for achievement in achievements:
            await self._cleanup_achievement(achievement_repo, achievement.id)
    
    @pytest.mark.asyncio
    async def test_get_achievements_by_category(self, achievement_repo: AchievementRepository):
        """Test getting achievements by category."""
        # Create test achievements in different categories
        achievements = [
            Achievement("cat_test_1", "Cat Test 1", "Description 1", "🏆", "", "messages_count", 10, "activity"),
            Achievement("cat_test_2", "Cat Test 2", "Description 2", "🎯", "", "xp", 100, "activity"),
            Achievement("cat_test_3", "Cat Test 3", "Description 3", "⭐", "", "level", 5, "progression")
        ]
        
        for achievement in achievements:
            await achievement_repo.save_achievement(achievement)
        
        # Get achievements by category
        activity_achievements = await achievement_repo.get_achievements_by_category("activity")
        progression_achievements = await achievement_repo.get_achievements_by_category("progression")
        
        # Verify filtering
        activity_ids = [a.id for a in activity_achievements if a.id.startswith("cat_test_")]
        progression_ids = [a.id for a in progression_achievements if a.id.startswith("cat_test_")]
        
        assert "cat_test_1" in activity_ids
        assert "cat_test_2" in activity_ids
        assert "cat_test_3" in progression_ids
        assert "cat_test_3" not in activity_ids
        
        # Clean up
        for achievement in achievements:
            await self._cleanup_achievement(achievement_repo, achievement.id)
    
    @pytest.mark.asyncio
    async def test_unlock_achievement(self, achievement_repo: AchievementRepository, sample_achievement: Achievement, sample_user_achievement: UserAchievement):
        """Test unlocking achievement for user."""
        # Save achievement first
        await achievement_repo.save_achievement(sample_achievement)
        
        # Unlock achievement
        await achievement_repo.unlock_achievement(sample_user_achievement)
        
        # Verify unlock
        has_achievement = await achievement_repo.has_achievement(
            sample_user_achievement.user_id,
            sample_user_achievement.chat_id,
            sample_user_achievement.achievement_id
        )
        assert has_achievement is True
        
        # Clean up
        await self._cleanup_user_achievement(achievement_repo, sample_user_achievement)
        await self._cleanup_achievement(achievement_repo, sample_achievement.id)
    
    @pytest.mark.asyncio
    async def test_has_achievement_false(self, achievement_repo: AchievementRepository):
        """Test has_achievement returns False for non-existent achievement."""
        has_achievement = await achievement_repo.has_achievement(99999, 88888, "nonexistent")
        assert has_achievement is False
    
    @pytest.mark.asyncio
    async def test_get_user_achievements(self, achievement_repo: AchievementRepository, sample_achievement: Achievement):
        """Test getting user achievements."""
        user_id = 60001
        chat_id = 70001
        
        # Save achievement
        await achievement_repo.save_achievement(sample_achievement)
        
        # Create user achievements
        user_achievements = [
            UserAchievement(user_id, chat_id, sample_achievement.id),
        ]
        
        for user_achievement in user_achievements:
            await achievement_repo.unlock_achievement(user_achievement)
        
        # Get user achievements
        retrieved_achievements = await achievement_repo.get_user_achievements(user_id, chat_id)
        
        # Verify retrieval
        assert len(retrieved_achievements) == 1
        assert retrieved_achievements[0].achievement_id == sample_achievement.id
        
        # Clean up
        for user_achievement in user_achievements:
            await self._cleanup_user_achievement(achievement_repo, user_achievement)
        await self._cleanup_achievement(achievement_repo, sample_achievement.id)
    
    @pytest.mark.asyncio
    async def test_get_user_achievements_with_details(self, achievement_repo: AchievementRepository, sample_achievement: Achievement):
        """Test getting user achievements with full details."""
        user_id = 60002
        chat_id = 70002
        
        # Save achievement
        await achievement_repo.save_achievement(sample_achievement)
        
        # Unlock achievement
        user_achievement = UserAchievement(user_id, chat_id, sample_achievement.id)
        await achievement_repo.unlock_achievement(user_achievement)
        
        # Get achievements with details
        achievements_with_details = await achievement_repo.get_user_achievements_with_details(user_id, chat_id)
        
        # Verify retrieval
        assert len(achievements_with_details) == 1
        user_ach, achievement = achievements_with_details[0]
        assert user_ach.achievement_id == sample_achievement.id
        assert achievement.title == sample_achievement.title
        assert achievement.emoji == sample_achievement.emoji
        
        # Clean up
        await self._cleanup_user_achievement(achievement_repo, user_achievement)
        await self._cleanup_achievement(achievement_repo, sample_achievement.id)
    
    @pytest.mark.asyncio
    async def test_bulk_unlock_achievements(self, achievement_repo: AchievementRepository):
        """Test bulk unlocking achievements."""
        user_id = 60003
        chat_id = 70003
        
        # Create test achievements
        achievements = [
            Achievement("bulk_1", "Bulk 1", "Description 1", "🏆", "", "messages_count", 10, "test"),
            Achievement("bulk_2", "Bulk 2", "Description 2", "🎯", "", "xp", 100, "test")
        ]
        
        for achievement in achievements:
            await achievement_repo.save_achievement(achievement)
        
        # Create user achievements for bulk unlock
        user_achievements = [
            UserAchievement(user_id, chat_id, "bulk_1"),
            UserAchievement(user_id, chat_id, "bulk_2")
        ]
        
        # Bulk unlock
        await achievement_repo.bulk_unlock_achievements(user_achievements)
        
        # Verify unlocks
        for user_achievement in user_achievements:
            has_achievement = await achievement_repo.has_achievement(
                user_achievement.user_id,
                user_achievement.chat_id,
                user_achievement.achievement_id
            )
            assert has_achievement is True
        
        # Clean up
        for user_achievement in user_achievements:
            await self._cleanup_user_achievement(achievement_repo, user_achievement)
        for achievement in achievements:
            await self._cleanup_achievement(achievement_repo, achievement.id)
    
    @pytest.mark.asyncio
    async def test_get_achievement_stats(self, achievement_repo: AchievementRepository):
        """Test getting achievement statistics."""
        chat_id = 70004
        user_id = 60004
        
        # Create test achievement
        achievement = Achievement("stats_test", "Stats Test", "Description", "🏆", "", "messages_count", 10, "test")
        await achievement_repo.save_achievement(achievement)
        
        # Unlock achievement for user
        user_achievement = UserAchievement(user_id, chat_id, achievement.id)
        await achievement_repo.unlock_achievement(user_achievement)
        
        # Get stats
        stats = await achievement_repo.get_achievement_stats(chat_id)
        
        # Verify stats structure
        assert 'total_achievements' in stats
        assert 'unlocked_achievements' in stats
        assert 'users_with_achievements' in stats
        assert 'most_popular_achievement' in stats
        assert 'most_popular_count' in stats
        
        # Verify our test data is reflected
        assert stats['unlocked_achievements'] >= 1
        assert stats['users_with_achievements'] >= 1
        
        # Clean up
        await self._cleanup_user_achievement(achievement_repo, user_achievement)
        await self._cleanup_achievement(achievement_repo, achievement.id)
    
    async def _cleanup_achievement(self, repo: AchievementRepository, achievement_id: str):
        """Helper method to clean up achievement test data."""
        async with repo._connection_manager.get_connection() as conn:
            await conn.execute("DELETE FROM achievements WHERE id = $1", achievement_id)
    
    async def _cleanup_user_achievement(self, repo: AchievementRepository, user_achievement: UserAchievement):
        """Helper method to clean up user achievement test data."""
        async with repo._connection_manager.get_connection() as conn:
            await conn.execute(
                "DELETE FROM user_achievements WHERE user_id = $1 AND chat_id = $2 AND achievement_id = $3",
                user_achievement.user_id, user_achievement.chat_id, user_achievement.achievement_id
            )


class TestLevelingRepository:
    """Test cases for LevelingRepository."""
    
    @pytest.mark.asyncio
    async def test_update_user_xp_atomic(self, leveling_repo: LevelingRepository):
        """Test atomic XP update with achievements."""
        user_id = 80001
        chat_id = 90001
        
        # Create test achievement
        achievement = Achievement("atomic_test", "Atomic Test", "Description", "🏆", "", "messages_count", 1, "test")
        await leveling_repo.achievements.save_achievement(achievement)
        
        # Prepare update data
        xp_gain = 50
        new_level = 2
        activity_updates = {'messages_count': 1, 'links_shared': 1}
        new_achievements = [UserAchievement(user_id, chat_id, achievement.id)]
        
        # Perform atomic update
        updated_stats = await leveling_repo.update_user_xp_atomic(
            user_id, chat_id, xp_gain, new_level, activity_updates, new_achievements
        )
        
        # Verify update
        assert updated_stats.xp == xp_gain
        assert updated_stats.level == new_level
        assert updated_stats.messages_count == 1
        assert updated_stats.links_shared == 1
        
        # Verify achievement was unlocked
        has_achievement = await leveling_repo.achievements.has_achievement(user_id, chat_id, achievement.id)
        assert has_achievement is True
        
        # Clean up
        await self._cleanup_leveling_data(leveling_repo, user_id, chat_id, achievement.id)
    
    @pytest.mark.asyncio
    async def test_get_user_profile(self, leveling_repo: LevelingRepository):
        """Test getting complete user profile."""
        user_id = 80002
        chat_id = 90002
        username = "test_user"
        
        # Create user stats
        user_stats = await leveling_repo.user_stats.create_user_stats(user_id, chat_id)
        user_stats.xp = 150
        user_stats.level = 2
        user_stats.messages_count = 25
        await leveling_repo.user_stats.update_user_stats(user_stats)
        
        # Create and unlock achievement
        achievement = Achievement("profile_test", "Profile Test", "Description", "🏆", "", "messages_count", 10, "test")
        await leveling_repo.achievements.save_achievement(achievement)
        user_achievement = UserAchievement(user_id, chat_id, achievement.id)
        await leveling_repo.achievements.unlock_achievement(user_achievement)
        
        # Get user profile
        profile = await leveling_repo.get_user_profile(user_id, chat_id, username)
        
        # Verify profile
        assert profile is not None
        assert profile.user_id == user_id
        assert profile.username == username
        assert profile.level == 2
        assert profile.xp == 150
        assert len(profile.achievements) == 1
        assert profile.achievements[0].id == achievement.id
        assert profile.stats['messages_count'] == 25
        assert profile.rank is not None
        
        # Clean up
        await self._cleanup_leveling_data(leveling_repo, user_id, chat_id, achievement.id)
    
    @pytest.mark.asyncio
    async def test_get_user_profile_nonexistent(self, leveling_repo: LevelingRepository):
        """Test getting profile for non-existent user."""
        profile = await leveling_repo.get_user_profile(99999, 88888, "nonexistent")
        assert profile is None
    
    async def _cleanup_leveling_data(self, repo: LevelingRepository, user_id: int, chat_id: int, achievement_id: str):
        """Helper method to clean up leveling test data."""
        async with repo._connection_manager.get_connection() as conn:
            await conn.execute("DELETE FROM user_achievements WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)
            await conn.execute("DELETE FROM user_chat_stats WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)
            await conn.execute("DELETE FROM achievements WHERE id = $1", achievement_id)


# Test configuration and fixtures for database setup
@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Set up test database before running tests."""
    # Initialize database
    await Database.initialize()
    yield
    # Cleanup is handled by individual test methods


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])