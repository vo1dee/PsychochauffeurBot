"""Weather module for fetching and displaying weather information."""

import asyncio
import html as html_lib
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
from config_v2.compat import get_shared_config_manager
from modules.const import Config
from modules.logger import error_logger, general_logger
from modules.file_manager import save_user_location
from modules.gpt import gpt_response

# Cache expiration time in seconds (10 minutes)
CACHE_EXPIRATION = 600

_AQI_LABELS = {1: "Добра", 2: "Прийнятна", 3: "Помірна", 4: "Погана", 5: "Дуже погана"}
_RISK_EMOJIS = {"Низький": "🟢", "Середній": "🟡", "Високий": "🔴"}


@dataclass
class WeatherCommand:
    """Weather command response data structure"""
    temperature: float
    feels_like: float
    description: str
    clothing_advice: str


@dataclass
class PressureTrend:
    """Pressure trend over ~3 hours."""
    current_hpa: int
    forecast_hpa: int
    delta_hpa: float  # positive = rising, negative = falling


@dataclass
class AirQualityData:
    """Air quality data relevant to headache risk."""
    aqi: int  # 1–5 scale
    pm2_5: float
    no2: float
    o3: float


@dataclass
class HeadacheRiskAssessment:
    """Combined headache/migraine risk from weather, air quality, and geomagnetic data."""
    risk_level: str  # Низький / Середній / Високий
    risk_score: int
    pressure_trend: Optional[PressureTrend]
    air_quality: Optional[AirQualityData]
    k_index: Optional[int]
    explanation: str


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
    pressure: int        # hPa
    lat: float
    lon: float
    timezone_offset: int  # seconds from UTC
    local_time: int       # unix timestamp (UTC)

    async def get_clothing_advice(self, update: Optional[Update] = None, context: Optional[CallbackContext[Any, Any, Any, Any]] = None) -> WeatherCommand:
        from datetime import datetime, timedelta
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
                advice_result = await gpt_response(update, context, response_type="weather", message_text_override=prompt, return_text=True)
                advice = advice_result if isinstance(advice_result, str) else ""
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

    async def get_headache_risk(
        self,
        weather_api: "WeatherAPI",
        geo_api: Any,
        update: Optional[Update] = None,
        context: Optional[CallbackContext[Any, Any, Any, Any]] = None,
    ) -> HeadacheRiskAssessment:
        """Fetch pressure trend, air quality, and geomagnetic data in parallel, then compute headache risk."""
        results = await asyncio.gather(
            weather_api.fetch_pressure_trend(self.lat, self.lon, self.pressure),
            weather_api.fetch_air_quality(self.lat, self.lon),
            geo_api.fetch_geomagnetic_data(),
            return_exceptions=True,
        )

        pressure_trend: Optional[PressureTrend] = results[0] if isinstance(results[0], PressureTrend) else None
        air_quality: Optional[AirQualityData] = results[1] if isinstance(results[1], AirQualityData) else None
        geo_data = results[2] if not isinstance(results[2], Exception) else None

        if isinstance(results[0], Exception):
            error_logger.error(f"Pressure trend fetch failed: {results[0]}")
        if isinstance(results[1], Exception):
            error_logger.error(f"Air quality fetch failed: {results[1]}")
        if isinstance(results[2], Exception):
            error_logger.error(f"Geomagnetic fetch failed: {results[2]}")

        k_index: Optional[int] = geo_data.current_value if geo_data else None
        delta = pressure_trend.delta_hpa if pressure_trend else 0.0
        aqi = air_quality.aqi if air_quality else 1

        score = _compute_headache_risk_score(delta, aqi, k_index)
        risk_level = _risk_level_from_score(score)

        explanation = await _get_headache_explanation(
            city=self.city_name,
            pressure_trend=pressure_trend,
            air_quality=air_quality,
            k_index=k_index,
            risk_level=risk_level,
            update=update,
            context=context,
        )

        return HeadacheRiskAssessment(
            risk_level=risk_level,
            risk_score=score,
            pressure_trend=pressure_trend,
            air_quality=air_quality,
            k_index=k_index,
            explanation=explanation,
        )

    async def format_message_raw(self) -> str:
        """Format weather data into a readable message without AI advice."""
        weather_emoji = await get_weather_emoji(self.weather_id)
        country_flag = country_code_to_emoji(self.country_code)
        feels_like_emoji = await get_feels_like_emoji(self.feels_like)
        humidity_emoji = await get_humidity_emoji(self.humidity)
        from datetime import datetime, timedelta
        local_dt = datetime.utcfromtimestamp(self.local_time) + timedelta(seconds=self.timezone_offset)
        local_time_str = local_dt.strftime('%H:%M %d.%m.%Y')

        return (
            f"Погода в {self.city_name}, {self.country_code} {country_flag} (місцевий час: {local_time_str}):\n"
            f"{weather_emoji} {self.description.capitalize()}\n"
            f"🌡 Температура: {round(self.temperature)}°C\n"
            f"{feels_like_emoji} Відчувається як: {round(self.feels_like)}°C\n"
            f"{humidity_emoji} Вологість: {self.humidity}%\n"
            f"📊 Тиск: {self.pressure} гПа"
        )

    async def format_message(self, update: Optional[Update] = None, context: Optional[CallbackContext[Any, Any, Any, Any]] = None) -> str:
        """Format weather data into a readable message with AI clothing advice."""
        raw = await self.format_message_raw()
        clothing_advice = await self.get_clothing_advice(update, context)
        return f"{raw}\n\n👕 {clothing_advice.clothing_advice}"


