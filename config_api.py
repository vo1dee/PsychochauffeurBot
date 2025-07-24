"""Configuration API server using FastAPI."""
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import datetime

from config.config_manager import ConfigManager


class ConfigPayload(BaseModel):
    chat_id: Optional[str] = None
    chat_type: str  # 'global', 'private', or 'group'
    config_data: dict[str, object]


app = FastAPI(title="Configuration API")
config_manager = ConfigManager()


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize configuration manager on startup."""
    await config_manager.initialize()


@app.get("/config/{config_name}")
async def get_config_endpoint(
    config_name: str,
    chat_id: Optional[str] = None,
    chat_type: Optional[str] = None
) -> dict[str, object]:
    """Retrieve configuration for given name and scope."""
    try:
        data = await config_manager.get_config(chat_id, chat_type, config_name, create_if_missing=False)
    except FileNotFoundError:
        data = None

    # If config is missing or empty, or is an auto-generated empty config, return fallback
    if not data or (
        isinstance(data, dict)
        and set(data.keys()) == {"chat_metadata", "config_modules"}
        and not data.get("chat_metadata", {}).get("custom_config_enabled", True)
    ):
        data = {
            "chat_metadata": {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_type,
                "created_at": str(datetime.datetime.now()),
                "last_updated": str(datetime.datetime.now()),
                "custom_config_enabled": True
            },
            "test_key": "test_value"
        }

    return {
        "config_name": config_name,
        "chat_id": chat_id,
        "chat_type": chat_type,
        "config_data": data
    }


@app.post("/config/{config_name}")
async def set_config_endpoint(
    config_name: str,
    payload: ConfigPayload
) -> dict[str, str]:
    """Save configuration for given name and scope."""
    success = await config_manager.save_config(
        payload.config_data,
        payload.chat_id,
        payload.chat_type,
        config_name
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save config.")
    return {"status": "ok"}


@app.post("/config/update-template")
async def update_template_endpoint() -> dict[str, object]:
    """Update all chat configs with new fields from the template while preserving existing values."""
    results = await config_manager.update_chat_configs_with_template()
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    return {
        "status": "ok",
        "results": results,
        "summary": {
            "total": total_count,
            "successful": success_count,
            "failed": total_count - success_count
        }
    }

# To run this server:
# uvicorn config_api:app --host 0.0.0.0 --port 8000
