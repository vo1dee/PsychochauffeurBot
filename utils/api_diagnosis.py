#!/usr/bin/env python3
"""
API Connection Diagnostic Tool for PsychochauffeurBot
This script tests OpenRouter API connectivity and diagnoses common issues.
"""

import asyncio
import os
import sys
import httpx
import json
from datetime import datetime

# Get API key and base URL from environment or .env file
def get_config():
    # Try to import from dotenv if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ No API key found. Set OPENROUTER_API_KEY in your environment or .env file.")
        sys.exit(1)
    
    # Get the base URL, provide default if not set
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    print(f"Using API base URL: {base_url}")
    
    # Extract domain for DNS check
    from urllib.parse import urlparse
    domain = urlparse(base_url).netloc
    
    return api_key, base_url, domain

# Basic network connectivity check - try multiple reliable domains
async def check_internet():
    domains_to_try = [
        "https://1.1.1.1",
        "https://www.google.com",
        "https://www.cloudflare.com"
    ]
    
    for url in domains_to_try:
        try:
            print(f"Testing connectivity to {url}...")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"✅ Internet connectivity: OK (connected to {url})")
                    return True
        except Exception as e:
            print(f"❌ Failed to connect to {url}: {str(e)}")
    
    print("❌ Internet connectivity issue: Could not connect to any test servers")
    return False

# Check DNS resolution
async def check_dns(domain):
    try:
        import socket
        print(f"Resolving DNS for {domain}...")
        ip = socket.gethostbyname(domain)
        print(f"✅ DNS resolution for {domain}: {ip}")
        return True
    except Exception as e:
        print(f"❌ DNS resolution failed for {domain}: {str(e)}")
        return False

# Test API endpoint directly
async def test_api_endpoint(base_url, api_key):
    print(f"\nTesting API endpoint: {base_url}")
    try:
        # First try a basic HEAD request to see if the domain is reachable at all
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                print(f"Testing basic connectivity to {base_url}...")
                response = await client.head(base_url)
                print(f"✅ Basic connectivity: {response.status_code}")
            except Exception as e:
                print(f"❌ Basic connectivity failed: {str(e)}")
                return False
            
            # Now try with authentication
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://vo1dee.com",
                "X-Title": "PsychochauffeurBot"
            }
            
            # Try to hit models endpoint as a test
            print("Testing API authentication...")
            try:
                models_url = f"{base_url}/models"
                print(f"Requesting: {models_url}")
                response = await client.get(models_url, headers=headers)
                print(f"API models endpoint response: {response.status_code}")
                
                # Check what kind of response we got
                content_type = response.headers.get("content-type", "")
                print(f"Response content type: {content_type}")
                
                if "html" in content_type.lower():
                    print("⚠️ API returned HTML instead of JSON - possible authentication issue")
                    print(f"First 300 characters of response: {response.text[:300]}")
                    return False
                    
                if response.status_code == 200:
                    print("✅ API authentication successful")
                    try:
                        # Try to parse as JSON
                        data = response.json()
                        if "data" in data and isinstance(data["data"], list):
                            models = [m.get("id", "unknown") for m in data["data"][:5]]
                            print(f"Available models: {', '.join(models)}...")
                        else:
                            print(f"Unexpected response structure: {data}")
                        return True
                    except json.JSONDecodeError:
                        print("⚠️ API returned invalid JSON:")
                        print(response.text[:300])
                        return False
                else:
                    print(f"❌ API authentication failed: {response.status_code}")
                    print(f"Response: {response.text[:300]}")
                    return False
            except Exception as e:
                print(f"❌ API request failed: {str(e)}")
                return False
    except Exception as e:
        print(f"❌ Failed to connect to API: {str(e)}")
        return False

# Test a simple completion request
async def test_completion(base_url, api_key):
    print("\nTesting a simple completion request...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://vo1dee.com", 
                "X-Title": "PsychochauffeurBot"
            }
            
            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say hello!"}
                ],
                "max_tokens": 50
            }
            
            completion_url = f"{base_url}/chat/completions"
            print(f"Sending request to: {completion_url}")
            
            response = await client.post(
                completion_url, 
                headers=headers,
                json=payload,
                timeout=15.0
            )
            
            print(f"Completion API response: {response.status_code}")
            content_type = response.headers.get("content-type", "")
            print(f"Response content type: {content_type}")
            
            if "html" in content_type.lower():
                print("⚠️ API returned HTML instead of JSON response")
                print(f"First 300 characters: {response.text[:300]}")
                return False
                
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        message = data["choices"][0]["message"]["content"]
                        print(f"✅ Completion successful: {message}")
                        return True
                    else:
                        print(f"⚠️ Unexpected response structure: {data}")
                        return False
                except json.JSONDecodeError:
                    print("⚠️ API returned non-JSON response:")
                    print(response.text[:300])
                    return False
            else:
                print(f"❌ Completion request failed: {response.status_code}")
                print(f"Response: {response.text[:300]}")
                return False
    except Exception as e:
        print(f"❌ Completion request error: {str(e)}")
        return False

# Function to check proxy settings
def check_proxy_settings():
    print("\nChecking proxy settings...")
    proxies = {
        'http': os.environ.get('HTTP_PROXY', None),
        'https': os.environ.get('HTTPS_PROXY', None),
    }
    
    if any(proxies.values()):
        print(f"⚠️ Proxy settings detected:")
        for protocol, proxy in proxies.items():
            if proxy:
                print(f"  {protocol.upper()}_PROXY: {proxy}")
        print("These may affect API connectivity.")
    else:
        print("✅ No proxy environment variables detected.")
    
    return proxies

async def main():
    print(f"=== OpenRouter API Diagnostics ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Running network diagnostics...\n")
    
    # Check proxy settings
    proxies = check_proxy_settings()
    
    # Get config
    api_key, base_url, domain = get_config()
    print(f"Domain to check: {domain}")
    
    # Check internet
    internet_ok = await check_internet()
    if not internet_ok:
        print("\n❌ DIAGNOSIS: No internet connectivity")
        print("Please check your network connection.")
        print("Try pinging common domains manually:")
        print("  ping google.com")
        print("  ping cloudflare.com")
        return
    
    # Check DNS for API domain
    dns_ok = await check_dns(domain)
    if not dns_ok:
        print("\n❌ DIAGNOSIS: DNS resolution issues")
        print(f"Cannot resolve {domain}. Please check:")
        print("  1. If the domain is correct")
        print("  2. Your DNS settings")
        print("  3. Try 'nslookup openrouter.ai' to verify DNS resolution")
        return
    
    # Test API endpoint
    endpoint_ok = await test_api_endpoint(base_url, api_key)
    if not endpoint_ok:
        print("\n❌ DIAGNOSIS: API endpoint unreachable or authentication failed")
        print("Possible issues:")
        print("  1. Check your API key")
        print("  2. Verify your OpenRouter account is active")
        print("  3. Check for service outages at OpenRouter")
        return
    
    # Test completion
    completion_ok = await test_completion(base_url, api_key)
    if not completion_ok:
        print("\n❌ DIAGNOSIS: Completion requests failing")
        print("Your API connection works but completion requests are failing.")
        print("Check model availability and your quota/rate limits.")
        return
    
    print("\n✅ DIAGNOSIS: All tests passed!")
    print("Your OpenRouter API connection appears to be working correctly.")

if __name__ == "__main__":
    asyncio.run(main())