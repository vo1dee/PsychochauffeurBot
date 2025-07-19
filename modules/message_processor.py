"""
Message processing module for handling message-related operations.
"""

from typing import Dict, Optional, Tuple
from telegram import Update
from telegram.ext import CallbackContext

from modules.logger import general_logger, error_logger
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity
from modules.const import VideoPlatforms, LinkModification
from modules.url_processor import extract_urls, modify_url, is_modified_domain

# Global message history
last_user_messages: Dict[int, Dict[str, str]] = {}

def needs_gpt_response(update: Update, context: CallbackContext, message_text: str) -> Tuple[bool, str]:
    """
    Determine if a message needs a GPT response and what type of response it needs.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        message_text: The message text to analyze
        
    Returns:
        tuple[bool, str]: (needs_response, response_type)
            - needs_response: Whether the message needs a GPT response
            - response_type: Type of response needed ('command', 'mention', 'private', 'random')
    """
    # If the message contains any URL, do NOT trigger GPT response
    from modules.url_processor import extract_urls
    if extract_urls(message_text):
        return False, ''

    bot_username = context.bot.username
    is_private_chat = update.effective_chat.type == 'private'
    mentioned = f"@{bot_username}" in message_text
    contains_video_platform = any(platform in message_text.lower() for platform in VideoPlatforms.SUPPORTED_PLATFORMS)
    contains_modified_domain = any(domain in message_text for domain in LinkModification.DOMAINS)
    
    # Log the detection details
    general_logger.info(
        f"GPT response check: bot_username={bot_username}, mentioned={mentioned}, is_private={is_private_chat}",
        extra={
            'chat_id': update.effective_chat.id,
            'chattitle': update.effective_chat.title or f"Private_{update.effective_chat.id}",
            'username': update.effective_user.username or f"ID:{update.effective_user.id}"
        }
    )
    
    # Check if bot is mentioned
    if mentioned:
        # Extract the message parts before and after the mention
        parts = message_text.split(f"@{bot_username}", 1)
        # Trigger if there is text before the mention, or after the mention.
        if parts[0].strip() or (len(parts) > 1 and parts[1].strip()):
            return True, 'mention'
    
    # Check if it's a private chat message that needs private response
    if is_private_chat and not (contains_video_platform or contains_modified_domain):
        return True, 'private'
    
    return False, ''

def update_message_history(user_id: int, message_text: str) -> None:
    """
    Update the message history for a user.
    
    Args:
        user_id: User ID
        message_text: Message text
    """
    if user_id not in last_user_messages:
        last_user_messages[user_id] = {}
    
    # Move current message to previous
    if 'current' in last_user_messages[user_id]:
        last_user_messages[user_id]['previous'] = last_user_messages[user_id]['current']
    
    # Update current message
    last_user_messages[user_id]['current'] = message_text

def get_previous_message(user_id: int) -> Optional[str]:
    """
    Get the previous message for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        Optional[str]: Previous message or None if not found
    """
    return last_user_messages.get(user_id, {}).get('previous')

def process_message_content(message_text: str) -> Tuple[str, list[str]]:
    """
    Process message content to extract and modify URLs.
    
    Args:
        message_text: Message text to process
        
    Returns:
        Tuple[str, list[str]]: (cleaned_text, modified_links)
    """
    urls = extract_urls(message_text)
    modified_links = []
    cleaned_text = message_text
    
    for url in urls:
        modified_url = modify_url(url)
        if modified_url:
            modified_links.append(modified_url)
            cleaned_text = cleaned_text.replace(url, modified_url)
    
    return cleaned_text, modified_links

def should_restrict_user(message_text: str) -> bool:
    """
    Check if a user should be restricted based on message content.
    
    Args:
        message_text: Message text to check
        
    Returns:
        bool: True if user should be restricted
    """
    # Check for prohibited characters
    prohibited_chars = {'Ы', 'ы', 'Ъ', 'ъ', 'Э', 'э', 'Ё', 'ё'}
    return any(char in message_text for char in prohibited_chars) 