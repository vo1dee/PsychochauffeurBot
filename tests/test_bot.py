import unittest
from unittest.mock import mock_open, patch
from utils import extract_urls
from modules.file_manager import save_user_location, get_last_used_city

class TestBot(unittest.TestCase):

    def test_extract_urls(self):
        """Test URL extraction from a message."""
        message_text = "Check this out: https://example.com and also http://test.com"
        expected_urls = ["https://example.com", "http://test.com"]
        extracted_urls = extract_urls(message_text)
        self.assertEqual(extracted_urls, expected_urls)

import pytest
from unittest.mock import mock_open
from modules.file_manager import save_user_location

def test_save_user_location(mocker):
    """Test saving user location."""
    mock_file = mocker.patch('modules.file_manager.open', mock_open())
    user_id = 123
    city = "Kyiv"
    save_user_location(user_id, city)

    # Check that file was opened for writing
    mock_file.assert_any_call('data/user_locations.csv', mode='w', newline='', encoding='utf-8')

    @patch('modules.file_manager.open', new_callable=mock_open, read_data="123,Kiev,2023-01-01T00:00:00")
    def test_get_last_used_city(self, mock_file):
        """Test retrieving last used city."""
        user_id = 123
        city = get_last_used_city(user_id)
        self.assertEqual(city, "Kyiv")

if __name__ == '__main__':
    unittest.main() 