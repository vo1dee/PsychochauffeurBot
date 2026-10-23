"""get_weather tool exposed to the GPT chat flow via OpenAI function calling."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, TYPE_CHECKING

from modules.logger import error_logger, general_logger

if TYPE_CHECKING:
    from modules.weather import WeatherAPI

WEATHER_TOOL_NAME = "get_weather"

WEATHER_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": WEATHER_TOOL_NAME,
        "description": (
            "Get current real-time weather for a city: temperature, feels-like, "
            "humidity, pressure, wind, precipitation and whether a thunderstorm is "
            "being reported. Call this for any question about weather or conditions "
            "in a location."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, optionally with country code, e.g. 'Kyiv', 'Goes, NL'.",
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
    "wind, snow, storms) for any location, ALWAYS call the get_weather tool for real-time "
    "data — never make up or guess weather data. Report temperature, precipitation, wind "
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
        result = await get_weather_tool_result(str(args.get("city", "")))
    except Exception as e:
        error_logger.error(f"get_weather tool failed: {e}", exc_info=True)
        result = {"error": "Weather lookup failed."}
    general_logger.info(f"get_weather tool call for {args.get('city')!r}: {'error' if 'error' in result else 'ok'}")
    return json.dumps(result, ensure_ascii=False)
