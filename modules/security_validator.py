"""
Comprehensive security measures and input validation system.

This module provides security validation, input sanitization, rate limiting,
and abuse prevention mechanisms for the PsychoChauffeur bot.
"""

import re
import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from typing import (
    Dict, List, Optional, Any, Set, Tuple, Union, Callable, Pattern
)
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import ipaddress

from telegram import Update, User, Message
from telegram.ext import CallbackContext

from modules.types import UserId, ChatId, ValidationResult, JSONDict
from modules.shared_constants import (
    SecurityConstants, RegexPatterns, MAX_MESSAGE_LENGTH, 
    MAX_CAPTION_LENGTH, FileTypes
)
from modules.shared_utilities import (
    SingletonMeta, RateLimiter, HashGenerator, ValidationMixin
)
from modules.error_decorators import handle_validation_errors

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security validation levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    STRICT = "strict"


class ThreatType(Enum):
    """Types of security threats."""
    SPAM = "spam"
    MALICIOUS_URL = "malicious_url"
    INJECTION_ATTEMPT = "injection_attempt"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_FILE = "suspicious_file"
    INVALID_INPUT = "invalid_input"
    ABUSE_DETECTED = "abuse_detected"


@dataclass
class SecurityThreat:
    """Security threat information."""
    threat_type: ThreatType
    severity: str
    description: str
    user_id: Optional[UserId]
    chat_id: Optional[ChatId]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationRule:
    """Input validation rule."""
    name: str
    pattern: Optional[Pattern[str]]
    validator: Optional[Callable[[Any], ValidationResult]]
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    required: bool = True
    sanitize: bool = False


class InputSanitizer:
    """Input sanitization utilities."""
    
    # Dangerous patterns that should be blocked or sanitized
    DANGEROUS_PATTERNS = {
        'sql_injection': re.compile(
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)|'
            r'(--|#|/\*|\*/|;|\||&)',
            re.IGNORECASE
        ),
        'script_injection': re.compile(
            r'<script(?:\s[^>]*)?>.*?</script>|javascript:|vbscript:|onload\s*=|onerror\s*=',
            re.IGNORECASE | re.DOTALL
        ),
        'command_injection': re.compile(
            r'(\||&|;|`|\$\(|\${|<|>|\n|\r)',
            re.IGNORECASE
        ),
        'path_traversal': re.compile(
            r'(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)',
            re.IGNORECASE
        )
    }
    
    # HTML entities for sanitization
    HTML_ENTITIES = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;'
    }
    
    @classmethod
    def sanitize_text(cls, text: Any, strict: bool = False) -> str:
        """Sanitize text input to prevent injection attacks."""
        if not isinstance(text, str):
            return str(text)
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        if strict:
            # HTML entity encoding
            for char, entity in cls.HTML_ENTITIES.items():
                text = text.replace(char, entity)
            
            # Remove potentially dangerous characters
            text = re.sub(r'[<>"\'\x00-\x1f\x7f-\x9f]', '', text)
        
        return str(text)
    
    @classmethod
    def sanitize_filename(cls, filename: Any) -> str:
        """Sanitize filename for safe file system usage."""
        if not isinstance(filename, str):
            filename = str(filename)
        
        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > SecurityConstants.MAX_FILENAME_LENGTH:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = SecurityConstants.MAX_FILENAME_LENGTH - len(ext) - 1 if ext else SecurityConstants.MAX_FILENAME_LENGTH
            filename = name[:max_name_length] + ('.' + ext if ext else '')
        
        return filename or 'unnamed_file'
    
    @classmethod
    def sanitize_url(cls, url: Any) -> Optional[str]:
        """Sanitize and validate URL."""
        if not isinstance(url, str):
            return None
        
        url = url.strip()
        
        # Basic URL validation
        if not re.match(RegexPatterns.URL, url):
            return None
        
        try:
            parsed = urlparse(url)
            
            # Only allow http/https
            if parsed.scheme not in ('http', 'https'):
                return None
            
            # Block localhost and private IPs
            if parsed.hostname:
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if ip.is_private or ip.is_loopback:
                        return None
                except ValueError:
                    # Not an IP address, check for localhost
                    if parsed.hostname.lower() in ('localhost', '127.0.0.1', '::1'):
                        return None
            
            return str(url)
            
        except Exception:
            return None
    
    @classmethod
    def detect_threats(cls, text: str) -> List[ThreatType]:
        """Detect potential security threats in text."""
        threats = []
        
        for threat_name, pattern in cls.DANGEROUS_PATTERNS.items():
            if pattern.search(text):
                if threat_name == 'sql_injection':
                    threats.append(ThreatType.INJECTION_ATTEMPT)
                elif threat_name in ('script_injection', 'command_injection'):
                    threats.append(ThreatType.INJECTION_ATTEMPT)
                elif threat_name == 'path_traversal':
                    threats.append(ThreatType.SUSPICIOUS_FILE)
        
        return threats


