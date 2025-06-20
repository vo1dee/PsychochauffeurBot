"""Script to migrate configurations to the new modular structure."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.config_manager import ConfigManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to migrate configurations."""
    try:
        # Initialize config manager
        config_manager = ConfigManager()
        await config_manager.initialize()
        
        # Migrate configurations
        print("Starting configuration migration...")
        
        # First migrate existing configs to new directory structure
        migration_results = await config_manager.migrate_existing_configs()
        if migration_results is None:
            migration_results = {}
        print("Configuration directory migration completed")
        for chat_id, result in migration_results.items():
            print(f"Chat {chat_id}: {result}")

        # Then migrate to modular structure
        modular_results = await config_manager.migrate_all_to_modular()
        if modular_results is None:
            modular_results = {}
        print("Modular configuration migration completed")
        for chat_id, result in modular_results.items():
            print(f"Chat {chat_id}: {result}")

        # Add/update missing fields from template
        print("Updating chat configs with new template fields...")
        update_results = await config_manager.update_chat_configs_with_template()
        if update_results is None:
            update_results = {}
        print("Template field update completed")
        for chat_id, result in update_results.items():
            print(f"Chat {chat_id}: {result}")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 