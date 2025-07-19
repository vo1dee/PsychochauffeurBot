"""Weather module for fetching and displaying weather information."""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Any
import time
import httpx
from telegram import Update
from telegram.ext import CallbackContext

from modules.utils import (
    country_code_to_emoji,
    get_weather_emoji,
    get_city_translation,
    get_feels_like_emoji,
    get_last_used_city,
    get_humidity_emoji
)
from config.config_manager import ConfigManager
from modules.const import Config, Weather
from modules.logger import error_logger, general_logger
from modules.file_manager import save_user_location
from modules.gpt import ask_gpt_command, gpt_response

# Cache expiration time in seconds (10 minutes)
CACHE_EXPIRATION = 600


@dataclass
class WeatherCommand:
    """Weather command response data structure"""
    temperature: float
    feels_like: float
    description: str
    clothing_advice: str

@dataclass
class WeatherData:
    """Structure for holding weather information."""
    city_name: str
    country_code: str
    weather_id: int
    description: str
    temperature: float
    feels_like: float
    humidity: int
    timezone_offset: int  # seconds from UTC
    local_time: int      # unix timestamp (UTC)

    async def get_clothing_advice(self, update: Optional[Update] = None, context: Optional[CallbackContext[Any, Any, Any, Any]] = None) -> WeatherCommand:
        # Convert local_time to local time string
        from datetime import datetime, timezone, timedelta
        local_dt = datetime.utcfromtimestamp(self.local_time) + timedelta(seconds=self.timezone_offset)
        local_time_str = local_dt.strftime('%H:%M %d.%m.%Y')
        prompt = f"""Дай коротку пораду, що краще вдягнути при такій погоді в місті {self.city_name}, {self.country_code} о {local_time_str}. 2-3 речення.:
        Температура: {round(self.temperature)}°C
        Відчувається як: {round(self.feels_like)}°C
        Вологість: {self.humidity}%
        Погода: {self.description}
        """
        advice: str = ""
        if update is not None and context is not None:
            try:
                advice = await gpt_response(update, context, response_type="weather", message_text_override=prompt, return_text=True)
                general_logger.info(f"Clothing advice: {advice}")
            except httpx.HTTPStatusError as e:
                error_logger.error(f"HTTP status error getting clothing advice: {e}")
            except httpx.RequestError as e:
                error_logger.error(f"Request error getting clothing advice: {e}")
            except Exception as e:
                error_logger.error(f"Unexpected error getting clothing advice: {e}")
        return WeatherCommand(
            temperature=self.temperature,
            feels_like=self.feels_like,
            description=self.description,
            clothing_advice=advice or ""
        )

    async def format_message(self, update: Optional[Update] = None, context: Optional[CallbackContext[Any, Any, Any, Any]] = None) -> str:
        """Format weather data into a readable message."""
        weather_emoji = await get_weather_emoji(self.weather_id)
        country_flag = country_code_to_emoji(self.country_code)
        feels_like_emoji = await get_feels_like_emoji(self.feels_like)
        humidity_emoji = await get_humidity_emoji(self.humidity)
        from datetime import datetime, timedelta
        local_dt = datetime.utcfromtimestamp(self.local_time) + timedelta(seconds=self.timezone_offset)
        local_time_str = local_dt.strftime('%H:%M %d.%m.%Y')
        # Get clothing advice
        clothing_advice = await self.get_clothing_advice(update, context)

        return (
            f"Погода в {self.city_name}, {self.country_code} {country_flag} (місцевий час: {local_time_str}):\n"
            f"{weather_emoji} {self.description.capitalize()}\n"
            f"🌡 Температура: {round(self.temperature)}°C\n"
            f"{feels_like_emoji} Відчувається як: {round(self.feels_like)}°C\n"
            f"{humidity_emoji} Вологість: {self.humidity}%\n"
            f"\n👕 {clothing_advice.clothing_advice}"
        )