def _compute_headache_risk_score(pressure_delta: float, aqi: int, k_index: Optional[int]) -> int:
    score = 0
    abs_delta = abs(pressure_delta)
    if abs_delta >= 15:
        score += 2
    elif abs_delta >= 8:
        score += 1
    if aqi >= 4:
        score += 2
    elif aqi >= 3:
        score += 1
    if k_index is not None:
        if k_index >= 6:
            score += 2
        elif k_index >= 4:
            score += 1
    return score


def _risk_level_from_score(score: int) -> str:
    if score <= 1:
        return "Низький"
    elif score <= 3:
        return "Середній"
    return "Високий"


async def _get_headache_explanation(
    city: str,
    pressure_trend: Optional[PressureTrend],
    air_quality: Optional[AirQualityData],
    k_index: Optional[int],
    risk_level: str,
    update: Optional[Update],
    context: Optional[CallbackContext[Any, Any, Any, Any]],
) -> str:
    if update is None or context is None:
        return ""

    parts = []
    if pressure_trend:
        direction = "знижується" if pressure_trend.delta_hpa < 0 else "підвищується"
        parts.append(f"Атмосферний тиск {direction} на {abs(pressure_trend.delta_hpa):.0f} гПа за 3 год ({pressure_trend.current_hpa} → {pressure_trend.forecast_hpa} гПа)")
    if air_quality:
        aqi_label = _AQI_LABELS.get(air_quality.aqi, "невідома")
        parts.append(f"Якість повітря: {aqi_label} (AQI {air_quality.aqi}/5), PM2.5={air_quality.pm2_5:.0f} мкг/м³, NO2={air_quality.no2:.0f} мкг/м³, O3={air_quality.o3:.0f} мкг/м³")
    if k_index is not None:
        parts.append(f"Геомагнітна активність: K-індекс {k_index}")

    data_summary = "\n".join(parts) if parts else "Дані відсутні"
    prompt = (
        f"Місто: {city}\n"
        f"Рівень ризику мігрені/головного болю: {risk_level}\n"
        f"Дані:\n{data_summary}\n\n"
        f"Дай коротке пояснення (2-3 речення), які фактори найбільше впливають на ризик та кому варто бути обережним."
    )

    try:
        result = await gpt_response(update, context, response_type="headache_risk", message_text_override=prompt, return_text=True)
        return result if isinstance(result, str) else ""
    except Exception as e:
        error_logger.error(f"Error getting headache explanation: {e}")
        return ""


