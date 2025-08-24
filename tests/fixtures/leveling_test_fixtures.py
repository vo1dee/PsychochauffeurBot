"""
Test data fixtures for the User Leveling System.

This module provides comprehensive test data fixtures for various user scenarios,
message types, achievements, and edge cases to support thorough testing of the
leveling system components.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock

from telegram import Message, User, Chat, Bot
from telegram.ext import ContextTypes

from modules.leveling_models import UserStats, Achievement, UserAchievement, LevelUpResult
from modules.repositories import UserStatsRepository, AchievementRepository


class LevelingTestFixtures:
    """Centralized test fixtures for the leveling system."""
    
    @staticmethod
    def create_test_user(user_id: int = 12345, username: str = "testuser", 
                        is_bot: bool = False, **kwargs) -> User:
        """Create a test Telegram user."""
        return User(
            id=user_id,
            is_bot=is_bot,
            first_name=kwargs.get('first_name', 'Test'),
            last_name=kwargs.get('last_name', 'User'),
            username=username,
            language_code=kwargs.get('language_code', 'en')
        )
    
    @staticmethod
    def create_test_chat(chat_id: int = -1001234567890, chat_type: str = 'supergroup',
                        title: str = "Test Group", **kwargs) -> Chat:
        """Create a test Telegram chat."""
        if chat_type == 'private':
            return Chat(
                id=chat_id,
                type=Chat.PRIVATE,
                username=kwargs.get('username', 'testuser'),
                first_name=kwargs.get('first_name', 'Test'),
                last_name=kwargs.get('last_name', 'User')
            )
        else:
            return Chat(
                id=chat_id,
                type=Chat.SUPERGROUP if chat_type == 'supergroup' else Chat.GROUP,
                title=title,
                description=kwargs.get('description', 'A test group chat')
            )
    
    @staticmethod
    def create_test_message(text: str, user: User = None, chat: Chat = None,
                           message_id: int = 1, reply_to_message: Message = None,
                           **kwargs) -> Message:
        """Create a test Telegram message."""
        if user is None:
            user = LevelingTestFixtures.create_test_user()
        if chat is None:
            chat = LevelingTestFixtures.create_test_chat()
        
        return Message(
            message_id=message_id,
            date=kwargs.get('date', datetime.now()),
            chat=chat,
            from_user=user,
            text=text,
            reply_to_message=reply_to_message,
            **{k: v for k, v in kwargs.items() if k not in ['date']}
        )


@pytest.fixture
def test_users():
    """Fixture providing various test users."""
    return {
        'alice': LevelingTestFixtures.create_test_user(12345, 'alice', first_name='Alice'),
        'bob': LevelingTestFixtures.create_test_user(12346, 'bob', first_name='Bob'),
        'charlie': LevelingTestFixtures.create_test_user(12347, 'charlie', first_name='Charlie'),
        'bot_user': LevelingTestFixtures.create_test_user(98765, 'testbot', is_bot=True),
        'no_username': LevelingTestFixtures.create_test_user(12348, None, first_name='NoUsername'),
    }


@pytest.fixture
def test_chats():
    """Fixture providing various test chats."""
    return {
        'group': LevelingTestFixtures.create_test_chat(-1001234567890, 'supergroup', 'Test Group'),
        'private': LevelingTestFixtures.create_test_chat(12345, 'private'),
        'small_group': LevelingTestFixtures.create_test_chat(-1001111111111, 'group', 'Small Group'),
        'large_group': LevelingTestFixtures.create_test_chat(-1002222222222, 'supergroup', 'Large Group'),
    }


@pytest.fixture
def sample_user_stats():
    """Fixture providing sample user statistics for various scenarios."""
    base_time = datetime.now()
    
    return {
        'new_user': UserStats(
            user_id=12345,
            chat_id=-1001234567890,
            username='newuser',
            xp=0,
            level=1,
            messages_count=0,
            links_shared=0,
            thanks_received=0,
            last_activity=base_time,
            created_at=base_time,
            updated_at=base_time
        ),
        'active_user': UserStats(
            user_id=12346,
            chat_id=-1001234567890,
            username='activeuser',
            xp=150,
            level=3,
            messages_count=75,
            links_shared=10,
            thanks_received=5,
            last_activity=base_time,
            created_at=base_time - timedelta(days=30),
            updated_at=base_time
        ),
        'veteran_user': UserStats(
            user_id=12347,
            chat_id=-1001234567890,
            username='veteran',
            xp=5000,
            level=10,
            messages_count=2500,
            links_shared=200,
            thanks_received=150,
            last_activity=base_time,
            created_at=base_time - timedelta(days=365),
            updated_at=base_time
        ),
        'level_up_candidate': UserStats(
            user_id=12348,
            chat_id=-1001234567890,
            username='levelup',
            xp=49,  # One XP away from level 2
            level=1,
            messages_count=49,
            links_shared=0,
            thanks_received=0,
            last_activity=base_time,
            created_at=base_time - timedelta(days=7),
            updated_at=base_time
        ),
        'multi_level_candidate': UserStats(
            user_id=12349,
            chat_id=-1001234567890,
            username='multilevel',
            xp=96,  # 4 XP away from level 3 (will jump from level 2)
            level=2,
            messages_count=50,
            links_shared=15,
            thanks_received=2,
            last_activity=base_time,
            created_at=base_time - timedelta(days=14),
            updated_at=base_time
        ),
        'inactive_user': UserStats(
            user_id=12350,
            chat_id=-1001234567890,
            username='inactive',
            xp=25,
            level=1,
            messages_count=25,
            links_shared=0,
            thanks_received=0,
            last_activity=base_time - timedelta(days=90),
            created_at=base_time - timedelta(days=180),
            updated_at=base_time - timedelta(days=90)
        )
    }


@pytest.fixture
def sample_achievements():
    """Fixture providing sample achievements for testing."""
    base_time = datetime.now()
    
    return {
        'novice': Achievement(
            id='novice',
            title='👶 Новачок',
            description='Send your first message',
            emoji='👶',
            sticker='👶',
            condition_type='messages_count',
            condition_value=1,
            category='activity',
            created_at=base_time
        ),
        'young_fluder': Achievement(
            id='young_fluder',
            title='🐣 Молодий флудер',
            description='Відправив 100+ повідомлень',
            emoji='🐣',
            sticker='🐣',
            condition_type='messages_count',
            condition_value=100,
            category='activity',
            created_at=base_time
        ),
        'helpful': Achievement(
            id='helpful',
            title='🤝 Helpful',
            description='Receive 5+ thanks',
            emoji='🤝',
            sticker='🤝',
            condition_type='thanks_received',
            condition_value=5,
            category='social',
            created_at=base_time
        ),
        'linker': Achievement(
            id='linker',
            title='🔗 Linker',
            description='Share 10+ links',
            emoji='🔗',
            sticker='🔗',
            condition_type='links_shared',
            condition_value=10,
            category='media',
            created_at=base_time
        ),
        'level_up': Achievement(
            id='level_up',
            title='🆙 Level Up!',
            description='Reach level 5',
            emoji='🆙',
            sticker='🆙',
            condition_type='level',
            condition_value=5,
            category='level',
            created_at=base_time
        ),
        'rare_achievement': Achievement(
            id='novelist',
            title='📚 Романіст',
            description='Send the longest message in chat history',
            emoji='📚',
            sticker='📚',
            condition_type='longest_message',
            condition_value=1,
            category='rare',
            created_at=base_time
        )
    }


@pytest.fixture
def sample_user_achievements(sample_user_stats, sample_achievements):
    """Fixture providing sample user achievements."""
    base_time = datetime.now()
    
    return [
        UserAchievement(
            user_id=12346,  # active_user
            chat_id=-1001234567890,
            achievement_id='novice',
            unlocked_at=base_time - timedelta(days=29)
        ),
        UserAchievement(
            user_id=12346,  # active_user
            chat_id=-1001234567890,
            achievement_id='helpful',
            unlocked_at=base_time - timedelta(days=10)
        ),
        UserAchievement(
            user_id=12347,  # veteran_user
            chat_id=-1001234567890,
            achievement_id='novice',
            unlocked_at=base_time - timedelta(days=364)
        ),
        UserAchievement(
            user_id=12347,  # veteran_user
            chat_id=-1001234567890,
            achievement_id='young_fluder',
            unlocked_at=base_time - timedelta(days=300)
        ),
        UserAchievement(
            user_id=12347,  # veteran_user
            chat_id=-1001234567890,
            achievement_id='helpful',
            unlocked_at=base_time - timedelta(days=250)
        ),
        UserAchievement(
            user_id=12347,  # veteran_user
            chat_id=-1001234567890,
            achievement_id='linker',
            unlocked_at=base_time - timedelta(days=200)
        ),
        UserAchievement(
            user_id=12347,  # veteran_user
            chat_id=-1001234567890,
            achievement_id='level_up',
            unlocked_at=base_time - timedelta(days=100)
        )
    ]


@pytest.fixture
def message_scenarios(test_users, test_chats):
    """Fixture providing various message scenarios for testing."""
    alice = test_users['alice']
    bob = test_users['bob']
    group = test_chats['group']
    
    # Create reply message for thank you scenarios
    original_message = LevelingTestFixtures.create_test_message(
        "Here's some helpful information",
        user=alice,
        chat=group,
        message_id=1
    )
    
    return {
        'simple_message': LevelingTestFixtures.create_test_message(
            "Hello everyone!",
            user=alice,
            chat=group
        ),
        'message_with_link': LevelingTestFixtures.create_test_message(
            "Check out this cool website: https://example.com",
            user=alice,
            chat=group
        ),
        'message_with_multiple_links': LevelingTestFixtures.create_test_message(
            "Visit https://example.com and http://test.org for more info",
            user=alice,
            chat=group
        ),
        'thank_you_reply': LevelingTestFixtures.create_test_message(
            "Thank you so much!",
            user=bob,
            chat=group,
            reply_to_message=original_message
        ),
        'thank_you_mention': LevelingTestFixtures.create_test_message(
            "Thanks @alice for the help!",
            user=bob,
            chat=group
        ),
        'complex_message': LevelingTestFixtures.create_test_message(
            "Thanks @alice! Check https://example.com and http://test.org",
            user=bob,
            chat=group,
            reply_to_message=original_message
        ),
        'long_message': LevelingTestFixtures.create_test_message(
            "This is a very long message. " * 100,
            user=alice,
            chat=group
        ),
        'empty_message': LevelingTestFixtures.create_test_message(
            "",
            user=alice,
            chat=group
        ),
        'bot_message': LevelingTestFixtures.create_test_message(
            "I am a bot message",
            user=test_users['bot_user'],
            chat=group
        ),
        'private_message': LevelingTestFixtures.create_test_message(
            "Private message",
            user=alice,
            chat=test_chats['private']
        ),
        'ukrainian_thanks': LevelingTestFixtures.create_test_message(
            "Дякую @alice за допомогу!",
            user=bob,
            chat=group
        ),
        'hebrew_thanks': LevelingTestFixtures.create_test_message(
            "תודה @alice",
            user=bob,
            chat=group
        ),
        'multiple_mentions': LevelingTestFixtures.create_test_message(
            "Thanks @alice and @charlie for your help!",
            user=bob,
            chat=group
        )
    }


@pytest.fixture
def xp_calculation_test_cases():
    """Fixture providing test cases for XP calculation scenarios."""
    return [
        {
            'name': 'simple_message',
            'text': 'Hello world!',
            'expected_sender_xp': 1,
            'expected_thanked_xp': {},
            'has_links': False,
            'is_thanks': False
        },
        {
            'name': 'message_with_link',
            'text': 'Check https://example.com',
            'expected_sender_xp': 4,  # 1 + 3
            'expected_thanked_xp': {},
            'has_links': True,
            'is_thanks': False
        },
        {
            'name': 'message_with_multiple_links',
            'text': 'Visit https://example.com and http://test.org',
            'expected_sender_xp': 4,  # 1 + 3 (still only 3 for links)
            'expected_thanked_xp': {},
            'has_links': True,
            'is_thanks': False
        },
        {
            'name': 'thank_you_message',
            'text': 'Thank you!',
            'expected_sender_xp': 1,
            'expected_thanked_xp': {54321: 5},  # Assuming reply to user 54321
            'has_links': False,
            'is_thanks': True,
            'reply_to_user_id': 54321
        },
        {
            'name': 'complex_message',
            'text': 'Thanks! Check https://example.com',
            'expected_sender_xp': 4,  # 1 + 3
            'expected_thanked_xp': {54321: 5},
            'has_links': True,
            'is_thanks': True,
            'reply_to_user_id': 54321
        },
        {
            'name': 'no_protocol_link',
            'text': 'Visit example.com',
            'expected_sender_xp': 1,
            'expected_thanked_xp': {},
            'has_links': False,
            'is_thanks': False
        },
        {
            'name': 'empty_message',
            'text': '',
            'expected_sender_xp': 1,
            'expected_thanked_xp': {},
            'has_links': False,
            'is_thanks': False
        }
    ]


@pytest.fixture
def level_progression_test_cases():
    """Fixture providing test cases for level progression scenarios."""
    return [
        {
            'name': 'level_1_start',
            'xp': 0,
            'expected_level': 1,
            'next_level_xp_needed': 50,
            'progress_percentage': 0.0
        },
        {
            'name': 'level_1_middle',
            'xp': 25,
            'expected_level': 1,
            'next_level_xp_needed': 25,
            'progress_percentage': 50.0
        },
        {
            'name': 'level_2_exact',
            'xp': 50,
            'expected_level': 2,
            'next_level_xp_needed': 50,
            'progress_percentage': 0.0
        },
        {
            'name': 'level_2_middle',
            'xp': 75,
            'expected_level': 2,
            'next_level_xp_needed': 25,
            'progress_percentage': 50.0
        },
        {
            'name': 'level_3_exact',
            'xp': 100,
            'expected_level': 3,
            'next_level_xp_needed': 100,
            'progress_percentage': 0.0
        },
        {
            'name': 'level_4_exact',
            'xp': 200,
            'expected_level': 4,
            'next_level_xp_needed': 200,
            'progress_percentage': 0.0
        },
        {
            'name': 'level_5_exact',
            'xp': 400,
            'expected_level': 5,
            'next_level_xp_needed': 400,
            'progress_percentage': 0.0
        },
        {
            'name': 'high_level',
            'xp': 12800,
            'expected_level': 10,
            'next_level_xp_needed': 12800,
            'progress_percentage': 0.0
        }
    ]


@pytest.fixture
def achievement_test_scenarios(sample_achievements):
    """Fixture providing achievement testing scenarios."""
    return [
        {
            'name': 'first_message_achievement',
            'user_stats': {
                'messages_count': 1,
                'links_shared': 0,
                'thanks_received': 0,
                'level': 1,
                'xp': 1
            },
            'expected_achievements': ['novice'],
            'context_data': {}
        },
        {
            'name': 'multiple_achievements',
            'user_stats': {
                'messages_count': 100,
                'links_shared': 10,
                'thanks_received': 5,
                'level': 3,
                'xp': 150
            },
            'expected_achievements': ['novice', 'young_fluder', 'helpful', 'linker'],
            'context_data': {}
        },
        {
            'name': 'level_achievement',
            'user_stats': {
                'messages_count': 200,
                'links_shared': 20,
                'thanks_received': 10,
                'level': 5,
                'xp': 400
            },
            'expected_achievements': ['novice', 'young_fluder', 'helpful', 'linker', 'level_up'],
            'context_data': {}
        },
        {
            'name': 'no_achievements',
            'user_stats': {
                'messages_count': 0,
                'links_shared': 0,
                'thanks_received': 0,
                'level': 1,
                'xp': 0
            },
            'expected_achievements': [],
            'context_data': {}
        },
        {
            'name': 'rare_achievement',
            'user_stats': {
                'messages_count': 50,
                'links_shared': 5,
                'thanks_received': 2,
                'level': 2,
                'xp': 75
            },
            'expected_achievements': ['novice', 'novelist'],
            'context_data': {'is_longest_message': True}
        }
    ]


@pytest.fixture
def performance_test_data():
    """Fixture providing data for performance testing."""
    return {
        'message_templates': [
            "Simple message {i}",
            "Message with link https://example.com/{i}",
            "Thanks @user{i} for the help!",
            "Complex message with https://example.com/{i} and thanks @user{i}!",
            "Long message " + "word " * 100 + " {i}",
        ],
        'user_count': 100,
        'messages_per_user': 10,
        'concurrent_batches': 5,
        'performance_thresholds': {
            'max_processing_time': 0.1,  # seconds
            'max_memory_growth': 50,     # MB
            'max_database_calls_per_message': 2
        }
    }


@pytest.fixture
def error_scenarios():
    """Fixture providing error scenarios for testing."""
    return {
        'database_connection_error': {
            'error_type': 'ConnectionError',
            'error_message': 'Database connection failed',
            'should_retry': True,
            'max_retries': 3
        },
        'database_timeout_error': {
            'error_type': 'TimeoutError',
            'error_message': 'Database operation timed out',
            'should_retry': True,
            'max_retries': 2
        },
        'achievement_engine_error': {
            'error_type': 'RuntimeError',
            'error_message': 'Achievement engine failed',
            'should_retry': False,
            'fallback_behavior': 'skip_achievements'
        },
        'notification_error': {
            'error_type': 'NetworkError',
            'error_message': 'Failed to send notification',
            'should_retry': False,
            'fallback_behavior': 'log_error'
        },
        'invalid_user_data': {
            'error_type': 'ValueError',
            'error_message': 'Invalid user data format',
            'should_retry': False,
            'fallback_behavior': 'skip_processing'
        }
    }


@pytest.fixture
def integration_test_scenarios(test_users, test_chats, sample_user_stats):
    """Fixture providing integration test scenarios."""
    return {
        'new_user_journey': {
            'description': 'Complete journey of a new user from first message to achievements',
            'steps': [
                {'action': 'send_message', 'text': 'Hello everyone!', 'expected_xp': 1, 'expected_level': 1},
                {'action': 'send_message', 'text': 'Check https://example.com', 'expected_xp': 5, 'expected_level': 1},
                {'action': 'send_multiple', 'count': 45, 'text': 'Regular message', 'expected_xp': 50, 'expected_level': 2},
                {'action': 'send_multiple', 'count': 50, 'text': 'More messages', 'expected_xp': 100, 'expected_level': 3}
            ]
        },
        'group_interaction': {
            'description': 'Multiple users interacting in a group',
            'participants': ['alice', 'bob', 'charlie'],
            'interactions': [
                {'user': 'alice', 'action': 'send_message', 'text': 'Helpful info: https://example.com'},
                {'user': 'bob', 'action': 'reply_thanks', 'text': 'Thanks Alice!', 'reply_to': 'alice'},
                {'user': 'charlie', 'action': 'mention_thanks', 'text': 'Thank you @alice!'}
            ]
        },
        'concurrent_processing': {
            'description': 'Multiple users sending messages simultaneously',
            'user_count': 10,
            'messages_per_user': 5,
            'message_types': ['simple', 'with_link', 'thanks'],
            'expected_no_errors': True
        },
        'achievement_unlocking': {
            'description': 'User unlocking multiple achievements',
            'user': 'alice',
            'starting_stats': sample_user_stats['level_up_candidate'],
            'actions': [
                {'send_message': 'Message to reach 100 total', 'expected_achievement': 'young_fluder'},
                {'send_link': 'https://example.com', 'expected_achievement': 'linker'},
                {'receive_thanks': 5, 'expected_achievement': 'helpful'}
            ]
        }
    }


class MockRepositoryFactory:
    """Factory for creating mock repositories with realistic behavior."""
    
    @staticmethod
    def create_user_stats_repository(initial_data: Dict[tuple, UserStats] = None):
        """Create a mock UserStatsRepository with realistic behavior."""
        if initial_data is None:
            initial_data = {}
        
        repo = Mock(spec=UserStatsRepository)
        
        async def mock_get_user_stats(user_id: int, chat_id: int) -> Optional[UserStats]:
            return initial_data.get((user_id, chat_id))
        
        async def mock_create_user_stats(user_id: int, chat_id: int) -> UserStats:
            stats = UserStats(
                user_id=user_id,
                chat_id=chat_id,
                xp=0,
                level=1,
                messages_count=0,
                links_shared=0,
                thanks_received=0
            )
            initial_data[(user_id, chat_id)] = stats
            return stats
        
        async def mock_update_user_stats(stats: UserStats) -> None:
            initial_data[(stats.user_id, stats.chat_id)] = stats
        
        async def mock_get_leaderboard(chat_id: int, limit: int = 10) -> List[UserStats]:
            chat_stats = [stats for (uid, cid), stats in initial_data.items() if cid == chat_id]
            return sorted(chat_stats, key=lambda s: s.xp, reverse=True)[:limit]
        
        repo.get_user_stats.side_effect = mock_get_user_stats
        repo.create_user_stats.side_effect = mock_create_user_stats
        repo.update_user_stats.side_effect = mock_update_user_stats
        repo.get_leaderboard.side_effect = mock_get_leaderboard
        
        return repo
    
    @staticmethod
    def create_achievement_repository(initial_achievements: List[Achievement] = None,
                                    initial_user_achievements: List[UserAchievement] = None):
        """Create a mock AchievementRepository with realistic behavior."""
        if initial_achievements is None:
            initial_achievements = []
        if initial_user_achievements is None:
            initial_user_achievements = []
        
        repo = Mock(spec=AchievementRepository)
        
        async def mock_get_all_achievements() -> List[Achievement]:
            return initial_achievements.copy()
        
        async def mock_get_user_achievements(user_id: int, chat_id: int) -> List[UserAchievement]:
            return [ua for ua in initial_user_achievements 
                   if ua.user_id == user_id and ua.chat_id == chat_id]
        
        async def mock_has_achievement(user_id: int, chat_id: int, achievement_id: str) -> bool:
            return any(ua.user_id == user_id and ua.chat_id == chat_id and ua.achievement_id == achievement_id
                      for ua in initial_user_achievements)
        
        async def mock_unlock_achievement(user_achievement: UserAchievement) -> None:
            initial_user_achievements.append(user_achievement)
        
        repo.get_all_achievements.side_effect = mock_get_all_achievements
        repo.get_user_achievements.side_effect = mock_get_user_achievements
        repo.has_achievement.side_effect = mock_has_achievement
        repo.unlock_achievement.side_effect = mock_unlock_achievement
        
        return repo


@pytest.fixture
def mock_repositories(sample_user_stats, sample_achievements, sample_user_achievements):
    """Fixture providing mock repositories with sample data."""
    # Convert sample_user_stats to the format expected by MockRepositoryFactory
    initial_user_data = {}
    for key, stats in sample_user_stats.items():
        initial_user_data[(stats.user_id, stats.chat_id)] = stats
    
    return {
        'user_stats_repo': MockRepositoryFactory.create_user_stats_repository(initial_user_data),
        'achievement_repo': MockRepositoryFactory.create_achievement_repository(
            sample_achievements.values(),
            sample_user_achievements
        )
    }


@pytest.fixture
def mock_telegram_context():
    """Fixture providing a mock Telegram context."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = Mock(spec=Bot)
    context.bot.send_message = Mock()
    context.bot.send_sticker = Mock()
    context.args = []
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    return context