class WeatherAPI:
    """Handler for OpenWeatherMap API interactions."""
    
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
    
    def __init__(self) -> None:
        # Cache structure: {city: (weather_data, timestamp)}
        self.cache: Dict[str, Tuple[WeatherData, float]] = {}
        self.api_key = Config.OPENWEATHER_API_KEY
        if self.api_key and len(self.api_key) > 4:
            general_logger.info(f"WeatherAPI initialized with key ending in '...{self.api_key[-4:]}'")
        else:
            general_logger.error("WeatherAPI initialized WITHOUT a valid API key.")
        self.client = httpx.AsyncClient()
    
    def _is_cache_valid(self, city: str) -> bool:
        """Check if cached data for a city is still valid."""
        if city not in self.cache:
            return False
        
        _, timestamp = self.cache[city]
        current_time = time.time()
        return (current_time - timestamp) < CACHE_EXPIRATION
    
    async def fetch_weather(self, city: str) -> Optional[WeatherData]:
        """Fetch weather data from OpenWeatherMap API."""
        # Check if we have valid cached data
        if self._is_cache_valid(city):
            weather_data, _ = self.cache[city]
            general_logger.info(f"Using cached weather data for {city} (cache is still valid)")
            return weather_data
        
        # Clear expired cache entry if it exists
        if city in self.cache:
            del self.cache[city]
            general_logger.info(f"Cleared expired cache for {city}")
        
        translated_city = await get_city_translation(city)
        general_logger.info(f"Fetching fresh weather data for city: {translated_city} (original: {city})")
        
        params = {
            "q": translated_city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "uk"  # Request weather descriptions in Ukrainian
        }
        
        try:
            # Use the client from initialization instead of creating new one
            response = await self.client.get(self.BASE_URL, params=params)
            data = response.json()

            cod = data.get("cod")
            general_logger.info(f"Weather API response code: {cod} (type: {type(cod).__name__})")
            
            # Check if cod is not "200" or 200 (API can return either)
            if str(cod) != "200":
                error_logger.error(f"Weather API error response: {data}")
                raise ValueError(f"API Error: {data.get('message', 'Unknown error')}")
            else:
                # This is a successful response, should NOT be logged as an error
                general_logger.info(f"Weather API successful response for {data.get('name', 'Unknown')} with temp {data.get('main', {}).get('temp')}°C")

            weather = data.get("weather", [{}])[0]
            main = data.get("main", {})
            weather_data = WeatherData(
                city_name=data.get("name", "Unknown city"),
                country_code=data.get("sys", {}).get("country", "Unknown"),
                weather_id=weather.get("id", 0),
                description=weather.get("description", "No description"),
                temperature=main.get("temp", 0),
                feels_like=main.get("feels_like", 0),
                humidity=main.get("humidity", 0),
                timezone_offset=data.get("timezone", 0),
                local_time=data.get("dt", 0)
            )
            
            # Cache the new data with current timestamp
            self.cache[city] = (weather_data, time.time())
            general_logger.info(f"Cached fresh weather data for {city}")
            return weather_data
        except httpx.RequestError as e:
            error_logger.error(f"Network or request error fetching weather data: {e}")
            return None
        except httpx.HTTPStatusError as e:
            error_logger.error(f"HTTP status error fetching weather data: {e}")
            return None
        except ValueError as e:
            error_logger.error(f"Value error fetching weather data: {e}")
            return None
        except Exception as e:
            error_logger.error(f"Unexpected error fetching weather data: {e}")
            return None


class WeatherCommandHandler:
    """Handler for weather-related telegram commands."""
    
    def __init__(self) -> None:
        self.weather_api = WeatherAPI()
        self.config_manager = ConfigManager()
    
    async def handle_weather_request(self, city: str, update: Optional[Update] = None, context: Optional[CallbackContext[Any, Any, Any, Any]] = None) -> str:
        """Process weather request and return formatted message."""
        weather_data = await self.weather_api.fetch_weather(city)
        if weather_data:
            return await weather_data.format_message(update, context)
        return "Не вдалося отримати дані про погоду. "
    
    async def __call__(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle /weather command."""
        user_id: Optional[int] = update.effective_user.id if update.effective_user else None
        chat_id: Optional[int] = update.effective_chat.id if update.effective_chat else None
        
        try:
            if context.args:
                city = " ".join(context.args)
                if user_id is not None:
                    save_user_location(user_id, city, chat_id)
            else:
                # get_last_used_city expects (int, Optional[int])
                city = get_last_used_city(user_id if user_id is not None else 0, chat_id) or ""
                if not city:
                    if update.message:
                        await update.message.reply_text(
                            "Будь ласка, вкажіть назву міста або задайте його спочатку."
                        )
                    return
            
            # Get weather info and pass update, context parameters
            weather_info = await self.handle_weather_request(city, update, context)
            
            if update.message:
                await update.message.reply_text(weather_info)
                
        except httpx.HTTPStatusError as e:
            error_logger.error(f"HTTP status error in weather command: {e}")
            if update.message:
                await update.message.reply_text(
                    f"Виникла помилка HTTP при отриманні погоди. {e}."
                )
        except httpx.RequestError as e:
            error_logger.error(f"Request error in weather command: {e}")
            if update.message:
                await update.message.reply_text(
                    f"Виникла помилка запиту при отриманні погоди. {e}."
                )
        except ValueError as e:
            error_logger.error(f"Value error in weather command: {e}")
            if update.message:
                await update.message.reply_text(
                    f"Виникла помилка значення при отриманні погоди. {e}."
                )
        except Exception as e:
            error_logger.error(f"Unexpected error in weather command: {e}")
            if update.message:
                await update.message.reply_text(
                    f"Виникла несподівана помилка при отриманні погоди. {e}."
                )
