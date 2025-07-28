import re
from typing import Optional, Dict, Any, List
from telegram import Update
from telegram.ext import CallbackContext
from modules.logger import general_logger, error_logger
from config.config_manager import ConfigManager

class SafetyManager:
    def __init__(self) -> None:
        self.config_manager = ConfigManager()

    async def initialize(self) -> bool:
        """Initialize the safety manager."""
        # Initialize config manager if needed
        await self.config_manager.initialize()
        general_logger.info("Safety manager initialized successfully")
        return True

    async def stop(self) -> bool:
        """Clean up resources when stopping the safety manager."""
        general_logger.info("Safety manager stopped successfully")
        return True

    async def check_message_safety(self, update: Update, context: CallbackContext[Any, Any, Any, Any], message_text: str) -> bool:
        """
        Check if a message passes all safety checks.
        
        Args:
            update: Telegram update object
            context: Telegram callback context
            message_text: The message text to check
            
        Returns:
            bool: True if message passes all safety checks, False otherwise
        """
        try:
            chat_id = str(update.effective_chat.id) if update.effective_chat else None
            chat_type = 'private' if update.effective_chat and update.effective_chat.type == 'private' else 'group'
            
            # Get safety module configuration
            safety_config = await self.config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name="safety")
            if not safety_config.get("enabled", False):
                return True  # Safety checks are disabled
                
            overrides = safety_config.get("overrides", {})
            
            # Check content filter level
            content_filter_level = overrides.get("content_filter_level", "medium")
            if not self._check_content_filter(message_text, content_filter_level):
                if update.message:
                    await update.message.reply_text("⚠️ This message contains content that violates our content policy.")
                return False
                
            # Check profanity filter
            if overrides.get("profanity_filter_enabled", False):
                if self._check_profanity(message_text):
                    if update.message:
                        await update.message.reply_text("⚠️ This message contains inappropriate language.")
                    return False
                    
            # Check sensitive content warning
            if overrides.get("sensitive_content_warning_enabled", False):
                if self._check_sensitive_content(message_text):
                    if update.message:
                        await update.message.reply_text("⚠️ This message may contain sensitive content.")
                    return False
                    
            # Check restricted domains
            restricted_domains = overrides.get("restricted_domains", [])
            if restricted_domains and self._check_restricted_domains(message_text, restricted_domains):
                if update.message:
                    await update.message.reply_text("⚠️ This message contains links to restricted domains.")
                return False
                
            return True
            
        except Exception as e:
            error_logger.error(f"Error in safety check: {str(e)}")
            return True  # Allow message on error to prevent blocking legitimate messages
            
    def _check_content_filter(self, text: str, level: str) -> bool:
        """Check content against filter level."""
        if level == "low":
            return True  # No filtering
            
        # Medium level checks
        if level == "medium":
            # Check for common spam patterns
            spam_patterns = [
                r'(?i)buy\s+now',
                r'(?i)click\s+here',
                r'(?i)limited\s+time',
                r'(?i)act\s+now',
                r'(?i)exclusive\s+offer'
            ]
            return not any(re.search(pattern, text) for pattern in spam_patterns)
            
        # High level checks
        if level == "high":
            # Add more strict patterns
            strict_patterns = [
                r'(?i)earn\s+money',
                r'(?i)make\s+money',
                r'(?i)work\s+from\s+home',
                r'(?i)get\s+rich',
                r'(?i)investment\s+opportunity'
            ]
            return not any(re.search(pattern, text) for pattern in strict_patterns)
            
        return True
        
    def _check_profanity(self, text: str) -> bool:
        """Check for profanity in text."""
        # Add your profanity word list here
        profanity_words: List[str] = [
            # Add your list of profanity words
        ]
        return any(word.lower() in text.lower() for word in profanity_words)
        
    def _check_sensitive_content(self, text: str) -> bool:
        """Check for potentially sensitive content."""
        sensitive_patterns = [
            r'(?i)suicide',
            r'(?i)self\s*harm',
            r'(?i)kill\s*self',
            r'(?i)end\s*life'
        ]
        return any(re.search(pattern, text) for pattern in sensitive_patterns)
        
    def _check_restricted_domains(self, text: str, restricted_domains: List[str]) -> bool:
        """Check if text contains links to restricted domains."""
        url_pattern = r'http[s]?://(?:[a-zA-Z0-9]|[\$\-_@.&+]|[!*\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            for domain in restricted_domains:
                if domain in url:
                    return True
        return False
        
    async def check_file_safety(self, update: Update, context: CallbackContext[Any, Any, Any, Any], file_type: str) -> bool:
        """
        Check if a file type is allowed.
        
        Args:
            update: Telegram update object
            context: Telegram callback context
            file_type: MIME type of the file
            
        Returns:
            bool: True if file type is allowed, False otherwise
        """
        try:
            chat_id = str(update.effective_chat.id) if update.effective_chat else None
            chat_type = 'private' if update.effective_chat and update.effective_chat.type == 'private' else 'group'
            
            # Get safety module configuration
            safety_config = await self.config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name="safety")
            if not safety_config.get("enabled", False):
                return True  # Safety checks are disabled
                
            allowed_types = safety_config.get("overrides", {}).get("allowed_file_types", [])
            return file_type in allowed_types
            
        except Exception as e:
            error_logger.error(f"Error in file safety check: {str(e)}")
            return True  # Allow file on error to prevent blocking legitimate files

# Create a singleton instance
safety_manager = SafetyManager() 