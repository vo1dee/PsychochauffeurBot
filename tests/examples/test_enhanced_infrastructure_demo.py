"""
Demonstration of the enhanced test infrastructure and utilities.
This module shows how to use all the new testing components.
"""

import pytest
import asyncio
from typing import Dict, Any

# Import the enhanced test utilities
from tests.utils.comprehensive_test_utilities import ComprehensiveTestUtilities
from tests.mocks.enhanced_mocks import EnhancedOpenAIMock, EnhancedDatabaseMock


class TestEnhancedInfrastructureDemo:
    """Demonstration of enhanced test infrastructure capabilities."""
    
    def test_basic_mock_usage(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test basic usage of enhanced mocks."""
        # Get enhanced mocks
        openai_mock = comprehensive_test_utils.get_openai_mock()
        database_mock = comprehensive_test_utils.get_database_mock()
        
        # Configure OpenAI mock
        openai_mock.set_responses(["Hello, this is a test response!"])
        
        # Seed database mock
        test_data = [
            {"id": 1, "name": "Test User", "email": "test@example.com"},
            {"id": 2, "name": "Another User", "email": "another@example.com"}
        ]
        database_mock.seed_data("users", test_data)
        
        # Verify setup
        assert len(database_mock.data["users"]) == 2
        assert openai_mock.responses == ["Hello, this is a test response!"]
        
    @pytest.mark.asyncio
    async def test_async_mock_functionality(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test async mock functionality."""
        # Create async mocks
        async_mock = comprehensive_test_utils.create_async_mock(return_value="async result")
        
        # Test async mock
        result = await async_mock()
        assert result == "async result"
        
        # Test async patterns
        async def sample_async_operation():
            await asyncio.sleep(0.1)
            return "completed"
            
        result = await comprehensive_test_utils.run_with_timeout(
            sample_async_operation(), timeout=1.0
        )
        assert result == "completed"
        
    @pytest.mark.asyncio
    async def test_database_mock_operations(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test database mock operations."""
        database_mock = comprehensive_test_utils.get_database_mock()
        
        # Seed test data
        users = [
            {"id": 1, "username": "testuser1", "active": True},
            {"id": 2, "username": "testuser2", "active": False}
        ]
        database_mock.seed_data("users", users)
        
        # Test database operations
        conn_mock = database_mock.create_connection_mock()
        
        # Test fetch operation
        results = await conn_mock.fetch("SELECT * FROM users")
        assert len(results) == 2
        assert results[0]["username"] == "testuser1"
        
        # Test fetchrow operation
        row = await conn_mock.fetchrow("SELECT * FROM users WHERE id = 1")
        assert row["username"] == "testuser1"
        
    def test_filesystem_mock_operations(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test file system mock operations."""
        fs_mock = comprehensive_test_utils.get_filesystem_mock()
        
        # Create file structure
        structure = {
            "config": {
                "app.json": '{"setting": "value"}',
                "database.json": '{"host": "localhost"}'
            },
            "logs": {
                "app.log": "2024-01-01 INFO: Application started"
            },
            "readme.txt": "This is a test file"
        }
        
        comprehensive_test_utils.create_filesystem_structure(structure)
        
        # Test file operations
        assert fs_mock.exists("config")
        assert fs_mock.is_directory("config")
        assert fs_mock.exists("readme.txt")
        assert fs_mock.is_file("readme.txt")
        
        # Test directory listing
        config_contents = fs_mock.list_directory("config")
        assert "app.json" in config_contents
        assert "database.json" in config_contents
        
    @pytest.mark.asyncio
    async def test_openai_mock_realistic_behavior(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test OpenAI mock with realistic behavior."""
        openai_mock = comprehensive_test_utils.get_openai_mock()
        
        # Configure responses
        responses = [
            "First response",
            "Second response",
            "Third response"
        ]
        openai_mock.set_responses(responses)
        openai_mock.set_delay_range(0.01, 0.02)  # Very short delay for testing
        
        # Create client mock
        client_mock = openai_mock.create_client_mock()
        
        # Test multiple calls
        for i, expected_response in enumerate(responses):
            response = await client_mock.chat.completions.create(
                messages=[{"role": "user", "content": f"Test message {i+1}"}]
            )
            assert response.choices[0].message.content == expected_response
            assert response.usage.total_tokens > 0
            
        assert openai_mock.call_count == 3
        
    def test_security_mock_validation(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test security mock validation functionality."""
        security_mock = comprehensive_test_utils.get_security_mock()
        
        # Test input validation
        valid_input = "This is a normal message"
        result = security_mock.validate_input(valid_input)
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        
        # Test SQL injection detection
        malicious_input = "SELECT * FROM users; DROP TABLE users;"
        result = security_mock.validate_input(malicious_input)
        assert result["valid"] is False
        assert any("SQL injection" in error for error in result["errors"])
        
        # Test XSS detection
        xss_input = "<script>alert('xss')</script>"
        result = security_mock.validate_input(xss_input)
        assert result["valid"] is False
        assert any("XSS" in error for error in result["errors"])
        
    def test_config_mock_operations(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test configuration mock operations."""
        config_mock = comprehensive_test_utils.get_config_mock()
        
        # Test configuration setup
        test_configs = {
            "app_config": {
                "debug": True,
                "log_level": "INFO",
                "features": ["feature1", "feature2"]
            },
            "user_config": {
                "theme": "dark",
                "language": "en",
                "notifications": True
            }
        }
        
        comprehensive_test_utils.setup_config_data(test_configs)
        
        # Test config retrieval
        app_config = config_mock.load_config("app_config")
        assert app_config["debug"] is True
        assert app_config["log_level"] == "INFO"
        
        user_config = config_mock.load_config("user_config")
        assert user_config["theme"] == "dark"
        
    @pytest.mark.asyncio
    async def test_performance_measurement(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test performance measurement capabilities."""
        
        async def fast_operation():
            await asyncio.sleep(0.01)
            return "fast result"
            
        def slow_operation():
            import time
            time.sleep(0.1)
            return "slow result"
            
        # Measure async operation
        async_perf = await comprehensive_test_utils.measure_performance(
            fast_operation, expected_max_time=0.05
        )
        assert async_perf["success"] is True
        assert async_perf["execution_time"] < 0.05
        assert async_perf["result"] == "fast result"
        
        # Measure sync operation
        sync_perf = await comprehensive_test_utils.measure_performance(
            slow_operation, expected_max_time=0.2
        )
        assert sync_perf["success"] is True
        assert sync_perf["execution_time"] > 0.05
        assert sync_perf["result"] == "slow result"
        
    @pytest.mark.asyncio
    async def test_error_injection(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test error injection capabilities."""
        # Configure error injection
        error_config = {
            "openai": {"rate": 1.0},  # 100% error rate
            "database": {"rate": 0.5}  # 50% error rate
        }
        comprehensive_test_utils.inject_errors(error_config)
        
        # Test OpenAI errors
        openai_mock = comprehensive_test_utils.get_openai_mock()
        client_mock = openai_mock.create_client_mock()
        
        with pytest.raises(Exception):
            await client_mock.chat.completions.create(
                messages=[{"role": "user", "content": "test"}]
            )
            
        # Clear errors
        comprehensive_test_utils.clear_all_errors()
        
        # Verify errors are cleared
        assert openai_mock.error_rate == 0.0
        
    @pytest.mark.asyncio
    async def test_integration_context(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test integration test context manager."""
        
        # Define test data
        database_data = {
            "users": [
                {"id": 1, "name": "Test User"},
                {"id": 2, "name": "Another User"}
            ]
        }
        
        filesystem_structure = {
            "config.json": '{"test": true}',
            "data": {
                "file1.txt": "content1",
                "file2.txt": "content2"
            }
        }
        
        config_data = {
            "test_config": {
                "enabled": True,
                "value": 42
            }
        }
        
        # Use integration context
        async with comprehensive_test_utils.integration_test_context(
            scenario="default",
            database_data=database_data,
            filesystem_structure=filesystem_structure,
            config_data=config_data
        ) as utils:
            # Verify setup
            db_mock = utils.get_database_mock()
            assert len(db_mock.data["users"]) == 2
            
            fs_mock = utils.get_filesystem_mock()
            assert fs_mock.exists("config.json")
            assert fs_mock.exists("data")
            
            config_mock = utils.get_config_mock()
            test_config = config_mock.load_config("test_config")
            assert test_config["enabled"] is True
            assert test_config["value"] == 42
            
    def test_quick_setup(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test quick setup functionality."""
        components = comprehensive_test_utils.quick_setup(
            scenario="fast",
            with_database=True,
            with_filesystem=True,
            with_config=True
        )
        
        # Verify all components are available
        assert "database" in components
        assert "filesystem" in components
        assert "config" in components
        assert "openai" in components
        assert "security" in components
        
        # Verify scenario configuration
        openai_mock = components["openai"]
        assert openai_mock.delay_range == (0.01, 0.05)  # Fast scenario
        
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test concurrent async operations."""
        
        async def async_task(task_id: int, delay: float = 0.1):
            await asyncio.sleep(delay)
            return f"Task {task_id} completed"
            
        # Run tasks concurrently
        tasks = [
            async_task(1, 0.05),
            async_task(2, 0.03),
            async_task(3, 0.07)
        ]
        
        results = await comprehensive_test_utils.run_concurrently(*tasks, timeout=1.0)
        
        assert len(results) == 3
        assert "Task 1 completed" in results
        assert "Task 2 completed" in results
        assert "Task 3 completed" in results
        
    def test_mock_validation(self, comprehensive_test_utils: ComprehensiveTestUtilities):
        """Test mock interaction validation."""
        # Use some mocks
        openai_mock = comprehensive_test_utils.get_openai_mock()
        database_mock = comprehensive_test_utils.get_database_mock()
        
        # Simulate some usage
        openai_mock.call_count = 3
        database_mock.query_count = 5
        
        # Validate interactions
        validation_results = comprehensive_test_utils.validate_mock_interactions()
        
        assert validation_results["openai_calls"] == 3
        assert validation_results["database_queries"] == 5
        assert validation_results["validation_passed"] is True