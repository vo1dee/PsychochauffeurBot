#!/usr/bin/env python3
"""Test script to verify ConfigManager functionality."""

import unittest
import json
import tempfile
import os
import sys
import pytest
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.config_manager import ConfigManager

@pytest.mark.asyncio
async def test_config_manager():
    """Test the ConfigManager with a test private chat config."""
    
    print("🧪 Testing ConfigManager...")
    
    config_manager = ConfigManager()
    await config_manager.initialize()
    
    # Test 1: Load global config
    print("\n1️⃣ Testing global config load...")
    global_config = await config_manager.get_config()
    assert global_config is not None, "Global config should be loaded"
    assert 'config_modules' in global_config, "Global config should have modules"
    print(f"Global config loaded: {bool(global_config)}")
    print(f"Global config modules: {list(global_config.get('config_modules', {}).keys())}")
    
    # Create and enable custom config for the test chat
    chat_id = "123456789"  # Mock test chat ID
    chat_type = "private"
    await config_manager.create_new_chat_config(chat_id, chat_type)
    await config_manager.enable_custom_config(chat_id, chat_type)
    
    # Test 2: Load your private chat config
    print("\n2️⃣ Testing private chat config...")
    chat_config = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type)
    assert chat_config is not None, "Chat config should be loaded"
    assert chat_config.get('chat_metadata', {}).get('custom_config_enabled'), "Custom config should be enabled"
    print(f"Chat config loaded: {bool(chat_config)}")
    print(f"Custom config enabled: {chat_config.get('chat_metadata', {}).get('custom_config_enabled')}")
    print(f"Chat config modules: {list(chat_config.get('config_modules', {}).keys())}")
    
    # Test 3: Test GPT module inheritance
    print("\n3️⃣ Testing GPT module inheritance...")
    gpt_config = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name="gpt")
    assert gpt_config.get('enabled'), "GPT module should be enabled"
    print(f"GPT module enabled: {gpt_config.get('enabled')}")
    
    # Check if your Ukrainian prompts are preserved
    command_prompt = gpt_config.get("overrides", {}).get("command", {}).get("system_prompt", "")
    assert 'зірка' in command_prompt, "Ukrainian prompts should be preserved"
    print(f"Command prompt contains Ukrainian: {'зірка' in command_prompt}")
    print(f"Command prompt: {command_prompt[:50]}...")
    
    # Test 4: Test module that should inherit from global
    print("\n4️⃣ Testing safety module (should inherit from global)...")
    safety_config = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name="safety")
    assert safety_config.get('enabled'), "Safety module should be enabled"
    print(f"Safety module enabled: {safety_config.get('enabled')}")
    print(f"Safety overrides exist: {bool(safety_config.get('overrides'))}")
    
    # Test 5: Test non-existent module
    print("\n5️⃣ Testing non-existent module...")
    fake_config = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name="nonexistent")
    assert fake_config == {}, "Non-existent module should return empty config"
    print(f"Non-existent module config: {fake_config}")
    
    print("\n✅ ConfigManager test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_config_manager()) 