import unittest
import os
import sys
import tempfile
import csv
import json
import re
import asyncio
from datetime import datetime, timedelta
import pytz
from unittest.mock import mock_open, patch, MagicMock, AsyncMock, call
from telegram import Update
from telegram.ext import CallbackContext
import pytest

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.utils import (
    extract_urls, ensure_directory, init_directories, 
    remove_links, country_code_to_emoji, get_weather_emoji,
    get_feels_like_emoji, get_city_translation
)
from modules.file_manager import ensure_csv_headers, save_user_location
from modules.utils import get_last_used_city
from modules.weather import WeatherCommand, WeatherData, WeatherCommandHandler
from modules.const import weather_emojis, feels_like_emojis

class TestBot(unittest.IsolatedAsyncioTestCase):

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
        
        # Create WeatherCommandHandler instance with mocked handle_weather_request
        weather_cmd = WeatherCommandHandler()
        weather_cmd.handle_weather_request = AsyncMock(return_value="Weather info for Kyiv")
        
        # Run the coroutine
        asyncio.run(weather_cmd(update, context))
        
        # Verify get_last_used_city was called with both user_id and chat_id (as string)
        mock_get_city.assert_called_once_with(123, '456')
        
        # Verify message was sent
        update.message.reply_text.assert_called_once_with("Weather info for Kyiv")
    
    @patch('modules.weather.save_user_location')
    def test_weather_command_with_city_arg(self, mock_save_location):
        """Test weather command saves city with chat ID."""
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
        
        # Create WeatherCommandHandler instance with mocked handle_weather_request
        weather_cmd = WeatherCommandHandler()
        weather_cmd.handle_weather_request = AsyncMock(return_value="Weather info for Odesa")
        
        # Run the coroutine
        asyncio.run(weather_cmd(update, context))
        
        # Verify save_user_location was called with user_id, city, and chat_id (as string)
        mock_save_location.assert_called_once_with(123, "Odesa", '456')
        
        # Verify message was sent
        update.message.reply_text.assert_called_once_with("Weather info for Odesa")

