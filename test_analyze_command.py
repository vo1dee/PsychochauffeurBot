#!/usr/bin/env python3
"""
Test script to verify analyze command functionality.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from modules.database import Database
from modules.chat_analysis import get_messages_for_chat_today, get_last_n_messages_in_chat
from modules.const import Config, KYIV_TZ

async def test_message_retrieval():
    """Test message retrieval functions used by analyze command."""
    print("Testing message retrieval for analyze command...")
    
    try:
        await Database.initialize()
        print("✅ Database initialized successfully")
        
        # Test with a real chat ID (use a test chat ID)
        test_chat_id = -1001234567890  # Replace with actual chat ID if needed
        
        # First, let's see what messages exist in the database
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Get total message count
            total_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
            print(f"📊 Total messages in database: {total_count}")
            
            # Get messages for different chats
            chat_counts = await conn.fetch("""
                SELECT chat_id, COUNT(*) as count 
                FROM messages 
                GROUP BY chat_id 
                ORDER BY count DESC 
                LIMIT 5
            """)
            print("📊 Messages per chat:")
            for row in chat_counts:
                print(f"  Chat {row['chat_id']}: {row['count']} messages")
            
            if chat_counts:
                # Use the chat with the most messages for testing
                test_chat_id = chat_counts[0]['chat_id']
                print(f"🎯 Using chat {test_chat_id} for testing")
                
                # Test get_messages_for_chat_today
                print("\n🔍 Testing get_messages_for_chat_today...")
                today_messages = await get_messages_for_chat_today(test_chat_id)
                print(f"✅ Found {len(today_messages)} messages for today")
                
                if today_messages:
                    print("📝 Sample messages:")
                    for i, (timestamp, sender, text) in enumerate(today_messages[:3]):
                        print(f"  {i+1}. [{timestamp}] {sender}: {text[:50]}...")
                
                # Test get_last_n_messages_in_chat
                print("\n🔍 Testing get_last_n_messages_in_chat...")
                last_messages = await get_last_n_messages_in_chat(test_chat_id, 5)
                print(f"✅ Found {len(last_messages)} recent messages")
                
                if last_messages:
                    print("📝 Recent messages:")
                    for i, (timestamp, sender, text) in enumerate(last_messages):
                        print(f"  {i+1}. [{timestamp}] {sender}: {text[:50]}...")
                
                return True
            else:
                print("❌ No messages found in database")
                return False
                
    except Exception as e:
        print(f"❌ Message retrieval test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("🧪 Testing analyze command functionality...\n")
    
    success = await test_message_retrieval()
    
    if success:
        print("\n✅ Analyze command should work correctly!")
        print("💡 If analyze command still doesn't work, the issue might be:")
        print("   - No recent messages in the chat you're testing")
        print("   - Message handler not saving messages properly")
        print("   - Bot not receiving messages due to handler setup")
    else:
        print("\n❌ Analyze command tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())