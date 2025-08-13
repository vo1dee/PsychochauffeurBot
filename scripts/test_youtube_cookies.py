#!/usr/bin/env python3
"""
Test script to check YouTube cookie authentication with yt-dlp.
This script helps diagnose cookie-related issues for YouTube downloads.
"""

import subprocess
import sys
import os
from typing import List, Tuple

def test_browser_cookies() -> List[Tuple[str, bool, str]]:
    """Test cookie access for different browsers."""
    browsers = ["chrome", "firefox", "safari", "edge"]
    results = []
    
    # Test URL - a simple YouTube video
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    for browser in browsers:
        print(f"Testing {browser} cookies...")
        try:
            result = subprocess.run([
                "yt-dlp",
                "--cookies-from-browser", browser,
                "--simulate",
                "--get-title",
                test_url
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                title = result.stdout.strip()
                results.append((browser, True, f"Success: {title}"))
                print(f"  ✅ {browser}: {title}")
            else:
                error_msg = result.stderr.strip()
                results.append((browser, False, error_msg))
                print(f"  ❌ {browser}: {error_msg}")
                
        except subprocess.TimeoutExpired:
            results.append((browser, False, "Timeout"))
            print(f"  ⏰ {browser}: Timeout")
        except FileNotFoundError:
            results.append((browser, False, "yt-dlp not found"))
            print(f"  ❌ {browser}: yt-dlp not found")
        except Exception as e:
            results.append((browser, False, str(e)))
            print(f"  ❌ {browser}: {e}")
    
    return results

def test_youtube_shorts_download():
    """Test downloading a YouTube Shorts video with cookies."""
    # Use the URL from your error log
    test_url = "https://youtube.com/shorts/anOe3Q1vIS4"
    
    print(f"\nTesting YouTube Shorts download: {test_url}")
    
    # Try with different cookie strategies
    strategies = [
        (["--cookies-from-browser", "chrome"], "Chrome cookies"),
        (["--cookies-from-browser", "firefox"], "Firefox cookies"),
        (["--cookies-from-browser", "safari"], "Safari cookies"),
        ([], "No cookies")
    ]
    
    for args, description in strategies:
        print(f"\nTrying {description}...")
        try:
            cmd = ["yt-dlp", "--simulate", "--get-title"] + args + [test_url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0:
                title = result.stdout.strip()
                print(f"  ✅ Success with {description}: {title}")
                return True
            else:
                error_msg = result.stderr.strip()
                print(f"  ❌ Failed with {description}: {error_msg}")
                
        except subprocess.TimeoutExpired:
            print(f"  ⏰ Timeout with {description}")
        except Exception as e:
            print(f"  ❌ Error with {description}: {e}")
    
    return False

def check_yt_dlp_version():
    """Check yt-dlp version and basic functionality."""
    print("Checking yt-dlp installation...")
    try:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ yt-dlp version: {version}")
            return True
        else:
            print(f"❌ yt-dlp version check failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ yt-dlp not found. Please install it first.")
        return False
    except Exception as e:
        print(f"❌ Error checking yt-dlp: {e}")
        return False

def main():
    """Main test function."""
    print("YouTube Cookie Authentication Test")
    print("=" * 40)
    
    # Check yt-dlp installation
    if not check_yt_dlp_version():
        sys.exit(1)
    
    print("\n" + "=" * 40)
    print("Testing browser cookie access...")
    print("=" * 40)
    
    # Test browser cookies
    results = test_browser_cookies()
    
    # Summary
    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)
    
    working_browsers = [browser for browser, success, _ in results if success]
    if working_browsers:
        print(f"✅ Working browsers: {', '.join(working_browsers)}")
    else:
        print("❌ No browsers with accessible cookies found")
    
    # Test the specific failing URL
    print("\n" + "=" * 40)
    print("Testing problematic YouTube Shorts URL...")
    print("=" * 40)
    
    success = test_youtube_shorts_download()
    
    if success:
        print("\n✅ YouTube Shorts download should work now!")
    else:
        print("\n❌ YouTube Shorts download still failing.")
        print("\nTroubleshooting suggestions:")
        print("1. Make sure you're logged into YouTube in your browser")
        print("2. Try visiting the video URL in your browser first")
        print("3. Update yt-dlp: pip install --upgrade yt-dlp")
        print("4. Clear browser cache and cookies, then log back into YouTube")

if __name__ == "__main__":
    main()