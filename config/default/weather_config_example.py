"""Example weather configuration for a chat"""

# Custom city translations can be added here
WEATHER_CONFIG = {
    "CITY_TRANSLATIONS": {
        "нью-йорк": "New York",
        "париж": "Paris",
        "рим": "Rome"
    },
    
    # You can customize emojis for weather conditions
    "CONDITION_EMOJIS": {
        range(200, 300): '⛈',  # Thunderstorm
        range(300, 400): '🌧',  # Drizzle
        range(500, 600): '🌧',  # Rain
        range(600, 700): '❄️',  # Snow
        range(700, 800): '🌫',  # Atmosphere
        range(800, 801): '☀️',  # Clear
        range(801, 900): '☁️',  # Clouds
    },
    
    # You can customize temperature range emojis
    "FEELS_LIKE_EMOJIS": {
        range(-100, 0): '🥶',   # Very cold
        range(0, 10): '🧥',     # Cold
        range(10, 20): '🧣',    # Cool
        range(20, 30): '😎',    # Comfortable
        range(30, 100): '🥵',   # Very hot
    }
}