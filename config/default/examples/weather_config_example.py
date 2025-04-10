"""Example weather configuration file.

Copy to config/default/weather_config.py and customize as needed.
"""

from range import range

WEATHER_CONFIG = {
    # Maps normalized city names to their official English names
    "CITY_TRANSLATIONS": {
        "київ": "Kyiv",
        "киев": "Kyiv",
        "львів": "Lviv",
        "львов": "Lviv",
        "одеса": "Odesa",
        "одесса": "Odesa",
        "харків": "Kharkiv",
        "харьков": "Kharkiv",
        "дніпро": "Dnipro",
        "днепр": "Dnipro",
        "запоріжжя": "Zaporizhzhia",
        "запорожье": "Zaporizhzhia",
    },
    
    # Weather condition ID ranges mapped to appropriate emojis
    "CONDITION_EMOJIS": {
        range(200, 300): "⛈",  # Thunderstorm
        range(300, 400): "🌧",  # Drizzle
        range(500, 600): "🌧",  # Rain
        range(600, 700): "❄️",  # Snow
        range(700, 800): "🌫️",  # Atmosphere (fog, mist, etc.)
        range(800, 801): "☀️",  # Clear sky
        range(801, 803): "🌤",  # Few clouds
        range(803, 805): "☁️",  # Cloudy
    },
    
    # Temperature ranges (in Celsius) mapped to appropriate emojis
    "FEELS_LIKE_EMOJIS": {
        range(-50, -20): "🥶",  # Extremely cold
        range(-20, -10): "❄️",  # Very cold
        range(-10, 0): "🧊",    # Cold
        range(0, 10): "🍃",     # Chilly
        range(10, 20): "🌱",    # Mild
        range(20, 25): "🌿",    # Warm
        range(25, 30): "☀️",    # Hot
        range(30, 50): "🔥",    # Very hot
    }
}