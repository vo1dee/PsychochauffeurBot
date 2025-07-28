"""
Shared constants and configuration definitions to reduce duplication.

This module centralizes all constants, configuration keys, and shared values
used across multiple modules in the application.
"""

from enum import Enum
from typing import Dict, List, Set, Tuple
import os

# Application constants
APP_NAME = "PsychoChauffeur Bot"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Advanced Telegram bot with AI integration and multimedia support"

# File and directory constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, 'downloads')
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config')
CACHE_DIR = os.path.join(PROJECT_ROOT, '.cache')

# Database constants
DEFAULT_DATABASE_URL = "sqlite:///bot.db"
DATABASE_POOL_SIZE = 10
DATABASE_TIMEOUT = 30
DATABASE_RETRY_ATTEMPTS = 3

# Network constants
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MAX_CONCURRENT_REQUESTS = 10
USER_AGENT = "PsychoChauffeur-Bot/2.0.0"

# Message limits (Telegram API)
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
MAX_INLINE_KEYBOARD_BUTTONS = 100
MAX_FILE_SIZE_MB = 50

# Rate limiting constants
DEFAULT_RATE_LIMIT_REQUESTS = 30
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
ADMIN_RATE_LIMIT_REQUESTS = 100
ADMIN_RATE_LIMIT_WINDOW = 60

# Cache constants
DEFAULT_CACHE_TTL = 300  # 5 minutes
LONG_CACHE_TTL = 3600   # 1 hour
SHORT_CACHE_TTL = 60    # 1 minute
MAX_CACHE_SIZE = 1000

# Error handling constants
MAX_ERROR_MESSAGE_LENGTH = 200
ERROR_RETRY_ATTEMPTS = 3
ERROR_RETRY_DELAY = 2.0
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 60

# Logging constants
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Configuration keys
class ConfigKeys:
    """Configuration key constants."""
    
    # Bot configuration
    BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
    BOT_USERNAME = "bot_username"
    BOT_DESCRIPTION = "bot_description"
    
    # API keys
    OPENAI_API_KEY = "OPENAI_API_KEY"
    OPENROUTER_API_KEY = "OPENROUTER_API_KEY"
    OPENWEATHER_API_KEY = "OPENWEATHER_API_KEY"
    SPEECHMATICS_API_KEY = "SPEECHMATICS_API_KEY"
    
    # Service URLs
    OPENROUTER_BASE_URL = "OPENROUTER_BASE_URL"
    WEATHER_API_URL = "WEATHER_API_URL"
    DISCORD_WEBHOOK_URL = "DISCORD_WEBHOOK_URL"
    
    # Feature flags
    ENABLE_AI_RESPONSES = "enable_ai_responses"
    ENABLE_VIDEO_DOWNLOAD = "enable_video_download"
    ENABLE_WEATHER = "enable_weather"
    ENABLE_SPEECH_RECOGNITION = "enable_speech_recognition"
    ENABLE_RANDOM_RESPONSES = "enable_random_responses"
    
    # Limits and thresholds
    MAX_MESSAGE_HISTORY = "max_message_history"
    AI_RESPONSE_PROBABILITY = "ai_response_probability"
    MESSAGE_THRESHOLD = "message_threshold"
    MIN_WORDS_FOR_RESPONSE = "min_words_for_response"

# Default configuration values
DEFAULT_CONFIG = {
    ConfigKeys.BOT_USERNAME: "psychochauffeur_bot",
    ConfigKeys.BOT_DESCRIPTION: "Advanced Telegram bot",
    ConfigKeys.ENABLE_AI_RESPONSES: True,
    ConfigKeys.ENABLE_VIDEO_DOWNLOAD: True,
    ConfigKeys.ENABLE_WEATHER: True,
    ConfigKeys.ENABLE_SPEECH_RECOGNITION: True,
    ConfigKeys.ENABLE_RANDOM_RESPONSES: False,
    ConfigKeys.MAX_MESSAGE_HISTORY: 50,
    ConfigKeys.AI_RESPONSE_PROBABILITY: 0.02,
    ConfigKeys.MESSAGE_THRESHOLD: 50,
    ConfigKeys.MIN_WORDS_FOR_RESPONSE: 5,
}

