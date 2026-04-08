"""
Web UI for config management — FastAPI + Jinja2 + HTMX.

Forms are generated dynamically from Pydantic schema metadata.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from config_v2.schema import MODULE_REGISTRY, get_module_label, Widget
from config_v2.manager import config_manager

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Bot Config")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
def _get_field_meta(model_class: type, field_name: str) -> dict[str, Any]:
    """Extract scope/widget/label metadata from a Pydantic field."""
    field_info = model_class.model_fields.get(field_name)
    if not field_info:
        return {}
    extra = field_info.json_schema_extra or {}

    # Extract ge/le from pydantic metadata constraints
    ge_val = None
    le_val = None
    for m in (field_info.metadata or []):
        if hasattr(m, "ge") and m.ge is not None:
            ge_val = m.ge
        if hasattr(m, "le") and m.le is not None:
            le_val = m.le

    return {
        "scope": extra.get("scope", "per_chat"),
        "widget": extra.get("widget", "text"),
        "label": extra.get("label", field_name.replace("_", " ").title()),
        "description": extra.get("description", ""),
        "choices": extra.get("choices"),
        "ge": ge_val,
        "le": le_val,
    }


def _build_form_fields(
    module_key: str,
    resolved: dict[str, Any],
    overrides: dict[str, Any],
    chat_id: str,
) -> list[dict[str, Any]]:
    """Build form field descriptors for the template."""
    model_class = MODULE_REGISTRY.get(module_key)
    if not model_class:
        return []

    fields = []
    for field_name, field_info in model_class.model_fields.items():
        meta = _get_field_meta(model_class, field_name)
        value = resolved.get(field_name)
        has_override = field_name in overrides

        # Skip per-chat fields when editing global, skip global-only fields when editing per-chat
        if chat_id != "global" and meta["scope"] == "global":
            continue

        # Hide 'enabled' field in per-chat mode — controlled by mode selector
        if field_name == "enabled" and chat_id != "global":
            continue

        # Sub-models (like GPTContextConfig) get special handling
        if isinstance(value, dict) and _is_sub_model(model_class, field_name):
            sub_fields = _build_sub_model_fields(
                module_key, field_name, value,
                overrides.get(field_name, {}),
                chat_id, model_class,
            )
            fields.append({
                "name": field_name,
                "type": "sub_model",
                "label": meta["label"] or field_name.replace("_", " ").title(),
                "fields": sub_fields,
                "has_override": has_override,
            })
        else:
            fields.append({
                "name": field_name,
                "value": value,
                "has_override": has_override,
                **meta,
            })

    return fields


def _is_sub_model(model_class: type, field_name: str) -> bool:
    """Check if a field is a Pydantic sub-model."""
    from pydantic import BaseModel
    annotation = model_class.model_fields[field_name].annotation
    try:
        return isinstance(annotation, type) and issubclass(annotation, BaseModel)
    except TypeError:
        return False


def _build_sub_model_fields(
    module_key: str,
    parent_name: str,
    values: dict[str, Any],
    overrides: dict[str, Any],
    chat_id: str,
    parent_model: type,
) -> list[dict[str, Any]]:
    """Build fields for a sub-model (e.g. GPTContextConfig)."""
    sub_model = parent_model.model_fields[parent_name].annotation
    if not sub_model:
        return []

    fields = []
    for field_name in sub_model.model_fields:
        meta = _get_field_meta(sub_model, field_name)
        value = values.get(field_name)
        has_override = field_name in overrides if isinstance(overrides, dict) else False

        fields.append({
            "name": field_name,
            "value": value,
            "has_override": has_override,
            "parent": parent_name,
            **meta,
        })

    return fields


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard — list of chats + global config link."""
    mgr = config_manager()
    chats = await mgr.db.get_chats()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "chats": chats,
        "modules": list(MODULE_REGISTRY.keys()),
        "module_labels": {k: get_module_label(k) for k in MODULE_REGISTRY},
    })


