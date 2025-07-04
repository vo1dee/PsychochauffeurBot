#!/usr/bin/env python3
"""
Migration script to add context_messages_count to random_response_settings
in existing chat configurations.
"""

import json
import os
import glob
from pathlib import Path

def migrate_chat_configs():
    """Add context_messages_count to random_response_settings in all chat configs."""
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "config"
    
    # Find all config.json files in group and private directories
    config_files = []
    config_files.extend(glob.glob(str(config_dir / "group" / "*" / "config.json")))
    config_files.extend(glob.glob(str(config_dir / "private" / "*" / "config.json")))
    
    migrated_count = 0
    
    for config_file in config_files:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check if chat_behavior module exists and has random_response_settings
            chat_behavior = config.get("config_modules", {}).get("chat_behavior", {})
            if chat_behavior:
                overrides = chat_behavior.get("overrides", {})
                random_settings = overrides.get("random_response_settings", {})
                
                # Add context_messages_count if it doesn't exist
                if random_settings and "context_messages_count" not in random_settings:
                    random_settings["context_messages_count"] = 3
                    migrated_count += 1
                    print(f"Added context_messages_count to {config_file}")
                    
                    # Write back the updated config
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"Error processing {config_file}: {e}")
    
    print(f"\nMigration complete! Updated {migrated_count} configuration files.")

if __name__ == "__main__":
    migrate_chat_configs() 