import requests

from telegram import Update
from telegram.ext import CallbackContext
from utils import country_code_to_emoji, get_weather_emoji, get_city_translation, get_feels_like_emoji
from const import OPENWEATHER_API_KEY
from modules.file_manager import general_logger, save_user_location, get_last_used_city



# Function to fetch weather data from OpenWeatherMap
async def get_weather(city: str) -> str:
    # Same as before, fetching weather data from OpenWeatherMap API
    city = get_city_translation(city)
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "uk"
    }
    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get("cod") != 200:
            general_logger.error(f"Weather API error response: {data}")
            return f"Error: {data.get('message', 'Unknown error')}"

        weather = data.get("weather")
        if not weather:
            return "Failed to retrieve weather data: Weather data not available"

        city_name = data.get("name", "Unknown city")
        country_code = data["sys"].get("country", "Unknown country")
        weather_id = weather[0].get("id", 0)
        weather_description = weather[0].get("description", "No description")
        temp = round(data["main"].get("temp", "N/A"))
        feels_like = round(data["main"].get("feels_like", "N/A"))

        weather_emoji = get_weather_emoji(weather_id)
        country_flag = country_code_to_emoji(country_code)
        feels_like_emoji = get_feels_like_emoji(feels_like)

        return (f"Погода в {city_name}, {country_code} {country_flag}:\n"
                f"{weather_emoji} {weather_description.capitalize()}\n"
                f"🌡 Температура: {temp}°C\n"
                f"{feels_like_emoji} Відчувається як: {feels_like}°C")
    except Exception as e:
        general_logger.error(f"Error fetching weather data: {e}")
        return f"Failed to retrieve weather data: {str(e)}"


# Command handler for /weather <city>
async def weather(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if context.args:
        city = " ".join(context.args)
        # Save the user's location to the CSV file
        save_user_location(user_id, city)
        weather_info = await get_weather(city)
        if update.message:
            await update.message.reply_text(weather_info)
    else:
        # Try to get the last saved city for the user
        city = get_last_used_city(user_id)
        if city:
            weather_info = await get_weather(city)
            if update.message:
                await update.message.reply_text(weather_info)
        else:
            await update.message.reply_text("Будь ласка, вкажіть назву міста або задайте його спочатку.")