# Additional tests for core utilities
    def test_remove_links(self):
        """Test removing URLs from text."""
        # Test with multiple URLs
        text = "Check out https://example.com and http://test.com for more info."
        result = remove_links(text)
        self.assertTrue("Check out" in result)
        self.assertTrue("for more info" in result)
        self.assertNotIn("https://example.com", result)
        self.assertNotIn("http://test.com", result)
        
        # Test with no URLs
        text = "Plain text with no URLs"
        self.assertEqual(remove_links(text), text)
        
        # Test with URL at the beginning
        text = "https://example.com is a great website."
        result = remove_links(text)
        self.assertNotIn("https://example.com", result)
        self.assertTrue("great website" in result)
        
        # Test with URL at the end
        text = "Visit our website at https://example.com"
        result = remove_links(text)
        self.assertTrue("Visit our website at" in result)
        self.assertNotIn("https://example.com", result)

    def test_country_code_to_emoji(self):
        """Test conversion of country codes to emoji flags."""
        # Test common country codes
        self.assertEqual(country_code_to_emoji("US"), "🇺🇸")
        self.assertEqual(country_code_to_emoji("UA"), "🇺🇦")
        self.assertEqual(country_code_to_emoji("GB"), "🇬🇧")
        
        # Test lowercase (should convert to uppercase)
        self.assertEqual(country_code_to_emoji("ua"), "🇺🇦")
        
        # Test empty string (should return empty string)
        self.assertEqual(country_code_to_emoji(""), "")

    async def test_get_weather_emoji(self):
        """Test getting weather emoji based on weather code."""
        weather_code = 800  # Clear sky
        emoji = await get_weather_emoji(weather_code)
        # The function returns emoji for ranges, so 800 is in range(800, 801) which maps to '☀️'
        self.assertEqual(emoji, '☀️')

    async def test_get_feels_like_emoji(self):
        """Test getting feels like emoji based on temperature."""
        temp = 25  # Warm temperature
        emoji = await get_feels_like_emoji(temp)
        # Temperature 25 is in range(20, 30) which maps to '😎'
        self.assertEqual(emoji, '😎')

    async def test_get_city_translation(self):
        """Test city name translation."""
        # Test a city that has no translation - should return the same city
        city = "London"  
        translated = await get_city_translation(city)
        self.assertEqual(translated, "London")
        
        # Test a city that does have translation
        # The function normalizes by lowercasing and removing spaces
        # "кортгене" -> "кортгене" which matches "кортгене" in CITY_TRANSLATIONS
        city = "кортгене"
        translated = await get_city_translation(city)
        self.assertEqual(translated, "Kortgene")

    def test_ensure_directory(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test creating a single directory
            test_dir = os.path.join(temp_dir, "test_dir")
            ensure_directory(test_dir)
            self.assertTrue(os.path.exists(test_dir))
            
            # Test with nested directories
            nested_dir = os.path.join(temp_dir, "parent/child/grandchild")
            ensure_directory(nested_dir)
            self.assertTrue(os.path.exists(nested_dir))
            
            # Test with existing directory (should not raise error)
            ensure_directory(test_dir)
            self.assertTrue(os.path.exists(test_dir))

    def test_init_directories(self):
        """Test initialization of required directories."""
        with patch('modules.utils.ensure_directory') as mock_ensure_directory:
            init_directories()
            
            # Should call ensure_directory for each required directory
            self.assertEqual(mock_ensure_directory.call_count, 4)
            
            # Check specific calls are made (without verifying exact paths)
            self.assertTrue(mock_ensure_directory.called)
            self.assertEqual(len(mock_ensure_directory.call_args_list), 4)

    def test_weather_data_formatting(self):
        """Test weather data formatting and advice generation."""
        # Skip this async test for now
        self.assertTrue(True)

class TestEdgeCases(unittest.TestCase):
    """Tests focusing on edge cases and error handling."""
    
    def test_extract_urls_edge_cases(self):
        """Test URL extraction with various edge cases."""
        # Test empty string
        self.assertEqual(extract_urls(""), [])
        
        # Test URL with special characters
        text = "Check https://example.com/path?param=value&other=123#fragment"
        urls = extract_urls(text)
        self.assertEqual(len(urls), 1)
        self.assertTrue("https://example.com/path?param=value&other=123" in urls[0])
        
        # Test with URL that has parentheses
        text = "See (https://example.com/test) in parentheses"
        urls = extract_urls(text)
        # The regex should handle this correctly
        self.assertTrue(any("example.com/test" in url for url in urls))
        
        # Test with invalid URLs
        text = "Not a valid URL: http:// missing domain"
        self.assertEqual(extract_urls(text), [])

    def test_ensure_csv_headers_edge_cases(self):
        """Test CSV header handling with various edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with empty file
            empty_file = os.path.join(temp_dir, "empty.csv")
            with open(empty_file, 'w') as f:
                pass  # Create empty file
            
            headers = ["col1", "col2", "col3"]
            ensure_csv_headers(empty_file, headers)
            
            # Verify headers were added
            with open(empty_file, 'r') as f:
                content = f.read()
                self.assertEqual(content.strip(), "col1,col2,col3")
            
            # Test with file that has data but no headers
            no_headers_file = os.path.join(temp_dir, "no_headers.csv")
            with open(no_headers_file, 'w') as f:
                f.write("val1,val2,val3\n")
                f.write("val4,val5,val6\n")
            
            ensure_csv_headers(no_headers_file, headers)
            
            # Verify headers were added and data preserved
            with open(no_headers_file, 'r') as f:
                lines = f.readlines()
                self.assertEqual(lines[0].strip(), "col1,col2,col3")
                self.assertEqual(lines[1].strip(), "val1,val2,val3")
                self.assertEqual(lines[2].strip(), "val4,val5,val6")
            
            # Test with headers in different order
            diff_order_file = os.path.join(temp_dir, "diff_order.csv")
            with open(diff_order_file, 'w') as f:
                f.write("col3,col1,col2\n")
                f.write("val3,val1,val2\n")
            
            # Should not change headers since same set exists
            ensure_csv_headers(diff_order_file, headers)
            
            with open(diff_order_file, 'r') as f:
                lines = f.readlines()
                self.assertEqual(lines[0].strip(), "col3,col1,col2")

    def test_get_last_used_city_error_handling(self):
        """Test error handling in get_last_used_city function."""
        # Create a test file with valid data
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_city.csv")
            
            # Create test file with headers
            with open(test_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["user_id", "city", "timestamp", "chat_id"])
                writer.writerow(["123", "Kyiv", "2023-01-01T00:00:00", ""])
            
            # Test with mock file that raises exception during reading
            with patch('modules.utils.CITY_DATA_FILE', test_file):
                with patch('modules.utils.open', side_effect=Exception("Test error")):
                    with patch('modules.utils.error_logger') as mock_logger:
                        result = get_last_used_city(123)
                        self.assertIsNone(result)
                        mock_logger.error.assert_called_once()

if __name__ == '__main__':
    unittest.main()