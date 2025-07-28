#!/usr/bin/env python3
"""Test script to verify GPT config works correctly with your Ukrainian prompts."""

import pytest
import sys
import os
import unittest
import json
import tempfile
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime
import typing

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.config_manager import ConfigManager
from modules.gpt import get_system_prompt

@pytest.fixture
def gpt_config() -> typing.Any:
    """Fixture to provide a mock chat config for testing."""
    return {
        "config_modules": {
            "gpt": {
                "overrides": {
                    "command": {"system_prompt": "Command prompt"},
                    "mention": {"system_prompt": "Mention prompt"},
                    "private": {"system_prompt": "Private prompt"},
                    "random": {"system_prompt": "Random prompt"},
                }
            }
        },
        "chat_metadata": {"custom_config_enabled": True},
    }

@pytest.mark.asyncio
async def test_gpt_config(gpt_config: typing.Any) -> None:
    """Test GPT configuration specifically for your chat."""
    
    print("🧪 Testing GPT Configuration...")
    
    config_manager = ConfigManager()
    await config_manager.initialize()
    
    # Get your chat config
    chat_config = await config_manager.get_config(chat_id="15671125", chat_type="private")
    
    print(f"Chat custom config enabled: {chat_config.get('chat_metadata', {}).get('custom_config_enabled')}")
    
    # Test each GPT response type
    response_types = ["command", "mention", "private", "random"]
    
    for response_type in response_types:
        print(f"\n📝 Testing {response_type} prompt...")
        
        # Get the system prompt
        system_prompt = await get_system_prompt(response_type, chat_config)
        
        print(f"  Length: {len(system_prompt)}")
        print(f"  Contains Ukrainian: {'зірка' in system_prompt or 'ковбаса' in system_prompt or 'реплай' in system_prompt}")
        print(f"  Prompt: {system_prompt[:60]}...")
        
        # Test the direct config lookup
        gpt_module = chat_config.get("config_modules", {}).get("gpt", {})
        direct_prompt = gpt_module.get("overrides", {}).get(response_type, {}).get("system_prompt", "")
        print(f"  Direct lookup works: {bool(direct_prompt)}")
    
    # Test a response type that should inherit from global
    print(f"\n📝 Testing weather response type (should inherit from global)...")
    weather_prompt = await get_system_prompt("weather", chat_config)
    print(f"  Length: {len(weather_prompt)}")
    print(f"  Contains 'weather': {'weather' in weather_prompt.lower()}")
    print(f"  Prompt: {weather_prompt[:60]}...")
    
    print("\n✅ GPT Configuration test completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_gpt_config()) 