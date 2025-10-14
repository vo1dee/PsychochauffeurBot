#!/usr/bin/env python3
"""
Debug script to identify service connectivity issues.
"""

import asyncio
import aiohttp
import os
import socket
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_basic_connectivity():
    """Test basic network connectivity."""
    print("🌐 Testing basic connectivity...")
    
    # Test DNS resolution
    try:
        socket.gethostbyname('google.com')
        print("   ✅ DNS resolution working")
    except Exception as e:
        print(f"   ❌ DNS resolution failed: {e}")
        return False
    
    # Test HTTP connectivity
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://httpbin.org/get', timeout=10) as response:
                if response.status == 200:
                    print("   ✅ HTTP connectivity working")
                    return True
                else:
                    print(f"   ❌ HTTP test failed with status {response.status}")
                    return False
    except Exception as e:
        print(f"   ❌ HTTP connectivity failed: {e}")
        return False

async def test_service_configuration():
    """Test service configuration."""
    print("\n⚙️  Testing service configuration...")
    
    service_url = os.getenv('YTDL_SERVICE_URL')
    api_key = os.getenv('YTDL_SERVICE_API_KEY')
    
    print(f"   Service URL: {service_url}")
    print(f"   API Key: {'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'Not set'}")
    
    if not service_url:
        print("   ❌ YTDL_SERVICE_URL not configured")
        return False
    
    if not api_key:
        print("   ❌ YTDL_SERVICE_API_KEY not configured")
        return False
    
    # Parse URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(service_url)
        print(f"   Scheme: {parsed.scheme}")
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        
        if parsed.scheme not in ['http', 'https']:
            print(f"   ❌ Invalid scheme: {parsed.scheme}")
            return False
            
        if not parsed.hostname:
            print("   ❌ No hostname in URL")
            return False
            
        print("   ✅ Service configuration looks valid")
        return True
        
    except Exception as e:
        print(f"   ❌ URL parsing failed: {e}")
        return False

async def test_service_reachability():
    """Test if service is reachable."""
    print("\n🔍 Testing service reachability...")
    
    service_url = os.getenv('YTDL_SERVICE_URL')
    if not service_url:
        print("   ❌ No service URL configured")
        return False
    
    from urllib.parse import urlparse
    parsed = urlparse(service_url)
    host = parsed.hostname
    port = parsed.port or (80 if parsed.scheme == 'http' else 443)
    
    # Test TCP connectivity
    print(f"   Testing TCP connection to {host}:{port}...")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=10.0
        )
        writer.close()
        await writer.wait_closed()
        print(f"   ✅ TCP connection successful")
        return True
    except asyncio.TimeoutError:
        print(f"   ❌ TCP connection timeout")
        return False
    except Exception as e:
        print(f"   ❌ TCP connection failed: {e}")
        return False

async def test_service_health():
    """Test service health endpoint."""
    print("\n🏥 Testing service health...")
    
    service_url = os.getenv('YTDL_SERVICE_URL')
    api_key = os.getenv('YTDL_SERVICE_API_KEY')
    
    if not service_url or not api_key:
        print("   ❌ Service not configured")
        return False
    
    try:
        health_url = f"{service_url.rstrip('/')}/health"
        headers = {"X-API-Key": api_key}
        
        print(f"   Requesting: {health_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(health_url, headers=headers, timeout=10, ssl=False) as response:
                print(f"   Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Service health check successful")
                    print(f"      Status: {data.get('status')}")
                    print(f"      yt-dlp version: {data.get('yt_dlp_version')}")
                    print(f"      FFmpeg: {data.get('ffmpeg_available')}")
                    return True
                elif response.status == 403:
                    print("   ❌ Authentication failed (invalid API key)")
                    return False
                else:
                    text = await response.text()
                    print(f"   ❌ Health check failed: {text}")
                    return False
                    
    except aiohttp.ClientConnectorError as e:
        print(f"   ❌ Connection failed: {e}")
        return False
    except asyncio.TimeoutError:
        print("   ❌ Request timeout")
        return False
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
        return False

async def suggest_solutions():
    """Suggest solutions based on test results."""
    print("\n💡 TROUBLESHOOTING SUGGESTIONS")
    print("=" * 50)
    
    service_url = os.getenv('YTDL_SERVICE_URL')
    if not service_url:
        print("1. Configure YTDL_SERVICE_URL in your .env file")
        print("   Example: YTDL_SERVICE_URL=http://localhost:8000")
        return
    
    from urllib.parse import urlparse
    parsed = urlparse(service_url)
    
    if parsed.hostname in ['localhost', '127.0.0.1']:
        print("🔧 Service is configured for localhost:")
        print("   1. Make sure the service is running on the same machine")
        print("   2. Check if service is actually listening on port", parsed.port or 8000)
        print("   3. Try: curl http://localhost:8000/health")
        
    elif parsed.hostname.startswith('192.168.') or parsed.hostname.startswith('10.'):
        print("🔧 Service is configured for local network:")
        print("   1. Make sure both bot and service are on same network")
        print("   2. Check firewall rules")
        print("   3. Verify service is binding to 0.0.0.0, not just localhost")
        
    else:
        print("🔧 Service is configured for remote host:")
        print("   1. Check if service is publicly accessible")
        print("   2. Verify firewall/security group settings")
        print("   3. Check if service is running and healthy")
    
    print("\n🔧 General troubleshooting:")
    print("   1. Check service logs: tail -f /var/log/ytdl_service.log")
    print("   2. Restart service: systemctl restart ytdl-service")
    print("   3. Test service manually:")
    print(f"      curl -H 'X-API-Key: YOUR_KEY' {service_url}/health")
    print("   4. The bot will use fallback strategies if service is unavailable")

async def main():
    """Main debug function."""
    print("YouTube Service Debug Tool")
    print("=" * 50)
    
    # Run all tests
    connectivity_ok = await test_basic_connectivity()
    config_ok = await test_service_configuration()
    
    if connectivity_ok and config_ok:
        reachable = await test_service_reachability()
        if reachable:
            health_ok = await test_service_health()
        else:
            health_ok = False
    else:
        reachable = False
        health_ok = False
    
    # Summary
    print("\n" + "=" * 50)
    print("DIAGNOSIS SUMMARY")
    print("=" * 50)
    
    if health_ok:
        print("✅ Service is working correctly!")
        print("   The bot should be able to use the service for downloads.")
    elif reachable:
        print("⚠️  Service is reachable but not healthy")
        print("   Check service logs and configuration.")
    elif config_ok:
        print("⚠️  Configuration is valid but service is not reachable")
        print("   Service may be down or network issues exist.")
    else:
        print("❌ Configuration or connectivity issues")
        print("   Fix basic configuration first.")
    
    print(f"\n📊 Test Results:")
    print(f"   Connectivity: {'✅' if connectivity_ok else '❌'}")
    print(f"   Configuration: {'✅' if config_ok else '❌'}")
    print(f"   Reachability: {'✅' if reachable else '❌'}")
    print(f"   Health: {'✅' if health_ok else '❌'}")
    
    if not health_ok:
        await suggest_solutions()
    
    print(f"\n🔄 Fallback Status:")
    print(f"   The bot will use direct yt-dlp strategies when service is unavailable.")
    print(f"   Based on our tests, the Android client strategy should work.")

if __name__ == "__main__":
    asyncio.run(main())