@app.get("/config/{chat_id}", response_class=HTMLResponse)
async def edit_config(request: Request, chat_id: str):
    """Edit config for a specific chat or global."""
    mgr = config_manager()

    chat = None
    if chat_id != "global":
        chat = await mgr.db.get_chat(chat_id)

    modules_data = []
    for module_key, model_class in MODULE_REGISTRY.items():
        resolved = await mgr.get_resolved_raw(chat_id, module_key)
        overrides = await mgr.get_raw_config(chat_id, module_key) if chat_id != "global" else {}
        fields = _build_form_fields(module_key, resolved, overrides, chat_id)

        # Determine module mode for per-chat configs
        if is_global:
            mode = "global"
        elif overrides:
            # Has per-chat overrides
            mode = "enabled" if resolved.get("enabled", True) else "disabled"
        else:
            mode = "global"

        modules_data.append({
            "key": module_key,
            "label": get_module_label(module_key),
            "fields": fields,
            "enabled": resolved.get("enabled", True),
            "mode": mode,
        })

    return templates.TemplateResponse("edit_config.html", {
        "request": request,
        "chat_id": chat_id,
        "chat": chat,
        "modules": modules_data,
        "is_global": chat_id == "global",
    })


@app.post("/config/{chat_id}/module/{module_key}", response_class=HTMLResponse)
async def save_module(request: Request, chat_id: str, module_key: str):
    """Save a module's config (HTMX form submission)."""
    mgr = config_manager()
    form = await request.form()

    model_class = MODULE_REGISTRY.get(module_key)
    if not model_class:
        return HTMLResponse('<div class="alert error">Unknown module</div>', status_code=400)

    # Parse form data into nested dict
    data: dict[str, Any] = {}
    for key, value in form.items():
        if key.startswith("_"):
            continue

        # Handle nested keys: "command.temperature" → {"command": {"temperature": ...}}
        parts = key.split(".")
        parsed_value = _parse_form_value(value, model_class, parts)

        if len(parts) == 1:
            data[parts[0]] = parsed_value
        elif len(parts) == 2:
            if parts[0] not in data:
                data[parts[0]] = {}
            data[parts[0]][parts[1]] = parsed_value

    # Handle toggle checkboxes (unchecked = not in form data)
    _fill_missing_toggles(data, model_class, form)

    await mgr.set_module_config(chat_id, module_key, data)

    return HTMLResponse(
        f'<div class="alert success" id="save-status-{module_key}">'
        f'Saved {get_module_label(module_key)}</div>'
    )


@app.post("/config/{chat_id}/module/{module_key}/reset", response_class=HTMLResponse)
async def reset_module(request: Request, chat_id: str, module_key: str):
    """Reset a per-chat module to global defaults (delete overrides)."""
    if chat_id == "global":
        return HTMLResponse('<div class="alert error">Cannot reset global config</div>', status_code=400)

    mgr = config_manager()
    await mgr.delete_module_overrides(chat_id, module_key)

    return HTMLResponse(
        status_code=200,
        headers={"HX-Redirect": f"/config/{chat_id}"},
        content="",
    )


@app.post("/config/{chat_id}/module/{module_key}/mode")
async def set_module_mode(request: Request, chat_id: str, module_key: str):
    """Set module mode: global, enabled, or disabled (HTMX)."""
    mgr = config_manager()
    form = await request.form()
    mode = form.get("mode", "global")

    if chat_id == "global":
        return HTMLResponse('<div class="alert error">Cannot set mode on global config</div>', status_code=400)

    if mode == "global":
        # Remove all per-chat overrides — inherit from global
        await mgr.delete_module_overrides(chat_id, module_key)
    elif mode == "disabled":
        # Remove config overrides, only store enabled=false
        await mgr.delete_module_overrides(chat_id, module_key)
        await mgr.set_value(chat_id, module_key, "enabled", False)
    elif mode == "enabled":
        # Ensure enabled=true is stored as per-chat override
        await mgr.set_value(chat_id, module_key, "enabled", True)

    # Return full page redirect to refresh the form state
    return HTMLResponse(
        status_code=200,
        headers={"HX-Redirect": f"/config/{chat_id}"},
        content="",
    )


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------
@app.get("/backups", response_class=HTMLResponse)
async def backups_page(request: Request):
    mgr = config_manager()
    backups = await mgr.list_backups()
    chats = await mgr.db.get_chats()
    return templates.TemplateResponse("backups.html", {
        "request": request,
        "backups": backups,
        "chats": chats,
    })


