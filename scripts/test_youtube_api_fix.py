#!/usr/bin/env python3
"""
Test script to check YouTube API extraction with different strategies.
This script helps diagnose YouTube API extraction failures.
"""

import subprocess
import sys
import os
import asyncio
from typing import List, Tuple

async def test_youtube_strategies(url: str) -> List[Tuple[str, bool, str]]:
    """Test different YouTube extraction strategies."""
    
    strategies = [
        # Strategy 1: Web client with Firefox cookies
        {
            'name': 'Web + Firefox Cookies',
            'args': [
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--referer', 'https://www.youtube.com/',
                '--extractor-args', 'youtube:player_client=web',
                '--cookies-from-browser', 'firefox',
                '--sleep-interval', '1',
                '--max-sleep-interval', '3',
            ]
        },
        # Strategy 2: Android client
        {
            'name': 'Android Client',
            'args': [
                '--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                '--extractor-args', 'youtube:player_client=android',
                '--cookies-from-browser', 'firefox',
            ]
        },
        # Strategy 3: iOS client
        {
            'name': 'iOS Client',
            'args': [
                '--user-agent', 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
                '--extractor-args', 'youtube:player_client=ios',
            ]
        },
        # Strategy 4: Basic web
        {
            'name': 'Basic Web',
            'args': [
                '--user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                '--extractor-args', 'youtube:player_client=web',
            ]
        },
        # Strategy 5: No special args (baseline)
        {
            'name': 'Default',
            'args': []
        }
    ]
    
    results = []
    
    for strategy in strategies:
        print(f"Testing {strategy['name']}...")
        
        try:
            cmd = ['yt-dlp', '--simulate', '--get-title'] + strategy['args'] + [url]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode == 0:
                title = stdout.decode().strip()
                results.append((strategy['name'], True, f"Success: {title}"))
                print(f"  ✅ {strategy['name']}: {title}")
                return results  # Return on first success
            else:
                error_msg = stderr.decode().strip()
                results.append((strategy['name'], False, error_msg))
                print(f"  ❌ {strategy['name']}: {error_msg[:100]}...")
                
        except asyncio.TimeoutError:
            results.append((strategy['name'], False, "Timeout"))
            print(f"  ⏰ {strategy['name']}: Timeout")
        except Exception as e:
            results.append((strategy['name'], False, str(e)))
            print(f"  ❌ {strategy['name']}: {e}")
    
    return results

async def test_yt_dlp_update():
    """Test if yt-dlp needs updating."""
    print("Checking yt-dlp version and updates...")
    
    try:
        # Get current version
        result = await asyncio.create_subprocess_exec(
            'yt-dlp', '--version',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10)
        
        if result.returncode == 0:
            current_version = stdout.decode().strip()
            print(f"Current version: {current_version}")
            
            # Check for updates
            print("Checking for updates...")
            update_result = await asyncio.create_subprocess_exec(
                'yt-dlp', '--update',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            update_stdout, update_stderr = await asyncio.wait_for(update_result.communicate(), timeout=30)
            
            if update_result.returncode == 0:
                update_output = update_stdout.decode().strip()
                if "up to date" in update_output.lower():
                    print("✅ yt-dlp is up to date")
                    return True
                else:
                    print(f"📦 yt-dlp updated: {update_output}")
                    return True
            else:
                print(f"❌ Update failed: {update_stderr.decode()}")
                return False
        else:
            print(f"❌ Version check failed: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking yt-dlp: {e}")
        return False

async def main():
    """Main test function."""
    print("YouTube API Extraction Test")
    print("=" * 50)
    
    # Test the problematic URL
    test_url = "https://youtube.com/shorts/anOe3Q1vIS4"
    
    # First, try to update yt-dlp
    print("Step 1: Checking yt-dlp version and updates")
    print("-" * 50)
    await test_yt_dlp_update()
    
    print(f"\nStep 2: Testing YouTube API extraction strategies")
    print("-" * 50)
    print(f"Testing URL: {test_url}")
    print()
    
    # Test different strategies
    results = await test_youtube_strategies(test_url)
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    successful_strategies = [name for name, success, _ in results if success]
    if successful_strategies:
        print(f"✅ Working strategies: {', '.join(successful_strategies)}")
        print("\n🎉 YouTube API extraction should work now!")
    else:
        print("❌ All strategies failed.")
        print("\nTroubleshooting suggestions:")
        print("1. Update yt-dlp: pip install --upgrade yt-dlp")
        print("2. Check network connectivity to YouTube")
        print("3. Try using a VPN if geo-blocked")
        print("4. Wait a few minutes and try again (YouTube API issues are often temporary)")
        print("5. Check if the specific video is still available")
        
        # Show detailed errors
        print("\nDetailed errors:")
        for name, success, message in results:
            if not success:
                print(f"  {name}: {message[:150]}...")

if __name__ == "__main__":
    asyncio.run(main())