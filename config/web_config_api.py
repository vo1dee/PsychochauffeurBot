"""Web Configuration API for PsychoChauffeurBot.

FastAPI-based REST API and web UI for managing bot configuration.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

# --- Pydantic models ---

class ModuleUpdate(BaseModel):
    overrides: Dict[str, Any]

class ModuleToggle(BaseModel):
    enabled: bool

class ChatInfo(BaseModel):
    chat_id: str
    chat_type: str
    chat_name: str
    custom_config_enabled: bool
    last_updated: Optional[str] = None

# --- App setup ---

app = FastAPI(title="PsychoChauffeurBot Config", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton config manager instance
_config_manager: Optional[ConfigManager] = None
_config_manager_lock = asyncio.Lock()

API_TOKEN = os.getenv("CONFIG_API_TOKEN", "")

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def set_config_manager(cm: ConfigManager) -> None:
    """Set an existing ConfigManager instance (e.g. shared with the bot)."""
    global _config_manager
    _config_manager = cm


async def get_config_manager() -> ConfigManager:
    """Get or create the ConfigManager singleton."""
    global _config_manager
    if _config_manager is None:
        async with _config_manager_lock:
            if _config_manager is None:
                _config_manager = ConfigManager()
                await _config_manager.initialize()
    return _config_manager


async def verify_token(request: Request) -> None:
    """Verify API token if configured."""
    if not API_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_TOKEN}":
        # Also check query param for web UI convenience
        token = request.query_params.get("token", "")
        if token != API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid or missing API token")


# --- Helper functions ---

async def list_configured_chats(cm: ConfigManager) -> List[ChatInfo]:
    """Scan config directories to list all configured chats."""
    chats = []

    for chat_type, config_dir in [("group", cm.GROUP_CONFIG_DIR), ("private", cm.PRIVATE_CONFIG_DIR)]:
        if not config_dir.exists():
            continue
        for entry in sorted(config_dir.iterdir()):
            if not entry.is_dir():
                continue
            config_file = entry / "config.json"
            if not config_file.exists():
                continue

            chat_id = entry.name
            try:
                config = await cm.get_config(chat_id, chat_type, create_if_missing=False)
                metadata = config.get("chat_metadata", {})
                chats.append(ChatInfo(
                    chat_id=chat_id,
                    chat_type=metadata.get("chat_type", chat_type),
                    chat_name=metadata.get("chat_name", f"{chat_type}_{chat_id}"),
                    custom_config_enabled=metadata.get("custom_config_enabled", False),
                    last_updated=metadata.get("last_updated"),
                ))
            except Exception as e:
                logger.warning(f"Failed to read config for {chat_type}/{chat_id}: {e}")
                chats.append(ChatInfo(
                    chat_id=chat_id,
                    chat_type=chat_type,
                    chat_name=f"{chat_type}_{chat_id}",
                    custom_config_enabled=False,
                ))

    return chats


# --- API routes ---

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config/global")
async def get_global_config(
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Get the global configuration."""
    config = await cm.get_config()
    return config