# Command constants
class Commands:
    """Bot command constants."""
    
    # Basic commands
    START = "start"
    HELP = "help"
    SETTINGS = "settings"
    STATUS = "status"
    
    # AI commands
    GPT = "gpt"
    ANALYZE = "analyze"
    SUMMARIZE = "summarize"
    
    # Utility commands
    WEATHER = "weather"
    SCREENSHOT = "screenshot"
    CAT = "cat"
    TRANSLATE = "translate"
    
    # Admin commands
    ADMIN = "admin"
    CONFIG = "config"
    LOGS = "logs"
    STATS = "stats"
    RESTART = "restart"

# Sticker constants
class StickerIds:
    """Telegram sticker ID constants."""
    
    # General stickers
    LOCATION = 'CAACAgQAAxkBAAE3R61oaOg4WXbVWO3aeHPbKFcvKR8JRAACMhsAAl0KGFDROvkaE3ex5jYE'
    ALIEXPRESS = 'CAACAgQAAxkBAAEuNplnAqatdmo-G7S_065k9AXXnqUn4QACwhQAAlKL8FNCof7bbA2jAjYE'
    
    # Error stickers
    ERROR_GENERAL = "CAACAgQAAxkBAAExX39nn7xI2ENP9ev7Ib1-0GCV0TcFvwACNxUAAn_QmFB67ToFiTpdgTYE"
    ERROR_NETWORK = "CAACAgQAAxkBAAExYABnn7xJmVXzAAGOAAH-UqFN8KWOvJsAAjgVAAJ_0JhQeu06BYk6XYE2BA"
    ERROR_API = "CAACAgQAAxkBAAExYAFnn7xJwQABuQABjgAB_lKhTfCljryaAAI5FQACF9CYUHrtOgWJOl2BNgQ"
    
    # Restriction stickers
    RESTRICTION_STICKERS = [
        "CAACAgQAAxkBAAEt8tNm9Wc6jYEQdAgQzvC917u3e8EKPgAC9hQAAtMUCVP4rJSNEWepBzYE",
        "CAACAgIAAxkBAAEyoUxn0vCR2hi81ZEkZTuffMFmG9AexQACrBgAAk_x0Es_t_KsbxvdnTYE",
        "CAACAgIAAxkBAAEyoTBn0vAKKx5B8fDNzKVD1WDD3A4SzgACJSsAArOEUEpDLeMUdNLVODYE",
        "CAACAgIAAxkBAAEy4j9n3TOZf_YFKs9TdUCb9d3sNvVwbwAC32YAAvgziEr0xAPmmKNIFDYE"
    ]

# URL patterns and domains
class URLPatterns:
    """URL pattern constants."""
    
    # Social media domain modifications
    DOMAIN_REPLACEMENTS = {
        "twitter.com": "fxtwitter.com",
        "x.com": "fixupx.com",
        "instagram.com": "ddinstagram.com",
        "aliexpress.com": "aliexpress.com"  # Keep as is for tracking
    }
    
    # Supported video platforms
    VIDEO_PLATFORMS = [
        'tiktok.com', 'vm.tiktok.com', 'youtube.com/shorts',
        'youtu.be/shorts', 'vimeo.com', 'reddit.com', 
        'twitch.tv', 'youtube.com/clip', 'pinterest.com', 'pin.it'
    ]
    
    # URL regex patterns
    URL_PATTERN = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    DOMAIN_PATTERN = r'(?:https?://)?(?:www\.)?([^/]+)'

