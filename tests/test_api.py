"""Tests for the API module."""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import json

import api


class TestAPIHandlers(AioHTTPTestCase):
    """Test API handlers."""

    async def get_application(self):
        """Create test application."""
        return api.create_app()

    @unittest_run_loop
    async def test_handle_get_config_success(self):
        """Test successful config retrieval."""
        with patch('api.ConfigManager') as mock_config_manager:
            mock_manager = AsyncMock()
            mock_manager.get_config.return_value = {'test': 'data'}
            mock_config_manager.return_value = mock_manager
            
            resp = await self.client.request(
                "GET", 
                "/config/test_module?chat_id=123&chat_type=private"
            )
            
            assert resp.status == 200
            data = await resp.json()
            assert data['config_name'] == 'test_module'
            assert data['chat_id'] == '123'
            assert data['chat_type'] == 'private'
            assert data['config_data'] == {'test': 'data'}

    @unittest_run_loop
    async def test_handle_get_config_no_params(self):
        """Test config retrieval without parameters."""
        with patch('api.ConfigManager') as mock_config_manager:
            mock_manager = AsyncMock()
            mock_manager.get_config.return_value = {'default': 'config'}
            mock_config_manager.return_value = mock_manager
            
            resp = await self.client.request("GET", "/config/test_module")
            
            assert resp.status == 200
            data = await resp.json()
            assert data['config_name'] == 'test_module'
            assert data['chat_id'] is None
            assert data['chat_type'] is None

    @unittest_run_loop
    async def test_handle_set_config_success(self):
        """Test successful config setting."""
        with patch('api.ConfigManager') as mock_config_manager:
            mock_manager = AsyncMock()
            mock_manager.save_config.return_value = True
            mock_config_manager.return_value = mock_manager
            
            payload = {
                'chat_id': '123',
                'chat_type': 'private',
                'config_data': {'key': 'value'}
            }
            
            resp = await self.client.request(
                "POST", 
                "/config/test_module",
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            assert resp.status == 200
            data = await resp.json()
            assert data['status'] == 'ok'

    @unittest_run_loop
    async def test_handle_set_config_invalid_json(self):
        """Test config setting with invalid JSON."""
        resp = await self.client.request(
            "POST", 
            "/config/test_module",
            data="invalid json",
            headers={'Content-Type': 'application/json'}
        )
        
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
        assert data['error'] == 'Invalid JSON'

    @unittest_run_loop
    async def test_handle_set_config_missing_config_data(self):
        """Test config setting without config_data."""
        payload = {
            'chat_id': '123',
            'chat_type': 'private'
            # Missing config_data
        }
        
        resp = await self.client.request(
            "POST", 
            "/config/test_module",
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
        assert data['error'] == 'config_data required'

    @unittest_run_loop
    async def test_handle_set_config_save_failure(self):
        """Test config setting when save fails."""
        with patch('api.ConfigManager') as mock_config_manager:
            mock_manager = AsyncMock()
            mock_manager.save_config.return_value = False
            mock_config_manager.return_value = mock_manager
            
            payload = {
                'chat_id': '123',
                'chat_type': 'private',
                'config_data': {'key': 'value'}
            }
            
            resp = await self.client.request(
                "POST", 
                "/config/test_module",
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            assert resp.status == 500
            data = await resp.json()
            assert 'error' in data
            assert data['error'] == 'Failed to save config'


class TestAPIUtilities:
    """Test API utility functions."""

    def test_create_app(self):
        """Test application creation."""
        app = api.create_app()
        assert isinstance(app, web.Application)
        
        # Check that routes are registered
        routes = [route.method + ' ' + route.resource.canonical for route in app.router.routes()]
        assert 'GET /config/{config_name}' in routes
        assert 'POST /config/{config_name}' in routes

    @patch('api.web.run_app')
    @patch('api.argparse.ArgumentParser')
    def test_main_default_args(self, mock_parser, mock_run_app):
        """Test main function with default arguments."""
        mock_args = Mock()
        mock_args.host = '0.0.0.0'
        mock_args.port = 8000
        mock_parser.return_value.parse_args.return_value = mock_args
        
        api.main()
        
        mock_run_app.assert_called_once()
        call_args = mock_run_app.call_args
        assert call_args[1]['host'] == '0.0.0.0'
        assert call_args[1]['port'] == 8000

    @patch('api.web.run_app')
    @patch('api.argparse.ArgumentParser')
    def test_main_custom_args(self, mock_parser, mock_run_app):
        """Test main function with custom arguments."""
        mock_args = Mock()
        mock_args.host = '127.0.0.1'
        mock_args.port = 9000
        mock_parser.return_value.parse_args.return_value = mock_args
        
        api.main()
        
        mock_run_app.assert_called_once()
        call_args = mock_run_app.call_args
        assert call_args[1]['host'] == '127.0.0.1'
        assert call_args[1]['port'] == 9000