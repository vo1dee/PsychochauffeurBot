#!/usr/bin/env python3
import requests
import json

# Get detailed service health info
service_url = "https://ytdl.vo1dee.com"
api_key = "qeKcftNr5OIo7uF_esfXDr-GRxVur0G_3w7XIMFfvX0"

headers = {"X-API-Key": api_key}

print("🔍 Diagnosing service issues...")

try:
    response = requests.get(f"{service_url}/health", headers=headers, timeout=10)
    if response.status_code == 200:
        health_data = response.json()
        
        print(f"📊 Service Status: {health_data.get('status')}")
        
        # Check container health
        container_health = health_data.get('container_health', {})
        print(f"\n🐳 Container Health:")
        for key, value in container_health.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key}: {value}")
        
        # Check directories
        directories = health_data.get('directories', {})
        print(f"\n📁 Directory Status:")
        for key, value in directories.items():
            if 'writeable' in key or 'readable' in key or 'exists' in key:
                status = "✅" if value else "❌"
                print(f"   {status} {key}: {value}")
            else:
                print(f"   📂 {key}: {value}")
        
        # Check system info
        system_info = health_data.get('system_info', {})
        print(f"\n🖥️ System Info:")
        print(f"   yt-dlp version: {system_info.get('ytdlp_version')}")
        print(f"   ffmpeg version: {system_info.get('ffmpeg_version')}")
        print(f"   python version: {system_info.get('python_version')}")
        
        # Identify critical issues
        print(f"\n🚨 Critical Issues:")
        if not container_health.get('downloads_dir_accessible', True):
            print("   ❌ Downloads directory not accessible")
        if not directories.get('downloads_dir_writeable', True):
            print("   ❌ Downloads directory not writeable - THIS IS LIKELY THE MAIN ISSUE")
        if not directories.get('logs_dir_writeable', True):
            print("   ❌ Logs directory not writeable")
            
        print(f"\n💡 Recommendations:")
        if not directories.get('downloads_dir_writeable', True):
            print("   🔧 Fix directory permissions on the service server:")
            print("      sudo chown -R www-data:www-data /opt/ytdl_service/downloads")
            print("      sudo chmod -R 755 /opt/ytdl_service/downloads")
        
    else:
        print(f"❌ Health check failed: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error checking service health: {e}")