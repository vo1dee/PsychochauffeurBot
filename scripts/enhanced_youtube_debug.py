#!/usr/bin/env python3
"""
Enhanced YouTube download debugging script with comprehensive logging.
"""

import asyncio
import aiohttp
import os
import sys
import subprocess
import uuid
from urllib.parse import urljoin
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.logger import error_logger

# Load environment variables
load_dotenv()

class YouTubeDebugger:
    def __init__(self):
        self.service_url = os.getenv('YTDL_SERVICE_URL')
        self.api_key = os.getenv('YTDL_SERVICE_API_KEY')
        self.max_retries = int(os.getenv('YTDL_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('YTDL_RETRY_DELAY', '1'))
        
        # Test URLs from your error logs
        self.test_urls = [
            "https://youtube.com/shorts/aV3v4rY5lAc",
            "https://youtube.com/shorts/REgWLOCgvT4",
            "https://youtube.com/shorts/anOe3Q1vIS4",  # From test script
        ]
        
        print("🔍 YouTube Download Debugger")
        print("=" * 50)
        print(f"Service URL: {self.service_url}")
        print(f"API Key: {'***' + self.api_key[-4:] if self.api_key and len(self.api_key) > 4 else 'Not configured'}")
        print(f"Test URLs: {len(self.test_urls)}")

    async def test_service_health(self):
        """Test service health with detailed logging."""
        print("\n🏥 Testing Service Health")
        print("-" * 30)
        
        if not self.service_url or not self.api_key:
            print("❌ Service not configured")
            print(f"   YTDL_SERVICE_URL: {self.service_url}")
            print(f"   YTDL_SERVICE_API_KEY: {'Set' if self.api_key else 'Not set'}")
            return False
        
        health_url = urljoin(self.service_url, "health")
        headers = {"X-API-Key": self.api_key}
        
        print(f"Health URL: {health_url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                print("Making health check request...")
                async with session.get(health_url, headers=headers, timeout=10, ssl=False) as response:
                    print(f"Response status: {response.status}")
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            print("✅ Service is healthy!")
                            print(f"   Status: {data.get('status', 'unknown')}")
                            print(f"   yt-dlp version: {data.get('yt_dlp_version', 'unknown')}")
                            print(f"   FFmpeg: {data.get('ffmpeg_available', 'unknown')}")
                            return True
                        except Exception as e:
                            print(f"⚠️ Health check returned 200 but JSON parsing failed: {e}")
                            return True
                    else:
                        text = await response.text()
                        print(f"❌ Health check failed")
                        print(f"   Response: {text[:200]}...")
                        return False
                        
        except aiohttp.ClientConnectorError as e:
            print(f"❌ Connection failed: {e}")
            print("   This usually means:")
            print("   - Service is not running")
            print("   - Wrong URL/port")
            print("   - Firewall blocking connection")
            return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

    async def test_service_download(self, url):
        """Test service download with detailed logging."""
        print(f"\n📥 Testing Service Download: {url}")
        print("-" * 50)
        
        if not self.service_url or not self.api_key:
            print("❌ Service not configured")
            return False
        
        download_url = urljoin(self.service_url, "download")
        headers = {"X-API-Key": self.api_key}
        payload = {"url": url, "format": "best[ext=mp4]/best"}
        
        print(f"Download URL: {download_url}")
        print(f"Payload: {payload}")
        
        try:
            async with aiohttp.ClientSession() as session:
                print("Making download request...")
                async with session.post(download_url, json=payload, headers=headers, timeout=60, ssl=False) as response:
                    print(f"Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"Response data: {data}")
                        
                        if data.get("success"):
                            print("✅ Service download successful!")
                            print(f"   Title: {data.get('title', 'Unknown')}")
                            print(f"   Status: {data.get('status', 'Unknown')}")
                            
                            if data.get('status') == 'processing':
                                print(f"   Download ID: {data.get('download_id')}")
                                print("   Background processing - would poll for completion")
                            
                            return True
                        else:
                            print(f"❌ Service reported failure: {data.get('error', 'Unknown error')}")
                            return False
                    else:
                        text = await response.text()
                        print(f"❌ Service download failed")
                        print(f"   Response: {text[:300]}...")
                        return False
                        
        except Exception as e:
            print(f"❌ Service download error: {e}")
            return False

    async def test_direct_strategies(self, url):
        """Test direct yt-dlp strategies."""
        print(f"\n🎯 Testing Direct Strategies: {url}")
        print("-" * 50)
        
        strategies = [
            {
                'name': 'Android client',
                'format': '18/22/best[ext=mp4]/best',
                'args': [
                    '--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                    '--extractor-args', 'youtube:player_client=android',
                ]
            },
            {
                'name': 'iOS client',
                'format': 'best[vcodec^=avc1]/18/22/best',
                'args': [
                    '--user-agent', 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
                    '--extractor-args', 'youtube:player_client=ios',
                ]
            },
            {
                'name': 'Web client',
                'format': '18/22/best[ext=mp4]/best',
                'args': [
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    '--referer', 'https://www.youtube.com/',
                    '--extractor-args', 'youtube:player_client=web',
                ]
            }
        ]
        
        for i, strategy in enumerate(strategies, 1):
            print(f"\n📋 Strategy {i}: {strategy['name']}")
            
            success = await self._test_single_strategy(url, strategy)
            if success:
                print(f"✅ Strategy '{strategy['name']}' works!")
                return True
            else:
                print(f"❌ Strategy '{strategy['name']}' failed")
        
        print("❌ All direct strategies failed")
        return False

    async def _test_single_strategy(self, url, strategy):
        """Test a single yt-dlp strategy."""
        unique_filename = f"debug_{uuid.uuid4().hex[:8]}.mp4"
        output_path = f"downloads/{unique_filename}"
        
        # Ensure downloads directory exists
        os.makedirs("downloads", exist_ok=True)
        
        cmd = [
            'yt-dlp', url,
            '-o', output_path,
            '--merge-output-format', 'mp4',
            '--no-check-certificate',
            '--geo-bypass',
            '--ignore-errors',
            '--no-playlist',
            '--socket-timeout', '30',
            '--retries', '1',
            '-f', strategy['format']
        ] + strategy['args']
        
        print(f"   Command: {' '.join(cmd[:8])}... (truncated)")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            
            if process.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"   ✅ Success: {file_size} bytes downloaded")
                
                # Clean up
                try:
                    os.remove(output_path)
                except:
                    pass
                
                return True
            else:
                stderr_text = stderr.decode()
                print(f"   ❌ Failed (code {process.returncode})")
                print(f"   Error: {stderr_text[:200]}...")
                return False
                
        except asyncio.TimeoutError:
            print(f"   ⏰ Timeout after 60 seconds")
            return False
        except Exception as e:
            print(f"   ❌ Execution error: {e}")
            return False
        finally:
            # Clean up any partial files
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass

    async def run_comprehensive_test(self):
        """Run comprehensive test on all URLs."""
        print("\n🚀 Starting Comprehensive Test")
        print("=" * 50)
        
        # Test service health first
        service_healthy = await self.test_service_health()
        
        results = {
            'service_healthy': service_healthy,
            'service_downloads': [],
            'direct_downloads': []
        }
        
        for url in self.test_urls:
            print(f"\n🎬 Testing URL: {url}")
            print("=" * 60)
            
            # Test service download if healthy
            if service_healthy:
                service_success = await self.test_service_download(url)
                results['service_downloads'].append((url, service_success))
            else:
                results['service_downloads'].append((url, False))
            
            # Test direct strategies
            direct_success = await self.test_direct_strategies(url)
            results['direct_downloads'].append((url, direct_success))
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 60)
        
        print(f"Service Health: {'✅ Healthy' if results['service_healthy'] else '❌ Unhealthy'}")
        
        service_success_count = sum(1 for _, success in results['service_downloads'] if success)
        direct_success_count = sum(1 for _, success in results['direct_downloads'] if success)
        
        print(f"\nService Downloads: {service_success_count}/{len(self.test_urls)} successful")
        for url, success in results['service_downloads']:
            status = "✅" if success else "❌"
            print(f"   {status} {url}")
        
        print(f"\nDirect Downloads: {direct_success_count}/{len(self.test_urls)} successful")
        for url, success in results['direct_downloads']:
            status = "✅" if success else "❌"
            print(f"   {status} {url}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        print("-" * 30)
        
        if service_success_count > 0:
            print("✅ Service is working - bot should use service for downloads")
        elif direct_success_count > 0:
            print("⚠️ Service issues but direct strategies work - bot will use fallback")
        else:
            print("❌ Both service and direct strategies failing")
            print("   Possible causes:")
            print("   - YouTube blocking this IP/region")
            print("   - yt-dlp needs updating")
            print("   - Network connectivity issues")
            print("   - All test videos are geo-blocked")
        
        if not results['service_healthy']:
            print(f"\n🔧 Service Issues:")
            print(f"   - Check if service is running: systemctl status ytdl-service")
            print(f"   - Check service logs: journalctl -u ytdl-service -f")
            print(f"   - Verify service URL and API key in .env")
            print(f"   - Test service manually: curl -H 'X-API-Key: {self.api_key}' {self.service_url}/health")

async def main():
    """Main function."""
    debugger = YouTubeDebugger()
    await debugger.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())