class FileValidator:
    """File validation and security checking."""
    
    @classmethod
    def validate_file_type(cls, filename: str, allowed_types: Optional[Set[str]] = None) -> ValidationResult:
        """Validate file type based on extension."""
        if not filename:
            return False, "Empty filename"
        
        # Get file extension
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Check against dangerous extensions
        if f'.{ext}' in SecurityConstants.DANGEROUS_EXTENSIONS:
            return False, f"Dangerous file type: .{ext}"
        
        # Check against allowed types if specified
        if allowed_types and f'.{ext}' not in allowed_types:
            return False, f"File type not allowed: .{ext}"
        
        return True, None
    
    @classmethod
    def validate_file_size(cls, file_size: int, max_size_mb: int = 50) -> ValidationResult:
        """Validate file size."""
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            return False, f"File too large: {file_size / 1024 / 1024:.1f}MB (max: {max_size_mb}MB)"
        
        return True, None
    
    @classmethod
    def scan_file_content(cls, content: bytes, filename: str) -> List[ThreatType]:
        """Scan file content for potential threats."""
        threats = []
        
        # Check for executable signatures
        executable_signatures = [
            b'MZ',  # Windows PE
            b'\x7fELF',  # Linux ELF
            b'\xca\xfe\xba\xbe',  # Java class
            b'PK\x03\x04',  # ZIP (could contain executables)
        ]
        
        for sig in executable_signatures:
            if content.startswith(sig):
                threats.append(ThreatType.SUSPICIOUS_FILE)
                break
        
        # Check for script content in non-script files
        if not filename.endswith(('.py', '.js', '.sh', '.bat', '.ps1')):
            script_patterns = [
                b'<script',
                b'javascript:',
                b'eval(',
                b'exec(',
                b'system(',
                b'shell_exec'
            ]
            
            content_lower = content.lower()
            for pattern in script_patterns:
                if pattern in content_lower:
                    threats.append(ThreatType.INJECTION_ATTEMPT)
                    break
        
        return threats