@app.put("/api/config/global/module/{module_name}")
async def update_global_module(
    module_name: str,
    body: ModuleUpdate,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Update a global module's overrides."""
    for setting_path, value in _flatten_dict(body.overrides):
        success = await cm.update_module_setting(module_name, setting_path, value)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to update {module_name}.{setting_path}")
    return {"status": "updated", "module": module_name}


@app.get("/api/config/chats")
async def list_chats(
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """List all configured chats."""
    chats = await list_configured_chats(cm)
    return {"chats": [c.model_dump() for c in chats]}


@app.get("/api/config/chat/{chat_type}/{chat_id}")
async def get_chat_config(
    chat_type: str,
    chat_id: str,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Get configuration for a specific chat."""
    config = await cm.get_config(chat_id, chat_type, create_if_missing=False)
    if not config:
        raise HTTPException(status_code=404, detail="Chat config not found")
    return config


@app.put("/api/config/chat/{chat_type}/{chat_id}/module/{module_name}")
async def update_chat_module(
    chat_type: str,
    chat_id: str,
    module_name: str,
    body: ModuleUpdate,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Update a chat-specific module's overrides."""
    for setting_path, value in _flatten_dict(body.overrides):
        success = await cm.update_module_setting(module_name, setting_path, value, chat_id, chat_type)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to update {module_name}.{setting_path}")
    return {"status": "updated", "chat_id": chat_id, "module": module_name}


@app.put("/api/config/chat/{chat_type}/{chat_id}/module/{module_name}/toggle")
async def toggle_chat_module(
    chat_type: str,
    chat_id: str,
    module_name: str,
    body: ModuleToggle,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Enable or disable a module for a specific chat."""
    if body.enabled:
        success = await cm.enable_module(chat_id, chat_type, module_name)
    else:
        success = await cm.disable_module(chat_id, chat_type, module_name)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to toggle {module_name}")
    return {"status": "toggled", "module": module_name, "enabled": body.enabled}


@app.post("/api/config/chat/{chat_type}/{chat_id}/custom-config")
async def toggle_custom_config(
    chat_type: str,
    chat_id: str,
    body: ModuleToggle,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Enable or disable custom config for a chat."""
    if body.enabled:
        success = await cm.enable_custom_config(chat_id, chat_type)
    else:
        success = await cm.disable_custom_config(chat_id, chat_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to toggle custom config")
    return {"status": "toggled", "custom_config_enabled": body.enabled}


@app.post("/api/config/chat/{chat_type}/{chat_id}/backup")
async def backup_chat_config(
    chat_type: str,
    chat_id: str,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Create a backup of a chat's configuration."""
    success = await cm.backup_config(chat_id, chat_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create backup")
    return {"status": "backup_created"}


@app.post("/api/config/chat/{chat_type}/{chat_id}/archive")
async def archive_chat(
    chat_type: str,
    chat_id: str,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Archive a chat's configuration."""
    success = await cm.archive_chat(chat_id, chat_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to archive chat config")
    return {"status": "archived", "chat_id": chat_id}


@app.post("/api/config/chat/{chat_type}/{chat_id}/unarchive")
async def unarchive_chat(
    chat_type: str,
    chat_id: str,
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Restore a chat's configuration from archive."""
    success = await cm.unarchive_chat(chat_id, chat_type)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to unarchive chat config")
    return {"status": "unarchived", "chat_id": chat_id}


@app.get("/api/config/archived")
async def list_archived(
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """List all archived chats."""
    archived = await cm.list_archived_chats()
    return {"chats": archived}


@app.post("/api/config/refresh-chat-names")
async def refresh_chat_names(
    _: None = Depends(verify_token),
    cm: ConfigManager = Depends(get_config_manager),
):
    """Refresh chat names from the database for all configured chats."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "telegram_bot")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{name}"

    try:
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch("SELECT chat_id, title FROM chats WHERE title IS NOT NULL")
            title_map = {str(row["chat_id"]): row["title"] for row in rows}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to query chat titles from database: {e}")
        raise HTTPException(status_code=500, detail="Failed to query database for chat titles")

    updated = []
    chats = await list_configured_chats(cm)
    for chat in chats:
        db_title = title_map.get(chat.chat_id)
        if db_title and db_title != chat.chat_name:
            try:
                config = await cm.get_config(chat.chat_id, chat.chat_type, chat_name=db_title)
                updated.append({"chat_id": chat.chat_id, "chat_name": db_title})
            except Exception as e:
                logger.warning(f"Failed to update chat name for {chat.chat_id}: {e}")

    return {"status": "ok", "updated": updated}


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the web UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Config UI</h1><p>Place index.html in config/static/</p>")


# --- Utilities ---

def _flatten_dict(d: Dict[str, Any], prefix: str = "") -> list:
    """Flatten a nested dict into (dotted_path, value) pairs."""
    items = []
    for key, value in d.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.extend(_flatten_dict(value, path))
        else:
            items.append((path, value))
    return items


# --- Server entry point ---

async def start_background(
    config_manager: Optional[ConfigManager] = None,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> asyncio.Task:
    """Start the web config server as a background asyncio task.

    Intended to be called from the bot's startup sequence so both
    the bot and the config UI share the same event loop and ConfigManager.
    """
    if config_manager:
        set_config_manager(config_manager)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    logger.info(f"Config web UI started on http://{host}:{port}")
    return task


def run_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
    log_level: str = "info",
):
    """Run the configuration web server standalone."""
    uvicorn.run(
        "config.web_config_api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )
