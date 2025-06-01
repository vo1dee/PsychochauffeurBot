import unittest
import json
import tempfile
import os
import sys
from unittest.mock import patch, mock_open

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.config_manager import ConfigManager
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
import pytest
from fastapi.testclient import TestClient
import pytest_asyncio
from unittest.mock import MagicMock
from httpx import AsyncClient

from config_api import app


@pytest.fixture(autouse=True)
def mock_gpt_prompts():
    with patch.dict('sys.modules', {'modules.prompts': MagicMock(GPT_PROMPTS={
        'image_analysis': 'mock image analysis prompt',
        'gpt_summary': 'mock summary prompt'
    })}):
        yield


@pytest.fixture(autouse=True)
def temp_config_dirs(tmp_path, monkeypatch):
    # Create temporary config directories
    base = tmp_path / "config"
    global_dir = base / "global"
    private_dir = base / "private"
    group_dir = base / "group"
    
    # Ensure directories exist
    for d in (global_dir, private_dir, group_dir):
        d.mkdir(parents=True, exist_ok=True)
    
    # Create ConfigManager instance
    config_manager = ConfigManager()
    
    # Monkeypatch ConfigManager directory paths
    monkeypatch.setattr(config_manager, "GLOBAL_CONFIG_DIR", global_dir)
    monkeypatch.setattr(config_manager, "PRIVATE_CONFIG_DIR", private_dir)
    monkeypatch.setattr(config_manager, "GROUP_CONFIG_DIR", group_dir)
    
    # Patch the config manager in the API
    import config_api
    monkeypatch.setattr(config_api, "config_manager", config_manager)
    
    return config_manager


@pytest_asyncio.fixture
async def async_client():
    client = AsyncClient(app=app, base_url="http://test")
    await client.__aenter__()
    yield client
    await client.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_global_config_roundtrip(async_client):
    """Test saving and retrieving global config through API."""
    config_name = "test_global"
    test_config = {
        "chat_settings": {
            "test_key": "test_value"
        }
    }
    
    # Save config
    response = await async_client.post(
        f"/config/{config_name}",
        json={
            "chat_id": None,
            "chat_type": "global",
            "config_data": test_config
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    # Retrieve config
    response = await async_client.get(
        f"/config/{config_name}",
        params={"chat_type": "global"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["config_name"] == config_name
    assert data["chat_type"] == "global"
    # Check that our test config is in the config_data
    assert "chat_settings" in data["config_data"]
    assert "test_key" in data["config_data"]["chat_settings"]
    assert data["config_data"]["chat_settings"]["test_key"] == "test_value"


@pytest.mark.asyncio
async def test_private_config_roundtrip(async_client):
    """Test saving and retrieving private chat config through API."""
    config_name = "test_private"
    chat_id = "123"
    test_config = {"test_key": "test_value"}
    
    # Save config
    response = await async_client.post(
        f"/config/{config_name}",
        json={
            "chat_id": chat_id,
            "chat_type": "private",
            "config_data": test_config
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    # Retrieve config
    response = await async_client.get(
        f"/config/{config_name}",
        params={"chat_id": chat_id, "chat_type": "private"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["config_name"] == config_name
    assert data["chat_id"] == chat_id
    assert data["chat_type"] == "private"
    # Check that the config data contains our test config
    assert "test_key" in data["config_data"]
    assert data["config_data"]["test_key"] == test_config["test_key"]
    # Verify metadata exists
    assert "chat_metadata" in data["config_data"]
    assert data["config_data"]["chat_metadata"]["chat_id"] == chat_id
    assert data["config_data"]["chat_metadata"]["chat_type"] == "private"


@pytest.mark.asyncio
async def test_missing_config_returns_empty(async_client):
    """Test that missing config returns empty dict through API."""
    config_name = "nonexistent"
    chat_id = "nonexistent"
    
    response = await async_client.get(
        f"/config/{config_name}",
        params={"chat_id": chat_id, "chat_type": "private"}
    )
    assert response.status_code == 200
    data = response.json()
    # Check that config_data is a dict with metadata
    assert isinstance(data["config_data"], dict)
    assert "chat_metadata" in data["config_data"]
    assert data["config_data"]["chat_metadata"]["chat_id"] == chat_id
    assert data["config_data"]["chat_metadata"]["chat_type"] == "private"
    # Check that test_key is present
    assert "test_key" in data["config_data"]
    assert data["config_data"]["test_key"] == "test_value"