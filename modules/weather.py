"""Weather module for fetching and displaying weather information."""

from dataclasses import dataclass
from typing import Optional
import httpx
from telegram import Update
from telegram.ext import CallbackContext

from utils import (
    country_code_to_emoji,
    get_weather_emoji,
    get_city_translation,
    get_feels_like_emoji
)
from const import Config
from modules.logger import init_error_handler, error_logger, general_logger
from modules.file_manager import save_user_location, get_last_used_city
from modules.gpt import ask_gpt_command


@dataclass
class WeatherData:
    """Structure for holding weather information."""
    city_name: str
    country_code: str
    weather_id: int
    description: str
    temperature: float
    feels_like: float

    async def get_clothing_advice(self, update: Update = None, context: CallbackContext = None) -> str:
        prompt = f"""Дай коротку пораду (1-2 речення) щодо того, що краще вдягнути при такій погоді:
        Температура: {round(self.temperature)}°C
        Відчувається як: {round(self.feels_like)}°C
        Погода: {self.description}
        
        Відповідай тільки порадою, без додаткового тексту."""
        try:
            advice = await ask_gpt_command(prompt, update, context, return_text=True)
            return f"\n👕 {advice}"
        except Exception as e:
            general_logger.error(f"Error getting clothing advice: {e}")
            return ""

    async def format_message(self, update: Update = None, context: CallbackContext = None) -> str:
        """Format weather data into a readable message."""
        weather_emoji = get_weather_emoji(self.weather_id)
        country_flag = country_code_to_emoji(self.country_code)
        feels_like_emoji = get_feels_like_emoji(self.feels_like)
        
        # Get clothing advice
        clothing_advice = await self.get_clothing_advice(update, context)

        return (
            f"Погода в {self.city_name}, {self.country_code} {country_flag}:\n"
            f"{weather_emoji} {self.description.capitalize()}\n"
            f"🌡 Температура: {round(self.temperature)}°C\n"
            f"{feels_like_emoji} Відчувається як: {round(self.feels_like)}°C"
            f"{clothing_advice}"
        )


class WeatherAPI:
    """Handler for OpenWeatherMap API interactions."""
    
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
    
    def __init__(self):
        self.api_key = Config.OPENWEATHER_API_KEY
    
    async def fetch_weather(self, city: str) -> Optional[WeatherData]:
        """Fetch weather data from OpenWeatherMap API."""
        translated_city = get_city_translation(city)
        
        params = {
            "q": translated_city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "uk"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params)
                data = response.json()

            if data.get("cod") != 200:
                general_logger.error(f"Weather API error response: {data}")
                raise ValueError(f"API Error: {data.get('message', 'Unknown error')}")

            weather = data.get("weather", [{}])[0]
            main = data.get("main", {})
            
            return WeatherData(
                city_name=data.get("name", "Unknown city"),
                country_code=data.get("sys", {}).get("country", "Unknown"),
                weather_id=weather.get("id", 0),
                description=weather.get("description", "No description"),
                temperature=main.get("temp", 0),
                feels_like=main.get("feels_like", 0)
            )
            
        except httpx.HTTPStatusError as e:
            general_logger.error(f"HTTP error fetching weather data: {e}")
            return None
        except Exception as e:
            general_logger.error(f"Error fetching weather data: {e}")
            return None


class WeatherCommand:
    """Handler for weather-related telegram commands."""
    
    def __init__(self):
        self.weather_api = WeatherAPI()
    
    async def handle_weather_request(self, city: str, update: Update = None, context: CallbackContext = None) -> str:
        """Process weather request and return formatted message."""
        weather_data = await self.weather_api.fetch_weather(city)
        if weather_data:
            return await weather_data.format_message(update, context)
        return "Не вдалося отримати дані про погоду. Спробуйте пізніше."
    
    async def __call__(self, update: Update, context: CallbackContext) -> None:
        """Handle /weather command."""
        user_id = update.effective_user.id
        
        try:
            if context.args:
                city = " ".join(context.args)
                save_user_location(user_id, city)
            else:
                city = get_last_used_city(user_id)
                if not city:
                    await update.message.reply_text(
                        "Будь ласка, вкажіть назву міста або задайте його спочатку."
                    )
                    return
            
            # Get weather info and pass update, context parameters
            weather_info = await self.handle_weather_request(city, update, context)
            
            if update.message:
                await update.message.reply_text(weather_info)
                
        except Exception as e:
            general_logger.error(f"Error in weather command: {e}")
            await update.message.reply_text(
                "Виникла помилка при отриманні погоди. Спробуйте пізніше."
            )


# Initialize the weather command handler
weather = WeatherCommand()