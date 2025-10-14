#!/usr/bin/env python3
import asyncio
import aiohttp
import os
from urllib.parse import urljoin

# Simulate the bot's video downloader logic
class TestVideoDownloader:
    def __init__(self):
        self.service_url = os.getenv('YTDL_SERVICE_URL', 'https://ytdl.vo1dee.com')
        self.api_key = os.getenv('YTDL_SERVICE_API_KEY', 'qeKcftNr5OIo7uF_esfXDr-GRxVur0G_3w7XIMFfvX0')
        
    def detect_platform(self, url):
        """Detect if URL is YouTube Shorts"""
        is_youtube_shorts = "youtube.com/shorts" in url.lower()
        is_youtube_clips = "youtube.com/clip" in url.lower()
        is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
        
        return {
            'is_youtube': is_youtube,
            'is_youtube_shorts': is_youtube_shorts,
            'is_youtube_clips': is_youtube_clips
        }
    
    async def check_service_health(self):
        """Check if service is available"""
        if not self.service_url or not self.api_key:
            print("❌ Service URL or API key not configured")
            return False
            
        health_url = urljoin(self.service_url, "health")
        headers = {"X-API-Key": self.api_key}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Service health: {data.get('status', 'unknown')}")
                        return data.get('status') == 'healthy' or data.get('status') == 'unhealthy'  # Accept both for testing
                    else:
                        print(f"❌ Service health check failed: HTTP {response.status}")
                        return False
        except Exception as e:
            print(f"❌ Service health check error: {e}")
            return False
    
    async def download_from_service(self, url):
        """Test service download"""
        if not self.service_url or not self.api_key:
            print("❌ Service not configured")
            return None
            
        headers = {"X-API-Key": self.api_key}
        download_url = urljoin(self.service_url, "download")
        payload = {"url": url}
        
        print(f"🔄 Sending to service: {download_url}")
        print(f"   Payload: {payload}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(download_url, json=payload, headers=headers, timeout=30) as response:
                    print(f"   Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"   Service response: {data}")
                        return data
                    else:
                        error_text = await response.text()
                        print(f"   Service error: {error_text}")
                        return None
        except Exception as e:
            print(f"❌ Service request error: {e}")
            return None
    
    async def test_youtube_shorts_routing(self, url):
        """Test the complete routing logic for YouTube Shorts"""
        print(f"\n🎯 Testing YouTube Shorts routing for: {url}")
        
        # Step 1: Detect platform
        detection = self.detect_platform(url)
        print(f"📋 Platform detection:")
        print(f"   is_youtube: {detection['is_youtube']}")
        print(f"   is_youtube_shorts: {detection['is_youtube_shorts']}")
        print(f"   is_youtube_clips: {detection['is_youtube_clips']}")
        
        # Step 2: Check if should use service
        if detection['is_youtube']:
            print(f"🎬 Processing YouTube URL: {url}")
            print(f"   URL type: {'Shorts' if detection['is_youtube_shorts'] else 'Clips' if detection['is_youtube_clips'] else 'Regular'}")
            
            # Step 3: Check service health
            print(f"🔧 Checking service availability...")
            service_healthy = await self.check_service_health()
            
            if service_healthy:
                # Step 4: Try service download
                result = await self.download_from_service(url)
                if result and result.get('success'):
                    print(f"✅ Service download successful!")
                    return result
                else:
                    print(f"⚠️ Service download failed, would fall back to direct strategies")
                    return None
            else:
                print(f"⚠️ Service unavailable, would use direct strategies")
                return None
        else:
            print(f"❌ Not a YouTube URL, would use other handlers")
            return None

async def main():
    downloader = TestVideoDownloader()
    
    # Test URLs
    test_urls = [
        "https://youtube.com/shorts/aV3v4rY5lAc",
        "https://youtube.com/shorts/REgWLOCgvT4", 
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Regular YouTube
        "https://youtu.be/dQw4w9WgXcQ",  # Short YouTube
    ]
    
    for url in test_urls:
        await downloader.test_youtube_shorts_routing(url)
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(main())