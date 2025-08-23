"""
XP Calculation Engine for the User Leveling System.

This module contains the core XP calculation logic, including activity detectors
for messages, links, and thank you expressions.
"""

import re
from typing import List, Dict, Optional, Set, Tuple
from telegram import Message, User
from modules.leveling_models import UserStats
import logging

logger = logging.getLogger(__name__)


class ActivityDetector:
    """Base class for activity detection."""
    
    def detect(self, message: Message) -> bool:
        """
        Detect if the message contains the specific activity.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            True if activity is detected
        """
        raise NotImplementedError
    
    def calculate_xp(self, message: Message) -> int:
        """
        Calculate XP for the detected activity.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            XP amount to award
        """
        raise NotImplementedError


class LinkDetector(ActivityDetector):
    """Detects link sharing activities."""
    
    # URL pattern to match http:// and https:// links
    URL_PATTERN = re.compile(r'https?://[^\s]+', re.IGNORECASE)
    
    def detect(self, message: Message) -> bool:
        """
        Detect if the message contains any links.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            True if message contains links
        """
        if not message.text:
            return False
        
        return bool(self.URL_PATTERN.search(message.text))
    
    def calculate_xp(self, message: Message) -> int:
        """
        Calculate XP for link sharing (3 XP per message with links).
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            3 XP if links are detected, 0 otherwise
        """
        return 3 if self.detect(message) else 0
    
    def extract_links(self, text: str) -> List[str]:
        """
        Extract all links from text.
        
        Args:
            text: Text to search for links
            
        Returns:
            List of found URLs
        """
        if not text:
            return []
        
        return self.URL_PATTERN.findall(text)


class ThankYouDetector(ActivityDetector):
    """Detects gratitude expressions with user mentions."""
    
    # Thank you keywords in multiple languages
    THANK_KEYWORDS = {
        # English
        'thanks', 'thank you', 'thx', 'ty', '10x',
        # Ukrainian
        'дякую', 'дяки', 'дякі', 'спасибі', 'спс', 'дяк',
        # Hebrew
        'תודה',
        # Additional variations
        'thank', 'спасибо', 'дякую тобі', 'дякую вам'
    }
    
    # Mention pattern to match @username
    MENTION_PATTERN = re.compile(r'@(\w+)', re.IGNORECASE)
    
    def __init__(self):
        """Initialize the detector with compiled patterns."""
        # Create a pattern that matches any of the thank keywords
        keywords_pattern = '|'.join(re.escape(keyword) for keyword in self.THANK_KEYWORDS)
        self.thank_pattern = re.compile(f'\\b({keywords_pattern})\\b', re.IGNORECASE)
    
    def detect(self, message: Message) -> bool:
        """
        Detect if the message is a thank you message.
        
        A thank you message must contain:
        1. Thank keywords AND
        2. Either user mentions (@username) OR be a reply to another message
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            True if message is a thank you message
        """
        if not message.text:
            return False
        
        # Check if message contains thank keywords
        has_thanks = bool(self.thank_pattern.search(message.text))
        if not has_thanks:
            return False
        
        # Check if message has mentions or is a reply
        has_mentions = bool(self.MENTION_PATTERN.search(message.text))
        is_reply = message.reply_to_message is not None
        
        return has_mentions or is_reply
    
    def calculate_xp(self, message: Message) -> int:
        """
        Calculate XP for thank you messages (5 XP per thanked user).
        
        Note: XP is awarded to the thanked users, not the sender.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            5 XP per thanked user if thank you is detected, 0 otherwise
        """
        if not self.detect(message):
            return 0
        
        thanked_users = self.get_thanked_users(message)
        return 5 * len(thanked_users)
    
    def get_thanked_users(self, message: Message) -> List[int]:
        """
        Get list of user IDs that are being thanked.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            List of user IDs being thanked
        """
        if not self.detect(message):
            return []
        
        thanked_users = []
        
        # If it's a reply, the replied-to user is being thanked
        if message.reply_to_message and message.reply_to_message.from_user:
            thanked_users.append(message.reply_to_message.from_user.id)
        
        # Extract mentioned usernames and try to resolve them
        # Note: Telegram doesn't provide user IDs for @username mentions directly
        # This would need to be resolved through a user database lookup
        # For now, we'll return the reply-to user if available
        
        return thanked_users
    
    def get_mentioned_usernames(self, text: str) -> List[str]:
        """
        Extract mentioned usernames from text.
        
        Args:
            text: Text to search for mentions
            
        Returns:
            List of mentioned usernames (without @)
        """
        if not text:
            return []
        
        return self.MENTION_PATTERN.findall(text)


