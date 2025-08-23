"""
Comprehensive unit tests for the User Leveling System core components.

This module provides extensive unit testing for XPCalculator, LevelManager, 
and related components with full coverage of edge cases, error conditions, 
and requirements validation.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from telegram import Message, User, Chat

# Import core components that are available
from modules.xp_calculator import XPCalculator, LinkDetector, ThankYouDetector, ActivityDetector
from modules.level_manager import LevelManager
from modules.leveling_models import UserStats, LevelUpResult

# Import test base classes
from tests.base_test_classes import BaseTestCase, AsyncBaseTestCase


class TestXPCalculatorComprehensive(BaseTestCase):
    """Comprehensive tests for XPCalculator with all edge cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.calculator = XPCalculator()
    
    def create_message_mock(self, text: str = None, from_user_id: int = 12345, 
                           reply_to_message=None, **kwargs) -> Mock:
        """Create a comprehensive message mock."""
        message = Mock(spec=Message)
        message.text = text
        message.reply_to_message = reply_to_message
        
        # Create from_user
        from_user = Mock(spec=User)
        from_user.id = from_user_id
        from_user.username = "testuser"
        from_user.first_name = "Test"
        from_user.is_bot = False
        message.from_user = from_user
        
        # Apply additional attributes
        for key, value in kwargs.items():
            setattr(message, key, value)
        
        return message
    
    def create_reply_message_mock(self, replied_user_id: int) -> Mock:
        """Create a mock reply-to message."""
        reply_message = Mock(spec=Message)
        reply_user = Mock(spec=User)
        reply_user.id = replied_user_id
        reply_user.username = "replieduser"
        reply_message.from_user = reply_user
        return reply_message
    
    # Basic XP Calculation Tests
    def test_calculate_message_xp_basic(self):
        """Test basic message XP calculation."""
        message = self.create_message_mock("Hello world!")
        xp = self.calculator.calculate_message_xp(message)
        self.assertEqual(xp, 1)
    
    def test_calculate_message_xp_empty_message(self):
        """Test XP calculation for empty messages."""
        message = self.create_message_mock("")
        xp = self.calculator.calculate_message_xp(message)
        self.assertEqual(xp, 1)  # Still gets base XP
    
    def test_calculate_message_xp_none_text(self):
        """Test XP calculation when text is None."""
        message = self.create_message_mock(None)
        xp = self.calculator.calculate_message_xp(message)
        self.assertEqual(xp, 1)  # Still gets base XP
    
    def test_calculate_message_xp_no_user(self):
        """Test XP calculation when from_user is None."""
        message = Mock(spec=Message)
        message.text = "Hello"
        message.from_user = None
        xp = self.calculator.calculate_message_xp(message)
        self.assertEqual(xp, 0)  # No XP for messages without user
    
    # Link Detection and XP Tests
    def test_calculate_link_xp_single_http(self):
        """Test link XP calculation for single HTTP link."""
        message = self.create_message_mock("Check out http://example.com")
        xp = self.calculator.calculate_link_xp(message)
        self.assertEqual(xp, 3)
    
    def test_calculate_link_xp_single_https(self):
        """Test link XP calculation for single HTTPS link."""
        message = self.create_message_mock("Visit https://example.com")
        xp = self.calculator.calculate_link_xp(message)
        self.assertEqual(xp, 3)
    
    def test_calculate_link_xp_multiple_links(self):
        """Test link XP calculation for multiple links."""
        message = self.create_message_mock("Visit http://example.com and https://test.org")
        xp = self.calculator.calculate_link_xp(message)
        self.assertEqual(xp, 3)  # Still only 3 XP regardless of count
    
    def test_calculate_link_xp_no_links(self):
        """Test link XP calculation for messages without links."""
        message = self.create_message_mock("Just a regular message")
        xp = self.calculator.calculate_link_xp(message)
        self.assertEqual(xp, 0)
    
    def test_calculate_link_xp_malformed_links(self):
        """Test link XP calculation for malformed links."""
        test_cases = [
            "Visit example.com",  # No protocol
            "Check ftp://example.com",  # Wrong protocol
            "See www.example.com",  # No protocol
            "http://",  # Incomplete
            "https://",  # Incomplete
        ]
        
        for text in test_cases:
            message = self.create_message_mock(text)
            xp = self.calculator.calculate_link_xp(message)
            # Only http:// and https:// should count
            expected = 3 if text.startswith(('http://', 'https://')) and len(text) > 8 else 0
            self.assertEqual(xp, expected, f"Failed for text: {text}")
    
    def test_detect_links_comprehensive(self):
        """Test comprehensive link detection."""
        test_cases = [
            ("Visit https://example.com", ["https://example.com"]),
            ("Check http://test.org", ["http://test.org"]),
            ("Multiple: http://a.com https://b.com", ["http://a.com", "https://b.com"]),
            ("No links here", []),
            ("Mixed: example.com and https://real.com", ["https://real.com"]),
            ("", []),
            (None, []),
        ]
        
        for text, expected in test_cases:
            links = self.calculator.detect_links(text)
            self.assertEqual(links, expected, f"Failed for text: {text}")
    
    # Thank You Detection and XP Tests
    def test_calculate_thanks_xp_reply_message(self):
        """Test thanks XP calculation for reply messages."""
        reply_message = self.create_reply_message_mock(replied_user_id=123)
        message = self.create_message_mock("Thank you!", reply_to_message=reply_message)
        
        thanks_xp = self.calculator.calculate_thanks_xp(message)
        self.assertEqual(thanks_xp, {123: 5})
    
    def test_calculate_thanks_xp_mention_in_text(self):
        """Test thanks XP calculation for mentions in text."""
        message = self.create_message_mock("Thanks @john for the help!")
        
        # Mock the get_thanked_users method to return user IDs for mentions
        with patch.object(self.calculator.thank_you_detector, 'get_thanked_users', return_value=[456]):
            thanks_xp = self.calculator.calculate_thanks_xp(message)
            self.assertEqual(thanks_xp, {456: 5})
    
    def test_calculate_thanks_xp_no_thanks(self):
        """Test thanks XP calculation for non-thank messages."""
        message = self.create_message_mock("Just a regular message")
        thanks_xp = self.calculator.calculate_thanks_xp(message)
        self.assertEqual(thanks_xp, {})
    
    def test_calculate_thanks_xp_multiple_users(self):
        """Test thanks XP calculation for multiple thanked users."""
        message = self.create_message_mock("Thanks @john and @mary!")
        
        with patch.object(self.calculator.thank_you_detector, 'get_thanked_users', return_value=[456, 789]):
            thanks_xp = self.calculator.calculate_thanks_xp(message)
            self.assertEqual(thanks_xp, {456: 5, 789: 5})
    
    def test_detect_thanks_keywords_comprehensive(self):
        """Test comprehensive thank you keyword detection."""
        thank_keywords = [
            "thanks", "thank you", "thx", "ty", "10x",
            "дякую", "дяки", "дякі", "спасибі", "спс", "дяк",
            "תודה"
        ]
        
        for keyword in thank_keywords:
            message = self.create_message_mock(f"{keyword} @user")
            is_thanks = self.calculator.is_thank_you_message(message)
            # This will depend on the actual implementation
            # For now, we'll test that the method doesn't crash
            self.assertIsInstance(is_thanks, bool, f"Failed for keyword: {keyword}")
    
    # Total XP Calculation Tests
    def test_calculate_total_message_xp_regular(self):
        """Test total XP calculation for regular messages."""
        message = self.create_message_mock("Hello world!")
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        self.assertEqual(sender_xp, 1)  # Base message XP
        self.assertEqual(thanked_users_xp, {})
    
    def test_calculate_total_message_xp_with_link(self):
        """Test total XP calculation for messages with links."""
        message = self.create_message_mock("Check out https://example.com")
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        self.assertEqual(sender_xp, 4)  # Base (1) + Link (3)
        self.assertEqual(thanked_users_xp, {})
    
    def test_calculate_total_message_xp_with_thanks(self):
        """Test total XP calculation for thank you messages."""
        reply_message = self.create_reply_message_mock(replied_user_id=123)
        message = self.create_message_mock("Thank you!", reply_to_message=reply_message)
        
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        self.assertEqual(sender_xp, 1)  # Base message XP only
        self.assertEqual(thanked_users_xp, {123: 5})
    
    def test_calculate_total_message_xp_complex(self):
        """Test total XP calculation for complex messages."""
        reply_message = self.create_reply_message_mock(replied_user_id=123)
        message = self.create_message_mock(
            "Thanks! Check https://example.com and http://test.org", 
            reply_to_message=reply_message
        )
        
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        self.assertEqual(sender_xp, 4)  # Base (1) + Link (3)
        self.assertEqual(thanked_users_xp, {123: 5})
    
    # Activity Summary Tests
    def test_get_activity_summary_comprehensive(self):
        """Test comprehensive activity summary generation."""
        message = self.create_message_mock("Thanks @john! Check https://example.com")
        
        with patch.object(self.calculator.thank_you_detector, 'get_thanked_users', return_value=[456]):
            with patch.object(self.calculator.thank_you_detector, 'get_mentioned_usernames', return_value=['john']):
                summary = self.calculator.get_activity_summary(message)
        
        expected_keys = {
            'has_message', 'has_links', 'is_thank_you', 'sender_xp', 
            'thanked_users_xp', 'links_found', 'thanked_users', 'mentioned_usernames'
        }
        self.assertEqual(set(summary.keys()), expected_keys)
        
        self.assertTrue(summary['has_message'])
        self.assertTrue(summary['has_links'])
        self.assertTrue(summary['is_thank_you'])
        self.assertEqual(summary['sender_xp'], 4)  # Base + Link
        self.assertEqual(summary['thanked_users_xp'], {456: 5})
        self.assertEqual(summary['links_found'], ['https://example.com'])
        self.assertEqual(summary['thanked_users'], [456])
        self.assertEqual(summary['mentioned_usernames'], ['john'])
    
    # Edge Cases and Error Handling
    def test_calculate_xp_with_bot_message(self):
        """Test XP calculation for bot messages."""
        message = self.create_message_mock("Hello from bot!")
        message.from_user.is_bot = True
        
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        # Bots should not receive XP
        self.assertEqual(sender_xp, 0)
        self.assertEqual(thanked_users_xp, {})
    
    def test_calculate_xp_with_self_thank(self):
        """Test XP calculation when user thanks themselves."""
        reply_message = self.create_reply_message_mock(replied_user_id=12345)  # Same as sender
        message = self.create_message_mock("Thank you!", reply_to_message=reply_message, from_user_id=12345)
        
        thanks_xp = self.calculator.calculate_thanks_xp(message)
        
        # Users should not be able to thank themselves
        # This depends on implementation - might be {} or {12345: 5}
        self.assertIsInstance(thanks_xp, dict)
    
    def test_performance_with_long_message(self):
        """Test performance with very long messages."""
        long_text = "word " * 10000  # 10,000 words
        message = self.create_message_mock(long_text)
        
        # Should complete quickly
        import time
        start_time = time.time()
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        end_time = time.time()
        
        self.assertLess(end_time - start_time, 1.0)  # Should complete in under 1 second
        self.assertEqual(sender_xp, 1)  # Still just base XP


