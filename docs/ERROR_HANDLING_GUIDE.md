# Error Handling Guide

This guide provides comprehensive documentation for the standardized error handling framework in the PsychoChauffeur Bot.

## Overview

The error handling framework provides consistent error management across the entire application with:

- **Standardized error classes** with severity levels and categories
- **Decorators** for automatic error handling in different contexts
- **User-friendly messaging** with appropriate feedback
- **Comprehensive logging** and analytics
- **Retry mechanisms** for transient failures
- **Circuit breaker patterns** for preventing cascade failures

## Core Components

### 1. StandardError Class

The `StandardError` class is the foundation of our error handling system:

```python
from modules.error_handler import StandardError, ErrorSeverity, ErrorCategory

# Create a standardized error
error = StandardError(
    message="Database connection failed",
    severity=ErrorSeverity.HIGH,
    category=ErrorCategory.DATABASE,
    context={"operation": "user_lookup", "retry_count": 3},
    original_exception=original_exception
)
```

#### Error Severities

- **LOW**: Minor issues that don't affect functionality
- **MEDIUM**: Significant issues that degrade some functionality  
- **HIGH**: Critical issues that break core functionality
- **CRITICAL**: Fatal errors requiring immediate attention

#### Error Categories

- **NETWORK**: Network/connection issues
- **API**: External API errors
- **DATABASE**: Database errors
- **PARSING**: Data parsing/formatting issues
- **INPUT**: User input validation errors
- **PERMISSION**: Authorization/permission errors
- **RESOURCE**: Resource (file/memory) errors
- **GENERAL**: Uncategorized errors

### 2. Error Handling Decorators

#### Command Handler Decorator

Use for Telegram command handlers:

```python
from modules.error_decorators import handle_command_errors, telegram_command

@telegram_command(
    feedback_message="Weather service is temporarily unavailable.",
    fallback_response="Please try again later."
)
async def weather_command(update: Update, context: CallbackContext):
    # Command implementation
    pass

# Or with more control:
@handle_command_errors(
    feedback_message="Custom error message",
    severity=ErrorSeverity.MEDIUM,
    category=ErrorCategory.API,
    retry_count=2,
    fallback_response="Service unavailable"
)
async def my_command(update: Update, context: CallbackContext):
    # Command implementation
    pass
```

#### Service Method Decorator

Use for service layer methods:

```python
from modules.error_decorators import handle_service_errors

@handle_service_errors(
    service_name="WeatherAPI",
    fallback_value=None,
    log_errors=True,
    raise_on_critical=True
)
async def get_weather_data(city: str):
    # Service implementation
    pass
```

#### Database Operation Decorator

Use for database operations:

```python
from modules.error_decorators import database_operation

@database_operation("user_lookup")
async def get_user_by_id(user_id: int):
    # Database operation
    pass
```

#### Network/API Call Decorator

Use for external API calls:

```python
from modules.error_decorators import external_api

@external_api("OpenAI", timeout=30.0)
async def call_openai_api(prompt: str):
    # API call implementation
    pass
```

#### Input Validation Decorator

Use for input validation:

```python
from modules.error_decorators import user_input_validation

@user_input_validation("email_address")
async def validate_email(email: str):
    # Validation logic
    pass
```

#### Circuit Breaker Decorator

Use to prevent cascade failures:

```python
from modules.error_decorators import circuit_breaker

@circuit_breaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=ConnectionError
)
async def external_service_call():
    # External service call
    pass
```

### 3. Error Messages and User Feedback

#### Getting User-Friendly Messages

```python
from modules.error_messages import get_user_error_message, get_error_response
from modules.error_handler import ErrorCategory, ErrorSeverity

# Get a simple message
message = get_user_error_message(
    ErrorCategory.NETWORK,
    ErrorSeverity.MEDIUM
)

# Get a complete response for Telegram
response = get_error_response(
    ErrorCategory.API,
    ErrorSeverity.HIGH,
    custom_message="OpenAI service is down",
    include_help=True
)

# Send to user
await update.message.reply_text(response["text"], parse_mode=response["parse_mode"])
```

#### Admin Error Reports

```python
from modules.error_messages import get_admin_error_report

admin_report = get_admin_error_report(
    ErrorCategory.DATABASE,
    function_name="get_user_preferences",
    context={"user_id": 12345, "retry_count": 3},
    original_error="Connection timeout"
)
```

## Best Practices

### 1. Choosing the Right Decorator

- **Command handlers**: Use `@telegram_command` or `@handle_command_errors`
- **Service methods**: Use `@handle_service_errors`
- **Database operations**: Use `@database_operation`
- **External APIs**: Use `@external_api`
- **Input validation**: Use `@user_input_validation`
- **Unreliable services**: Add `@circuit_breaker`

### 2. Error Severity Guidelines

- **LOW**: Validation errors, minor formatting issues
- **MEDIUM**: Service unavailable, parsing errors, user input errors
- **HIGH**: Database failures, critical API failures, permission errors
- **CRITICAL**: System-wide failures, security breaches, data corruption

### 3. Error Categories

Choose the most specific category:
- Use **NETWORK** for connection issues
- Use **API** for external service errors
- Use **DATABASE** for data persistence issues
- Use **INPUT** for user input validation
- Use **PERMISSION** for authorization failures
- Use **RESOURCE** for file/memory issues
- Use **GENERAL** only when no other category fits

