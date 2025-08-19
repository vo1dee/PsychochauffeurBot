#!/usr/bin/env python3
"""
Test the bot's video download functionality directly.
"""

import asyncio
import os
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.video_downloader import VideoDownloader
from modules.url_processor import extract_urls

async def test_video_download():
    """Test video download functionality."""
    print("🎬 Testing Bot Video Download Functionality")
    print("=" * 50)
    
    # Initialize video downloader
    downloader = VideoDownloader(extract_urls_func=extract_urls)
    
    # Test URLs from your error logs
    test_urls = [
        "https://youtube.com/shorts/aV3v4rY5lAc",
        "https://youtube.com/shorts/REgWLOCgvT4",
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n📹 Test {i}: {url}")
        print("-" * 40)
        
        try:
            filename, title = await downloader.download_video(url)
            
            if filename and os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print(f"✅ Download successful!")
                print(f"   File: {filename}")
                print(f"   Title: {title}")
                print(f"   Size: {file_size} bytes")
                
                # Clean up test file
                try:
                    os.remove(filename)
                    print(f"   Cleaned up test file")
                except:
                    pass
            else:
                print(f"❌ Download failed - no file returned")
                
        except Exception as e:
            print(f"❌ Download error: {e}")
    
    print(f"\n🎯 Test completed!")
    print(f"If downloads were successful, the bot should work correctly.")

if __name__ == "__main__":
    asyncio.run(test_video_download())