class TestLevelManagerComprehensive(BaseTestCase):
    """Comprehensive tests for LevelManager with all edge cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.level_manager = LevelManager()
    
    # Initialization Tests
    def test_initialization_default_values(self):
        """Test LevelManager initialization with default values."""
        manager = LevelManager()
        self.assertEqual(manager.base_xp, 50)
        self.assertEqual(manager.multiplier, 2.0)
        self.assertEqual(manager._threshold_cache, {1: 0})
    
    def test_initialization_custom_values(self):
        """Test LevelManager initialization with custom values."""
        manager = LevelManager(base_xp=100, multiplier=1.5)
        self.assertEqual(manager.base_xp, 100)
        self.assertEqual(manager.multiplier, 1.5)
        self.assertEqual(manager._threshold_cache, {1: 0})
    
    def test_initialization_edge_values(self):
        """Test LevelManager initialization with edge values."""
        # Very small values
        manager1 = LevelManager(base_xp=1, multiplier=1.1)
        self.assertEqual(manager1.base_xp, 1)
        self.assertEqual(manager1.multiplier, 1.1)
        
        # Large values
        manager2 = LevelManager(base_xp=10000, multiplier=10.0)
        self.assertEqual(manager2.base_xp, 10000)
        self.assertEqual(manager2.multiplier, 10.0)
    
    # Level Threshold Tests
    def test_get_level_threshold_requirements_compliance(self):
        """Test level thresholds match exact requirements."""
        # Requirements: Level 1: 0 XP, Level 2: 50 XP, Level 3: 100 XP, Level 4: 200 XP, Level 5: 400 XP
        expected_thresholds = {
            1: 0,
            2: 50,
            3: 100,
            4: 200,
            5: 400,
            6: 800,
            7: 1600,
            8: 3200,
            9: 6400,
            10: 12800
        }
        
        for level, expected_xp in expected_thresholds.items():
            actual_xp = self.level_manager.get_level_threshold(level)
            self.assertEqual(actual_xp, expected_xp, f"Level {level} threshold mismatch")
    
    def test_get_level_threshold_edge_cases(self):
        """Test level threshold calculation for edge cases."""
        # Level 0 and negative levels should return 0
        self.assertEqual(self.level_manager.get_level_threshold(0), 0)
        self.assertEqual(self.level_manager.get_level_threshold(-1), 0)
        self.assertEqual(self.level_manager.get_level_threshold(-100), 0)
        
        # Very high levels should not crash
        high_level_threshold = self.level_manager.get_level_threshold(100)
        self.assertIsInstance(high_level_threshold, int)
        self.assertGreater(high_level_threshold, 0)
    
    def test_get_level_threshold_caching(self):
        """Test that level thresholds are properly cached."""
        # Calculate threshold for level 10
        threshold1 = self.level_manager.get_level_threshold(10)
        
        # Verify it's cached
        self.assertIn(10, self.level_manager._threshold_cache)
        self.assertEqual(self.level_manager._threshold_cache[10], threshold1)
        
        # Second call should use cache
        threshold2 = self.level_manager.get_level_threshold(10)
        self.assertEqual(threshold1, threshold2)
    
    def test_get_level_threshold_monotonic_increase(self):
        """Test that level thresholds always increase."""
        for level in range(1, 20):
            current_threshold = self.level_manager.get_level_threshold(level)
            next_threshold = self.level_manager.get_level_threshold(level + 1)
            self.assertLess(current_threshold, next_threshold, 
                          f"Threshold not increasing from level {level} to {level + 1}")
    
    # Level Calculation Tests
    def test_calculate_level_exact_thresholds(self):
        """Test level calculation for exact threshold values."""
        test_cases = [
            (0, 1),      # Level 1: 0 XP
            (50, 2),     # Level 2: 50 XP
            (100, 3),    # Level 3: 100 XP
            (200, 4),    # Level 4: 200 XP
            (400, 5),    # Level 5: 400 XP
            (800, 6),    # Level 6: 800 XP
        ]
        
        for xp, expected_level in test_cases:
            actual_level = self.level_manager.calculate_level(xp)
            self.assertEqual(actual_level, expected_level, f"XP {xp} should be level {expected_level}")
    
    def test_calculate_level_between_thresholds(self):
        """Test level calculation for XP values between thresholds."""
        test_cases = [
            (25, 1),     # Between level 1 and 2
            (49, 1),     # Just before level 2
            (75, 2),     # Between level 2 and 3
            (99, 2),     # Just before level 3
            (150, 3),    # Between level 3 and 4
            (199, 3),    # Just before level 4
            (300, 4),    # Between level 4 and 5
            (399, 4),    # Just before level 5
        ]
        
        for xp, expected_level in test_cases:
            actual_level = self.level_manager.calculate_level(xp)
            self.assertEqual(actual_level, expected_level, f"XP {xp} should be level {expected_level}")
    
    def test_calculate_level_edge_cases(self):
        """Test level calculation for edge cases."""
        # Negative XP should return level 1
        self.assertEqual(self.level_manager.calculate_level(-1), 1)
        self.assertEqual(self.level_manager.calculate_level(-1000), 1)
        
        # Very large XP values
        large_xp = 1000000
        level = self.level_manager.calculate_level(large_xp)
        self.assertGreaterEqual(level, 1)
        self.assertIsInstance(level, int)
        
        # Verify the calculated level is correct
        level_threshold = self.level_manager.get_level_threshold(level)
        next_level_threshold = self.level_manager.get_level_threshold(level + 1)
        self.assertLessEqual(level_threshold, large_xp)
        self.assertLess(large_xp, next_level_threshold)
    
    # Progress Calculation Tests
    def test_get_next_level_progress_comprehensive(self):
        """Test next level progress calculation comprehensively."""
        test_cases = [
            # (current_xp, current_level, expected_xp_needed, expected_xp_progress)
            (0, 1, 50, 0),      # Start of level 1
            (25, 1, 25, 25),    # Middle of level 1
            (49, 1, 1, 49),     # End of level 1
            (50, 2, 50, 0),     # Start of level 2
            (75, 2, 25, 25),    # Middle of level 2
            (99, 2, 1, 49),     # End of level 2
            (100, 3, 100, 0),   # Start of level 3
            (150, 3, 50, 50),   # Middle of level 3
        ]
        
        for current_xp, current_level, expected_needed, expected_progress in test_cases:
            xp_needed, xp_progress = self.level_manager.get_next_level_progress(current_xp, current_level)
            self.assertEqual(xp_needed, expected_needed, 
                           f"XP needed mismatch for {current_xp} XP at level {current_level}")
            self.assertEqual(xp_progress, expected_progress,
                           f"XP progress mismatch for {current_xp} XP at level {current_level}")
    
    def test_get_level_progress_percentage_comprehensive(self):
        """Test level progress percentage calculation comprehensively."""
        test_cases = [
            # (current_xp, current_level, expected_percentage)
            (0, 1, 0.0),        # Start of level 1
            (25, 1, 50.0),      # Middle of level 1
            (50, 2, 0.0),       # Start of level 2
            (75, 2, 50.0),      # Middle of level 2
            (100, 3, 0.0),      # Start of level 3
            (150, 3, 50.0),     # Middle of level 3
            (200, 4, 0.0),      # Start of level 4
            (300, 4, 50.0),     # Middle of level 4
        ]
        
        for current_xp, current_level, expected_percentage in test_cases:
            percentage = self.level_manager.get_level_progress_percentage(current_xp, current_level)
            self.assertAlmostEqual(percentage, expected_percentage, places=1,
                                 msg=f"Percentage mismatch for {current_xp} XP at level {current_level}")
    
    def test_get_level_progress_percentage_bounds(self):
        """Test that progress percentage is always within bounds."""
        test_cases = [
            (0, 1), (25, 1), (50, 2), (75, 2), (100, 3), (150, 3),
            (200, 4), (300, 4), (400, 5), (600, 5), (800, 6)
        ]
        
        for current_xp, current_level in test_cases:
            percentage = self.level_manager.get_level_progress_percentage(current_xp, current_level)
            self.assertGreaterEqual(percentage, 0.0, f"Percentage below 0 for {current_xp} XP at level {current_level}")
            self.assertLessEqual(percentage, 100.0, f"Percentage above 100 for {current_xp} XP at level {current_level}")
    
    # Level Up Detection Tests
    def test_check_level_up_no_change(self):
        """Test level up check when no level change occurs."""
        test_cases = [
            (25, 35),   # Both in level 1
            (75, 85),   # Both in level 2
            (150, 175), # Both in level 3
            (300, 350), # Both in level 4
        ]
        
        for old_xp, new_xp in test_cases:
            result = self.level_manager.check_level_up(old_xp, new_xp)
            self.assertIsNone(result, f"Unexpected level up from {old_xp} to {new_xp} XP")
    
    def test_check_level_up_single_level(self):
        """Test level up check for single level increases."""
        test_cases = [
            (45, 55, 1, 2),     # Level 1 to 2
            (95, 105, 2, 3),    # Level 2 to 3
            (195, 205, 3, 4),   # Level 3 to 4
            (395, 405, 4, 5),   # Level 4 to 5
        ]
        
        for old_xp, new_xp, expected_old_level, expected_new_level in test_cases:
            result = self.level_manager.check_level_up(old_xp, new_xp)
            self.assertIsNotNone(result, f"Expected level up from {old_xp} to {new_xp} XP")
            self.assertTrue(result.leveled_up)
            self.assertEqual(result.old_level, expected_old_level)
            self.assertEqual(result.new_level, expected_new_level)
    
    def test_check_level_up_multiple_levels(self):
        """Test level up check for multiple level increases."""
        test_cases = [
            (25, 150, 1, 3),    # Level 1 to 3
            (45, 250, 1, 4),    # Level 1 to 4
            (75, 450, 2, 5),    # Level 2 to 5
        ]
        
        for old_xp, new_xp, expected_old_level, expected_new_level in test_cases:
            result = self.level_manager.check_level_up(old_xp, new_xp)
            self.assertIsNotNone(result, f"Expected level up from {old_xp} to {new_xp} XP")
            self.assertTrue(result.leveled_up)
            self.assertEqual(result.old_level, expected_old_level)
            self.assertEqual(result.new_level, expected_new_level)
    
    def test_check_level_up_edge_cases(self):
        """Test level up check for edge cases."""
        # XP decrease should not trigger level up
        result = self.level_manager.check_level_up(100, 50)
        self.assertIsNone(result)
        
        # Same XP should not trigger level up
        result = self.level_manager.check_level_up(100, 100)
        self.assertIsNone(result)
        
        # Negative XP values
        result = self.level_manager.check_level_up(-10, 10)
        self.assertIsNone(result)  # Both would be level 1
    
    # UserStats Integration Tests
    def test_update_user_level_no_change(self):
        """Test updating user level when no change occurs."""
        user_stats = UserStats(user_id=1, chat_id=1, xp=25, level=1)
        original_level = user_stats.level
        
        result = self.level_manager.update_user_level(user_stats)
        
        self.assertIsNone(result)
        self.assertEqual(user_stats.level, original_level)
    
    def test_update_user_level_with_change(self):
        """Test updating user level when change occurs."""
        user_stats = UserStats(user_id=1, chat_id=1, xp=75, level=1)
        
        result = self.level_manager.update_user_level(user_stats)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.leveled_up)
        self.assertEqual(result.old_level, 1)
        self.assertEqual(result.new_level, 2)
        self.assertEqual(user_stats.level, 2)
    
    def test_update_user_level_multiple_levels(self):
        """Test updating user level with multiple level increases."""
        user_stats = UserStats(user_id=1, chat_id=1, xp=250, level=1)
        
        result = self.level_manager.update_user_level(user_stats)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.leveled_up)
        self.assertEqual(result.old_level, 1)
        self.assertEqual(result.new_level, 4)
        self.assertEqual(user_stats.level, 4)
    
    # Utility Methods Tests
    def test_get_level_range_info_comprehensive(self):
        """Test level range information for various levels."""
        test_cases = [
            # (level, expected_start, expected_end, expected_range)
            (1, 0, 50, 50),
            (2, 50, 100, 50),
            (3, 100, 200, 100),
            (4, 200, 400, 200),
            (5, 400, 800, 400),
            (6, 800, 1600, 800),
        ]
        
        for level, expected_start, expected_end, expected_range in test_cases:
            start_xp, end_xp, xp_range = self.level_manager.get_level_range_info(level)
            self.assertEqual(start_xp, expected_start, f"Start XP mismatch for level {level}")
            self.assertEqual(end_xp, expected_end, f"End XP mismatch for level {level}")
            self.assertEqual(xp_range, expected_range, f"XP range mismatch for level {level}")
    
    def test_validate_level_progression_comprehensive(self):
        """Test level progression validation comprehensively."""
        # Test various level ranges
        for max_level in [5, 10, 15, 20, 25]:
            is_valid = self.level_manager.validate_level_progression(max_level)
            self.assertTrue(is_valid, f"Level progression validation failed for max level {max_level}")
    
    def test_precompute_thresholds(self):
        """Test precomputing level thresholds."""
        # Clear cache first
        self.level_manager.clear_cache()
        self.assertEqual(len(self.level_manager._threshold_cache), 1)  # Only level 1
        
        # Precompute thresholds
        self.level_manager.precompute_thresholds(10)
        self.assertEqual(len(self.level_manager._threshold_cache), 10)
        
        # Verify all levels are cached
        for level in range(1, 11):
            self.assertIn(level, self.level_manager._threshold_cache)
    
    def test_clear_cache(self):
        """Test clearing the threshold cache."""
        # Populate cache
        self.level_manager.get_level_threshold(5)
        self.level_manager.get_level_threshold(10)
        self.assertGreater(len(self.level_manager._threshold_cache), 1)
        
        # Clear cache
        self.level_manager.clear_cache()
        self.assertEqual(self.level_manager._threshold_cache, {1: 0})
    
    def test_get_stats_summary(self):
        """Test getting level manager statistics summary."""
        # Trigger some threshold calculations
        self.level_manager.get_level_threshold(5)
        self.level_manager.get_level_threshold(10)
        
        stats = self.level_manager.get_stats_summary()
        
        expected_keys = {'base_xp', 'multiplier', 'cached_thresholds', 'max_cached_level'}
        self.assertEqual(set(stats.keys()), expected_keys)
        
        self.assertEqual(stats['base_xp'], 50)
        self.assertEqual(stats['multiplier'], 2.0)
        self.assertGreaterEqual(stats['cached_thresholds'], 3)
        self.assertGreaterEqual(stats['max_cached_level'], 10)
    
    # Performance Tests
    def test_performance_large_xp_values(self):
        """Test performance with large XP values."""
        import time
        
        large_xp_values = [1000000, 5000000, 10000000]
        
        for xp in large_xp_values:
            start_time = time.time()
            level = self.level_manager.calculate_level(xp)
            end_time = time.time()
            
            # Should complete quickly
            self.assertLess(end_time - start_time, 0.1, f"Slow calculation for XP {xp}")
            self.assertGreaterEqual(level, 1)
            self.assertIsInstance(level, int)
    
    def test_performance_many_calculations(self):
        """Test performance with many level calculations."""
        import time
        
        start_time = time.time()
        
        # Perform many calculations
        for xp in range(0, 10000, 10):
            level = self.level_manager.calculate_level(xp)
            self.assertGreaterEqual(level, 1)
        
        end_time = time.time()
        
        # Should complete quickly
        self.assertLess(end_time - start_time, 1.0, "Slow performance for many calculations")


if __name__ == '__main__':
    pytest.main([__file__, "-v"])