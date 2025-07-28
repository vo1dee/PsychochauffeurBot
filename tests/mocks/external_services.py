"""
Mock factories for external services used in testing.
"""

from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any, Optional, List
import json
from datetime import datetime, timedelta

from modules.const import KYIV_TZ


class OpenAIMockFactory:
    """Factory for creating OpenAI API mocks."""
    
    @staticmethod
    def create_client_mock(responses: Optional[List[str]] = None) -> Mock:
        """Create a mock OpenAI client with configurable responses."""
        if responses is None:
            responses = ["Test AI response"]
        
        mock_client = Mock()
        
        # Mock the chat completions create method
        async def mock_create(*args: Any, **kwargs: Any) -> Mock:
            response_text = responses[0] if responses else "Default response"
            if len(responses) > 1:
                responses.pop(0)  # Cycle through responses
            
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = response_text
            mock_response.usage = Mock()
            mock_response.usage.total_tokens = 100
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 50
            
            return mock_response
        
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
        return mock_client
    
    @staticmethod
    def create_error_client_mock(error_type: Exception = Exception("API Error")) -> Mock:
        """Create a mock OpenAI client that raises errors."""
        mock_client = Mock()
        mock_client.chat.completions.create = AsyncMock(side_effect=error_type)
        return mock_client


class WeatherAPIMockFactory:
    """Factory for creating weather API mocks."""
    
    @staticmethod
    def create_success_mock(weather_data: Optional[Dict[str, Any]] = None) -> Mock:
        """Create a mock weather API that returns successful responses."""
        if weather_data is None:
            weather_data = {
                "name": "Kyiv",
                "main": {
                    "temp": 20.5,
                    "feels_like": 22.0,
                    "humidity": 65,
                    "pressure": 1013
                },
                "weather": [
                    {
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
                    "sunset": 1642687200
                }
            }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = weather_data
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        
        return mock_client
    
    @staticmethod
    def create_error_mock(status_code: int = 404, error_message: str = "City not found") -> Mock:
        """Create a mock weather API that returns error responses."""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {
            "cod": status_code,
            "message": error_message
        }
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        
        return mock_client


class VideoDownloaderMockFactory:
    """Factory for creating video downloader mocks."""
    
    @staticmethod
    def create_success_mock(download_result: Optional[Dict[str, Any]] = None) -> Mock:
        """Create a mock video downloader that returns successful downloads."""
        if download_result is None:
            download_result = {
                "success": True,
                "file_path": "/tmp/test_video.mp4",
                "title": "Test Video",
                "duration": 120,
                "file_size": 1024000,
                "thumbnail": "/tmp/test_thumbnail.jpg"
            }
        
        mock_downloader = Mock()
        mock_downloader.download = AsyncMock(return_value=download_result)
        mock_downloader.get_info = AsyncMock(return_value={
            "title": download_result.get("title", "Test Video"),
            "duration": download_result.get("duration", 120),
            "uploader": "Test Uploader"
        })
        
        return mock_downloader
    
    @staticmethod
    def create_error_mock(error_message: str = "Download failed") -> Mock:
        """Create a mock video downloader that fails."""
        mock_downloader = Mock()
        mock_downloader.download = AsyncMock(side_effect=Exception(error_message))
        mock_downloader.get_info = AsyncMock(side_effect=Exception(error_message))
        
        return mock_downloader


class DatabaseMockFactory:
    """Factory for creating database mocks."""
    
    @staticmethod
    def create_connection_mock(query_results: Optional[Dict[str, Any]] = None) -> Mock:
        """Create a mock database connection."""
        if query_results is None:
            query_results = {}
        
        mock_connection = Mock()
        
        # Mock common database operations
        mock_connection.execute = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=query_results.get("fetch", []))
        mock_connection.fetchrow = AsyncMock(return_value=query_results.get("fetchrow", None))
        mock_connection.fetchval = AsyncMock(return_value=query_results.get("fetchval", None))
        mock_connection.executemany = AsyncMock()
        
        # Mock transaction support
        mock_transaction = Mock()
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_connection.transaction = Mock(return_value=mock_transaction)
        
        return mock_connection
    
    @staticmethod
    def create_pool_mock(connections: Optional[List[Mock]] = None) -> Mock:
        """Create a mock database connection pool."""
        if connections is None:
            connections = [DatabaseMockFactory.create_connection_mock()]
        
        mock_pool = Mock()
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=connections[0])
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_pool.close = AsyncMock()
        mock_pool.wait_closed = AsyncMock()
        
        return mock_pool


