"""
Test cases for location message handling functionality.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any
from telegram import Update, Location
from telegram.ext import CallbackContext

# Add the project root to the Python path so we can import modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from main import handle_location
from modules.const import Stickers


class TestLocationHandler(unittest.IsolatedAsyncioTestCase):
    """Test cases for location message handling."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.update = MagicMock(spec=Update)
        self.context = MagicMock(spec=CallbackContext)
        
        # Mock the message
        self.message = MagicMock()
        self.update.message = self.message
        
        # Mock the location
        self.location = MagicMock(spec=Location)
        self.location.latitude = 50.4501
        self.location.longitude = 30.5234
        self.message.location = self.location
        
        # Mock reply_sticker method
        self.message.reply_sticker = AsyncMock()
        self.message.reply_text = AsyncMock()

    async def test_handle_location_sends_sticker(self) -> None:
        """Test that handle_location sends the correct sticker."""
        await handle_location(self.update, self.context)
        
        # Verify that reply_sticker was called with the correct sticker
        self.message.reply_sticker.assert_called_once_with(sticker=Stickers.LOCATION)

    async def test_handle_location_no_location(self) -> None:
        """Test that handle_location does nothing when no location is present."""
        self.message.location = None
        
        await handle_location(self.update, self.context)
        
        # Verify that no methods were called
        self.message.reply_sticker.assert_not_called()
        self.message.reply_text.assert_not_called()

    async def test_handle_location_no_message(self) -> None:
        """Test that handle_location does nothing when no message is present."""
        self.update.message = None
        
        await handle_location(self.update, self.context)
        
        # Verify that no methods were called
        self.message.reply_sticker.assert_not_called()
        self.message.reply_text.assert_not_called()

    @patch('main.error_logger')
    async def test_handle_location_sticker_failure_fallback(self, mock_error_logger: Any) -> None:
        """Test that handle_location falls back to text when sticker fails."""
        # Make reply_sticker raise an exception
        self.message.reply_sticker.side_effect = Exception("Sticker error")
        
        await handle_location(self.update, self.context)
        
        # Verify that reply_sticker was called first
        self.message.reply_sticker.assert_called_once_with(sticker=Stickers.LOCATION)
        
        # Verify that error was logged
        mock_error_logger.error.assert_called_once()
        
        # Verify that fallback text was sent
        self.message.reply_text.assert_called_once_with("📍 Location received!")

    async def test_handle_location_logs_coordinates(self) -> None:
        """Test that handle_location logs the location coordinates."""
        with patch('main.general_logger') as mock_logger:
            await handle_location(self.update, self.context)
            
            # Verify that coordinates were logged
            mock_logger.info.assert_any_call(
                "Received location: lat=50.4501, lon=30.5234"
            )
            # Verify that success message was logged
            mock_logger.info.assert_any_call(
                "Sent location sticker in response to location message"
            )


if __name__ == '__main__':
    unittest.main() 