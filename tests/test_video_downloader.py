import unittest
import os
import sys

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.utils import extract_urls

class TestVideoDownloader(unittest.TestCase):
    """Test cases for the VideoDownloader class."""

    def test_placeholder(self):
        """Placeholder test"""
        self.assertTrue(True)

# Run the tests
if __name__ == '__main__':
    unittest.main()