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

# Meta platform domains
META_PLATFORMS = [
    'instagram.com',
    'facebook.com',
    'threads.net'
]

def is_meta_platform(url: str) -> bool:
    """
    Check if URL is from a Meta platform (Instagram, Facebook, or Threads).
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if URL is from a Meta platform
    """
    try:
        domain = urlparse(url).netloc.lower()
        return any(platform in domain for platform in META_PLATFORMS)
    except Exception:
        return False

def sanitize_url(url: str) -> str:
    """
    Sanitize and validate a URL.
    
    Args:
        url: The URL to sanitize
        
    Returns:
        str: Sanitized URL or empty string if invalid
        
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
            return ""
            
        # Check for invalid characters in domain
        if '_' in parsed.netloc:
            return ""
            
        # Check for IP addresses
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', parsed.netloc):
            return ""
            
        # Check for credentials in URL
        if '@' in parsed.netloc:
            return ""
            
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
        return ""

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
    # Robust URL pattern that handles:
    # - URLs with or without www
    # - URLs with special characters in path
    # - URLs with query parameters
    # - URLs with fragments
    # - URLs with international characters
    # - URLs with subdomains
    # - URLs with ports
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[^\s]*)?'
    urls = re.findall(url_pattern, text)
    general_logger.info(f"Extracted URLs from text: {urls}")
    return urls

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
        domain = parsed.netloc.lower()
        general_logger.info(f"Processing URL: {url}, domain: {domain}")
        
        # Special case for x.com/twitter.com
        if domain in ['x.com', 'twitter.com']:
            modified = url.replace(domain, 'fixupx.com')
            general_logger.info(f"Modified x.com/twitter.com URL: {modified}")
            return modified
        
        # Check if domain needs modification
        for original_domain, modified_domain in LinkModification.DOMAINS.items():
            # Handle both exact matches and subdomains
            if domain == original_domain or domain.endswith('.' + original_domain):
                # Replace the domain while preserving the rest of the URL
                modified_url = url.replace(domain, modified_domain)
                # Special case for AliExpress
                if original_domain == 'aliexpress.com':
                    modified_url = f"{modified_url} #aliexpress"
                general_logger.info(f"Modified URL: {modified_url}")
                return modified_url
                    
        general_logger.info(f"No modification needed for URL: {url}")
        return None
        
    except Exception as e:
        error_logger.error(f"URL modification failed: {str(e)}", exc_info=True)
        return None 