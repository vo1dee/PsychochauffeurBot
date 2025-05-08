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
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENWEATHER_API_KEY: str = os.getenv('OPENWEATHER_API_KEY', '')
    DISCORD_WEBHOOK_URL: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
    ERROR_CHANNEL_ID: str = os.getenv('ERROR_CHANNEL_ID', '')
    SCREENSHOT_DIR: str = 'python-web-screenshots'

class Stickers:
    """Telegram sticker IDs."""
    ALIEXPRESS: str = 'CAACAgQAAxkBAAEz68ZoA3ZmvEtE8gkXYQUf9T4FToQcggAC9BwAAlW6GVDc_WkMgxhxJzYE'

class LinkModification:
    """Domain modifications for various social media platforms."""
    DOMAINS: Dict[str, str] = {
        "twitter.com": "fxtwitter.com",
        "x.com": "fixupx.com",
        "instagram.com": "ddinstagram.com"
    }

class VideoPlatforms:
    """Supported video platforms."""
    SUPPORTED_PLATFORMS = [
        'tiktok.com', 'instagram.com/reels', 'youtube.com/shorts',
        'youtu.be/shorts', 'facebook.com',
        'vimeo.com', 'reddit.com', 'twitch.tv', 'youtube.com/clip'
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
    
    CONDITION_EMOJIS = {
        range(200, 300): "⛈",
        range(300, 400): "🌧",
        range(500, 600): "🌧",
        range(600, 700): "❄️",
        range(700, 800): "🌫",
        range(800, 801): "☀️",
        range(801, 900): "☁️",
    }
    
    FEELS_LIKE_EMOJIS = {
        range(-100, 0): "🥶",
        range(0, 10): "🧥",
        range(10, 20): "🧣",
        range(20, 30): "😎",
        range(30, 100): "🥵",
    }

# Files (deprecated: game and word‑game features removed)
# GAME_STATE_FILE and USED_WORDS_FILE no longer used

# For backwards compatibility
TOKEN = Config.TELEGRAM_BOT_TOKEN
OPENAI_API_KEY = Config.OPENAI_API_KEY
SCREENSHOT_DIR = Config.SCREENSHOT_DIR
OPENROUTER_BASE_URL = Config.OPENROUTER_BASE_URL
ALIEXPRESS_STICKER_ID = Stickers.ALIEXPRESS
domain_modifications = LinkModification.DOMAINS
city_translations = Weather.CITY_TRANSLATIONS
weather_emojis = Weather.CONDITION_EMOJIS
feels_like_emojis = Weather.FEELS_LIKE_EMOJIS
platforms = VideoPlatforms.SUPPORTED_PLATFORMS
