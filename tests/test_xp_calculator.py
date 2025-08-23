"""
Unit tests for the XP calculation engine.

Tests all XP calculation logic including activity detectors for messages, links, and thank you expressions.
"""

import pytest
from unittest.mock import Mock, MagicMock
from telegram import Message, User
from modules.xp_calculator import XPCalculator, LinkDetector, ThankYouDetector, ActivityDetector


class TestActivityDetector:
    """Test the base ActivityDetector class."""
    
    def test_detect_not_implemented(self):
        """Test that detect method raises NotImplementedError."""
        detector = ActivityDetector()
        message = Mock(spec=Message)
        
        with pytest.raises(NotImplementedError):
            detector.detect(message)
    
    def test_calculate_xp_not_implemented(self):
        """Test that calculate_xp method raises NotImplementedError."""
        detector = ActivityDetector()
        message = Mock(spec=Message)
        
        with pytest.raises(NotImplementedError):
            detector.calculate_xp(message)


class TestLinkDetector:
    """Test the LinkDetector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = LinkDetector()
    
    def create_message(self, text: str) -> Mock:
        """Create a mock message with given text."""
        message = Mock(spec=Message)
        message.text = text
        return message
    
    def test_detect_http_link(self):
        """Test detection of HTTP links."""
        message = self.create_message("Check out http://example.com")
        assert self.detector.detect(message) is True
    
    def test_detect_https_link(self):
        """Test detection of HTTPS links."""
        message = self.create_message("Visit https://example.com for more info")
        assert self.detector.detect(message) is True
    
    def test_detect_multiple_links(self):
        """Test detection of multiple links in one message."""
        message = self.create_message("Visit http://example.com and https://test.org")
        assert self.detector.detect(message) is True
    
    def test_detect_no_links(self):
        """Test that messages without links are not detected."""
        message = self.create_message("Just a regular message")
        assert self.detector.detect(message) is False
    
    def test_detect_empty_message(self):
        """Test that empty messages are not detected."""
        message = Mock(spec=Message)
        message.text = None
        assert self.detector.detect(message) is False
    
    def test_detect_case_insensitive(self):
        """Test that link detection is case insensitive."""
        message = self.create_message("Check HTTP://EXAMPLE.COM")
        assert self.detector.detect(message) is True
    
    def test_calculate_xp_with_links(self):
        """Test XP calculation for messages with links."""
        message = self.create_message("Check out https://example.com")
        assert self.detector.calculate_xp(message) == 3
    
    def test_calculate_xp_without_links(self):
        """Test XP calculation for messages without links."""
        message = self.create_message("Just a regular message")
        assert self.detector.calculate_xp(message) == 0
    
    def test_extract_links_single(self):
        """Test extraction of a single link."""
        links = self.detector.extract_links("Visit https://example.com")
        assert links == ["https://example.com"]
    
    def test_extract_links_multiple(self):
        """Test extraction of multiple links."""
        text = "Visit http://example.com and https://test.org"
        links = self.detector.extract_links(text)
        assert len(links) == 2
        assert "http://example.com" in links
        assert "https://test.org" in links
    
    def test_extract_links_none(self):
        """Test extraction from text without links."""
        links = self.detector.extract_links("No links here")
        assert links == []
    
    def test_extract_links_empty_text(self):
        """Test extraction from empty text."""
        links = self.detector.extract_links("")
        assert links == []
        
        links = self.detector.extract_links(None)
        assert links == []


class TestThankYouDetector:
    """Test the ThankYouDetector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ThankYouDetector()
    
    def create_message(self, text: str, reply_to_message=None, from_user_id=1) -> Mock:
        """Create a mock message with given text and optional reply."""
        message = Mock(spec=Message)
        message.text = text
        message.reply_to_message = reply_to_message
        
        # Create from_user
        from_user = Mock(spec=User)
        from_user.id = from_user_id
        message.from_user = from_user
        
        return message
    
    def create_reply_message(self, replied_user_id: int) -> Mock:
        """Create a mock reply-to message."""
        reply_message = Mock(spec=Message)
        reply_user = Mock(spec=User)
        reply_user.id = replied_user_id
        reply_message.from_user = reply_user
        return reply_message
    
    def test_detect_thanks_with_mention(self):
        """Test detection of thank you with user mention."""
        message = self.create_message("Thanks @john for the help!")
        assert self.detector.detect(message) is True
    
    def test_detect_thanks_with_reply(self):
        """Test detection of thank you as a reply."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        assert self.detector.detect(message) is True
    
    def test_detect_ukrainian_thanks_with_mention(self):
        """Test detection of Ukrainian thank you with mention."""
        message = self.create_message("Дякую @петро за допомогу!")
        assert self.detector.detect(message) is True
    
    def test_detect_hebrew_thanks_with_mention(self):
        """Test detection of Hebrew thank you with mention."""
        message = self.create_message("תודה @user")
        assert self.detector.detect(message) is True
    
    def test_detect_various_thank_keywords(self):
        """Test detection of various thank you keywords."""
        keywords = ["thanks", "thank you", "thx", "ty", "10x", "дякую", "дяки", "спасибі", "спс"]
        
        for keyword in keywords:
            message = self.create_message(f"{keyword} @user")
            assert self.detector.detect(message) is True, f"Failed to detect '{keyword}'"
    
    def test_detect_case_insensitive(self):
        """Test that thank you detection is case insensitive."""
        message = self.create_message("THANKS @USER")
        assert self.detector.detect(message) is True
    
    def test_detect_thanks_without_mention_or_reply(self):
        """Test that thanks without mention or reply is not detected."""
        message = self.create_message("Thanks for the help!")
        assert self.detector.detect(message) is False
    
    def test_detect_mention_without_thanks(self):
        """Test that mention without thanks is not detected."""
        message = self.create_message("Hey @john, how are you?")
        assert self.detector.detect(message) is False
    
    def test_detect_empty_message(self):
        """Test that empty messages are not detected."""
        message = Mock(spec=Message)
        message.text = None
        message.reply_to_message = None
        assert self.detector.detect(message) is False
    
    def test_calculate_xp_with_thanks(self):
        """Test XP calculation for thank you messages."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        assert self.detector.calculate_xp(message) == 5
    
    def test_calculate_xp_without_thanks(self):
        """Test XP calculation for non-thank you messages."""
        message = self.create_message("Just a regular message")
        assert self.detector.calculate_xp(message) == 0
    
    def test_get_thanked_users_from_reply(self):
        """Test getting thanked users from reply messages."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        
        thanked_users = self.detector.get_thanked_users(message)
        assert thanked_users == [123]
    
    def test_get_thanked_users_no_thanks(self):
        """Test getting thanked users from non-thank you messages."""
        message = self.create_message("Just a regular message")
        thanked_users = self.detector.get_thanked_users(message)
        assert thanked_users == []
    
    def test_get_thanked_users_no_reply_user(self):
        """Test getting thanked users when reply message has no user."""
        reply_message = Mock(spec=Message)
        reply_message.from_user = None
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        
        thanked_users = self.detector.get_thanked_users(message)
        assert thanked_users == []
    
    def test_get_mentioned_usernames(self):
        """Test extraction of mentioned usernames."""
        usernames = self.detector.get_mentioned_usernames("Thanks @john and @mary!")
        assert set(usernames) == {"john", "mary"}
    
    def test_get_mentioned_usernames_single(self):
        """Test extraction of single mentioned username."""
        usernames = self.detector.get_mentioned_usernames("Thanks @john!")
        assert usernames == ["john"]
    
    def test_get_mentioned_usernames_none(self):
        """Test extraction when no usernames are mentioned."""
        usernames = self.detector.get_mentioned_usernames("Thanks for the help!")
        assert usernames == []
    
    def test_get_mentioned_usernames_empty_text(self):
        """Test extraction from empty text."""
        usernames = self.detector.get_mentioned_usernames("")
        assert usernames == []
        
        usernames = self.detector.get_mentioned_usernames(None)
        assert usernames == []


class TestXPCalculator:
    """Test the main XPCalculator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = XPCalculator()
    
    def create_message(self, text: str, from_user_id=1, reply_to_message=None) -> Mock:
        """Create a mock message with given text."""
        message = Mock(spec=Message)
        message.text = text
        message.reply_to_message = reply_to_message
        
        # Create from_user
        from_user = Mock(spec=User)
        from_user.id = from_user_id
        message.from_user = from_user
        
        return message
    
    def create_reply_message(self, replied_user_id: int) -> Mock:
        """Create a mock reply-to message."""
        reply_message = Mock(spec=Message)
        reply_user = Mock(spec=User)
        reply_user.id = replied_user_id
        reply_message.from_user = reply_user
        return reply_message
    
    def test_calculate_message_xp(self):
        """Test basic message XP calculation."""
        message = self.create_message("Hello world!")
        assert self.calculator.calculate_message_xp(message) == 1
    
    def test_calculate_link_xp_with_link(self):
        """Test link XP calculation for messages with links."""
        message = self.create_message("Check out https://example.com")
        assert self.calculator.calculate_link_xp(message) == 3
    
    def test_calculate_link_xp_without_link(self):
        """Test link XP calculation for messages without links."""
        message = self.create_message("Just a regular message")
        assert self.calculator.calculate_link_xp(message) == 0
    
    def test_calculate_thanks_xp_with_reply(self):
        """Test thanks XP calculation for reply messages."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        
        thanks_xp = self.calculator.calculate_thanks_xp(message)
        assert thanks_xp == {123: 5}
    
    def test_calculate_thanks_xp_without_thanks(self):
        """Test thanks XP calculation for non-thank you messages."""
        message = self.create_message("Just a regular message")
        thanks_xp = self.calculator.calculate_thanks_xp(message)
        assert thanks_xp == {}
    
    def test_calculate_total_message_xp_regular_message(self):
        """Test total XP calculation for regular messages."""
        message = self.create_message("Hello world!")
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        assert sender_xp == 1  # Base message XP
        assert thanked_users_xp == {}
    
    def test_calculate_total_message_xp_with_link(self):
        """Test total XP calculation for messages with links."""
        message = self.create_message("Check out https://example.com")
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        assert sender_xp == 4  # Base message XP (1) + Link XP (3)
        assert thanked_users_xp == {}
    
    def test_calculate_total_message_xp_with_thanks(self):
        """Test total XP calculation for thank you messages."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        assert sender_xp == 1  # Base message XP only
        assert thanked_users_xp == {123: 5}  # Thanks XP goes to thanked user
    
    def test_calculate_total_message_xp_with_link_and_thanks(self):
        """Test total XP calculation for messages with both links and thanks."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thanks! Check https://example.com", reply_to_message=reply_message)
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        
        assert sender_xp == 4  # Base message XP (1) + Link XP (3)
        assert thanked_users_xp == {123: 5}  # Thanks XP goes to thanked user
    
    def test_calculate_total_message_xp_no_user(self):
        """Test total XP calculation for messages without from_user."""
        message = Mock(spec=Message)
        message.text = "Hello world!"
        message.from_user = None
        
        sender_xp, thanked_users_xp = self.calculator.calculate_total_message_xp(message)
        assert sender_xp == 0
        assert thanked_users_xp == {}
    
    def test_detect_links(self):
        """Test link detection method."""
        links = self.calculator.detect_links("Visit https://example.com and http://test.org")
        assert len(links) == 2
        assert "https://example.com" in links
        assert "http://test.org" in links
    
    def test_detect_thanks(self):
        """Test thank you detection method."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        
        thanked_users = self.calculator.detect_thanks(message)
        assert thanked_users == [123]
    
    def test_has_links_true(self):
        """Test has_links method for messages with links."""
        message = self.create_message("Check out https://example.com")
        assert self.calculator.has_links(message) is True
    
    def test_has_links_false(self):
        """Test has_links method for messages without links."""
        message = self.create_message("Just a regular message")
        assert self.calculator.has_links(message) is False
    
    def test_is_thank_you_message_true(self):
        """Test is_thank_you_message method for thank you messages."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you!", reply_to_message=reply_message)
        assert self.calculator.is_thank_you_message(message) is True
    
    def test_is_thank_you_message_false(self):
        """Test is_thank_you_message method for non-thank you messages."""
        message = self.create_message("Just a regular message")
        assert self.calculator.is_thank_you_message(message) is False
    
    def test_get_activity_summary_regular_message(self):
        """Test activity summary for regular messages."""
        message = self.create_message("Hello world!")
        summary = self.calculator.get_activity_summary(message)
        
        expected = {
            'has_message': True,
            'has_links': False,
            'is_thank_you': False,
            'sender_xp': 1,
            'thanked_users_xp': {},
            'links_found': [],
            'thanked_users': [],
            'mentioned_usernames': []
        }
        assert summary == expected
    
    def test_get_activity_summary_with_links(self):
        """Test activity summary for messages with links."""
        message = self.create_message("Check out https://example.com")
        summary = self.calculator.get_activity_summary(message)
        
        assert summary['has_message'] is True
        assert summary['has_links'] is True
        assert summary['is_thank_you'] is False
        assert summary['sender_xp'] == 4
        assert summary['thanked_users_xp'] == {}
        assert summary['links_found'] == ['https://example.com']
        assert summary['thanked_users'] == []
        assert summary['mentioned_usernames'] == []
    
    def test_get_activity_summary_with_thanks(self):
        """Test activity summary for thank you messages."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message("Thank you @john!", reply_to_message=reply_message)
        summary = self.calculator.get_activity_summary(message)
        
        assert summary['has_message'] is True
        assert summary['has_links'] is False
        assert summary['is_thank_you'] is True
        assert summary['sender_xp'] == 1
        assert summary['thanked_users_xp'] == {123: 5}
        assert summary['links_found'] == []
        assert summary['thanked_users'] == [123]
        assert summary['mentioned_usernames'] == ['john']
    
    def test_get_activity_summary_complex_message(self):
        """Test activity summary for complex messages with multiple activities."""
        reply_message = self.create_reply_message(replied_user_id=123)
        message = self.create_message(
            "Thanks @john! Check https://example.com and http://test.org", 
            reply_to_message=reply_message
        )
        summary = self.calculator.get_activity_summary(message)
        
        assert summary['has_message'] is True
        assert summary['has_links'] is True
        assert summary['is_thank_you'] is True
        assert summary['sender_xp'] == 4  # Base (1) + Links (3)
        assert summary['thanked_users_xp'] == {123: 5}
        assert len(summary['links_found']) == 2
        assert summary['thanked_users'] == [123]
        assert summary['mentioned_usernames'] == ['john']


if __name__ == '__main__':
    pytest.main([__file__])