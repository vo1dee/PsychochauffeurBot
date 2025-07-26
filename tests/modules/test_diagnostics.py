"""
Tests for the diagnostics module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from modules.diagnostics import run_diagnostics, api_health


class TestDiagnostics:
    """Test diagnostics functionality."""
    
    def test_api_health_global_variable(self):
        """Test that api_health global variable is properly initialized."""
        assert isinstance(api_health, dict)
        assert "last_check" in api_health
        assert "status" in api_health
        assert "consecutive_failures" in api_health
        assert "last_successful" in api_health
        
        # Test initial values
        assert api_health["last_check"] is None
        assert api_health["status"] == "unknown"
        assert api_health["consecutive_failures"] == 0
        assert api_health["last_successful"] is None
    
    @pytest.mark.asyncio
    async def test_run_diagnostics_no_url(self):
        """Test run_diagnostics without URL parameter."""
        with patch('modules.diagnostics.general_logger'):
            result = await run_diagnostics()
            
            # Should return a dictionary
            assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_run_diagnostics_with_url(self):
        """Test run_diagnostics with URL parameter."""
        test_url = "https://api.openai.com"
        
        with patch('modules.diagnostics.general_logger'):
            result = await run_diagnostics(test_url)
            
            # Should return a dictionary
            assert isinstance(result, dict)
    
    def test_module_imports(self):
        """Test that all required modules are imported correctly."""
        import modules.diagnostics as diag
        
        # Test that functions are available
        assert hasattr(diag, 'run_diagnostics')
        assert callable(diag.run_diagnostics)
        
        # Test that global variables are available
        assert hasattr(diag, 'api_health')
        assert isinstance(diag.api_health, dict)
    
    def test_api_health_structure(self):
        """Test that api_health has the correct structure."""
        required_keys = ["last_check", "status", "consecutive_failures", "last_successful"]
        
        for key in required_keys:
            assert key in api_health, f"Missing key: {key}"
        
        # Test data types
        assert isinstance(api_health["consecutive_failures"], int)
        assert isinstance(api_health["status"], str)


class TestDiagnosticsIntegration:
    """Test diagnostics integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_run_diagnostics_integration(self):
        """Test run_diagnostics integration."""
        # Test with None URL
        result1 = await run_diagnostics(None)
        assert isinstance(result1, dict)
        
        # Test with empty string
        result2 = await run_diagnostics("")
        assert isinstance(result2, dict)
        
        # Test with valid URL
        result3 = await run_diagnostics("https://example.com")
        assert isinstance(result3, dict)
    
    def test_api_health_modification(self):
        """Test that api_health can be modified."""
        original_status = api_health["status"]
        original_failures = api_health["consecutive_failures"]
        
        # Modify values
        api_health["status"] = "testing"
        api_health["consecutive_failures"] = 5
        api_health["last_check"] = datetime.now()
        
        # Verify changes
        assert api_health["status"] == "testing"
        assert api_health["consecutive_failures"] == 5
        assert api_health["last_check"] is not None
        
        # Restore original values
        api_health["status"] = original_status
        api_health["consecutive_failures"] = original_failures
        api_health["last_check"] = None
    
    @pytest.mark.asyncio
    async def test_diagnostics_with_mocked_dependencies(self):
        """Test diagnostics with mocked dependencies."""
        with patch('modules.diagnostics.socket') as mock_socket:
            with patch('modules.diagnostics.subprocess') as mock_subprocess:
                with patch('modules.diagnostics.platform') as mock_platform:
                    mock_platform.system.return_value = "Darwin"
                    
                    result = await run_diagnostics("https://test.com")
                    assert isinstance(result, dict)
    
    def test_diagnostics_constants(self):
        """Test that diagnostics uses proper constants."""
        import modules.diagnostics as diag
        
        # Should be able to import without errors
        assert hasattr(diag, 'api_health')
        
        # Test that datetime is available
        assert hasattr(diag, 'datetime')
        
        # Test that asyncio is available
        assert hasattr(diag, 'asyncio')