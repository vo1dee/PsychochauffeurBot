import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants and Configuration
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SCREENSHOT_DIR = 'python-web-screenshots'

# Load the OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Define the sticker file ID
ALIEXPRESS_STICKER_ID = 'CAACAgQAAxkBAAEuNplnAqatdmo-G7S_065k9AXXnqUn4QACwhQAAlKL8FNCof7bbA2jAjYE'

# Dictionary to map Ukrainian city names to English names (used by OpenWeatherMap)
city_translations = {
    "кортгене": "Kortgene",
    "Тель Авів": "Tel Aviv",
    "тель авів": "Tel Aviv",
    "тельавів": "Tel Aviv",
    # Add other base translations as needed
}

domain_modifications = {
    "tiktok.com": "tfxktok.com",
    "twitter.com": "fxtwitter.com",
    "x.com": "fixupx.com",
    "instagram.com": "ddinstagram.com"
    
}

weather_emojis = {
    range(200, 300): '⛈',  # Thunderstorm
    range(300, 400): '🌧',  # Drizzle
    range(500, 600): '🌧',  # Rain
    range(600, 700): '❄️',  # Snow
    range(700, 800): '🌫',  # Atmosphere
    range(800, 800): '☀️',  # Clear
    range(801, 900): '☁️',  # Clouds
}

feels_like_emojis = {
    range(-100, 0): '🥶',  # Дуже холодно
    range(0, 10):   '🧥',    # Холодно
    range(10, 20):  '🧣',   # Прохолодно
    range(20, 30):  '😎',   # Комфортно, тепло
    range(30, 100): '🥵',  # Дуже спекотно
}
