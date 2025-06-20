import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import asyncio
from config.config_manager import ConfigManager

async def main():
    config_manager = ConfigManager()
    await config_manager.initialize()
    await config_manager.create_global_config()
    print("Global config regenerated at config/global/global_config.json")

if __name__ == "__main__":
    asyncio.run(main())