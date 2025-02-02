"""
Constants and configuration settings for the PsychoChauffeur bot.
"""

import os
from typing import Dict, Union, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Bot configuration and API keys."""
    OPENWEATHER_API_KEY: str = os.getenv('OPENWEATHER_API_KEY', '')
    DISCORD_WEBHOOK_URL: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
    ERROR_CHANNEL_ID: str = os.getenv('ERROR_CHANNEL_ID', '')
    
    # File paths
    SCREENSHOT_DIR: str = 'python-web-screenshots'

class Stickers:
    """Telegram sticker IDs."""
    ALIEXPRESS: str = 'CAACAgQAAxkBAAEuNplnAqatdmo-G7S_065k9AXXnqUn4QACwhQAAlKL8FNCof7bbA2jAjYE'

class LinkModification:
    """Domain modifications for various social media platforms."""
    DOMAINS: Dict[str, str] = {
        # "tiktok.com": "tfxktok.com",
        "twitter.com": "fxtwitter.com",
        "x.com": "fixupx.com",
        # "instagram.com": "ddinstagram.com"
        
    }

class VideoPlatforms:
    # Supported platforms
    SUPPORTED_PLATFORMS = [
        'tiktok.com', 'instagram.com', 'youtube.com', 
        'youtu.be', 'facebook.com', 
        'vimeo.com', 'reddit.com'
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

    # Weather condition ID ranges to emoji mappings
    CONDITION_EMOJIS: Dict[range, str] = {
        range(200, 300): '⛈',  # Thunderstorm
        range(300, 400): '🌧',  # Drizzle
        range(500, 600): '🌧',  # Rain
        range(600, 700): '❄️',  # Snow
        range(700, 800): '🌫',  # Atmosphere
        range(800, 801): '☀️',  # Clear
        range(801, 900): '☁️',  # Clouds
    }

    # Temperature ranges to emoji mappings
    FEELS_LIKE_EMOJIS: Dict[range, str] = {
        range(-100, 0):  '🥶',  # Very cold
        range(0, 10):    '🧥',  # Cold
        range(10, 20):   '🧣',  # Cool
        range(20, 30):   '😎',  # Comfortable
        range(30, 100):  '🥵',  # Very hot
    }

# For backwards compatibility
TOKEN = Config.TELEGRAM_BOT_TOKEN
OPENAI_API_KEY = Config.OPENAI_API_KEY
SCREENSHOT_DIR = Config.SCREENSHOT_DIR
ALIEXPRESS_STICKER_ID = Stickers.ALIEXPRESS
domain_modifications = LinkModification.DOMAINS
city_translations = Weather.CITY_TRANSLATIONS
weather_emojis = Weather.CONDITION_EMOJIS
feels_like_emojis = Weather.FEELS_LIKE_EMOJIS
platforms = VideoPlatforms.SUPPORTED_PLATFORMS

# File paths
DATA_DIR = 'data'
GAME_STATE_FILE = os.path.join(DATA_DIR, 'game_state.json')
USED_WORDS_FILE = os.path.join(DATA_DIR, 'used_words.csv')
