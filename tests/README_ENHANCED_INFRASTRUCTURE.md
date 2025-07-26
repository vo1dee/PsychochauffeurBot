# Enhanced Test Infrastructure

This document describes the enhanced test infrastructure and utilities that have been implemented to improve test coverage and reliability.

## Overview

The enhanced test infrastructure provides:

1. **Shared Test Fixtures** - Common data structures and mock services
2. **Reusable Mock Classes** - Enhanced mocks for external services (OpenAI, database, file system)
3. **Async Test Utilities** - Patterns for consistent async testing
4. **Comprehensive Test Utilities** - Unified interface for all testing needs

## Components

### 1. Shared Fixtures (`tests/fixtures/shared_fixtures.py`)

Provides comprehensive fixtures for:
- **Core Data Structures**: Sample user, chat, message, config, and error data
- **File System**: Temporary directories with realistic structure
- **Database Records**: Sample database records for testing
- **Test Scenarios**: Common test scenarios and error cases
- **Performance Thresholds**: Performance benchmarks for operations

```python
def test_with_sample_data(sample_user_data, sample_chat_data):
    assert sample_user_data["user_id"] == 12345
    assert sample_chat_data["chat_type"] == "supergroup"
```

### 2. Enhanced Mocks (`tests/mocks/enhanced_mocks.py`)

#### EnhancedOpenAIMock
- Realistic response simulation with delays
- Configurable error rates and token usage
- Multiple response cycling

```python
def test_openai_mock(openai_mock):
    openai_mock.set_responses(["Hello!", "How can I help?"])
    openai_mock.set_error_rate(0.1)  # 10% error rate
    openai_mock.set_delay_range(0.1, 0.5)  # 100-500ms delay
```

#### EnhancedDatabaseMock
- Data persistence across operations
- Realistic query simulation
- Transaction support
- Configurable error injection

```python
def test_database_mock(database_mock):
    # Seed test data
    database_mock.seed_data("users", [{"id": 1, "name": "Test"}])
    
    # Create connection mock
    conn = database_mock.create_connection_mock()
    results = await conn.fetch("SELECT * FROM users")
    assert len(results) == 1
```

#### EnhancedFileSystemMock
- Virtual file system with permissions
- Realistic I/O delays and errors
- Directory structure support

```python
def test_filesystem_mock(filesystem_mock):
    filesystem_mock.create_file("/test.txt", "content")
    filesystem_mock.create_directory("/data")
    
    assert filesystem_mock.exists("/test.txt")
    assert filesystem_mock.is_directory("/data")
```

#### EnhancedConfigManagerMock
- Configuration validation
- Change history tracking
- Backup simulation

```python
def test_config_mock(config_mock):
    config = {"debug": True, "log_level": "INFO"}
    await config_mock.save_config("app", config)
    
    loaded = config_mock.load_config("app")
    assert loaded["debug"] is True
```

#### EnhancedSecurityValidatorMock
- Input validation (SQL injection, XSS, path traversal)
- File upload validation
- Rate limiting simulation

```python
def test_security_mock(security_mock):
    result = security_mock.validate_input("SELECT * FROM users")
    assert result["valid"] is False
    assert "SQL injection" in result["errors"][0]
```

### 3. Async Test Utilities (`tests/utils/async_test_utilities.py`)

#### AsyncTestEventLoopManager
- Proper event loop setup and cleanup
- Task cancellation and timeout handling

#### AsyncMockManager
- Standardized async mock creation
- Context manager and iterator mocks
- Automatic cleanup

#### AsyncTestPatterns
- Common async testing patterns
- Timeout and concurrency utilities
- Performance measurement

```python
@pytest.mark.asyncio
async def test_async_patterns(async_test_patterns):
    # Run with timeout
    result = await async_test_patterns.run_with_timeout(
        some_async_operation(), timeout=5.0
    )
    
    # Run concurrently
    results = await async_test_patterns.run_concurrently(
        task1(), task2(), task3()
    )
    
    # Wait for condition
    await async_test_patterns.wait_for_condition(
        lambda: some_condition_is_true(),
        timeout=10.0
    )
```

### 4. Comprehensive Test Utilities (`tests/utils/comprehensive_test_utilities.py`)

Unified interface that combines all components:

```python
def test_comprehensive_utilities(comprehensive_test_utils):
    # Quick setup
    components = comprehensive_test_utils.quick_setup(
        scenario="fast",
        with_database=True,
        with_filesystem=True
    )
    
    # Configure test scenario
    comprehensive_test_utils.configure_test_scenario("error_prone")
    
    # Measure performance
    perf = await comprehensive_test_utils.measure_performance(
        some_operation, expected_max_time=1.0
    )
```

