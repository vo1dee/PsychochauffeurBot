"""Configuration API server using aiohttp."""
import os
import argparse
from typing import Dict, Any
from aiohttp import web

from config.config_manager import ConfigManager

async def handle_get_config(request: web.Request) -> web.Response:
    config_name = request.match_info.get('config_name')
    chat_id = request.query.get('chat_id')
    chat_type = request.query.get('chat_type')
    config_manager = ConfigManager()
    data = await config_manager.get_config(chat_id=chat_id, chat_type=chat_type, module_name=config_name)
    return web.json_response({
        'config_name': config_name,
        'chat_id': chat_id,
        'chat_type': chat_type,
        'config_data': data
    })

async def handle_set_config(request: web.Request) -> web.Response:
    config_name = request.match_info.get('config_name')
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400)
    chat_id = payload.get('chat_id')
    chat_type = payload.get('chat_type', 'global')
    config_data = payload.get('config_data')
    if config_data is None:
        return web.json_response({'error': 'config_data required'}, status=400)
    
    config_manager = ConfigManager()
    success = await config_manager.save_config(config_data, module_name=config_name, chat_id=chat_id, chat_type=chat_type)
    if not success:
        return web.json_response({'error': 'Failed to save config'}, status=500)
    return web.json_response({'status': 'ok'})

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get('/config/{config_name}', handle_get_config)
    app.router.add_post('/config/{config_name}', handle_set_config)
    return app

def main() -> None:
    parser = argparse.ArgumentParser(description='Start the Configuration API server.')
    parser.add_argument('--host', default='0.0.0.0', help='Host to listen on')
    parser.add_argument('--port', type=int, default=int(os.environ.get('CONFIG_API_PORT', 8000)), help='Port to listen on')
    args = parser.parse_args()
    app = create_app()
    web.run_app(app, host=args.host, port=args.port)

if __name__ == '__main__':
    main()