class WeatherAPI:
    """Handler for OpenWeatherMap API interactions."""

    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
    FORECAST_URL = "http://api.openweathermap.org/data/2.5/forecast"
    AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

    def __init__(self) -> None:
        self.cache: Dict[str, Tuple[WeatherData, float]] = {}
        self._forecast_cache: Dict[Tuple[float, float], Tuple[PressureTrend, float]] = {}
        self._aq_cache: Dict[Tuple[float, float], Tuple[AirQualityData, float]] = {}
        self.api_key = Config.OPENWEATHER_API_KEY
        if self.api_key and len(self.api_key) > 4:
            general_logger.info(f"WeatherAPI initialized with key ending in '...{self.api_key[-4:]}'")
        else:
            error_logger.error("WeatherAPI initialized WITHOUT a valid API key.")
        self.client = httpx.AsyncClient()

    def _is_cache_valid(self, city: str) -> bool:
        if city not in self.cache:
            return False
        _, timestamp = self.cache[city]
        return (time.time() - timestamp) < CACHE_EXPIRATION

    async def fetch_weather(self, city: str) -> Optional[WeatherData]:
        """Fetch weather data from OpenWeatherMap API."""
        if self._is_cache_valid(city):
            weather_data, _ = self.cache[city]
            general_logger.info(f"Using cached weather data for {city}")
            return weather_data

        if city in self.cache:
            del self.cache[city]

        translated_city = await get_city_translation(city)
        general_logger.info(f"Fetching fresh weather data for city: {translated_city} (original: {city})")

        params = {
            "q": translated_city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "uk",
        }

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            data = response.json()

            cod = data.get("cod")
            general_logger.info(f"Weather API response code: {cod} (type: {type(cod).__name__})")

            if str(cod) != "200":
                error_logger.error(f"Weather API error response: {data}")
                raise ValueError(f"API Error: {data.get('message', 'Unknown error')}")
            else:
                general_logger.info(f"Weather API successful response for {data.get('name', 'Unknown')} with temp {data.get('main', {}).get('temp')}°C")

            weather = data.get("weather", [{}])[0]
            main = data.get("main", {})
            coord = data.get("coord", {})
            weather_data = WeatherData(
                city_name=data.get("name", "Unknown city"),
                country_code=data.get("sys", {}).get("country", "Unknown"),
                weather_id=weather.get("id", 0),
                description=weather.get("description", "No description"),
                temperature=main.get("temp", 0),
                feels_like=main.get("feels_like", 0),
                humidity=main.get("humidity", 0),
                pressure=main.get("pressure", 1013),
                lat=coord.get("lat", 0.0),
                lon=coord.get("lon", 0.0),
                timezone_offset=data.get("timezone", 0),
                local_time=data.get("dt", 0),
            )

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

    async def fetch_pressure_trend(self, lat: float, lon: float, current_pressure: int) -> Optional[PressureTrend]:
        """Fetch the next 3h forecast pressure to compute trend."""
        cache_key = (round(lat, 2), round(lon, 2))
        cached = self._forecast_cache.get(cache_key)
        if cached and (time.time() - cached[1]) < CACHE_EXPIRATION:
            return cached[0]

        try:
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric",
                "cnt": 1,
            }
            response = await self.client.get(self.FORECAST_URL, params=params)
            response.raise_for_status()
            data = response.json()
            forecast_list = data.get("list", [])
            if not forecast_list:
                return None
            forecast_pressure = forecast_list[0].get("main", {}).get("pressure", current_pressure)
            trend = PressureTrend(
                current_hpa=current_pressure,
                forecast_hpa=int(forecast_pressure),
                delta_hpa=round(forecast_pressure - current_pressure, 1),
            )
            self._forecast_cache[cache_key] = (trend, time.time())
            return trend
        except Exception as e:
            error_logger.error(f"Error fetching pressure trend: {e}")
            return None

    async def fetch_air_quality(self, lat: float, lon: float) -> Optional[AirQualityData]:
        """Fetch current air quality data."""
        cache_key = (round(lat, 2), round(lon, 2))
        cached = self._aq_cache.get(cache_key)
        if cached and (time.time() - cached[1]) < CACHE_EXPIRATION:
            return cached[0]

        try:
            params = {"lat": lat, "lon": lon, "appid": self.api_key}
            response = await self.client.get(self.AIR_POLLUTION_URL, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("list", [])
            if not items:
                return None
            item = items[0]
            aqi = item.get("main", {}).get("aqi", 1)
            components = item.get("components", {})
            aq = AirQualityData(
                aqi=int(aqi),
                pm2_5=float(components.get("pm2_5", 0)),
                no2=float(components.get("no2", 0)),
                o3=float(components.get("o3", 0)),
            )
            self._aq_cache[cache_key] = (aq, time.time())
            return aq
        except Exception as e:
            error_logger.error(f"Error fetching air quality: {e}")
            return None


class WeatherCommandHandler:
    """Handler for weather-related telegram commands."""

    def __init__(self) -> None:
        self.weather_api = WeatherAPI()
        self.config_manager = get_shared_config_manager()
        from modules.geomagnetic import GeomagneticAPI
        self.geo_api = GeomagneticAPI()

    async def __call__(self, update: Update, context: CallbackContext[Any, Any, Any, Any]) -> None:
        """Handle /weather command.

        Sends raw weather data immediately, then edits the message once
        with clothing advice and headache risk assessment.
        """
        user_id: Optional[int] = update.effective_user.id if update.effective_user else None
        chat_id: Optional[int] = update.effective_chat.id if update.effective_chat else None

        try:
            if context.args:
                city = " ".join(context.args)
                if user_id is not None:
                    save_user_location(user_id, city, chat_id)
            else:
                city = get_last_used_city(user_id if user_id is not None else 0, chat_id) or ""
                if not city:
                    if update.message:
                        await update.message.reply_text(
                            "Будь ласка, вкажіть назву міста або задайте його спочатку."
                        )
                    return

            weather_data = await self.weather_api.fetch_weather(city)
            if not weather_data:
                if update.message:
                    await update.message.reply_text("Не вдалося отримати дані про погоду.")
                return

            raw_message = await weather_data.format_message_raw()
            if not update.message:
                return
            sent_message = await update.message.reply_text(
                f"{raw_message}\n\n⏳ Завантаження рекомендацій..."
            )

            try:
                clothing, headache = await asyncio.gather(
                    weather_data.get_clothing_advice(update, context),
                    weather_data.get_headache_risk(self.weather_api, self.geo_api, update, context),
                    return_exceptions=True,
                )

                full_message = html_lib.escape(raw_message)

                # Append pressure trend detail if available
                if isinstance(headache, HeadacheRiskAssessment) and headache.pressure_trend:
                    trend = headache.pressure_trend
                    if trend.delta_hpa != 0:
                        arrow = "↓" if trend.delta_hpa < 0 else "↑"
                        full_message += f" ({arrow} {abs(trend.delta_hpa):.0f} гПа/3год)"

                # Append AQI line
                if isinstance(headache, HeadacheRiskAssessment) and headache.air_quality:
                    aq = headache.air_quality
                    aqi_label = _AQI_LABELS.get(aq.aqi, "Невідома")
                    full_message += (
                        f"\n💨 Повітря: {html_lib.escape(aqi_label)} (AQI {aq.aqi}/5)"
                        f" | PM2.5: {aq.pm2_5:.0f}, NO2: {aq.no2:.0f}, O3: {aq.o3:.0f} мкг/м³"
                    )

                # Clothing advice — expandable block
                if isinstance(clothing, WeatherCommand) and clothing.clothing_advice:
                    full_message += f"\n\n<blockquote expandable>👕 {html_lib.escape(clothing.clothing_advice)}</blockquote>"

                # Headache risk — expandable block
                if isinstance(headache, HeadacheRiskAssessment):
                    emoji = _RISK_EMOJIS.get(headache.risk_level, "⚪")
                    block_body = f"🧠 Ризик мігрені: {emoji} {html_lib.escape(headache.risk_level)}"
                    if headache.explanation:
                        block_body += f"\n{html_lib.escape(headache.explanation)}"
                    full_message += f"\n\n<blockquote expandable>{block_body}</blockquote>"

                await sent_message.edit_text(full_message, parse_mode="HTML")

            except Exception as e:
                error_logger.error(f"Error fetching weather advice: {e}")
                await sent_message.edit_text(raw_message)

        except httpx.HTTPStatusError as e:
            error_logger.error(f"HTTP status error in weather command: {e}")
            if update.message:
                await update.message.reply_text(f"Виникла помилка HTTP при отриманні погоди. {e}.")
        except httpx.RequestError as e:
            error_logger.error(f"Request error in weather command: {e}")
            if update.message:
                await update.message.reply_text(f"Виникла помилка запиту при отриманні погоди. {e}.")
        except ValueError as e:
            error_logger.error(f"Value error in weather command: {e}")
            if update.message:
                await update.message.reply_text(f"Виникла помилка значення при отриманні погоди. {e}.")
        except Exception as e:
            error_logger.error(f"Unexpected error in weather command: {e}")
            if update.message:
                await update.message.reply_text(f"Виникла несподівана помилка при отриманні погоди. {e}.")
