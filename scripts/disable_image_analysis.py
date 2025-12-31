#!/usr/bin/env python3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

# Directories containing config files
CONFIG_DIRS = [
    '/home/ubuntu/psychochauffeurbot/config/group',
    '/home/ubuntu/PsychochauffeurBot/config/private',
    '/home/ubuntu/PsychochauffeurBot/config/global'
]

# Backup directory
BACKUP_DIR = '/home/vo1dee/PsychochauffeurBot/config/backups'

def create_backup(file_path):
    """Create a timestamped backup of the config file."""
    try:
        # Create backup directory if it doesn't exist
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rel_path = os.path.relpath(file_path, '/home/vo1dee/PsychochauffeurBot/config')
        backup_path = os.path.join(BACKUP_DIR, f"{rel_path.replace(os.path.sep, '_')}_{timestamp}.bak")
        
        # Create necessary subdirectories in backup path
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Copy the file
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
        return True
    except Exception as e:
        print(f"Error creating backup for {file_path}: {e}")
        return False

def update_config_file(file_path):
    try:
        # Create backup before making changes
        if not create_backup(file_path):
            print(f"Skipping {file_path} due to backup failure")
            return False
            
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in {file_path}: {e}")
                return False
        
        # Navigate to the image_analysis section and update enabled flag
        modules = config.setdefault('config_modules', {})
        gpt = modules.setdefault('gpt', {})
        overrides = gpt.setdefault('overrides', {})
        
        # Initialize image_analysis if it doesn't exist
        if 'image_analysis' not in overrides:
            overrides['image_analysis'] = {}
        
        # Only update if the value is different
        if overrides['image_analysis'].get('enabled', True) != False:
            overrides['image_analysis']['enabled'] = False
            
            # Save the updated config
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    updated_count = 0
    total_processed = 0
    failed_files = []
    
    print("Starting configuration update...")
    print(f"Backup directory: {BACKUP_DIR}")
    
    for config_dir in CONFIG_DIRS:
        if not os.path.exists(config_dir):
            print(f"Warning: Directory not found: {config_dir}")
            continue
            
        print(f"\nProcessing directory: {config_dir}")
        for root, _, files in os.walk(config_dir):
            for file in files:
                if file == 'config.json':
                    file_path = os.path.join(root, file)
                    total_processed += 1
                    print(f"\nProcessing: {file_path}")
                    if update_config_file(file_path):
                        updated_count += 1
                        print(f"✅ Updated: {file_path}")
                    else:
                        failed_files.append(file_path)
    
    print("\n" + "="*50)
    print("Processing complete!")
    print(f"Total files processed: {total_processed}")
    print(f"Successfully updated: {updated_count}")
    
    if failed_files:
        print("\nFiles that failed to update:")
        for f in failed_files:
            print(f"- {f}")
    
    print("\nBackup location:")
    print(f"- {os.path.abspath(BACKUP_DIR)}")

if __name__ == "__main__":
    main()