@app.post("/backups/create")
async def create_backup(request: Request):
    form = await request.form()
    name = form.get("name", f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    chat_id = form.get("chat_id", "__full__")
    mgr = config_manager()
    backup_id = await mgr.create_backup(str(name), str(chat_id))
    return RedirectResponse("/backups", status_code=303)


@app.post("/backups/{backup_id}/restore")
async def restore_backup(backup_id: int):
    mgr = config_manager()
    ok = await mgr.restore_backup(backup_id)
    if not ok:
        return HTMLResponse('<div class="alert error">Backup not found</div>', status_code=404)
    return RedirectResponse("/backups", status_code=303)


@app.post("/backups/{backup_id}/delete")
async def delete_backup(backup_id: int):
    mgr = config_manager()
    await mgr.delete_backup(backup_id)
    return RedirectResponse("/backups", status_code=303)


@app.get("/export/{chat_id}")
async def export_chat(chat_id: str):
    """Export a chat's config as JSON download."""
    mgr = config_manager()
    data = await mgr.export_chat(chat_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="config_{chat_id}.json"'},
    )


@app.post("/import/{chat_id}")
async def import_chat(chat_id: str, file: UploadFile = File(...)):
    """Import a chat's config from JSON file."""
    content = await file.read()
    data = json.loads(content)
    mgr = config_manager()
    await mgr.import_chat(chat_id, data)
    return RedirectResponse(f"/config/{chat_id}", status_code=303)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_form_value(value: Any, model_class: type, parts: list[str]) -> Any:
    """Parse a form string value into the correct Python type."""
    if isinstance(value, str):
        # Boolean
        if value.lower() in ("true", "on", "1"):
            return True
        if value.lower() in ("false", "off", "0", ""):
            # Check if the field is boolean
            if _field_is_bool(model_class, parts):
                return False

        # Try numeric
        try:
            if "." in value:
                return float(value)
            return int(value)
        except (ValueError, TypeError):
            pass

        # Try JSON (for lists, dicts)
        if value.startswith("[") or value.startswith("{"):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # Tags (comma-separated)
        if "," in value and _field_is_list(model_class, parts):
            return [v.strip() for v in value.split(",") if v.strip()]

    return value


def _field_is_bool(model_class: type, parts: list[str]) -> bool:
    """Check if a field path points to a bool."""
    try:
        if len(parts) == 1:
            ann = model_class.model_fields[parts[0]].annotation
            return ann is bool
        elif len(parts) == 2:
            sub = model_class.model_fields[parts[0]].annotation
            if sub and hasattr(sub, "model_fields"):
                ann = sub.model_fields[parts[1]].annotation
                return ann is bool
    except (KeyError, AttributeError):
        pass
    return False


def _field_is_list(model_class: type, parts: list[str]) -> bool:
    """Check if a field path points to a list."""
    try:
        if len(parts) == 1:
            ann = model_class.model_fields[parts[0]].annotation
            origin = getattr(ann, "__origin__", None)
            return origin is list
    except (KeyError, AttributeError):
        pass
    return False


def _fill_missing_toggles(data: dict, model_class: type, form: Any) -> None:
    """Fill in False for toggle fields not present in form data (unchecked checkboxes)."""
    for field_name, field_info in model_class.model_fields.items():
        extra = field_info.json_schema_extra or {}
        if extra.get("widget") == "toggle" and field_name not in data and field_name not in form:
            data[field_name] = False

        # Check sub-models too
        if _is_sub_model(model_class, field_name):
            sub_model = field_info.annotation
            if sub_model and hasattr(sub_model, "model_fields"):
                for sub_field, sub_info in sub_model.model_fields.items():
                    sub_extra = sub_info.json_schema_extra or {}
                    full_key = f"{field_name}.{sub_field}"
                    if sub_extra.get("widget") == "toggle" and sub_field not in data.get(field_name, {}) and full_key not in form:
                        if field_name not in data:
                            data[field_name] = {}
                        data[field_name][sub_field] = False


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------
async def start_background(
    host: str = "0.0.0.0",
    port: int = 8080,
) -> asyncio.Task:
    """Start the web config server as a background asyncio task."""
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    logger.info("Config web UI v2 started on http://%s:%s", host, port)
    return task