class XPCalculator:
    """Main XP calculation engine."""
    
    def __init__(self):
        """Initialize the XP calculator with activity detectors."""
        self.link_detector = LinkDetector()
        self.thank_you_detector = ThankYouDetector()
        
        # XP rates as per requirements
        self.MESSAGE_XP = 1
        self.LINK_XP = 3
        self.THANKS_XP = 5
    
    def calculate_message_xp(self, message: Message) -> int:
        """
        Calculate XP for a regular message (1 XP per message).
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            1 XP for any message
        """
        return self.MESSAGE_XP
    
    def calculate_link_xp(self, message: Message) -> int:
        """
        Calculate XP for link sharing (3 XP if message contains links).
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            3 XP if message contains links, 0 otherwise
        """
        return self.link_detector.calculate_xp(message)
    
    def calculate_thanks_xp(self, message: Message) -> Dict[int, int]:
        """
        Calculate XP for thank you messages (5 XP per thanked user).
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            Dictionary mapping user_id to XP amount for thanked users
        """
        if not self.thank_you_detector.detect(message):
            return {}
        
        thanked_users = self.thank_you_detector.get_thanked_users(message)
        return {user_id: self.THANKS_XP for user_id in thanked_users}
    
    def calculate_total_message_xp(self, message: Message) -> Tuple[int, Dict[int, int]]:
        """
        Calculate total XP for a message including all activities.
        
        This calculates XP for the message sender and any thanked users.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            Tuple of (sender_xp, thanked_users_xp_dict)
        """
        if not message.from_user:
            return 0, {}
        
        sender_xp = 0
        thanked_users_xp = {}
        
        # Base message XP (always awarded to sender)
        sender_xp += self.calculate_message_xp(message)
        
        # Link sharing XP (awarded to sender if message contains links)
        link_xp = self.calculate_link_xp(message)
        if link_xp > 0:
            sender_xp += link_xp
        
        # Thank you XP (awarded to thanked users, not sender)
        thanked_users_xp = self.calculate_thanks_xp(message)
        
        return sender_xp, thanked_users_xp
    
    def detect_links(self, text: str) -> List[str]:
        """
        Detect and extract links from text.
        
        Args:
            text: Text to search for links
            
        Returns:
            List of found URLs
        """
        return self.link_detector.extract_links(text)
    
    def detect_thanks(self, message: Message) -> List[int]:
        """
        Detect thank you messages and return thanked user IDs.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            List of user IDs being thanked
        """
        return self.thank_you_detector.get_thanked_users(message)
    
    def has_links(self, message: Message) -> bool:
        """
        Check if message contains links.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            True if message contains links
        """
        return self.link_detector.detect(message)
    
    def is_thank_you_message(self, message: Message) -> bool:
        """
        Check if message is a thank you message.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            True if message is a thank you message
        """
        return self.thank_you_detector.detect(message)
    
    def get_activity_summary(self, message: Message) -> Dict[str, any]:
        """
        Get a summary of all detected activities in a message.
        
        Args:
            message: Telegram message to analyze
            
        Returns:
            Dictionary with activity detection results
        """
        sender_xp, thanked_users_xp = self.calculate_total_message_xp(message)
        
        return {
            'has_message': True,
            'has_links': self.has_links(message),
            'is_thank_you': self.is_thank_you_message(message),
            'sender_xp': sender_xp,
            'thanked_users_xp': thanked_users_xp,
            'links_found': self.detect_links(message.text or ''),
            'thanked_users': self.detect_thanks(message),
            'mentioned_usernames': self.thank_you_detector.get_mentioned_usernames(message.text or '')
        }