"""
Integration tests for weather service functionality.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import CallbackContext

from modules.weather import WeatherAPI, WeatherCommandHandler, WeatherData, WeatherCommand
from modules.error_handler import ErrorHandler


class TestWeatherServiceIntegration:
    """Integration tests for weather service."""
    
    @pytest.fixture
    def weather_api(self):
        """Create a weather API instance."""
        return WeatherAPI()
    
    @pytest.fixture
    def weather_handler(self):
        """Create a weather command handler."""
        return WeatherCommandHandler()
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=-1001234567890, type="supergroup")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="/weather London"
        )
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock callback context."""
        context = Mock(spec=CallbackContext)
        context.args = ["London"]
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context
    
    def test_weather_api_initialization(self, weather_api):
        """Test weather API initialization."""
        assert weather_api is not None
        assert hasattr(weather_api, 'api_key')
        assert weather_api.api_key is not None
    
    def test_weather_handler_initialization(self, weather_handler):
        """Test weather command handler initialization."""
        assert weather_handler is not None
        assert hasattr(weather_handler, 'weather_api')
    
    def test_weather_data_creation(self):
        """Test weather data structure creation."""
        weather_data = WeatherData(
            city_name="London",
            country_code="GB",
            weather_id=800,
            description="Partly cloudy",
            temperature=20.5,
            feels_like=22.0,
            humidity=65,
            timezone_offset=0,
            local_time=int(time.time())
        )
        
        assert weather_data.city_name == "London"
        assert weather_data.country_code == "GB"
        assert weather_data.weather_id == 800
        assert weather_data.temperature == 20.5
        assert weather_data.feels_like == 22.0
        assert weather_data.humidity == 65
        assert weather_data.description == "Partly cloudy"
    
    def test_weather_command_creation(self):
        """Test weather command structure creation."""
        weather_command = WeatherCommand(
            temperature=20.5,
            feels_like=22.0,
            description="Partly cloudy",
            clothing_advice="Wear a light jacket and comfortable shoes."
        )
        
        assert weather_command.temperature == 20.5
        assert weather_command.feels_like == 22.0
        assert weather_command.description == "Partly cloudy"
        assert weather_command.clothing_advice == "Wear a light jacket and comfortable shoes."
    
    @pytest.mark.asyncio
    async def test_weather_api_request_mock(self, weather_api):
        """Test weather API request with mocked response."""
        mock_response = {
            "name": "London",
            "sys": {"country": "GB"},
            "main": {
                "temp": 20.5,
                "feels_like": 22.0,
                "humidity": 65
            },
            "weather": [
                {"id": 801, "description": "partly cloudy"}
            ],
            "wind": {
                "speed": 5.2
            },
            "timezone": 0,
            "dt": int(time.time()),
            "cod": "200"
        }
        
        with patch.object(weather_api.client, 'get') as mock_request:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_request.return_value = asyncio.Future()
            mock_request.return_value.set_result(mock_response_obj)
            
            weather_data = await weather_api.fetch_weather("London")
            
            assert weather_data.city_name == "London"
            assert weather_data.temperature == 20.5
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_weather_command_handler(self, weather_handler, mock_update, mock_context):
        """Test weather command handling."""
        mock_weather_data = WeatherData(
            city_name="London",
            country_code="GB",
            weather_id=800,
            description="Partly cloudy",
            temperature=20.5,
            feels_like=22.0,
            humidity=65,
            timezone_offset=0,
            local_time=int(time.time())
        )
        
        with patch.object(weather_handler.weather_api, 'fetch_weather') as mock_get_weather:
            mock_get_weather.return_value = mock_weather_data
            
            await weather_handler(mock_update, mock_context)
            
            mock_get_weather.assert_called_once_with("London")
            mock_context.bot.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_weather_error_handling(self, weather_handler, mock_update, mock_context):
        """Test weather service error handling."""
        with patch.object(weather_handler.weather_api, 'fetch_weather') as mock_get_weather:
            mock_get_weather.side_effect = Exception("API Error")
            
            await weather_handler(mock_update, mock_context)
            
            # Should handle error gracefully and send error message
            mock_context.bot.send_message.assert_called_once()
            call_args = mock_context.bot.send_message.call_args
            assert "error" in call_args[1]['text'].lower() or "sorry" in call_args[1]['text'].lower()


