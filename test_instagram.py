#!/usr/bin/env python3
"""
Test script for Instagram video downloads
Usage: python test_instagram.py <instagram_url>
"""

import sys
import os
import asyncio
from modules.video_downloader import VideoDownloader

async def test_instagram_download(url):
    """Test Instagram video download functionality"""
    print(f"🔄 Testing Instagram download for: {url}")

    # Initialize downloader
    downloader = VideoDownloader()

    try:
        # Attempt download
        file_path, title = await downloader.download_video(url)

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print("✅ Download successful!")
            print(f"   📁 File: {file_path}")
            print(f"   📊 Size: {file_size / (1024*1024):.2f} MB")
            print(f"   📝 Title: {title}")

            # Clean up test file
            try:
                os.remove(file_path)
                print("🗑️  Test file cleaned up")
            except:
                pass

            return True
        else:
            print("❌ Download failed - no file returned")
            return False

    except Exception as e:
        print(f"❌ Download error: {str(e)}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_instagram.py <instagram_url>")
        print("Example: python test_instagram.py https://www.instagram.com/p/ABC123/")
        sys.exit(1)

    url = sys.argv[1]

    # Validate URL
    if 'instagram.com' not in url:
        print("❌ Please provide a valid Instagram URL")
        sys.exit(1)

    # Run test
    try:
        result = asyncio.run(test_instagram_download(url))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()