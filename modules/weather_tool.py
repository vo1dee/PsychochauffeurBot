"""get_weather tool exposed to the GPT chat flow via OpenAI function calling."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from modules.logger import error_logger, general_logger

if TYPE_CHECKING:
    from modules.weather import WeatherAPI

WEATHER_TOOL_NAME = "get_weather"
# OpenWeatherMap's free forecast covers 5 days in 3-hour steps.
MAX_FORECAST_DAYS = 5

WEATHER_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": WEATHER_TOOL_NAME,
        "description": (
            "Get real-time weather for a city: current conditions (days_ahead=0) or a "
            "forecast for a day up to 5 days ahead (days_ahead=1 is tomorrow). Returns "
            "temperature, wind, precipitation and whether thunderstorms are reported or "
            "expected. Call this for any question about weather or conditions in a location."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, optionally with country code, e.g. 'Kyiv', 'Goes, NL'.",
                },
                "days_ahead": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": MAX_FORECAST_DAYS,
                    "description": "0 for current weather (default), 1 for tomorrow, up to 5. Relative to the city's local date.",
                },
            },
            "required": ["city"],
        },
    },
}

# Appended to the chat's system prompt (outside the configurable prompt, so it
# doesn't count towards MAX_SYSTEM_PROMPT_LENGTH).
WEATHER_TOOL_RULES = (
    "Weather rules: when the user asks about weather or conditions (temperature, rain, "
    "wind, snow, storms) for any location, now or in the next 5 days, ALWAYS call the "
    "get_weather tool for real-time data (days_ahead=1 for tomorrow) — never make up or "
    "guess weather data. For follow-ups like 'and tomorrow?', reuse the city from the "
    "conversation. Report temperature, precipitation, wind "
    "and any storm/thunderstorm indication in a clean, readable format in the user's "
    "language. The tool has no official storm warnings; for those, or if the tool returns "
    "an error, suggest official sources (e.g. KNMI or Buienradar for the Netherlands, "
    "Ukrhydrometcenter for Ukraine, meteoalarm.org for Europe)."
)

# Response types that are user-facing conversations and should get the tool.
WEATHER_TOOL_RESPONSE_TYPES = frozenset({"command", "mention", "private", "random"})

_weather_api: Optional["WeatherAPI"] = None


def _get_weather_api() -> "WeatherAPI":
    # Imported lazily: modules.weather imports modules.gpt, which imports this module.
    global _weather_api
    if _weather_api is None:
        from modules.weather import WeatherAPI
        _weather_api = WeatherAPI()
    return _weather_api


async def get_weather_tool_result(city: str) -> Dict[str, Any]:
    """Fetch weather for ``city`` and return a JSON-serialisable dict for the model."""
    city = (city or "").strip()
    if not city:
        return {"error": "No city provided."}

    data = await _get_weather_api().fetch_weather(city)
    if data is None:
        return {
            "error": f"Weather data is unavailable for '{city}'.",
            "suggestion": "Suggest official sources such as KNMI, Buienradar, meteoalarm.org or Ukrhydrometcenter.",
        }

    local_dt = datetime.utcfromtimestamp(data.local_time) + timedelta(seconds=data.timezone_offset)
    return {
        "city": data.city_name,
        "country": data.country_code,
        "local_time": local_dt.strftime("%Y-%m-%d %H:%M"),
        "description": data.description,
        "temperature_c": round(data.temperature, 1),
        "feels_like_c": round(data.feels_like, 1),
        "humidity_pct": data.humidity,
        "pressure_hpa": data.pressure,
        "wind_speed_ms": data.wind_speed,
        "wind_gust_ms": data.wind_gust,
        "rain_last_1h_mm": data.rain_1h,
        "snow_last_1h_mm": data.snow_1h,
        # OpenWeatherMap condition codes 2xx are thunderstorms.
        "thunderstorm": 200 <= data.weather_id < 300,
        "official_warnings": "not available from this source",
    }


async def get_forecast_tool_result(city: str, days_ahead: int) -> Dict[str, Any]:
    """Summarise the forecast for the city's local date ``days_ahead`` days from now."""
    city = (city or "").strip()
    if not city:
        return {"error": "No city provided."}

    data = await _get_weather_api().fetch_forecast(city)
    if data is None:
        return {
            "error": f"Forecast is unavailable for '{city}'.",
            "suggestion": "Suggest official sources such as KNMI, Buienradar, meteoalarm.org or Ukrhydrometcenter.",
        }

    city_info = data.get("city", {})
    offset = timedelta(seconds=city_info.get("timezone", 0))
    target_date = (datetime.now(timezone.utc) + offset).date() + timedelta(days=days_ahead)

    entries = []
    for item in data.get("list", []):
        local_dt = datetime.fromtimestamp(item.get("dt", 0), timezone.utc) + offset
        if local_dt.date() == target_date:
            entries.append((local_dt, item))
    if not entries:
        return {"error": f"No forecast data for {target_date.isoformat()}; the forecast only covers the next {MAX_FORECAST_DAYS} days."}

    temps = [item.get("main", {}).get("temp", 0.0) for _, item in entries]
    winds = [item.get("wind", {}) for _, item in entries]
    gusts = [w["gust"] for w in winds if w.get("gust") is not None]
    weather_ids = [item.get("weather", [{}])[0].get("id", 0) for _, item in entries]
    descriptions = list(dict.fromkeys(item.get("weather", [{}])[0].get("description", "") for _, item in entries))

    return {
        "city": city_info.get("name", city),
        "country": city_info.get("country", ""),
        "date": target_date.isoformat(),
        "days_ahead": days_ahead,
        "temperature_min_c": round(min(temps), 1),
        "temperature_max_c": round(max(temps), 1),
        "descriptions": [d for d in descriptions if d],
        "wind_speed_max_ms": max(w.get("speed", 0.0) for w in winds),
        "wind_gust_max_ms": max(gusts) if gusts else None,
        "rain_total_mm": round(sum(item.get("rain", {}).get("3h", 0.0) for _, item in entries), 1),
        "snow_total_mm": round(sum(item.get("snow", {}).get("3h", 0.0) for _, item in entries), 1),
        "precipitation_probability_max_pct": round(max(item.get("pop", 0.0) for _, item in entries) * 100),
        "thunderstorm_expected": any(200 <= wid < 300 for wid in weather_ids),
        # 3-hour steps, local time
        "timeline": [
            {
                "time": local_dt.strftime("%H:%M"),
                "temp_c": round(item.get("main", {}).get("temp", 0.0)),
                "description": item.get("weather", [{}])[0].get("description", ""),
                "precipitation_probability_pct": round(item.get("pop", 0.0) * 100),
            }
            for local_dt, item in entries
        ],
        "official_warnings": "not available from this source",
    }


async def execute_tool_call(tool_call: Dict[str, Any]) -> str:
    """Run one tool call from a chat completion and return its content as a JSON string."""
    function = tool_call.get("function", {})
    name = function.get("name")
    if name != WEATHER_TOOL_NAME:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        args = json.loads(function.get("arguments") or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid tool arguments."})

    try:
        days_ahead = int(args.get("days_ahead") or 0)
    except (TypeError, ValueError):
        return json.dumps({"error": "days_ahead must be an integer."})
    if not 0 <= days_ahead <= MAX_FORECAST_DAYS:
        return json.dumps({"error": f"days_ahead must be between 0 and {MAX_FORECAST_DAYS}."})

    try:
        city = str(args.get("city", ""))
        if days_ahead:
            result = await get_forecast_tool_result(city, days_ahead)
        else:
            result = await get_weather_tool_result(city)
    except Exception as e:
        error_logger.error(f"get_weather tool failed: {e}", exc_info=True)
        result = {"error": "Weather lookup failed."}
    general_logger.info(f"get_weather tool call for {args.get('city')!r} (+{days_ahead}d): {'error' if 'error' in result else 'ok'}")
    return json.dumps(result, ensure_ascii=False)
