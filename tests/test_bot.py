import unittest
from unittest.mock import AsyncMock, patch
from utils import extract_urls
from modules.file_manager import save_user_location, get_last_used_city

class TestBot(unittest.TestCase):

    def test_extract_urls(self):
        """Test URL extraction from a message."""
        message_text = "Check this out: https://example.com and also http://test.com"
        expected_urls = ["https://example.com", "http://test.com"]
        extracted_urls = extract_urls(message_text)
        self.assertEqual(extracted_urls, expected_urls)

    @patch('modules.file_manager.open', new_callable=AsyncMock)
    def test_save_user_location(self, mock_open):
        """Test saving user location."""
        user_id = 123
        city = "Kyiv"
        save_user_location(user_id, city)
        mock_open.assert_called_once_with('data/user_locations.csv', mode='w', newline='', encoding='utf-8')

    @patch('modules.file_manager.open', new_callable=AsyncMock)
    def test_get_last_used_city(self, mock_open):
        """Test retrieving last used city."""
        user_id = 123
        mock_open.return_value.__enter__.return_value.read.return_value = "123,Kiev,2023-01-01T00:00:00"
        city = get_last_used_city(user_id)
        self.assertEqual(city, "Kiev")

if __name__ == '__main__':
    unittest.main() 