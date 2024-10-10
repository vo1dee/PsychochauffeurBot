import re

from const import weather_emojis, city_translations


# Utility function to remove all URLs from a given text
def remove_links(text):
    return re.sub(r'http[s]?://\S+', '', text).strip()

# Function to convert country code to flag emoji
def country_code_to_emoji(country_code: str) -> str:
    return ''.join(chr(127397 + ord(c)) for c in country_code.upper())

def get_weather_emoji(weather_id: int) -> str:
    return next((emoji for id_range, emoji in weather_emojis.items() if weather_id in id_range), '🌈')

def get_city_translation(city: str) -> str:
    normalized = city.lower().replace(" ", "")
    return city_translations.get(normalized, city)
