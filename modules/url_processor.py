"""
URL processing module for handling URL-related operations.
"""

import re
from typing import List, Optional
from urllib.parse import urlparse, urlunparse
import pyshorteners
from collections import deque
import os
from datetime import datetime

from modules.logger import general_logger, error_logger
from modules.const import LinkModification
from modules.error_handler import handle_errors, ErrorHandler, ErrorCategory, ErrorSeverity

# URL shortener cache and rate limiter
_url_shortener_cache: dict[str, str] = {}
_shortener_calls: deque = deque()
_SHORTENER_MAX_CALLS_PER_MINUTE: int = int(os.getenv('SHORTENER_MAX_CALLS_PER_MINUTE', '30'))

def sanitize_url(url: str) -> str:
    """
    Sanitize and validate a URL.
    
    Args:
        url: The URL to sanitize
        
    Returns:
        str: Sanitized URL
        
    Raises:
        ValueError: If URL is invalid
    """
    try:
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Parse URL
        parsed = urlparse(url)
        
        # Validate domain
        if not parsed.netloc:
            raise ValueError("Invalid URL: No domain found")
            
        # Reconstruct URL
        sanitized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return sanitized
        
    except Exception as e:
        error_logger.error(f"URL sanitization failed: {str(e)}", exc_info=True)
        raise ValueError(f"Invalid URL: {str(e)}")

@handle_errors(feedback_message="An error occurred while shortening the URL.")
async def shorten_url(url: str) -> str:
    """
    Shorten a URL using the URL shortener service.
    
    Args:
        url: The URL to shorten
        
    Returns:
        str: Shortened URL
    """
    # Quick return for short URLs
    if len(url) <= 30:
        return url
        
    # Check cache
    if url in _url_shortener_cache:
        return _url_shortener_cache[url]
        
    # Check rate limit
    current_time = datetime.now()
    while _shortener_calls and (current_time - _shortener_calls[0]).total_seconds() > 60:
        _shortener_calls.popleft()
        
    if len(_shortener_calls) >= _SHORTENER_MAX_CALLS_PER_MINUTE:
        error_logger.warning("URL shortener rate limit reached")
        return url
        
    try:
        shortener = pyshorteners.Shortener()
        shortened = shortener.tinyurl.short(url)
        _url_shortener_cache[url] = shortened
        _shortener_calls.append(current_time)
        return shortened
        
    except Exception as e:
        error_logger.error(f"URL shortening failed: {str(e)}", exc_info=True)
        return url

def extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text.
    
    Args:
        text: Text to extract URLs from
        
    Returns:
        List[str]: List of found URLs
    """
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    return re.findall(url_pattern, text)

def is_modified_domain(url: str) -> bool:
    """
    Check if URL is from a modified domain.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if URL is from a modified domain
    """
    try:
        domain = urlparse(url).netloc
        return any(domain.endswith(d) for d in LinkModification.DOMAINS)
    except Exception:
        return False

def modify_url(url: str) -> Optional[str]:
    """
    Modify URL if needed.
    
    Args:
        url: URL to modify
        
    Returns:
        Optional[str]: Modified URL or None if no modification needed
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Check if domain needs modification
        for mod_domain in LinkModification.DOMAINS:
            if domain.endswith(mod_domain):
                # Apply modification based on domain
                if mod_domain == 'aliexpress.com':
                    return f"{url} #aliexpress"
                    
        return None
        
    except Exception as e:
        error_logger.error(f"URL modification failed: {str(e)}", exc_info=True)
        return None 