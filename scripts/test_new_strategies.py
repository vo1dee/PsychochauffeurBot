#!/usr/bin/env python3
"""
Test script for the new YouTube download strategies.
"""

import asyncio
import subprocess
import os
import uuid

async def test_strategy(strategy_name, url, format_str, args):
    """Test a single YouTube download strategy."""
    print(f"\n🧪 Testing: {strategy_name}")
    print(f"   Format: {format_str}")
    print(f"   Args: {' '.join(args[:4])}...")
    
    # Create unique output file
    unique_filename = f"test_{uuid.uuid4().hex[:8]}.mp4"
    output_template = f"downloads/{unique_filename}"
    
    # Ensure downloads directory exists
    os.makedirs("downloads", exist_ok=True)
    
    # Build command
    cmd = [
        'yt-dlp', url,
        '-o', output_template,
        '--merge-output-format', 'mp4',
        '--no-check-certificate',
        '--geo-bypass',
        '--retries', '2',
        '--fragment-retries', '3',
        '-f', format_str
    ] + args
    
    try:
        print(f"   Executing: {' '.join(cmd[:8])}... (truncated)")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)
        
        if process.returncode == 0 and os.path.exists(output_template):
            file_size = os.path.getsize(output_template)
            print(f"   ✅ SUCCESS: Downloaded {file_size} bytes")
            
            # Clean up test file
            try:
                os.remove(output_template)
            except:
                pass
            
            return True
        else:
            stderr_text = stderr.decode()
            print(f"   ❌ FAILED: {stderr_text[:100]}...")
            return False
            
    except asyncio.TimeoutError:
        print(f"   ⏰ TIMEOUT: Strategy took too long")
        return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    finally:
        # Clean up any partial files
        if os.path.exists(output_template):
            try:
                os.remove(output_template)
            except:
                pass

async def main():
    """Test all strategies."""
    print("YouTube Download Strategy Test")
    print("=" * 50)
    
    # Test URL - the problematic one from your logs
    test_url = "https://youtube.com/shorts/anOe3Q1vIS4"
    print(f"Testing URL: {test_url}")
    
    # Define strategies (same as in the bot)
    strategies = [
        {
            'name': 'Android client with simple formats',
            'format': '18/22/best[ext=mp4]/best',
            'args': [
                '--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                '--extractor-args', 'youtube:player_client=android',
                '--sleep-interval', '1',
                '--max-sleep-interval', '3',
            ]
        },
        {
            'name': 'iOS client with H.264',
            'format': 'bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]/best',
            'args': [
                '--user-agent', 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
                '--extractor-args', 'youtube:player_client=ios',
            ]
        },
        {
            'name': 'Web client with headers',
            'format': '18/22/best[ext=mp4]/best',
            'args': [
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--referer', 'https://www.youtube.com/',
                '--extractor-args', 'youtube:player_client=web',
                '--sleep-interval', '1',
                '--max-sleep-interval', '3',
            ]
        },
        {
            'name': 'Any format fallback',
            'format': 'best',
            'args': [
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--extractor-args', 'youtube:player_client=web',
            ]
        }
    ]
    
    # Test each strategy
    results = []
    for strategy in strategies:
        success = await test_strategy(
            strategy['name'],
            test_url,
            strategy['format'],
            strategy['args']
        )
        results.append((strategy['name'], success))
        
        # If one succeeds, we can stop (like the bot does)
        if success:
            print(f"\n🎉 Found working strategy: {strategy['name']}")
            break
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    successful_strategies = [name for name, success in results if success]
    if successful_strategies:
        print(f"✅ Working strategies: {', '.join(successful_strategies)}")
        print("\n🎯 The bot should now be able to download YouTube videos!")
    else:
        print("❌ All strategies failed.")
        print("\nPossible issues:")
        print("1. YouTube is blocking all requests from this IP")
        print("2. The specific video is geo-blocked or unavailable")
        print("3. yt-dlp needs to be updated further")
        print("4. Network connectivity issues")
        
        print(f"\nTry testing with a different video:")
        print("python scripts/test_new_strategies.py")

if __name__ == "__main__":
    asyncio.run(main())