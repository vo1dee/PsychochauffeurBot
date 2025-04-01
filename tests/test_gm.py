import asyncio
from modules.geomagnetic import GeomagneticAPI

async def test():
    api = GeomagneticAPI()
    data = await api.fetch_geomagnetic_data()
    if data:
        print("Successfully fetched geomagnetic data")
        print(f"Current value: {data.current_value}")
        print(f"Description: {data.current_description}")
        print(f"Forecast length: {len(data.forecast)}")
        print(f"First 3 forecast items: {data.forecast[:3]}")
        
        # Test the formatted message
        print("\n----- FORMATTED MESSAGE -----")
        print(data.format_message())
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    asyncio.run(test())