import aiohttp
import asyncio
import os
import unittest
from dotenv import load_dotenv

class TestServiceConnection(unittest.TestCase):

    def test_service_connection(self):
        """Test connection to the YTDL service."""
        async def run_test():
            load_dotenv()
            service_url = os.getenv('YTDL_SERVICE_URL')
            api_key = os.getenv('YTDL_SERVICE_API_KEY')
            
            # Skip test if environment variables are not set
            if not service_url or not api_key:
                self.skipTest("Required environment variables not set")
                return

            async with aiohttp.ClientSession() as session:
                headers = {"X-API-Key": api_key}
                try:
                    async with session.get(
                        f"{service_url}/health",
                        headers=headers,
                        timeout=5,
                        ssl=False  # Add this if you're using self-signed certificates
                    ) as response:
                        self.assertEqual(response.status, 200)
                except aiohttp.ClientError:
                    self.skipTest("Service not available")

        # Run the async test
        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()