# Weather constants
class WeatherConstants:
    """Weather-related constants."""
    
    # API endpoints
    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
    WEATHER_WIDGET_URL = "https://api.meteoagent.com/widgets/v1/kindex"
    
    # City translations
    CITY_TRANSLATIONS = {
        "кортгене": "Kortgene",
        "тель авів": "Tel Aviv",
        "тельавів": "Tel Aviv",
        "Тель Авів": "Tel Aviv",
        "київ": "Kyiv",
        "киев": "Kyiv"
    }
    
    # Weather condition emojis
    CONDITION_EMOJIS = {
        range(200, 300): '⛈',  # Thunderstorm
        range(300, 400): '🌧',  # Drizzle
        range(500, 600): '🌧',  # Rain
        range(600, 700): '❄️',  # Snow
        range(700, 800): '🌫',  # Atmosphere
        range(800, 801): '☀️',  # Clear
        range(801, 900): '☁️',  # Clouds
    }
    
    # Temperature feeling emojis
    FEELS_LIKE_EMOJIS = {
        range(-100, 0): '🥶',   # Very cold
        range(0, 10): '🧥',     # Cold
        range(10, 20): '🧣',    # Cool
        range(20, 30): '😎',    # Comfortable
        range(30, 100): '🥵',   # Very hot
    }
    
    # Humidity emojis
    HUMIDITY_EMOJIS = {
        range(0, 40): '🌵',     # Dry
        range(40, 70): '😊',    # Comfortable
        range(70, 101): '💧',   # Humid
    }

# AI model constants
class AIModels:
    """AI model configuration constants."""
    
    # OpenRouter models
    GPT_3_5_TURBO = "openai/gpt-3.5-turbo"
    GPT_4 = "openai/gpt-4"
    GPT_4_TURBO = "openai/gpt-4-turbo"
    CLAUDE_3_HAIKU = "anthropic/claude-3-haiku"
    CLAUDE_3_SONNET = "anthropic/claude-3-sonnet"
    
    # Model parameters
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_TOP_P = 1.0
    
    # Response types
    RESPONSE_TYPES = ["direct", "random", "contextual", "analysis"]

# File type constants
class FileTypes:
    """File type and MIME type constants."""
    
    # Image types
    IMAGE_TYPES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'}
    
    # Video types
    VIDEO_TYPES = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
    VIDEO_MIMES = {'video/mp4', 'video/avi', 'video/x-msvideo', 'video/quicktime'}
    
    # Audio types
    AUDIO_TYPES = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac'}
    AUDIO_MIMES = {'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4', 'audio/flac'}
    
    # Document types
    DOCUMENT_TYPES = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}
    DOCUMENT_MIMES = {
        'application/pdf', 'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'application/rtf'
    }

# Security constants
class SecurityConstants:
    """Security-related constants."""
    
    # Input validation
    MAX_USERNAME_LENGTH = 32
    MAX_FILENAME_LENGTH = 255
    MAX_URL_LENGTH = 2048
    
    # Allowed characters
    SAFE_FILENAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    
    # Dangerous file extensions
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', 
        '.jar', '.sh', '.ps1', '.msi', '.deb', '.rpm'
    }
    
    # Rate limiting
    RATE_LIMITS = {
        'default': (30, 60),      # 30 requests per minute
        'admin': (100, 60),       # 100 requests per minute
        'download': (5, 300),     # 5 downloads per 5 minutes
        'ai_request': (10, 60),   # 10 AI requests per minute
    }

# Performance constants
class PerformanceConstants:
    """Performance monitoring constants."""
    
    # Thresholds
    SLOW_QUERY_THRESHOLD = 1.0      # seconds
    SLOW_REQUEST_THRESHOLD = 5.0    # seconds
    HIGH_MEMORY_THRESHOLD = 500     # MB
    
    # Monitoring intervals
    HEALTH_CHECK_INTERVAL = 30      # seconds
    METRICS_COLLECTION_INTERVAL = 60 # seconds
    CLEANUP_INTERVAL = 3600         # seconds (1 hour)
    
    # Limits
    MAX_CONCURRENT_OPERATIONS = 10
    MAX_QUEUE_SIZE = 100
    MAX_RETRY_ATTEMPTS = 3

