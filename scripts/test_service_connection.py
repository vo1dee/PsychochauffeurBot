#!/usr/bin/env python3
"""
Test script to verify the YouTube download service is working properly.
"""

import asyncio
import aiohttp
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_service_health():
    """Test if the download service is healthy."""
    service_url = os.getenv('YTDL_SERVICE_URL')
    api_key = os.getenv('YTDL_SERVICE_API_KEY')
    
    if not service_url or not api_key:
        print("❌ Service URL or API key not configured")
        print(f"   YTDL_SERVICE_URL: {service_url}")
        print(f"   YTDL_SERVICE_API_KEY: {'***' if api_key else 'Not set'}")
        return False
    
    print(f"Testing service at: {service_url}")
    
    try:
        health_url = f"{service_url.rstrip('/')}/health"
        headers = {"X-API-Key": api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(health_url, headers=headers, timeout=10, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Service health check successful")
                    print(f"   Status: {data.get('status')}")
                    print(f"   yt-dlp version: {data.get('yt_dlp_version')}")
                    print(f"   FFmpeg available: {data.get('ffmpeg_available')}")
                    return True
                else:
                    print(f"❌ Service health check failed with status {response.status}")
                    text = await response.text()
                    print(f"   Response: {text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Service health check failed: {e}")
        return False

async def test_service_download():
    """Test downloading the problematic YouTube Shorts URL via service."""
    service_url = os.getenv('YTDL_SERVICE_URL')
    api_key = os.getenv('YTDL_SERVICE_API_KEY')
    
    if not service_url or not api_key:
        print("❌ Service not configured for download test")
        return False
    
    test_url = "https://youtube.com/shorts/anOe3Q1vIS4"
    print(f"\nTesting service download for: {test_url}")
    
    try:
        download_url = f"{service_url.rstrip('/')}/download"
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        payload = {
            "url": test_url,
            "format": "best[ext=mp4]/best"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(download_url, json=payload, headers=headers, timeout=120, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Service download request successful")
                    print(f"   Success: {data.get('success')}")
                    print(f"   Title: {data.get('title')}")
                    print(f"   File size: {data.get('file_size_mb')} MB")
                    print(f"   Quality: {data.get('quality')}")
                    
                    if data.get('status') == 'processing':
                        print(f"   Download ID: {data.get('download_id')}")
                        print("   Status: Processing in background")
                        
                        # Poll for completion
                        download_id = data.get('download_id')
                        if download_id:
                            await poll_download_status(session, service_url, api_key, download_id)
                    
                    return True
                else:
                    print(f"❌ Service download failed with status {response.status}")
                    text = await response.text()
                    print(f"   Response: {text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Service download failed: {e}")
        return False

async def poll_download_status(session, service_url, api_key, download_id):
    """Poll the download status until completion."""
    status_url = f"{service_url.rstrip('/')}/status/{download_id}"
    headers = {"X-API-Key": api_key}
    
    print("   Polling download status...")
    
    for attempt in range(12):  # Poll for up to 2 minutes
        try:
            await asyncio.sleep(10)  # Wait 10 seconds between polls
            
            async with session.get(status_url, headers=headers, timeout=10, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get('status')
                    progress = data.get('progress', 0)
                    
                    print(f"   Status: {status} ({progress}%)")
                    
                    if status == 'completed':
                        print("✅ Background download completed successfully")
                        print(f"   Title: {data.get('title')}")
                        print(f"   File size: {data.get('file_size_mb')} MB")
                        print(f"   Quality: {data.get('quality')}")
                        return True
                    elif status == 'failed':
                        print(f"❌ Background download failed: {data.get('error')}")
                        return False
                    # Continue polling if still processing
                else:
                    print(f"   Status check failed: {response.status}")
                    
        except Exception as e:
            print(f"   Status check error: {e}")
    
    print("⏰ Download status polling timed out")
    return False

async def main():
    """Main test function."""
    print("YouTube Download Service Test")
    print("=" * 40)
    
    # Test service health
    print("Step 1: Testing service health")
    print("-" * 30)
    health_ok = await test_service_health()
    
    if not health_ok:
        print("\n❌ Service health check failed. Cannot proceed with download test.")
        return
    
    # Test service download
    print("\nStep 2: Testing service download")
    print("-" * 30)
    download_ok = await test_service_download()
    
    # Summary
    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)
    
    if health_ok and download_ok:
        print("✅ Service is working correctly!")
        print("   The bot should be able to download YouTube videos via the service.")
    elif health_ok:
        print("⚠️  Service is healthy but download test failed.")
        print("   Check service logs for more details.")
    else:
        print("❌ Service is not working properly.")
        print("   Check service configuration and ensure it's running.")

if __name__ == "__main__":
    asyncio.run(main())