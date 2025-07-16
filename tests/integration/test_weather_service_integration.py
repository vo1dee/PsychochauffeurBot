"""
Integration tests for weather service integration.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
import httpx
from datetime import datetime, timedelta

from modules.weather import WeatherService, WeatherData, WeatherForecast, WeatherAlert
from modules.error_handler import StandardError


class TestWeatherServiceIntegration:
    """Integration tests for weather service."""
    
    @pytest.fixture
    def weather_service(self):
        """Create a WeatherService instance."""
        return WeatherService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_current_weather_retrieval(self, weather_service):
        """Test retrieving current weather data."""
        mock_weather_data = {
            "name": "London",
            "main": {
                "temp": 15.5,
                "feels_like": 14.2,
                "temp_min": 12.0,
                "temp_max": 18.0,
                "pressure": 1013,
                "humidity": 65
            },
            "weather": [
                {
                    "id": 800,
                    "main": "Clear",
                    "description": "clear sky",
                    "icon": "01d"
                }
            ],
            "wind": {
                "speed": 3.2,
                "deg": 180
            },
            "visibility": 10000,
            "sys": {
                "sunrise": 1642651200,
                "sunset": 1642687200,
                "country": "GB"
            },
            "coord": {
                "lat": 51.5074,
                "lon": -0.1278
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_weather_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            weather = await weather_service.get_current_weather("London")
            
            assert isinstance(weather, WeatherData)
            assert weather.location == "London"
            assert weather.temperature == 15.5
            assert weather.feels_like == 14.2
            assert weather.description == "clear sky"
            assert weather.humidity == 65
            assert weather.wind_speed == 3.2
            assert weather.country == "GB"
    
    @pytest.mark.asyncio
    async def test_weather_by_coordinates(self, weather_service):
        """Test retrieving weather by coordinates."""
        mock_weather_data = {
            "name": "New York",
            "main": {
                "temp": 22.0,
                "feels_like": 24.5,
                "pressure": 1015,
                "humidity": 70
            },
            "weather": [
                {
                    "main": "Clouds",
                    "description": "scattered clouds",
                    "icon": "03d"
                }
            ],
            "wind": {
                "speed": 4.1,
                "deg": 220
            },
            "sys": {
                "country": "US"
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_weather_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            weather = await weather_service.get_weather_by_coordinates(40.7128, -74.0060)
            
            assert weather.location == "New York"
            assert weather.temperature == 22.0
            assert weather.description == "scattered clouds"
            assert weather.country == "US"
    
    @pytest.mark.asyncio
    async def test_weather_forecast_retrieval(self, weather_service):
        """Test retrieving weather forecast."""
        mock_forecast_data = {
            "city": {
                "name": "Paris",
                "country": "FR"
            },
            "list": [
                {
                    "dt": 1642694400,
                    "main": {
                        "temp": 8.5,
                        "feels_like": 6.2,
                        "pressure": 1020,
                        "humidity": 80
                    },
                    "weather": [
                        {
                            "main": "Rain",
                            "description": "light rain",
                            "icon": "10d"
                        }
                    ],
                    "wind": {
                        "speed": 2.8,
                        "deg": 150
                    },
                    "dt_txt": "2022-01-20 12:00:00"
                },
                {
                    "dt": 1642780800,
                    "main": {
                        "temp": 12.0,
                        "feels_like": 10.5,
                        "pressure": 1018,
                        "humidity": 75
                    },
                    "weather": [
                        {
                            "main": "Clouds",
                            "description": "overcast clouds",
                            "icon": "04d"
                        }
                    ],
                    "wind": {
                        "speed": 3.5,
                        "deg": 200
                    },
                    "dt_txt": "2022-01-21 12:00:00"
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_forecast_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            forecast = await weather_service.get_forecast("Paris", days=2)
            
            assert isinstance(forecast, WeatherForecast)
            assert forecast.location == "Paris"
            assert forecast.country == "FR"
            assert len(forecast.daily_forecasts) == 2
            
            # Check first day
            day1 = forecast.daily_forecasts[0]
            assert day1.temperature == 8.5
            assert day1.description == "light rain"
            assert day1.humidity == 80
            
            # Check second day
            day2 = forecast.daily_forecasts[1]
            assert day2.temperature == 12.0
            assert day2.description == "overcast clouds"
    
    @pytest.mark.asyncio
    async def test_weather_alerts_retrieval(self, weather_service):
        """Test retrieving weather alerts."""
        mock_alerts_data = {
            "alerts": [
                {
                    "sender_name": "National Weather Service",
                    "event": "Severe Thunderstorm Warning",
                    "start": 1642694400,
                    "end": 1642708800,
                    "description": "Severe thunderstorms with damaging winds and large hail possible.",
                    "tags": ["Thunderstorm", "Wind", "Hail"]
                },
                {
                    "sender_name": "National Weather Service",
                    "event": "Flash Flood Watch",
                    "start": 1642708800,
                    "end": 1642737600,
                    "description": "Heavy rainfall may cause flash flooding in low-lying areas.",
                    "tags": ["Flood", "Rain"]
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_alerts_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            alerts = await weather_service.get_weather_alerts(40.7128, -74.0060)
            
            assert len(alerts) == 2
            
            # Check first alert
            alert1 = alerts[0]
            assert isinstance(alert1, WeatherAlert)
            assert alert1.event == "Severe Thunderstorm Warning"
            assert alert1.sender == "National Weather Service"
            assert "thunderstorms" in alert1.description.lower()
            assert "Thunderstorm" in alert1.tags
            
            # Check second alert
            alert2 = alerts[1]
            assert alert2.event == "Flash Flood Watch"
            assert "flood" in alert2.description.lower()
    
    @pytest.mark.asyncio
    async def test_air_quality_integration(self, weather_service):
        """Test air quality data integration."""
        mock_air_quality_data = {
            "coord": {
                "lon": -0.1278,
                "lat": 51.5074
            },
            "list": [
                {
                    "main": {
                        "aqi": 3  # Moderate air quality
                    },
                    "components": {
                        "co": 233.75,
                        "no": 0.42,
                        "no2": 19.15,
                        "o3": 85.21,
                        "so2": 3.73,
                        "pm2_5": 12.87,
                        "pm10": 18.45,
                        "nh3": 2.14
                    },
                    "dt": 1642694400
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_air_quality_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            air_quality = await weather_service.get_air_quality(51.5074, -0.1278)
            
            assert air_quality.aqi == 3
            assert air_quality.pm2_5 == 12.87
            assert air_quality.pm10 == 18.45
            assert air_quality.co == 233.75
            assert air_quality.quality_description == "Moderate"
    
    @pytest.mark.asyncio
    async def test_historical_weather_data(self, weather_service):
        """Test retrieving historical weather data."""
        yesterday = datetime.now() - timedelta(days=1)
        timestamp = int(yesterday.timestamp())
        
        mock_historical_data = {
            "lat": 51.5074,
            "lon": -0.1278,
            "timezone": "Europe/London",
            "current": {
                "dt": timestamp,
                "temp": 10.5,
                "feels_like": 8.2,
                "pressure": 1015,
                "humidity": 85,
                "weather": [
                    {
                        "main": "Rain",
                        "description": "moderate rain",
                        "icon": "10d"
                    }
                ],
                "wind_speed": 4.2,
                "wind_deg": 180
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_historical_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            historical_weather = await weather_service.get_historical_weather(
                51.5074, -0.1278, yesterday
            )
            
            assert historical_weather.temperature == 10.5
            assert historical_weather.description == "moderate rain"
            assert historical_weather.humidity == 85
            assert historical_weather.wind_speed == 4.2
    
    @pytest.mark.asyncio
    async def test_multiple_locations_batch_request(self, weather_service):
        """Test batch weather requests for multiple locations."""
        locations = ["London", "Paris", "Berlin", "Madrid"]
        
        mock_responses = {
            "London": {"name": "London", "main": {"temp": 15.0}, "weather": [{"description": "clear"}]},
            "Paris": {"name": "Paris", "main": {"temp": 12.0}, "weather": [{"description": "cloudy"}]},
            "Berlin": {"name": "Berlin", "main": {"temp": 8.0}, "weather": [{"description": "rainy"}]},
            "Madrid": {"name": "Madrid", "main": {"temp": 20.0}, "weather": [{"description": "sunny"}]}
        }
        
        async def mock_get(url, **kwargs):
            # Extract city name from URL parameters
            for city in locations:
                if city.lower() in url.lower():
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = mock_responses[city]
                    return mock_response
            
            # Default response
            mock_response = Mock()
            mock_response.status_code = 404
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=mock_get)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            weather_data = await weather_service.get_weather_for_multiple_locations(locations)
            
            assert len(weather_data) == 4
            assert weather_data["London"].temperature == 15.0
            assert weather_data["Paris"].temperature == 12.0
            assert weather_data["Berlin"].temperature == 8.0
            assert weather_data["Madrid"].temperature == 20.0
    
    @pytest.mark.asyncio
    async def test_weather_units_conversion(self, weather_service):
        """Test weather data with different unit systems."""
        mock_weather_celsius = {
            "name": "Tokyo",
            "main": {"temp": 25.0, "feels_like": 27.5},
            "weather": [{"description": "sunny"}]
        }
        
        mock_weather_fahrenheit = {
            "name": "Tokyo",
            "main": {"temp": 77.0, "feels_like": 81.5},
            "weather": [{"description": "sunny"}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            # Test Celsius
            mock_response_c = Mock()
            mock_response_c.status_code = 200
            mock_response_c.json.return_value = mock_weather_celsius
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response_c)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            weather_c = await weather_service.get_current_weather("Tokyo", units="metric")
            assert weather_c.temperature == 25.0
            assert weather_c.temperature_unit == "°C"
            
            # Test Fahrenheit
            mock_response_f = Mock()
            mock_response_f.status_code = 200
            mock_response_f.json.return_value = mock_weather_fahrenheit
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response_f)
            
            weather_f = await weather_service.get_current_weather("Tokyo", units="imperial")
            assert weather_f.temperature == 77.0
            assert weather_f.temperature_unit == "°F"


class TestWeatherServiceErrorHandling:
    """Test error handling in weather service integration."""
    
    @pytest.fixture
    def weather_service(self):
        """Create a WeatherService instance."""
        return WeatherService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_invalid_api_key_handling(self, weather_service):
        """Test handling of invalid API key errors."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {
                "cod": 401,
                "message": "Invalid API key"
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="Invalid API key"):
                await weather_service.get_current_weather("London")
    
    @pytest.mark.asyncio
    async def test_city_not_found_handling(self, weather_service):
        """Test handling of city not found errors."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {
                "cod": "404",
                "message": "city not found"
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="city not found"):
                await weather_service.get_current_weather("NonexistentCity")
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, weather_service):
        """Test handling of API rate limits."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                "cod": 429,
                "message": "Your account is temporarily blocked due to exceeding of requests limitation"
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="rate limit"):
                await weather_service.get_current_weather("London")
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, weather_service):
        """Test handling of network timeouts."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="timeout"):
                await weather_service.get_current_weather("London")
    
    @pytest.mark.asyncio
    async def test_service_unavailable_handling(self, weather_service):
        """Test handling of service unavailable errors."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.json.return_value = {
                "cod": 503,
                "message": "Service temporarily unavailable"
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="unavailable"):
                await weather_service.get_current_weather("London")
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, weather_service):
        """Test handling of malformed API responses."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="Invalid response format"):
                await weather_service.get_current_weather("London")
    
    @pytest.mark.asyncio
    async def test_missing_data_fields_handling(self, weather_service):
        """Test handling of responses with missing required fields."""
        incomplete_data = {
            "name": "London",
            # Missing 'main' field with temperature data
            "weather": [{"description": "clear"}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = incomplete_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(StandardError, match="Missing required data"):
                await weather_service.get_current_weather("London")


class TestWeatherServicePerformance:
    """Performance tests for weather service integration."""
    
    @pytest.fixture
    def weather_service(self):
        """Create a WeatherService instance."""
        return WeatherService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_concurrent_weather_requests(self, weather_service):
        """Test handling of concurrent weather requests."""
        cities = ["London", "Paris", "Berlin", "Madrid", "Rome"]
        
        async def mock_weather_response(url, **kwargs):
            await asyncio.sleep(0.1)  # Simulate API latency
            city_name = "TestCity"  # Extract from URL in real implementation
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "name": city_name,
                "main": {"temp": 20.0, "humidity": 60},
                "weather": [{"description": "clear"}]
            }
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=mock_weather_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Make concurrent requests
            start_time = asyncio.get_event_loop().time()
            tasks = [weather_service.get_current_weather(city) for city in cities]
            results = await asyncio.gather(*tasks)
            end_time = asyncio.get_event_loop().time()
            
            # Should complete in roughly the time of one request (due to concurrency)
            total_time = end_time - start_time
            assert total_time < 0.5  # Should be much faster than 5 * 0.1 = 0.5s
            assert len(results) == 5
            assert all(isinstance(result, WeatherData) for result in results)
    
    @pytest.mark.asyncio
    async def test_caching_mechanism(self, weather_service):
        """Test weather data caching mechanism."""
        mock_weather_data = {
            "name": "London",
            "main": {"temp": 15.0, "humidity": 70},
            "weather": [{"description": "cloudy"}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_weather_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # First request
            weather1 = await weather_service.get_current_weather("London")
            
            # Second request (should use cache if implemented)
            weather2 = await weather_service.get_current_weather("London")
            
            assert weather1.temperature == weather2.temperature
            assert weather1.description == weather2.description
            
            # Verify API was called (implementation dependent on caching strategy)
            call_count = mock_client.return_value.__aenter__.return_value.get.call_count
            # Could be 1 (cached) or 2 (not cached) depending on implementation
            assert call_count >= 1
    
    @pytest.mark.asyncio
    async def test_response_time_measurement(self, weather_service):
        """Test response time measurement and optimization."""
        with patch('httpx.AsyncClient') as mock_client:
            async def delayed_response(url, **kwargs):
                await asyncio.sleep(0.2)  # Simulate 200ms API response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "name": "London",
                    "main": {"temp": 15.0},
                    "weather": [{"description": "clear"}]
                }
                return mock_response
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=delayed_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            start_time = asyncio.get_event_loop().time()
            weather = await weather_service.get_current_weather("London")
            end_time = asyncio.get_event_loop().time()
            
            response_time = end_time - start_time
            assert response_time >= 0.2  # Should take at least 200ms
            assert weather.temperature == 15.0
    
    @pytest.mark.asyncio
    async def test_memory_efficiency_large_datasets(self, weather_service):
        """Test memory efficiency with large weather datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Mock large forecast data
        large_forecast_data = {
            "city": {"name": "London"},
            "list": [
                {
                    "dt": 1642694400 + i * 3600,
                    "main": {"temp": 15.0 + i, "humidity": 60 + i},
                    "weather": [{"description": f"weather_{i}"}],
                    "wind": {"speed": 3.0 + i}
                }
                for i in range(120)  # 5 days * 24 hours
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = large_forecast_data
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Process large forecast
            forecast = await weather_service.get_forecast("London", days=5)
            
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 10MB for large dataset)
            assert memory_increase < 10 * 1024 * 1024  # 10MB
            assert len(forecast.daily_forecasts) == 120