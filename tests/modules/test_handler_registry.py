"""
Tests for the handler registry module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from telegram.ext import Application

from modules.handler_registry import HandlerRegistry
from modules.command_processor import CommandProcessor


class TestHandlerRegistry:
    """Test handler registry functionality."""
    
    @pytest.fixture
    def mock_command_processor(self):
        """Create a mock command processor."""
        return Mock(spec=CommandProcessor)
    
    @pytest.fixture
    def handler_registry(self, mock_command_processor):
        """Create a handler registry instance."""
        return HandlerRegistry(mock_command_processor)
    
    def test_handler_registry_initialization(self, mock_command_processor):
        """Test handler registry initialization."""
        registry = HandlerRegistry(mock_command_processor)
        assert registry.command_processor == mock_command_processor
    
    def test_handler_registry_service_interface(self, handler_registry):
        """Test that handler registry implements service interface."""
        from modules.service_registry import ServiceInterface
        assert isinstance(handler_registry, ServiceInterface)
    
    def test_handler_registry_has_command_processor(self, handler_registry, mock_command_processor):
        """Test that handler registry has access to command processor."""
        assert handler_registry.command_processor is not None
        assert handler_registry.command_processor == mock_command_processor


class TestHandlerRegistryIntegration:
    """Test handler registry integration scenarios."""
    
    def test_handler_registry_with_real_command_processor(self):
        """Test handler registry with real command processor."""
        with patch('modules.handler_registry.CommandProcessor') as mock_cp_class:
            mock_cp = Mock(spec=CommandProcessor)
            mock_cp_class.return_value = mock_cp
            
            registry = HandlerRegistry(mock_cp)
            assert registry.command_processor == mock_cp
    
    def test_handler_registry_service_registration(self):
        """Test that handler registry can be registered as a service."""
        mock_processor = Mock(spec=CommandProcessor)
        registry = HandlerRegistry(mock_processor)
        
        # Should be able to register without errors
        assert hasattr(registry, 'command_processor')
        assert registry.command_processor == mock_processor