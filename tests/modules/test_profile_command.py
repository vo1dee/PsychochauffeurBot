"""
Tests for profile command functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from modules.handlers.utility_commands import profile_command, _find_user_by_username
from modules.leveling_models import UserProfile, Achievement


class TestProfileCommand:
    """Test cases for profile command."""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock update object."""
        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.from_user = MagicMock(spec=User)
        update.message.from_user.id = 12345
        update.message.from_user.username = "testuser"
        update.message.from_user.first_name = "Test"
        update.message.from_user.is_bot = False
        update.message.reply_text = AsyncMock()
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 67890
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context object."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {}
        return context
    
    @pytest.fixture
    def mock_leveling_service(self):
        """Create a mock leveling service."""
        service = AsyncMock()
        service.is_enabled.return_value = True
        return service
    
    @pytest.fixture
    def mock_service_registry(self, mock_leveling_service):
        """Create a mock service registry."""
        registry = MagicMock()
        registry.get_service.return_value = mock_leveling_service
        return registry
    
    @pytest.fixture
    def sample_profile(self):
        """Create a sample user profile."""
        achievements = [
            Achievement("newcomer", "Newcomer", "First message", "👶", "", "messages_count", 1, "activity"),
            Achievement("chatterbox", "Chatterbox", "100 messages", "💬", "", "messages_count", 100, "activity")
        ]
        
        return UserProfile(
            user_id=12345,
            username="testuser",
            level=5,
            xp=250,
            next_level_xp=400,
            progress_percentage=62.5,
            achievements=achievements,
            stats={
                'messages_count': 150,
                'links_shared': 10,
                'thanks_received': 5
            }
        )
    
    @pytest.mark.asyncio
    async def test_profile_command_service_not_available(self, mock_update, mock_context):
        """Test profile command when service is not available."""
        mock_context.bot_data = {}
        
        await profile_command(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once_with("❌ Leveling system is not available.")
    
    @pytest.mark.asyncio
    async def test_profile_command_service_disabled(self, mock_update, mock_context, mock_service_registry, mock_leveling_service):
        """Test profile command when service is disabled."""
        mock_context.bot_data = {'service_registry': mock_service_registry}
        # Make is_enabled() return False synchronously
        mock_leveling_service.is_enabled = MagicMock(return_value=False)
        
        await profile_command(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once_with("❌ Leveling system is disabled.")
    
    @pytest.mark.asyncio
    async def test_profile_command_own_profile_no_data(self, mock_update, mock_context, mock_service_registry, mock_leveling_service):
        """Test profile command for own profile with no data."""
        mock_context.bot_data = {'service_registry': mock_service_registry}
        mock_leveling_service.get_user_profile.return_value = None
        
        await profile_command(mock_update, mock_context)
        
        mock_leveling_service.get_user_profile.assert_called_once_with(12345, 67890)
        mock_update.message.reply_text.assert_called_once_with(
            "📊 No leveling data found. Send some messages to start earning XP!"
        )
    
    @pytest.mark.asyncio
    async def test_profile_command_own_profile_success(self, mock_update, mock_context, mock_service_registry, mock_leveling_service, sample_profile):
        """Test successful profile command for own profile."""
        mock_context.bot_data = {'service_registry': mock_service_registry}
        mock_leveling_service.get_user_profile.return_value = sample_profile
        
        await profile_command(mock_update, mock_context)
        
        mock_leveling_service.get_user_profile.assert_called_once_with(12345, 67890)
        
        # Check that reply was called with profile information
        call_args = mock_update.message.reply_text.call_args
        assert call_args is not None
        profile_text = call_args[0][0]
        
        # Verify profile content (using markdown formatting)
        assert "Profile for testuser" in profile_text
        assert "**Level:** 5" in profile_text
        assert "**XP:** 250" in profile_text
        assert "**Progress:** 62.5%" in profile_text
        assert "Messages: 150" in profile_text
        assert "Links shared: 10" in profile_text
        assert "Thanks received: 5" in profile_text
        assert "**Achievements (2):**" in profile_text
        assert "👶 💬" in profile_text
    
    @pytest.mark.asyncio
    async def test_profile_command_no_achievements(self, mock_update, mock_context, mock_service_registry, mock_leveling_service):
        """Test profile command with no achievements."""
        mock_context.bot_data = {'service_registry': mock_service_registry}
        
        profile_no_achievements = UserProfile(
            user_id=12345,
            username="testuser",
            level=1,
            xp=10,
            next_level_xp=50,
            progress_percentage=20.0,
            achievements=[],
            stats={
                'messages_count': 10,
                'links_shared': 0,
                'thanks_received': 0
            }
        )
        
        mock_leveling_service.get_user_profile.return_value = profile_no_achievements
        
        await profile_command(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        profile_text = call_args[0][0]
        
        assert "**Achievements:** None yet - keep chatting to unlock some!" in profile_text
    
    @pytest.mark.asyncio
    async def test_profile_command_other_user_success(self, mock_update, mock_context, mock_service_registry, mock_leveling_service, sample_profile):
        """Test profile command for another user."""
        mock_context.bot_data = {'service_registry': mock_service_registry}
        mock_context.args = ["@otheruser"]
        
        # Mock the user lookup
        with patch('modules.handlers.utility_commands._find_user_by_username') as mock_find_user:
            mock_find_user.return_value = (54321, "otheruser")
            
            # Create profile for other user
            other_profile = UserProfile(
                user_id=54321,
                username="otheruser",
                level=3,
                xp=120,
                next_level_xp=200,
                progress_percentage=60.0,
                achievements=[],
                stats={
                    'messages_count': 80,
                    'links_shared': 5,
                    'thanks_received': 2
                }
            )
            mock_leveling_service.get_user_profile.return_value = other_profile
            
            await profile_command(mock_update, mock_context)
            
            mock_find_user.assert_called_once_with("otheruser", 67890, mock_context)
            mock_leveling_service.get_user_profile.assert_called_once_with(54321, 67890)
            
            call_args = mock_update.message.reply_text.call_args
            profile_text = call_args[0][0]
            
            assert "Profile for otheruser" in profile_text
            assert "**Level:** 3" in profile_text
    
    @pytest.mark.asyncio
    async def test_profile_command_user_not_found(self, mock_update, mock_context, mock_service_registry, mock_leveling_service):
        """Test profile command when target user is not found."""
        mock_context.bot_data = {'service_registry': mock_service_registry}
        mock_context.args = ["@nonexistent"]
        
        with patch('modules.handlers.utility_commands._find_user_by_username') as mock_find_user:
            mock_find_user.return_value = (None, None)
            
            await profile_command(mock_update, mock_context)
            
            mock_update.message.reply_text.assert_called_once_with(
                "❌ User @nonexistent not found in this chat or has no leveling data."
            )


class TestFindUserByUsername:
    """Test cases for _find_user_by_username helper function."""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context object."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {'service_registry': MagicMock()}
        return context
    
    @pytest.mark.asyncio
    async def test_find_user_by_username_success(self, mock_context):
        """Test successful user lookup by username."""
        with patch('modules.database.Database') as mock_db:
            # Make fetch_one an async mock
            mock_db.fetch_one = AsyncMock(return_value={
                'user_id': 12345,
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User'
            })
            
            user_id, display_name = await _find_user_by_username("testuser", 67890, mock_context)
            
            assert user_id == 12345
            assert display_name == "testuser"
            mock_db.fetch_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_user_by_username_not_found(self, mock_context):
        """Test user lookup when user is not found."""
        with patch('modules.database.Database') as mock_db:
            mock_db.fetch_one = AsyncMock(return_value=None)
            
            user_id, display_name = await _find_user_by_username("nonexistent", 67890, mock_context)
            
            assert user_id is None
            assert display_name is None
    
    @pytest.mark.asyncio
    async def test_find_user_by_username_no_service_registry(self):
        """Test user lookup when service registry is not available."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {}
        
        user_id, display_name = await _find_user_by_username("testuser", 67890, context)
        
        assert user_id is None
        assert display_name is None
    
    @pytest.mark.asyncio
    async def test_find_user_by_username_database_error(self, mock_context):
        """Test user lookup when database error occurs."""
        with patch('modules.database.Database') as mock_db:
            mock_db.fetch_one = AsyncMock(side_effect=Exception("Database error"))
            
            user_id, display_name = await _find_user_by_username("testuser", 67890, mock_context)
            
            assert user_id is None
            assert display_name is None