### 4. Context Information

Always provide relevant context:

```python
context = {
    "user_id": update.effective_user.id,
    "chat_id": update.effective_chat.id,
    "command": "weather",
    "parameters": {"city": "Kyiv"},
    "retry_count": 2
}
```

### 5. User Feedback

- **Always** provide user-friendly messages
- **Never** expose technical details to users
- **Include** helpful suggestions when possible
- **Use** appropriate stickers for visual feedback

## Error Handling Patterns

### 1. Command Handler Pattern

```python
@telegram_command("Weather service error occurred.")
async def weather_command(update: Update, context: CallbackContext):
    try:
        # Main command logic
        weather_data = await weather_service.get_weather(city)
        await update.message.reply_text(format_weather(weather_data))
    except WeatherServiceError as e:
        # Specific error handling if needed
        await update.message.reply_text("Weather service is temporarily down.")
        raise  # Re-raise to let decorator handle logging
```

### 2. Service Layer Pattern

```python
class WeatherService:
    @external_api("OpenWeatherMap", timeout=10.0)
    async def get_weather(self, city: str):
        # API call logic
        pass
    
    @handle_service_errors("WeatherService", fallback_value={})
    async def get_cached_weather(self, city: str):
        # Cache lookup logic
        pass
```

### 3. Database Layer Pattern

```python
class UserRepository:
    @database_operation("user_creation")
    async def create_user(self, user_data: dict):
        # Database insertion logic
        pass
    
    @database_operation("user_lookup")
    async def get_user(self, user_id: int):
        # Database query logic
        pass
```

### 4. Validation Pattern

```python
@user_input_validation("city_name")
async def validate_city_name(city: str) -> str:
    if not city or len(city.strip()) < 2:
        raise ValueError("City name must be at least 2 characters")
    
    if len(city) > 50:
        raise ValueError("City name too long")
    
    return city.strip().title()
```

## Error Analytics and Monitoring

### 1. Error Tracking

Errors are automatically tracked for analytics:

```python
from modules.error_analytics import error_tracker

# Get error statistics
stats = await error_tracker.get_error_stats(hours=24)
print(f"Errors in last 24h: {stats['total_count']}")

# Get error patterns
patterns = await error_tracker.get_error_patterns()
for pattern in patterns:
    print(f"Pattern: {pattern['category']} - {pattern['count']} occurrences")
```

### 2. Error Reports

Generate error reports for administrators:

```python
from modules.error_analytics import generate_error_report

report = await generate_error_report(
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
    include_patterns=True
)
```

## Testing Error Handling

### 1. Unit Tests

```python
import pytest
from modules.error_handler import StandardError, ErrorSeverity, ErrorCategory

@pytest.mark.asyncio
async def test_command_error_handling():
    # Test that errors are properly handled
    with pytest.raises(StandardError) as exc_info:
        await my_command_function()
    
    assert exc_info.value.severity == ErrorSeverity.MEDIUM
    assert exc_info.value.category == ErrorCategory.API
```

### 2. Integration Tests

```python
@pytest.mark.asyncio
async def test_error_feedback_to_user(mock_update):
    # Test that users receive appropriate feedback
    await command_with_error(mock_update, mock_context)
    
    # Verify user received error message
    mock_update.message.reply_text.assert_called_once()
    message = mock_update.message.reply_text.call_args[0][0]
    assert "temporarily unavailable" in message.lower()
```

## Migration Guide

### Updating Existing Code

1. **Replace generic try/catch blocks** with specific decorators:

```python
# Before
async def my_command(update, context):
    try:
        result = await external_api_call()
    except Exception as e:
        await update.message.reply_text("Error occurred")
        logger.error(f"Error: {e}")

# After
@telegram_command("Service temporarily unavailable")
async def my_command(update, context):
    result = await external_api_call()
```

2. **Add appropriate error categories** to existing StandardError usage:

```python
# Before
raise StandardError("Database error")

# After
raise StandardError(
    message="Database connection failed",
    severity=ErrorSeverity.HIGH,
    category=ErrorCategory.DATABASE,
    context={"operation": "user_lookup"}
)
```

3. **Use error message utilities** for consistent user feedback:

```python
# Before
await update.message.reply_text("Error occurred")

# After
response = get_error_response(ErrorCategory.API, ErrorSeverity.MEDIUM)
await update.message.reply_text(response["text"], parse_mode=response["parse_mode"])
```

## Troubleshooting

### Common Issues

1. **Decorator not catching errors**: Ensure the decorator is applied to async functions correctly
2. **User not receiving feedback**: Check that Update object is properly passed to error handler
3. **Circular imports**: Import error handling modules at function level if needed
4. **Performance impact**: Use appropriate retry counts and timeouts

### Debug Mode

Enable debug logging for error handling:

```python
import logging
logging.getLogger('modules.error_handler').setLevel(logging.DEBUG)
```

## Configuration

Error handling behavior can be configured:

```python
# In your configuration
ERROR_HANDLING_CONFIG = {
    "default_retry_count": 3,
    "default_timeout": 30.0,
    "circuit_breaker_threshold": 5,
    "enable_user_feedback": True,
    "log_level": "INFO"
}
```

This guide should be updated as the error handling framework evolves. For questions or suggestions, contact the development team.