# Regex patterns
class RegexPatterns:
    """Common regex patterns."""
    
    # URL patterns
    URL = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    DOMAIN = r'(?:https?://)?(?:www\.)?([^/\s]+)'
    
    # Text patterns
    EMAIL = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE = r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
    
    # Validation patterns
    USERNAME = r'^[a-zA-Z0-9_]{3,32}$'
    SAFE_FILENAME = r'^[a-zA-Z0-9._-]+$'
    
    # Command patterns
    COMMAND = r'^/([a-zA-Z0-9_]+)(?:\s+(.*))?$'
    MENTION = r'@([a-zA-Z0-9_]+)'

# Error messages
class ErrorMessages:
    """Standard error message constants."""
    
    # Generic errors
    UNKNOWN_ERROR = "An unexpected error occurred. Please try again."
    INVALID_INPUT = "Invalid input provided. Please check your data."
    PERMISSION_DENIED = "You don't have permission to perform this action."
    RATE_LIMITED = "Too many requests. Please wait before trying again."
    
    # Network errors
    NETWORK_ERROR = "Network connection error. Please try again later."
    TIMEOUT_ERROR = "Request timed out. Please try again."
    SERVICE_UNAVAILABLE = "Service is temporarily unavailable."
    
    # File errors
    FILE_NOT_FOUND = "File not found or inaccessible."
    FILE_TOO_LARGE = "File is too large to process."
    INVALID_FILE_TYPE = "Invalid file type."
    
    # AI errors
    AI_SERVICE_ERROR = "AI service is temporarily unavailable."
    AI_QUOTA_EXCEEDED = "AI service quota exceeded."
    AI_INVALID_REQUEST = "Invalid AI request format."

# Success messages
class SuccessMessages:
    """Standard success message constants."""
    
    OPERATION_COMPLETED = "Operation completed successfully."
    FILE_UPLOADED = "File uploaded successfully."
    SETTINGS_SAVED = "Settings saved successfully."
    COMMAND_EXECUTED = "Command executed successfully."

# Feature flags
class FeatureFlags:
    """Feature flag constants."""
    
    ENABLE_CACHING = True
    ENABLE_METRICS = True
    ENABLE_RATE_LIMITING = True
    ENABLE_CIRCUIT_BREAKER = True
    ENABLE_RETRY_LOGIC = True
    ENABLE_PERFORMANCE_MONITORING = True
    ENABLE_SECURITY_VALIDATION = True
    ENABLE_ERROR_ANALYTICS = True

# Environment-specific constants
class Environment:
    """Environment-specific constants."""
    
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    
    # Current environment (should be set via environment variable)
    CURRENT = os.getenv('ENVIRONMENT', DEVELOPMENT)
    
    # Debug mode
    DEBUG = CURRENT in [DEVELOPMENT, TESTING]
    
    # Logging levels by environment
    LOG_LEVELS = {
        DEVELOPMENT: "DEBUG",
        TESTING: "INFO",
        STAGING: "WARNING",
        PRODUCTION: "ERROR"
    }

# Module names for configuration
class ModuleNames:
    """Module name constants for configuration."""
    
    AI_PROCESSING = "ai_processing"
    VIDEO_DOWNLOADER = "video_downloader"
    WEATHER = "weather"
    SPEECH_RECOGNITION = "speechmatics"
    CHAT_BEHAVIOR = "chat_behavior"
    USER_MANAGEMENT = "user_management"
    LOGGING = "logging"
    PERFORMANCE = "performance"
    UI_MESSAGES = "ui_messages"

# Export commonly used constants
__all__ = [
    'APP_NAME', 'APP_VERSION', 'PROJECT_ROOT', 'DATA_DIR', 'LOG_DIR',
    'ConfigKeys', 'DEFAULT_CONFIG', 'Commands', 'StickerIds', 'URLPatterns',
    'WeatherConstants', 'AIModels', 'FileTypes', 'SecurityConstants',
    'PerformanceConstants', 'RegexPatterns', 'ErrorMessages', 'SuccessMessages',
    'FeatureFlags', 'Environment', 'ModuleNames'
]