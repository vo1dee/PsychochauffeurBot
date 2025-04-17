import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
import pytest
from fastapi.testclient import TestClient

from config_api import app
from config.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def temp_config_dirs(tmp_path, monkeypatch):
    # Create temporary config directories
    base = tmp_path / "config"
    default_dir = base / "default"
    global_dir = base / "global"
    private_dir = base / "private_chats"
    group_dir = base / "group_chats"
    # Ensure directories exist
    for d in (default_dir, global_dir, private_dir, group_dir):
        d.mkdir(parents=True, exist_ok=True)
    # Monkeypatch ConfigManager directory paths
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_DIR", str(default_dir))
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_DIR", str(global_dir))
    monkeypatch.setattr(ConfigManager, "PRIVATE_CONFIG_DIR", str(private_dir))
    monkeypatch.setattr(ConfigManager, "GROUP_CONFIG_DIR", str(group_dir))
    return tmp_path


@pytest.fixture
def client():
    return TestClient(app)


def test_global_config_roundtrip(client):
    # Post a global configuration
    config_name = "test_global"
    payload = {"chat_id": None, "chat_type": "global", "config_data": {"foo": "bar"}}
    response = client.post(f"/config/{config_name}", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Get the global configuration
    response = client.get(f"/config/{config_name}", params={"chat_type": "global"})
    assert response.status_code == 200
    data = response.json()
    assert data["config_name"] == config_name
    assert data["chat_type"] == "global"
    assert data["config_data"] == {"foo": "bar"}


def test_private_config_roundtrip(client):
    # Post a private chat configuration
    config_name = "test_private"
    payload = {"chat_id": "42", "chat_type": "private", "config_data": {"alpha": 1}}
    response = client.post(f"/config/{config_name}", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Get the private chat configuration
    response = client.get(f"/config/{config_name}", params={"chat_id": "42", "chat_type": "private"})
    assert response.status_code == 200
    data = response.json()
    assert data["config_name"] == config_name
    assert data["chat_id"] == "42"
    assert data["chat_type"] == "private"
    assert data["config_data"] == {"alpha": 1}


def test_missing_config_returns_empty(client):
    # Requesting a non-existent config returns empty dict
    response = client.get("/config/nonexistent", params={})
    assert response.status_code == 200
    data = response.json()
    assert data["config_data"] == {}