import unittest
import os
import tempfile
import csv
from unittest.mock import mock_open, patch, MagicMock, AsyncMock
from telegram import Update
from telegram.ext import CallbackContext
from modules.utils import extract_urls
from modules.file_manager import ensure_csv_headers, save_user_location
from modules.utils import get_last_used_city
from modules.weather import WeatherCommand

class TestBot(unittest.TestCase):

    def test_extract_urls(self):
        """Test URL extraction from a message."""
        message_text = "Check this out: https://example.com and also http://test.com"
        expected_urls = ["https://example.com", "http://test.com"]
        extracted_urls = extract_urls(message_text)
        self.assertEqual(extracted_urls, expected_urls)

    def test_ensure_csv_headers_new_file(self):
        """Test ensure_csv_headers creates a new file with headers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_headers.csv")
            headers = ["user_id", "city", "timestamp", "chat_id"]
            
            ensure_csv_headers(test_file, headers)
            
            # Verify file was created with correct headers
            with open(test_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                file_headers = next(reader, None)
                self.assertEqual(set(file_headers), set(headers))
    
    def test_ensure_csv_headers_existing_file(self):
        """Test ensure_csv_headers adds headers to existing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_existing.csv")
            
            # Create a file without headers
            with open(test_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["123", "Kyiv", "2023-01-01T00:00:00"])
            
            headers = ["user_id", "city", "timestamp", "chat_id"]
            ensure_csv_headers(test_file, headers)
            
            # Verify headers were added
            with open(test_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                file_headers = next(reader, None)
                first_row = next(reader, None)
                
                self.assertEqual(set(file_headers), set(headers))
                self.assertEqual(first_row[0], "123")
                self.assertEqual(first_row[1], "Kyiv")

    @patch('os.makedirs')
    def test_save_user_location(self, mock_makedirs):
        """Test saving user location."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_save.csv")
            
            # Patch CSV_FILE constant to use our test file
            with patch('modules.file_manager.CSV_FILE', test_file):
                save_user_location(123, "Kyiv")
                
                # Verify file was created with user data
                with open(test_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    row = next(reader)
                    self.assertEqual(row[0], "123")
                    self.assertEqual(row[1], "Kyiv")

    def test_save_user_location_with_kiev(self):
        """Test that 'kiev' is saved as 'Kyiv'."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_kiev.csv")
            
            # Patch CSV_FILE constant to use our test file
            with patch('modules.file_manager.CSV_FILE', test_file):
                save_user_location(123, "kiev")
                
                # Read the file and verify Kyiv is used
                with open(test_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    row = next(reader)
                    self.assertEqual(row[1], "Kyiv")

    def test_save_user_location_with_chat_id(self):
        """Test saving user location with chat_id."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_chat.csv")
            
            # Patch CSV_FILE constant to use our test file
            with patch('modules.file_manager.CSV_FILE', test_file):
                save_user_location(123, "Lviv", 456)
                
                # Read the file and verify chat_id is saved
                with open(test_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    row = next(reader)
                    self.assertEqual(row[1], "Lviv")
                    self.assertEqual(row[3], "456")

    def test_get_last_used_city_kiev_conversion(self):
        """Test that 'Kiev' is converted to 'Kyiv' when retrieved."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_city_file.csv")
            
            # Create test file with Kiev
            with open(test_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["user_id", "city", "timestamp", "chat_id"])
                writer.writerow(["123", "Kiev", "2023-01-01T00:00:00", ""])
            
            # Patch CITY_DATA_FILE to use our test file
            with patch('modules.utils.CITY_DATA_FILE', test_file):
                user_id = 123
                city = get_last_used_city(user_id)
                self.assertEqual(city, "Kyiv")

    def test_get_last_used_city_with_chat_id(self):
        """Test retrieving city with chat_id preference."""
        # Test with chat_id parameter
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_city_chat.csv")
            
            # Create test file with chat-specific city
            with open(test_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["user_id", "city", "timestamp", "chat_id"])
                writer.writerow(["123", "Lviv", "2023-01-01T00:00:00", "456"])
            
            # Patch CITY_DATA_FILE to use our test file
            with patch('modules.utils.CITY_DATA_FILE', test_file):
                user_id = 123
                chat_id = 456
                city = get_last_used_city(user_id, chat_id)
                self.assertEqual(city, "Lviv")
        
        # Test with no chat_id parameter (user's default)
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_city_default.csv")
            
            # Create test file with default city (no chat_id)
            with open(test_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["user_id", "city", "timestamp", "chat_id"])
                writer.writerow(["123", "Odesa", "2023-01-01T00:00:00", ""])
            
            # Patch CITY_DATA_FILE to use our test file
            with patch('modules.utils.CITY_DATA_FILE', test_file):
                user_id = 123
                city = get_last_used_city(user_id)
                self.assertEqual(city, "Odesa")

    @patch('modules.weather.save_user_location')
    @patch('modules.weather.get_last_used_city')
    def test_weather_command_with_chat_id(self, mock_get_city, mock_save_location):
        """Test weather command uses chat-specific cities."""
        import asyncio
        
        # Setup mocks
        mock_get_city.return_value = "Kyiv"
        
        # Create mock Update and Context
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock()
        update.effective_user.id = 123
        update.effective_chat = MagicMock()
        update.effective_chat.id = 456
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        
        context = MagicMock(spec=CallbackContext)
        context.args = []  # No city provided in command
        
        # Create WeatherCommand instance with mocked handle_weather_request
        weather_cmd = WeatherCommand()
        weather_cmd.handle_weather_request = AsyncMock(return_value="Weather info for Kyiv")
        
        # Run the coroutine
        asyncio.run(weather_cmd(update, context))
        
        # Verify get_last_used_city was called with both user_id and chat_id
        mock_get_city.assert_called_once_with(123, 456)
        
        # Verify message was sent
        update.message.reply_text.assert_called_once_with("Weather info for Kyiv")
    
    @patch('modules.weather.save_user_location')
    def test_weather_command_with_city_arg(self, mock_save_location):
        """Test weather command saves city with chat ID."""
        import asyncio
        
        # Create mock Update and Context
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock()
        update.effective_user.id = 123
        update.effective_chat = MagicMock()
        update.effective_chat.id = 456
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        
        context = MagicMock(spec=CallbackContext)
        context.args = ["Odesa"]  # City provided in command
        
        # Create WeatherCommand instance with mocked handle_weather_request
        weather_cmd = WeatherCommand()
        weather_cmd.handle_weather_request = AsyncMock(return_value="Weather info for Odesa")
        
        # Run the coroutine
        asyncio.run(weather_cmd(update, context))
        
        # Verify save_user_location was called with user_id, city, and chat_id
        mock_save_location.assert_called_once_with(123, "Odesa", 456)
        
        # Verify message was sent
        update.message.reply_text.assert_called_once_with("Weather info for Odesa")

if __name__ == '__main__':
    unittest.main()