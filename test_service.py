#!/usr/bin/env python3
import requests
import json

# Test the external service
service_url = "https://ytdl.vo1dee.com"
api_key = "qeKcftNr5OIo7uF_esfXDr-GRxVur0G_3w7XIMFfvX0"

headers = {
    "X-API-Key": api_key,
    "Content-Type": "application/json"
}

# Test YouTube Shorts with a real URL
test_url = "https://youtube.com/shorts/aV3v4rY5lAc"
payload = {"url": test_url}

print(f"Testing YouTube Shorts download: {test_url}")
print(f"Service URL: {service_url}/download")

try:
    response = requests.post(f"{service_url}/download", json=payload, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")