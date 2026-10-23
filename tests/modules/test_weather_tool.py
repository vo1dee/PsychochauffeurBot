"""Tests for the get_weather GPT tool and the tool-calling loop in modules.gpt."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from modules import gpt, weather_tool
from modules.weather import WeatherData


def _weather(**overrides):
    fields = dict(
        city_name="Goes", country_code="NL", weather_id=211, description="гроза",
        temperature=12.34, feels_like=10.0, humidity=88, pressure=1002,
        lat=51.5, lon=3.9, timezone_offset=7200, local_time=1_700_000_000,
        wind_speed=9.5, wind_gust=17.0, rain_1h=2.4,
    )
    fields.update(overrides)
    return WeatherData(**fields)


def _tool_call(city, call_id="call_1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "get_weather", "arguments": json.dumps({"city": city})},
    }


def _resp(content=None, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


@pytest.fixture
def weather_api():
    api = MagicMock()
    api.fetch_weather = AsyncMock(return_value=_weather())
    with patch.object(weather_tool, "_get_weather_api", return_value=api):
        yield api


@pytest.mark.asyncio
async def test_tool_result_contains_wind_rain_and_storm(weather_api):
    result = await weather_tool.get_weather_tool_result("Goes")
    weather_api.fetch_weather.assert_awaited_once_with("Goes")
    assert result["temperature_c"] == 12.3
    assert result["wind_speed_ms"] == 9.5
    assert result["wind_gust_ms"] == 17.0
    assert result["rain_last_1h_mm"] == 2.4
    assert result["thunderstorm"] is True


@pytest.mark.asyncio
async def test_tool_result_reports_unavailable_data(weather_api):
    weather_api.fetch_weather.return_value = None
    result = await weather_tool.get_weather_tool_result("Nowhere")
    assert "error" in result
    assert "KNMI" in result["suggestion"]


@pytest.mark.asyncio
async def test_execute_tool_call_rejects_unknown_tool_and_bad_args():
    unknown = await weather_tool.execute_tool_call({"function": {"name": "rm_rf", "arguments": "{}"}})
    assert "Unknown tool" in json.loads(unknown)["error"]
    bad = await weather_tool.execute_tool_call({"function": {"name": "get_weather", "arguments": "{oops"}})
    assert json.loads(bad)["error"] == "Invalid tool arguments."


@pytest.mark.asyncio
async def test_complete_with_tools_runs_tool_and_returns_final_answer(weather_api):
    create = AsyncMock(side_effect=[
        _resp(tool_calls=[_tool_call("Goes")]),
        _resp(content="  У Goes гроза, 12°C.  "),
    ])
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "Яка погода в Goes?"}]
    with patch.object(gpt.client.chat.completions.__class__, "create", create):
        text = await gpt._complete_with_tools("m", messages, 100, 0.5)

    assert text == "У Goes гроза, 12°C."
    assert create.await_count == 2
    first_kwargs = create.await_args_list[0].kwargs
    assert first_kwargs["tools"] == [weather_tool.WEATHER_TOOL]
    tool_msg = messages[-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_1"
    assert json.loads(tool_msg["content"])["city"] == "Goes"


@pytest.mark.asyncio
async def test_complete_with_tools_stops_after_max_rounds(weather_api):
    looping = [_resp(tool_calls=[_tool_call("Goes", f"c{i}")]) for i in range(gpt.MAX_TOOL_ROUNDS)]
    create = AsyncMock(side_effect=[*looping, _resp(content="done")])
    with patch.object(gpt.client.chat.completions.__class__, "create", create):
        text = await gpt._complete_with_tools("m", [{"role": "user", "content": "x"}], 100, 0.5)

    assert text == "done"
    assert create.await_args_list[-1].kwargs["tool_choice"] == "none"


@pytest.mark.asyncio
async def test_complete_with_tools_falls_back_when_tools_rejected():
    request = httpx.Request("POST", "https://example.invalid")
    error = httpx.HTTPStatusError("bad", request=request, response=httpx.Response(400, request=request))
    create = AsyncMock(side_effect=[error, _resp(content="plain")])
    with patch.object(gpt.client.chat.completions.__class__, "create", create):
        text = await gpt._complete_with_tools("m", [{"role": "user", "content": "x"}], 100, 0.5)

    assert text == "plain"
    assert "tools" not in create.await_args_list[-1].kwargs
