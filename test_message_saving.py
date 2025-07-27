#!/usr/bin/env python3
"""
Test script to verify message saving functionality.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from modules.database import Database
from modules.const import Config

async def test_database_connection():
    """Test basic database connectivity."""
    print("Testing database connection...")
    try:
        await Database.initialize()
        print("✅ Database initialized successfully")
        
        # Test a simple query
        manager = Database.get_connection_manager()
        async with manager.get_connection() as conn:
            result = await conn.fetchval("SELECT 1")
            print(f"✅ Database query test: {result}")
            
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def test_message_saving():
    """Test message saving functionality."""
    print("\nTesting message saving...")
    
    # Create a mock message object
    class MockUser:
        def __init__(self):
            self.id = 12345
            self.username = "test_user"
            self.first_name = "Test"
            self.last_name = "User"
            self.is_bot = False
    
    class MockChat:
        def __init__(self):
            self.id = -1001234567890
            self.type = "supergroup"
            self.title = "Test Chat"
    
    class MockMessage:
        def __init__(self):
            self.message_id = 999999
            self.chat = MockChat()
            self.from_user = MockUser()
            self.date = datetime.now()
            self.text = "Test message for database saving"
            self.reply_to_message = None
            
        def to_dict(self):
            return {
                "message_id": self.message_id,
                "chat": {
                    "id": self.chat.id,
                    "type": self.chat.type,
                    "title": self.chat.title
                },
                "from": {
                    "id": self.from_user.id,
                    "username": self.from_user.username,
                    "first_name": self.from_user.first_name,
                    "last_name": self.from_user.last_name,
                    "is_bot": self.from_user.is_bot
                },
                "date": int(self.date.timestamp()),
                "text": self.text
            }
    
    try:
        mock_message = MockMessage()
        await Database.save_message(mock_message)
        print("✅ Message saved successfully")
        
        # Try to retrieve the message
        manager = Database.get_connection_manager()
        async with manager.get_connection() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM messages WHERE chat_id = $1 AND message_id = $2",
                mock_message.chat.id, mock_message.message_id
            )
            if result:
                print(f"✅ Message retrieved: {result['text']}")
            else:
                print("❌ Message not found in database")
                
        return True
    except Exception as e:
        print(f"❌ Message saving failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("🧪 Testing message saving functionality...\n")
    
    # Test database connection
    db_ok = await test_database_connection()
    if not db_ok:
        print("\n❌ Database tests failed. Cannot proceed with message saving tests.")
        return
    
    # Test message saving
    msg_ok = await test_message_saving()
    
    if db_ok and msg_ok:
        print("\n✅ All tests passed! Message saving should work correctly.")
    else:
        print("\n❌ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())