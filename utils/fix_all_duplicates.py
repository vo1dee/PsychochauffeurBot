#!/usr/bin/env python3
"""
Comprehensive script to fix all duplicate user issues in the database.
This script will merge duplicate users and their messages, keeping the user with more messages.
"""

import asyncio
import os
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import Database

# Load environment variables
load_dotenv()

async def get_duplicate_usernames():
    """Get all usernames with duplicates."""
    
    await Database.initialize()
    pool = await Database.get_pool()
    
    async with pool.acquire() as conn:
        duplicate_usernames = await conn.fetch("""
            SELECT username, COUNT(*) as count
            FROM users 
            WHERE username IS NOT NULL
            GROUP BY username 
            HAVING COUNT(*) > 1
            ORDER BY count DESC, username
        """)
        
        return [row['username'] for row in duplicate_usernames]

async def fix_duplicate_for_username(username):
    """Fix duplicate users for a specific username."""
    
    pool = await Database.get_pool()
    
    async with pool.acquire() as conn:
        # Get all users with this username
        users = await conn.fetch("""
            SELECT user_id, username, first_name, last_name, created_at
            FROM users 
            WHERE username = $1
            ORDER BY created_at ASC
        """, username)
        
        if len(users) < 2:
            return f"Only {len(users)} user(s) found for {username}, skipping"
        
        print(f"\n🔧 Fixing duplicates for @{username} ({len(users)} users):")
        
        # Count messages for each user
        user_message_counts = []
        for user in users:
            message_count = await conn.fetchval("""
                SELECT COUNT(*) FROM messages WHERE user_id = $1
            """, user['user_id'])
            
            user_message_counts.append({
                'user': user,
                'message_count': message_count
            })
            
            print(f"   User {user['user_id']} ({user['first_name']} {user['last_name'] or ''}): {message_count} messages")
        
        # Sort by message count (descending)
        user_message_counts.sort(key=lambda x: x['message_count'], reverse=True)
        
        # Keep the user with the most messages
        keep_user = user_message_counts[0]['user']
        delete_users = [item['user'] for item in user_message_counts[1:]]
        
        print(f"   ✅ Keeping user {keep_user['user_id']} (most messages)")
        
        total_messages_moved = 0
        
        # Start transaction
        async with conn.transaction():
            # Move messages from all other users to the main user
            for delete_user in delete_users:
                moved_count = await conn.execute("""
                    UPDATE messages 
                    SET user_id = $1 
                    WHERE user_id = $2
                """, keep_user['user_id'], delete_user['user_id'])
                
                moved_count = int(moved_count.split()[-1])
                total_messages_moved += moved_count
                
                print(f"   📤 Moved {moved_count} messages from user {delete_user['user_id']}")
                
                # Delete the duplicate user
                await conn.execute("""
                    DELETE FROM users WHERE user_id = $1
                """, delete_user['user_id'])
                
                print(f"   🗑️  Deleted user {delete_user['user_id']}")
        
        # Verify final count
        final_count = await conn.fetchval("""
            SELECT COUNT(*) FROM messages WHERE user_id = $1
        """, keep_user['user_id'])
        
        print(f"   ✅ Final message count for user {keep_user['user_id']}: {final_count}")
        
        return f"Fixed {username}: moved {total_messages_moved} messages, deleted {len(delete_users)} users"

async def fix_all_duplicates():
    """Fix all duplicate usernames in the database."""
    
    print("🚀 Starting comprehensive duplicate user fix...")
    print("=" * 60)
    
    # Get all duplicate usernames
    duplicate_usernames = await get_duplicate_usernames()
    
    if not duplicate_usernames:
        print("✅ No duplicate usernames found!")
        return
    
    print(f"Found {len(duplicate_usernames)} usernames with duplicates:")
    for username in duplicate_usernames:
        print(f"   - @{username}")
    
    # Ask for confirmation
    response = input(f"\nProceed with fixing all {len(duplicate_usernames)} duplicate usernames? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ Operation cancelled")
        return
    
    # Fix each duplicate username
    results = []
    for i, username in enumerate(duplicate_usernames, 1):
        print(f"\n[{i}/{len(duplicate_usernames)}] Processing @{username}...")
        try:
            result = await fix_duplicate_for_username(username)
            results.append(result)
        except Exception as e:
            error_msg = f"Error fixing {username}: {e}"
            print(f"   ❌ {error_msg}")
            results.append(error_msg)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    for result in results:
        print(f"   {result}")
    
    print(f"\n✅ Processed {len(duplicate_usernames)} duplicate usernames")

async def add_unique_constraint():
    """Add unique constraint to prevent future duplicates."""
    
    await Database.initialize()
    pool = await Database.get_pool()
    
    print("\n🔧 Adding unique constraint to prevent future duplicates...")
    print("=" * 60)
    
    async with pool.acquire() as conn:
        try:
            # Check if constraint already exists
            constraint_exists = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints 
                WHERE constraint_name = 'unique_username' 
                AND table_name = 'users'
            """)
            
            if constraint_exists:
                print("✅ Unique constraint already exists")
                return
            
            # Add unique constraint
            await conn.execute("""
                ALTER TABLE users ADD CONSTRAINT unique_username UNIQUE (username)
            """)
            
            print("✅ Added unique constraint on username")
            
        except Exception as e:
            print(f"❌ Error adding constraint: {e}")
            print("This might be because there are still duplicate usernames in the database")

async def verify_fixes():
    """Verify that all fixes worked."""
    
    await Database.initialize()
    pool = await Database.get_pool()
    
    print("\n🔍 Verifying fixes...")
    print("=" * 60)
    
    async with pool.acquire() as conn:
        # Check for remaining duplicates
        remaining_duplicates = await conn.fetch("""
            SELECT username, COUNT(*) as count
            FROM users 
            WHERE username IS NOT NULL
            GROUP BY username 
            HAVING COUNT(*) > 1
            ORDER BY count DESC, username
        """)
        
        if remaining_duplicates:
            print(f"❌ Still have {len(remaining_duplicates)} usernames with duplicates:")
            for row in remaining_duplicates:
                print(f"   - @{row['username']}: {row['count']} entries")
        else:
            print("✅ No duplicate usernames remaining!")
        
        # Check specific users that were problematic
        test_users = ['kkazakova', 'vo1dee', 'daneryazmur']
        for username in test_users:
            users = await conn.fetch("""
                SELECT user_id, username, first_name, last_name
                FROM users 
                WHERE username = $1
            """, username)
            
            print(f"\n📊 @{username}: {len(users)} user(s)")
            for user in users:
                message_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM messages WHERE user_id = $1
                """, user['user_id'])
                print(f"   - User {user['user_id']}: {message_count} messages")

async def main():
    """Main function to run the comprehensive fix."""
    print("🚀 Starting comprehensive duplicate user fix...")
    
    try:
        await fix_all_duplicates()
        await add_unique_constraint()
        await verify_fixes()
        
        print("\n" + "=" * 60)
        print("✅ Comprehensive fix completed!")
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 