class SecurityValidator(metaclass=SingletonMeta):
    """Main security validation system."""
    
    def __init__(self) -> None:
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.threat_log: List[SecurityThreat] = []
        self.blocked_users: Set[UserId] = set()
        self.blocked_ips: Set[str] = set()
        self.validation_rules: Dict[str, ValidationRule] = {}
        self.security_level = SecurityLevel.MEDIUM
        
        # Initialize rate limiters
        self._init_rate_limiters()
        
        # Initialize validation rules
        self._init_validation_rules()
    
    def _init_rate_limiters(self) -> None:
        """Initialize rate limiters for different operations."""
        for operation, (max_requests, window) in SecurityConstants.RATE_LIMITS.items():
            self.rate_limiters[operation] = RateLimiter(max_requests, window)
    
    def _init_validation_rules(self) -> None:
        """Initialize validation rules."""
        self.validation_rules = {
            'username': ValidationRule(
                name='username',
                pattern=re.compile(RegexPatterns.USERNAME),
                validator=None,
                max_length=SecurityConstants.MAX_USERNAME_LENGTH,
                min_length=3
            ),
            'message_text': ValidationRule(
                name='message_text',
                pattern=None,
                validator=self._validate_message_text,
                max_length=MAX_MESSAGE_LENGTH,
                sanitize=True
            ),
            'filename': ValidationRule(
                name='filename',
                pattern=re.compile(RegexPatterns.SAFE_FILENAME),
                max_length=SecurityConstants.MAX_FILENAME_LENGTH,
                validator=self._validate_filename,
                sanitize=True
            ),
            'url': ValidationRule(
                name='url',
                pattern=re.compile(RegexPatterns.URL),
                max_length=SecurityConstants.MAX_URL_LENGTH,
                validator=self._validate_url,
                sanitize=True
            )
        }
    
    def set_security_level(self, level: SecurityLevel) -> None:
        """Set security validation level."""
        self.security_level = level
        logger.info(f"Security level set to: {level.value}")
    
    def validate_input(self, input_type: str, value: Any) -> ValidationResult:
        """Validate input based on type and rules."""
        if input_type not in self.validation_rules:
            return False, f"Unknown input type: {input_type}"
        
        rule = self.validation_rules[input_type]
        
        # Check if required
        if rule.required and (value is None or value == ''):
            return False, f"{rule.name} is required"
        
        # Skip validation for empty optional values
        if not rule.required and (value is None or value == ''):
            return True, None
        
        # Convert to string for validation
        str_value = str(value) if value is not None else ''
        
        # Length validation
        if rule.max_length and len(str_value) > rule.max_length:
            return False, f"{rule.name} too long (max: {rule.max_length})"
        
        if rule.min_length and len(str_value) < rule.min_length:
            return False, f"{rule.name} too short (min: {rule.min_length})"
        
        # Pattern validation
        if rule.pattern and not rule.pattern.match(str_value):
            return False, f"Invalid {rule.name} format"
        
        # Custom validator
        if rule.validator:
            return rule.validator(value)
        
        return True, None
    
    def _validate_message_text(self, text: Any) -> ValidationResult:
        """Validate message text for security threats."""
        if not isinstance(text, str):
            return False, "Message text must be string"
        
        # Detect threats
        threats = InputSanitizer.detect_threats(text)
        if threats:
            return False, f"Security threat detected: {threats[0].value}"
        
        # Check for spam patterns (simple heuristics)
        if self._is_spam(text):
            return False, "Spam content detected"
        
        return True, None
    
    def _validate_filename(self, filename: Any) -> ValidationResult:
        """Validate filename for security."""
        if not isinstance(filename, str):
            return False, "Filename must be string"
        
        # Check file type
        return FileValidator.validate_file_type(filename)
    
    def _validate_url(self, url: Any) -> ValidationResult:
        """Validate URL for security."""
        if not isinstance(url, str):
            return False, "URL must be string"
        
        sanitized_url = InputSanitizer.sanitize_url(url)
        if not sanitized_url:
            return False, "Invalid or unsafe URL"
        
        return True, None
    
    def _is_spam(self, text: str) -> bool:
        """Simple spam detection heuristics."""
        text_lower = text.lower()
        
        # Check for excessive repetition
        words = text_lower.split()
        if len(words) > 5:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                return True
        
        # Check for excessive caps
        if len(text) > 20:
            caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
            if caps_ratio > 0.7:  # More than 70% caps
                return True
        
        # Check for spam keywords
        spam_keywords = [
            'buy now', 'click here', 'free money', 'get rich quick',
            'limited time', 'act now', 'guaranteed', 'no risk'
        ]
        
        for keyword in spam_keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def check_rate_limit(self, operation: str, user_id: UserId) -> bool:
        """Check if user is within rate limits for operation."""
        if operation not in self.rate_limiters:
            return True  # No limit defined
        
        key = f"{operation}:{user_id}"
        return self.rate_limiters[operation].is_allowed(key)
    
    def validate_telegram_update(self, update: Update) -> ValidationResult:
        """Validate incoming Telegram update for security."""
        try:
            # Check if user is blocked
            if update.effective_user and update.effective_user.id in self.blocked_users:
                return False, "User is blocked"
            
            # Validate message content
            if update.message and update.message.text:
                result = self.validate_input('message_text', update.message.text)
                if not result[0]:
                    self._log_threat(
                        ThreatType.INVALID_INPUT,
                        "high",
                        f"Invalid message content: {result[1]}",
                        update.effective_user.id if update.effective_user else None,
                        update.effective_chat.id if update.effective_chat else None
                    )
                    return result
            
            # Check rate limits
            if update.effective_user:
                user_id = update.effective_user.id
                
                # Check general rate limit
                if not self.check_rate_limit('default', user_id):
                    self._log_threat(
                        ThreatType.RATE_LIMIT_EXCEEDED,
                        "medium",
                        "Rate limit exceeded",
                        user_id,
                        update.effective_chat.id if update.effective_chat else None
                    )
                    return False, "Rate limit exceeded"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating update: {e}")
            return False, "Validation error"
    
    def validate_file_upload(
        self,
        filename: str,
        file_size: int,
        content: Optional[bytes] = None
    ) -> ValidationResult:
        """Validate file upload for security."""
        # Validate filename
        result = self.validate_input('filename', filename)
        if not result[0]:
            return result
        
        # Validate file type
        result = FileValidator.validate_file_type(filename)
        if not result[0]:
            return result
        
        # Validate file size
        result = FileValidator.validate_file_size(file_size)
        if not result[0]:
            return result
        
        # Scan content if provided
        if content:
            threats = FileValidator.scan_file_content(content, filename)
            if threats:
                return False, f"File contains threats: {[t.value for t in threats]}"
        
        return True, None
    
    def sanitize_input(self, input_type: str, value: Any) -> Any:
        """Sanitize input based on type."""
        if input_type not in self.validation_rules:
            return value
        
        rule = self.validation_rules[input_type]
        if not rule.sanitize:
            return value
        
        if input_type == 'message_text':
            return InputSanitizer.sanitize_text(str(value), strict=self.security_level == SecurityLevel.STRICT)
        elif input_type == 'filename':
            return InputSanitizer.sanitize_filename(str(value))
        elif input_type == 'url':
            return InputSanitizer.sanitize_url(str(value))
        
        return value
    
    def _log_threat(
        self,
        threat_type: ThreatType,
        severity: str,
        description: str,
        user_id: Optional[UserId] = None,
        chat_id: Optional[ChatId] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log security threat."""
        threat = SecurityThreat(
            threat_type=threat_type,
            severity=severity,
            description=description,
            user_id=user_id,
            chat_id=chat_id,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.threat_log.append(threat)
        
        # Keep only recent threats (last 1000)
        if len(self.threat_log) > 1000:
            self.threat_log = self.threat_log[-1000:]
        
        logger.warning(f"Security threat logged: {threat.description}")
    
    def block_user(self, user_id: UserId, reason: str) -> None:
        """Block user for security reasons."""
        self.blocked_users.add(user_id)
        self._log_threat(
            ThreatType.ABUSE_DETECTED,
            "high",
            f"User blocked: {reason}",
            user_id=user_id
        )
        logger.warning(f"User {user_id} blocked: {reason}")
    
    def unblock_user(self, user_id: UserId) -> None:
        """Unblock user."""
        self.blocked_users.discard(user_id)
        logger.info(f"User {user_id} unblocked")
    
    def get_security_report(self) -> Dict[str, Any]:
        """Get comprehensive security report."""
        recent_threats = [
            t for t in self.threat_log
            if (datetime.now() - t.timestamp).total_seconds() < 3600  # Last hour
        ]
        
        threat_counts: Dict[str, int] = {}
        for threat in recent_threats:
            threat_counts[threat.threat_type.value] = threat_counts.get(threat.threat_type.value, 0) + 1
        
        return {
            'security_level': self.security_level.value,
            'blocked_users_count': len(self.blocked_users),
            'blocked_ips_count': len(self.blocked_ips),
            'total_threats_logged': len(self.threat_log),
            'recent_threats_count': len(recent_threats),
            'threat_breakdown': threat_counts,
            'rate_limiter_stats': {
                name: {
                    'active_keys': len(limiter.requests),
                    'max_requests': limiter.max_requests,
                    'time_window': limiter.time_window
                }
                for name, limiter in self.rate_limiters.items()
            }
        }


# Decorators for security validation
def validate_input_security(input_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate input security."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            validator = SecurityValidator()
            
            # Try to find the input value in args/kwargs
            # This is a simplified approach - in practice, you'd specify which parameter to validate
            for arg in args:
                if isinstance(arg, (str, int)):
                    result = validator.validate_input(input_type, arg)
                    if not result[0]:
                        raise ValueError(f"Security validation failed: {result[1]}")
                    break
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_rate_limit(operation: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to enforce rate limiting."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            validator = SecurityValidator()
            
            # Try to extract user_id from Update object
            user_id = None
            for arg in args:
                if hasattr(arg, 'effective_user') and arg.effective_user:
                    user_id = arg.effective_user.id
                    break
            
            if user_id and not validator.check_rate_limit(operation, user_id):
                raise ValueError("Rate limit exceeded")
            
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            validator = SecurityValidator()
            
            # Try to extract user_id from Update object
            user_id = None
            for arg in args:
                if hasattr(arg, 'effective_user') and arg.effective_user:
                    user_id = arg.effective_user.id
                    break
            
            if user_id and not validator.check_rate_limit(operation, user_id):
                raise ValueError("Rate limit exceeded")
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global security validator instance
security_validator = SecurityValidator()