class TelegramAPIMockFactory:
    """Factory for creating Telegram API mocks."""
    
    @staticmethod
    def create_bot_mock() -> Mock:
        """Create a comprehensive mock Telegram Bot."""
        mock_bot = Mock()
        
        # Basic bot info
        mock_bot.token = "test_token"
        mock_bot.username = "test_bot"
        
        # Mock API methods
        mock_bot.get_me = AsyncMock(return_value=Mock(
            id=123456789,
            is_bot=True,
            first_name="Test Bot",
            username="test_bot"
        ))
        
        mock_bot.send_message = AsyncMock(return_value=Mock(message_id=1))
        mock_bot.send_photo = AsyncMock(return_value=Mock(message_id=2))
        mock_bot.send_document = AsyncMock(return_value=Mock(message_id=3))
        mock_bot.send_sticker = AsyncMock(return_value=Mock(message_id=4))
        mock_bot.send_voice = AsyncMock(return_value=Mock(message_id=5))
        mock_bot.send_video = AsyncMock(return_value=Mock(message_id=6))
        
        mock_bot.edit_message_text = AsyncMock(return_value=Mock(message_id=1))
        mock_bot.delete_message = AsyncMock(return_value=True)
        
        mock_bot.get_file = AsyncMock(return_value=Mock(
            file_id="test_file_id",
            file_unique_id="test_unique_id",
            file_size=1024,
            file_path="test/path.jpg"
        ))
        
        mock_bot.get_chat = AsyncMock(return_value=Mock(
            id=12345,
            type="private",
            username="testuser"
        ))
        
        mock_bot.get_chat_member = AsyncMock(return_value=Mock(
            status="member",
            user=Mock(id=12345, username="testuser")
        ))
        
        return mock_bot
    
    @staticmethod
    def create_application_mock() -> Mock:
        """Create a mock Telegram Application."""
        mock_app = Mock()
        mock_app.bot = TelegramAPIMockFactory.create_bot_mock()
        mock_app.add_handler = Mock()
        mock_app.run_polling = AsyncMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        
        return mock_app


class SpeechmaticsMockFactory:
    """Factory for creating Speechmatics API mocks."""
    
    @staticmethod
    def create_success_mock(transcript: str = "Test transcript") -> Mock:
        """Create a mock Speechmatics API that returns successful transcriptions."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job": {
                "id": "test_job_id",
                "status": "done"
            },
            "results": [
                {
                    "alternatives": [
                        {
                            "content": transcript,
                            "confidence": 0.95
                        }
                    ]
                }
            ]
        }
        
        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        return mock_client
    
    @staticmethod
    def create_error_mock(error_type: str = "no_speech") -> Mock:
        """Create a mock Speechmatics API that returns errors."""
        error_responses = {
            "no_speech": {
                "status_code": 400,
                "json": {"error": "No speech detected"}
            },
            "language_not_supported": {
                "status_code": 400,
                "json": {"error": "Language not supported"}
            },
            "api_error": {
                "status_code": 500,
                "json": {"error": "Internal server error"}
            }
        }
        
        error_config = error_responses.get(error_type, error_responses["api_error"])
        
        mock_response = Mock()
        mock_response.status_code = error_config["status_code"]
        mock_response.json.return_value = error_config["json"]
        
        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        return mock_client


class ExternalServiceMockRegistry:
    """Registry for managing all external service mocks."""
    
    def __init__(self) -> None:
        self.mocks: Dict[str, Mock] = {}
    
    def register_openai_mock(self, responses: Optional[List[str]] = None) -> Mock:
        """Register an OpenAI mock."""
        self.mocks['openai'] = OpenAIMockFactory.create_client_mock(responses)
        return self.mocks['openai']
    
    def register_weather_mock(self, weather_data: Optional[Dict[str, Any]] = None) -> Mock:
        """Register a weather API mock."""
        self.mocks['weather'] = WeatherAPIMockFactory.create_success_mock(weather_data)
        return self.mocks['weather']
    
    def register_video_downloader_mock(self, download_result: Optional[Dict[str, Any]] = None) -> Mock:
        """Register a video downloader mock."""
        self.mocks['video_downloader'] = VideoDownloaderMockFactory.create_success_mock(download_result)
        return self.mocks['video_downloader']
    
    def register_database_mock(self, query_results: Optional[Dict[str, Any]] = None) -> Mock:
        """Register a database mock."""
        self.mocks['database'] = DatabaseMockFactory.create_connection_mock(query_results)
        return self.mocks['database']
    
    def register_telegram_mock(self) -> Mock:
        """Register a Telegram API mock."""
        self.mocks['telegram'] = TelegramAPIMockFactory.create_bot_mock()
        return self.mocks['telegram']
    
    def register_speechmatics_mock(self, transcript: str = "Test transcript") -> Mock:
        """Register a Speechmatics API mock."""
        self.mocks['speechmatics'] = SpeechmaticsMockFactory.create_success_mock(transcript)
        return self.mocks['speechmatics']
    
    def get_mock(self, service_name: str) -> Optional[Mock]:
        """Get a registered mock by name."""
        return self.mocks.get(service_name)
    
    def clear_mocks(self) -> None:
        """Clear all registered mocks."""
        self.mocks.clear()


# Convenience functions for common mock scenarios

def create_full_mock_environment() -> ExternalServiceMockRegistry:
    """Create a complete mock environment with all external services."""
    registry = ExternalServiceMockRegistry()
    
    registry.register_openai_mock()
    registry.register_weather_mock()
    registry.register_video_downloader_mock()
    registry.register_database_mock()
    registry.register_telegram_mock()
    registry.register_speechmatics_mock()
    
    return registry


def create_error_mock_environment() -> ExternalServiceMockRegistry:
    """Create a mock environment where all services return errors."""
    registry = ExternalServiceMockRegistry()
    
    registry.mocks['openai'] = OpenAIMockFactory.create_error_client_mock()
    registry.mocks['weather'] = WeatherAPIMockFactory.create_error_mock()
    registry.mocks['video_downloader'] = VideoDownloaderMockFactory.create_error_mock()
    registry.mocks['speechmatics'] = SpeechmaticsMockFactory.create_error_mock()
    
    return registry