class TestWeatherServiceErrorHandling:
    """Test error handling in weather service."""
    
    @pytest.fixture
    def weather_api(self):
        """Create a weather API instance."""
        return WeatherAPI()
    
    @pytest.mark.asyncio
    async def test_invalid_city_handling(self, weather_api):
        """Test handling of invalid city names."""
        with patch.object(weather_api.client, 'get') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {"cod": "404", "message": "City not found"}
            mock_request.return_value = asyncio.Future()
            mock_request.return_value.set_result(mock_response)
            
            result = await weather_api.fetch_weather("InvalidCityName123")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_api_key_error_handling(self, weather_api):
        """Test handling of API key errors."""
        with patch.object(weather_api.client, 'get') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {"cod": "401", "message": "Invalid API key"}
            mock_request.return_value = asyncio.Future()
            mock_request.return_value.set_result(mock_response)
            
            result = await weather_api.fetch_weather("London")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, weather_api):
        """Test handling of network errors."""
        with patch.object(weather_api.client, 'get') as mock_request:
            mock_request.side_effect = ConnectionError("Network error")
            
            result = await weather_api.fetch_weather("London")
            assert result is None


class TestWeatherServicePerformance:
    """Performance tests for weather service."""
    
    @pytest.fixture
    def weather_api(self):
        """Create a weather API instance."""
        return WeatherAPI()
    
    @pytest.mark.asyncio
    async def test_concurrent_weather_requests(self, weather_api):
        """Test handling of concurrent weather requests."""
        cities = ["London", "Paris", "New York", "Tokyo"]
        
        async def mock_get_response(url, params=None, **kwargs):
            await asyncio.sleep(0.1)  # Simulate API latency
            city_name = params.get("q", "Unknown")
            mock_response = Mock()
            mock_response.json.return_value = {
                "name": city_name,
                "sys": {"country": "XX"},
                "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 60},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 3.0},
                "timezone": 0,
                "dt": int(time.time()),
                "cod": "200"
            }
            return mock_response
        
        with patch.object(weather_api.client, 'get', side_effect=mock_get_response):
            tasks = [weather_api.fetch_weather(city) for city in cities]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 4
            assert all(isinstance(result, WeatherData) for result in results)
    
    @pytest.mark.asyncio
    async def test_weather_response_time(self, weather_api):
        """Test weather API response time."""
        async def delayed_get_response(url, params=None, **kwargs):
            await asyncio.sleep(0.2)  # 200ms delay
            mock_response = Mock()
            mock_response.json.return_value = {
                "name": "London",
                "sys": {"country": "GB"},
                "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 60},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 3.0},
                "timezone": 0,
                "dt": int(time.time()),
                "cod": "200"
            }
            return mock_response
        
        with patch.object(weather_api.client, 'get', side_effect=delayed_get_response):
            start_time = asyncio.get_event_loop().time()
            result = await weather_api.fetch_weather("London")
            end_time = asyncio.get_event_loop().time()
            
            response_time = end_time - start_time
            
            assert isinstance(result, WeatherData)
            assert response_time >= 0.2  # Should take at least 200ms
    
    @pytest.mark.asyncio
    async def test_weather_caching_behavior(self, weather_api):
        """Test weather data caching behavior."""
        mock_response = {
            "name": "London",
            "sys": {"country": "GB"},
            "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 60},
            "weather": [{"id": 800, "description": "clear sky"}],
            "wind": {"speed": 3.0},
            "timezone": 0,
            "dt": int(time.time()),
            "cod": "200"
        }
        
        with patch.object(weather_api.client, 'get') as mock_request:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_request.return_value = asyncio.Future()
            mock_request.return_value.set_result(mock_response_obj)
            
            # Make multiple requests for the same city
            result1 = await weather_api.fetch_weather("London")
            
            # Clear cache to test second request
            weather_api.cache = {}
            
            # Set up the mock again for the second request
            mock_request.return_value = asyncio.Future()
            mock_request.return_value.set_result(mock_response_obj)
            
            result2 = await weather_api.fetch_weather("London")
            
            assert result1.city_name == result2.city_name
            assert result1.temperature == result2.temperature
            
            # API should be called for each request since we cleared the cache
            assert mock_request.call_count == 2