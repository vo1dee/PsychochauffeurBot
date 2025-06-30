"""
Constants and configuration settings for the PsychoChauffeur bot.
"""
import os
from typing import Dict
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Base directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, 'downloads')

# Define timezone constant
KYIV_TZ = pytz.timezone('Europe/Kyiv')

class Config:
    """Bot configuration and API keys."""
    OPENWEATHER_API_KEY: str = os.getenv('OPENWEATHER_API_KEY', '')
    DISCORD_WEBHOOK_URL: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_BASE_URL: str = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    ERROR_CHANNEL_ID: str = os.getenv('ERROR_CHANNEL_ID', '')
    SCREENSHOT_DIR: str = 'python-web-screenshots'

class Stickers:
    """Telegram sticker IDs."""
    ALIEXPRESS: str = 'CAACAgQAAxkBAAEuNplnAqatdmo-G7S_065k9AXXnqUn4QACwhQAAlKL8FNCof7bbA2jAjYE'
    RESTRICTION_STICKERS = [
        "CAACAgQAAxkBAAEt8tNm9Wc6jYEQdAgQzvC917u3e8EKPgAC9hQAAtMUCVP4rJSNEWepBzYE",
        "CAACAgIAAxkBAAEyoUxn0vCR2hi81ZEkZTuffMFmG9AexQACrBgAAk_x0Es_t_KsbxvdnTYE",
        "CAACAgIAAxkBAAEyoTBn0vAKKx5B8fDNzKVD1WDD3A4SzgACJSsAArOEUEpDLeMUdNLVODYE",
        "CAACAgIAAxkBAAEy4j9n3TOZf_YFKs9TdUCb9d3sNvVwbwAC32YAAvgziEr0xAPmmKNIFDYE"
    ]

class LinkModification:
    """Domain modifications for various social media platforms."""
    DOMAINS: Dict[str, str] = {
        "twitter.com": "fxtwitter.com",
        "x.com": "fixupx.com",
        "aliexpress.com": "aliexpress.com",
        "instagram.com": "ddinstagram.com"
    }

class VideoPlatforms:
    """Supported video platforms."""
    SUPPORTED_PLATFORMS = [
        'tiktok.com', 'vm.tiktok.com', 'youtube.com/shorts',
        'youtu.be/shorts',
        'vimeo.com', 'reddit.com', 'twitch.tv', 'youtube.com/clip',
        'pinterest.com', 'pin.it'
    ]

class Weather:
    """Weather-related configurations and mappings."""
    # City name translations (Ukrainian -> English)
    CITY_TRANSLATIONS: Dict[str, str] = {
        "кортгене": "Kortgene",
        "тель авів": "Tel Aviv",
        "тельавів": "Tel Aviv",
        "Тель Авів": "Tel Aviv",
    }
    
    CONDITION_EMOJIS: Dict[range, str] = {
        range(200, 300): '⛈',  # Thunderstorm
        range(300, 400): '🌧',  # Drizzle
        range(500, 600): '🌧',  # Rain
        range(600, 700): '❄️',  # Snow
        range(700, 800): '🌫',  # Atmosphere
        range(800, 801): '☀️',  # Clear
        range(801, 900): '☁️',  # Clouds
    }
    
    FEELS_LIKE_EMOJIS: Dict[range, str] = {
        range(-100, 0): '🥶',  # Very cold
        range(0, 10): '🧥',    # Cold
        range(10, 20): '🧣',   # Cool
        range(20, 30): '😎',   # Comfortable
        range(30, 100): '🥵',  # Very hot
    }

    HUMIDITY_EMOJIS: Dict[range, str] = {
        range(0, 40): '🌵',    # Dry
        range(40, 70): '😊',   # Comfortable
        range(70, 101): '💧',  # Humid
    }

class GPT:
    """GPT model configurations."""
    # GPT model parameters