### 5. Enhanced Conftest (`tests/enhanced_conftest.py`)

Integrates all components with pytest:
- Enhanced event loop management
- Mock registry fixtures
- Async test utilities
- Custom pytest markers

## Usage Examples

### Basic Mock Usage

```python
def test_basic_functionality(comprehensive_test_utils):
    # Get enhanced mocks
    openai_mock = comprehensive_test_utils.get_openai_mock()
    database_mock = comprehensive_test_utils.get_database_mock()
    
    # Configure mocks
    openai_mock.set_responses(["Test response"])
    database_mock.seed_data("users", [{"id": 1, "name": "Test"}])
    
    # Your test logic here
```

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_functionality(comprehensive_test_utils):
    # Create async mocks
    async_mock = comprehensive_test_utils.create_async_mock(
        return_value="async result"
    )
    
    # Test with timeout
    result = await comprehensive_test_utils.run_with_timeout(
        async_operation(), timeout=5.0
    )
    
    # Assert async completion
    await comprehensive_test_utils.assert_async_operation_completes(
        another_async_operation()
    )
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_integration(comprehensive_test_utils):
    async with comprehensive_test_utils.integration_test_context(
        scenario="default",
        database_data={"users": [{"id": 1, "name": "Test"}]},
        filesystem_structure={"config.json": '{"test": true}'},
        config_data={"app": {"debug": True}}
    ) as utils:
        # Full integration test with all components set up
        result = await run_full_system_test()
        assert result.success
```

### Performance Testing

```python
@pytest.mark.asyncio
async def test_performance(comprehensive_test_utils):
    # Measure operation performance
    perf_data = await comprehensive_test_utils.measure_performance(
        expensive_operation,
        expected_max_time=2.0
    )
    
    assert perf_data["success"]
    assert perf_data["execution_time"] < 2.0
```

### Error Testing

```python
def test_error_handling(comprehensive_test_utils):
    # Inject errors
    comprehensive_test_utils.inject_errors({
        "openai": {"rate": 0.5},  # 50% error rate
        "database": {"rate": 0.2}  # 20% error rate
    })
    
    # Test error handling
    with pytest.raises(SomeExpectedException):
        operation_that_should_fail()
    
    # Clear errors
    comprehensive_test_utils.clear_all_errors()
```

## Test Scenarios

The infrastructure supports several predefined test scenarios:

- **default**: Normal operation with minimal delays
- **error_prone**: Higher error rates for testing error handling
- **slow_network**: Increased delays to simulate slow network
- **fast**: Minimal delays for quick test execution

```python
@pytest.mark.parametrize("scenario", ["default", "error_prone", "slow_network"])
def test_different_scenarios(comprehensive_test_utils, scenario):
    comprehensive_test_utils.configure_test_scenario(scenario)
    # Test logic that adapts to different scenarios
```

## Pytest Markers

Custom markers for organizing tests:

- `@pytest.mark.async_test`: Async tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.external_service`: Tests requiring external services
- `@pytest.mark.database`: Database tests
- `@pytest.mark.filesystem`: File system tests

## Best Practices

1. **Use Comprehensive Test Utilities**: Start with `comprehensive_test_utils` fixture for most tests
2. **Configure Scenarios**: Use appropriate test scenarios for different testing needs
3. **Measure Performance**: Use built-in performance measurement for critical operations
4. **Test Error Conditions**: Use error injection to test error handling
5. **Clean Up**: Fixtures automatically clean up, but manual cleanup is available
6. **Async Testing**: Use async utilities for proper async test management

## Migration from Existing Tests

To migrate existing tests to use the enhanced infrastructure:

1. Replace manual mock setup with enhanced mocks
2. Use `comprehensive_test_utils` fixture
3. Replace manual async setup with async utilities
4. Add appropriate pytest markers
5. Use integration context for complex tests

## Examples

See `tests/examples/test_enhanced_infrastructure_demo.py` for comprehensive examples of all features.

## Performance Benefits

The enhanced infrastructure provides:
- **Faster Test Execution**: Optimized event loop management
- **Better Isolation**: Proper cleanup prevents test interference
- **Realistic Testing**: Enhanced mocks simulate real-world conditions
- **Easier Debugging**: Better error messages and logging
- **Consistent Patterns**: Standardized approaches across all tests