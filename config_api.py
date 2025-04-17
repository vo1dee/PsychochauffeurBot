"""Configuration API server using FastAPI."""
import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.config_manager import ConfigManager


class ConfigPayload(BaseModel):
    chat_id: Optional[str] = None
    chat_type: str  # 'global', 'private', or 'group'
    config_data: dict


app = FastAPI(title="Configuration API")


@app.get("/config/{config_name}")
async def get_config_endpoint(
    config_name: str,
    chat_id: Optional[str] = None,
    chat_type: Optional[str] = None
) -> dict:
    """Retrieve configuration for given name and scope."""
    data = ConfigManager.get_config(config_name, chat_id, chat_type)
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
) -> dict:
    """Save configuration for given name and scope."""
    success = ConfigManager.save_chat_config(
        config_name,
        payload.config_data,
        payload.chat_id,
        payload.chat_type
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save config.")
    return {"status": "ok"}

# To run this server:
# uvicorn config_api:app --host 0.0.0.0 --port 8000