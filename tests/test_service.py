import aiohttp
import asyncio
import os
import unittest
from dotenv import load_dotenv

class TestServiceConnection(unittest.TestCase):

    async def test_service_connection(self):
        """Test connection to the YTDL service."""
        load_dotenv()
        service_url = os.getenv('YTDL_SERVICE_URL')
        api_key = os.getenv('YTDL_SERVICE_API_KEY')

        async with aiohttp.ClientSession() as session:
            headers = {"X-API-Key": api_key}
            async with session.get(
                f"{service_url}/health",
                headers=headers,
                timeout=5,
                ssl=False  # Add this if you're using self-signed certificates
            ) as response:
                self.assertEqual(response.status, 200)

    def run(self):
        asyncio.run(self.test_service_connection())

if __name__ == "__main__":
    unittest.main() 