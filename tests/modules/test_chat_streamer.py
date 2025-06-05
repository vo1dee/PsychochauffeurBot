import unittest
import os
import tempfile
import asyncio
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytz

from modules.chat_streamer import ChatStreamer
from modules.const import KYIV_TZ
from modules.logger import LOG_DIR

class TestChatStreamer(unittest.IsolatedAsyncioTestCase):
    """Test the ChatStreamer functionality."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        # Create a temporary directory for test logs
        self.test_dir = tempfile.TemporaryDirectory()
        self.original_log_dir = LOG_DIR
        
        # Patch LOG_DIR to use our test directory
        self.log_dir_patcher = patch('modules.logger.LOG_DIR', self.test_dir.name)
        self.log_dir_patcher.start()
        
        # Create ChatStreamer instance
        self.streamer = ChatStreamer()
        
        # Set up debug logging
        logging.basicConfig(level=logging.DEBUG)
    
    async def asyncTearDown(self):
        """Clean up test environment."""
        # Close the streamer
        await self.streamer.close()
        
        # Stop the patcher
        self.log_dir_patcher.stop()
        
        # Clean up temporary directory
        self.test_dir.cleanup()
    
    async def test_stream_message(self):
        """Test streaming a message to log file."""
        # Create mock update and context
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "Test message"
        update.effective_chat = MagicMock()
        update.effective_chat.id = "123456789"
        update.effective_chat.type = "group"
        update.effective_chat.title = "Test Group"
        update.effective_user = MagicMock()
        update.effective_user.username = "testuser"
        
        context = MagicMock()
        
        # Stream the message
        await self.streamer.stream_message(update, context)
        
        # Get today's date for the log file name
        today = datetime.now(KYIV_TZ).strftime('%Y-%m-%d')
        log_file = os.path.join(self.test_dir.name, f'chat_{update.effective_chat.id}', f'{today}.log')
        
        # Debug: Print directory contents
        logging.debug(f"Test directory contents: {os.listdir(self.test_dir.name)}")
        if os.path.exists(os.path.dirname(log_file)):
            logging.debug(f"Chat directory contents: {os.listdir(os.path.dirname(log_file))}")
        
        # Verify log file was created
        self.assertTrue(os.path.exists(log_file), f"Log file not found at {log_file}")
        
        # Read and verify log content
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn("Test message", log_content)
            self.assertIn("testuser", log_content)
            self.assertIn("Test Group", log_content)
            self.assertIn("group", log_content)
    
    async def test_stream_message_no_text(self):
        """Test streaming a message with no text."""
        # Create mock update with no text and no specific type
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = None
        # Explicitly set all media attributes to None to ensure it's treated as OTHER MEDIA
        update.message.sticker = None
        update.message.photo = None
        update.message.video = None
        update.message.voice = None
        update.message.audio = None
        update.message.document = None
        update.message.animation = None
        update.effective_chat = MagicMock()
        update.effective_chat.id = "123456789"
        update.effective_chat.type = "group"
        update.effective_chat.title = "Test Group"
        update.effective_user = MagicMock()
        update.effective_user.username = "testuser"
        
        context = MagicMock()
        
        # Stream the message
        await self.streamer.stream_message(update, context)
        
        # Get today's date for the log file name
        today = datetime.now(KYIV_TZ).strftime('%Y-%m-%d')
        log_file = os.path.join(self.test_dir.name, f'chat_{update.effective_chat.id}', f'{today}.log')
        
        # Verify log file was created
        self.assertTrue(os.path.exists(log_file), f"Log file not found at {log_file}")
        
        # Read and verify log content
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            self.assertIn("[OTHER MEDIA]", log_content)
            self.assertIn("testuser", log_content)
            self.assertIn("Test Group", log_content)
            self.assertIn("group", log_content)
    
    async def test_close(self):
        """Test closing the streamer."""
        # Create a logger first
        logger = self.streamer._get_logger("123456789")
        
        # Close the streamer
        await self.streamer.close()
        
        # Verify loggers dict is empty
        self.assertEqual(len(self.streamer._loggers), 0) 