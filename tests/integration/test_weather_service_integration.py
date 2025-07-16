"""
Integration tests for weather service functionality.
"""

import pytest
import asyncio
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
        return WeatherAPI(api_key="test_api_key")
    
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
        assert weather_api.api_key == "test_api_key"
    
    def test_weather_handler_initialization(self, weather_handler):
        """Test weather command handler initialization."""
        assert weather_handler is not None
        assert hasattr(weather_handler, 'weather_api')
    
    def test_weather_data_creation(self):
        """Test weather data structure creation."""
        weather_data = WeatherData(
            city_name="London",
            temperature=20.5,
            feels_like=22.0,
            humidity=65,
            description="Partly cloudy",
            wind_speed=5.2
        )
        
        assert weather_data.city_name == "London"
        assert weather_data.temperature == 20.5
        assert weather_data.feels_like == 22.0
        assert weather_data.humidity == 65
        assert weather_data.description == "Partly cloudy"
        assert weather_data.wind_speed == 5.2
    
    def test_weather_command_creation(self):
        """Test weather command structure creation."""
        weather_command = WeatherCommand(
            temperature=20.5,
            feels_like=22.0,
            humidity=65,
            description="Partly cloudy"
        )
        
        assert weather_command.temperature == 20.5
        assert weather_command.feels_like == 22.0
        assert weather_command.humidity == 65
        assert weather_command.description == "Partly cloudy"
    
    @pytest.mark.asyncio
    async def test_weather_api_request_mock(self, weather_api):
        """Test weather API request with mocked response."""
        mock_response = {
            "name": "London",
            "main": {
                "temp": 20.5,
                "feels_like": 22.0,
                "humidity": 65
            },
            "weather": [
                {"description": "partly cloudy"}
            ],
            "wind": {
                "speed": 5.2
            }
        }
        
        with patch.object(weather_api, '_make_api_request') as mock_request:
            mock_request.return_value = mock_response
            
            weather_data = await weather_api.get_weather("London")
            
            assert weather_data.city_name == "London"
            assert weather_data.temperature == 20.5
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_weather_command_handler(self, weather_handler, mock_update, mock_context):
        """Test weather command handling."""
        mock_weather_data = WeatherData(
            city_name="London",
            temperature=20.5,
            feels_like=22.0,
            humidity=65,
            description="Partly cloudy",
            wind_speed=5.2
        )
        
        with patch.object(weather_handler.weather_api, 'get_weather') as mock_get_weather:
            mock_get_weather.return_value = mock_weather_data
            
            await weather_handler(mock_update, mock_context)
            
            mock_get_weather.assert_called_once_with("London")
            mock_context.bot.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_weather_error_handling(self, weather_handler, mock_update, mock_context):
        """Test weather service error handling."""
        with patch.object(weather_handler.weather_api, 'get_weather') as mock_get_weather:
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
        return WeatherAPI(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_invalid_city_handling(self, weather_api):
        """Test handling of invalid city names."""
        with patch.object(weather_api, '_make_api_request') as mock_request:
            mock_request.side_effect = Exception("City not found")
            
            with pytest.raises(Exception):
                await weather_api.get_weather("InvalidCityName123")
    
    @pytest.mark.asyncio
    async def test_api_key_error_handling(self, weather_api):
        """Test handling of API key errors."""
        with patch.object(weather_api, '_make_api_request') as mock_request:
            mock_request.side_effect = Exception("Invalid API key")
            
            with pytest.raises(Exception):
                await weather_api.get_weather("London")
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, weather_api):
        """Test handling of network errors."""
        with patch.object(weather_api, '_make_api_request') as mock_request:
            mock_request.side_effect = ConnectionError("Network error")
            
            with pytest.raises(ConnectionError):
                await weather_api.get_weather("London")


class TestWeatherServicePerformance:
    """Performance tests for weather service."""
    
    @pytest.fixture
    def weather_api(self):
        """Create a weather API instance."""
        return WeatherAPI(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_concurrent_weather_requests(self, weather_api):
        """Test handling of concurrent weather requests."""
        cities = ["London", "Paris", "New York", "Tokyo"]
        
        async def mock_api_request(url):
            await asyncio.sleep(0.1)  # Simulate API latency
            city_name = url.split("q=")[1].split("&")[0]
            return {
                "name": city_name,
                "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 60},
                "weather": [{"description": "clear sky"}],
                "wind": {"speed": 3.0}
            }
        
        with patch.object(weather_api, '_make_api_request', side_effect=mock_api_request):
            tasks = [weather_api.get_weather(city) for city in cities]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 4
            assert all(isinstance(result, WeatherData) for result in results)
    
    @pytest.mark.asyncio
    async def test_weather_response_time(self, weather_api):
        """Test weather API response time."""
        async def delayed_api_request(url):
            await asyncio.sleep(0.2)  # 200ms delay
            return {
                "name": "London",
                "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 60},
                "weather": [{"description": "clear sky"}],
                "wind": {"speed": 3.0}
            }
        
        with patch.object(weather_api, '_make_api_request', side_effect=delayed_api_request):
            start_time = asyncio.get_event_loop().time()
            result = await weather_api.get_weather("London")
            end_time = asyncio.get_event_loop().time()
            
            response_time = end_time - start_time
            
            assert isinstance(result, WeatherData)
            assert response_time >= 0.2  # Should take at least 200ms
    
    @pytest.mark.asyncio
    async def test_weather_caching_behavior(self, weather_api):
        """Test weather data caching behavior."""
        mock_response = {
            "name": "London",
            "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 60},
            "weather": [{"description": "clear sky"}],
            "wind": {"speed": 3.0}
        }
        
        with patch.object(weather_api, '_make_api_request') as mock_request:
            mock_request.return_value = mock_response
            
            # Make multiple requests for the same city
            result1 = await weather_api.get_weather("London")
            result2 = await weather_api.get_weather("London")
            
            assert result1.city_name == result2.city_name
            assert result1.temperature == result2.temperature
            
            # API should be called for each request (no caching implemented yet)
            assert mock_request.call_count == 2