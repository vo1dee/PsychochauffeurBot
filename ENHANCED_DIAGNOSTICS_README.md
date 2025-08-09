# Enhanced Error Logging and Diagnostics System

This document describes the comprehensive error logging and diagnostics system implemented for the Telegram bot application. The system provides structured logging, metrics tracking, external service monitoring, and graceful error handling with user-friendly messages.

## Overview

The enhanced diagnostics system addresses the following requirements:
- **3.1**: Structured logging for all command executions with metrics tracking
- **3.2**: Detailed error context capture for debugging purposes
- **3.3**: Diagnostic information collection for configuration issues
- **3.4**: Monitoring for external service availability and timeouts
- **3.5**: Graceful error handling with user-friendly messages

## Architecture

### Core Components

1. **Enhanced Error Diagnostics** (`modules/enhanced_error_diagnostics.py`)
   - Central diagnostics system with comprehensive logging
   - Performance metrics tracking
   - External service health monitoring
   - System resource monitoring

2. **Command Diagnostics** (`modules/command_diagnostics.py`)
   - Command execution tracking and wrapping utilities
   - Database and API call tracking
   - Configuration validation
   - Dependency health checks

3. **Enhanced Command Implementations**
   - `modules/enhanced_analyze_command.py` - Enhanced analyze command
   - `modules/enhanced_flares_command.py` - Enhanced flares command
   - `modules/diagnostics_command.py` - System diagnostics command

4. **Integration and Initialization**
   - `modules/diagnostics_init.py` - System initialization and lifecycle management
   - `modules/diagnostics_integration.py` - Integration utilities for existing applications

## Features

### 1. Comprehensive Command Execution Tracking

Every command execution is tracked with detailed metrics:

```python
async with enhanced_diagnostics.track_command_execution(
    command_name="analyze",
    user_id=user_id,
    chat_id=chat_id
) as metrics:
    # Command execution
    pass
```

**Tracked Metrics:**
- Execution duration
- Memory usage
- CPU usage
- Database queries count
- API calls count
- Success/failure status
- Error details

### 2. External Service Health Monitoring

Continuous monitoring of external services:
- OpenRouter API
- Database connections
- MeteoAgent API
- Telegram API

**Service Health Metrics:**
- Response time
- Availability percentage
- Consecutive failures
- Last error information

### 3. Structured Error Logging

All errors are logged with comprehensive context:

```python
{
  "timestamp": "2025-01-08T10:30:00+02:00",
  "event": "command_execution_error",
  "command_name": "analyze",
  "user_id": 12345,
  "chat_id": -67890,
  "error_details": {
    "error_type": "DatabaseConnectionError",
    "error_message": "Connection timeout",
    "traceback": "...",
    "system_state": {...}
  },
  "service_health": {...}
}
```

### 4. User-Friendly Error Messages

Automatic translation of technical errors to user-friendly messages in Ukrainian:

```python
# Technical error: "asyncpg.exceptions.ConnectionDoesNotExistError"
# User message: "❌ Виникла проблема з підключенням до бази даних. Спробуйте пізніше або зверніться до адміністратора."
```

### 5. Configuration and Dependency Validation

Automatic validation of command requirements:

```python
config_validation = await validate_command_configuration("analyze")
dependency_check = await check_command_dependencies("analyze")
```

### 6. Performance Metrics and Milestones

Detailed performance tracking throughout command execution:

```python
log_command_milestone("analyze", "arguments_parsed", message_count=50)
log_command_performance_metric("analyze", "messages_processed", 50, "count")
```

## Usage

### Basic Integration

For new applications:

```python
from telegram.ext import Application
from modules.diagnostics_integration import setup_enhanced_diagnostics

# Create application
application = Application.builder().token("YOUR_BOT_TOKEN").build()

# Set up enhanced diagnostics
enhanced_commands = setup_enhanced_diagnostics(application)

# Add command handlers
from telegram.ext import CommandHandler
for command_name, handler in enhanced_commands.items():
    application.add_handler(CommandHandler(command_name, handler))

# Run application
application.run_polling()
```

### Existing Application Integration

For existing applications:

```python
from modules.diagnostics_integration import ExampleIntegration

# Integrate with existing application
ExampleIntegration.integrate_with_existing_bot(your_existing_application)
```

### Manual Command Enhancement

To enhance individual commands:

```python
from modules.command_diagnostics import enhance_command_with_diagnostics

@enhance_command_with_diagnostics("my_command")
async def my_command(update, context):
    # Your command implementation
    pass
```

### Database Operation Tracking

Track database operations within commands:

```python
async with track_database_query("SELECT", "messages") as db_tracker:
    messages = await get_messages_for_chat_today(chat_id)
    db_tracker.set_rows_affected(len(messages))
```

### API Call Tracking

Track external API calls:

```python
async with track_api_call("openrouter", "/chat/completions", "POST") as api_tracker:
    response = await make_api_call()
    api_tracker.set_status_code(response.status_code)
```

## Available Commands

### Enhanced Commands

1. **`/analyze`** - Enhanced analyze command with comprehensive diagnostics
2. **`/flares`** - Enhanced flares command with comprehensive diagnostics

### Diagnostic Commands

1. **`/diagnostics`** - Comprehensive system health report
   - `/diagnostics quick` - Quick health check
   - `/diagnostics services` - Service health only
   - `/diagnostics errors` - Recent errors only
   - `/diagnostics config` - Configuration validation
   - `/diagnostics commands` - Command execution metrics

2. **`/diagnostics_health`** - Diagnostics system health check

## Monitoring and Alerts

### Service Health Monitoring

The system continuously monitors external services and logs health status:

```python
# Service health summary
{
  "openrouter_api": {
    "status": "healthy",
    "response_time_ms": 250.5,
    "availability_percent": 99.8,
    "consecutive_failures": 0
  },
  "database": {
    "status": "healthy",
    "response_time_ms": 15.2,
    "availability_percent": 100.0,
    "consecutive_failures": 0
  }
}
```

### Error Analytics

Comprehensive error tracking and analysis:

```python
# Error summary
{
  "total_errors": 42,
  "by_category": {
    "database": 15,
    "api": 12,
    "network": 8,
    "parsing": 7
  },
  "by_severity": {
    "low": 20,
    "medium": 15,
    "high": 5,
    "critical": 2
  },
  "common_errors": [
    {"message": "Database connection timeout", "count": 8},
    {"message": "API rate limit exceeded", "count": 6}
  ]
}
```

## Configuration

### Environment Variables

Required configuration for enhanced diagnostics:

```bash
# Required for analyze command
OPENROUTER_API_KEY=your_api_key
DATABASE_URL=postgresql://user:pass@localhost/db

# Required for flares command
SCREENSHOT_DIR=/path/to/screenshots

# Optional diagnostics configuration
DIAGNOSTICS_LOG_LEVEL=INFO
DIAGNOSTICS_MONITORING_INTERVAL=300  # seconds
```

### Configuration Validation

The system automatically validates configuration for each command:

```python
# Analyze command validation
- OPENROUTER_API_KEY present
- DATABASE_URL configured
- Database connectivity

# Flares command validation  
- wkhtmltoimage tool available
- Screenshot directory writable
- MeteoAgent API accessible
```

## Logging Structure

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General information and milestones
- **WARNING**: Warning conditions and degraded performance
- **ERROR**: Error conditions that don't stop execution
- **CRITICAL**: Critical errors requiring immediate attention

### Log Format

All logs follow a structured format:

```json
{
  "timestamp": "2025-01-08T10:30:00.123+02:00",
  "level": "INFO",
  "logger": "enhanced_analyze",
  "message": "Command analyze executed successfully",
  "data": {
    "event": "command_success",
    "command_name": "analyze",
    "user_id": 12345,
    "chat_id": -67890,
    "duration_seconds": 2.456,
    "message_count": 50,
    "result_length": 1024
  }
}
```

## Error Handling Patterns

### Graceful Degradation

Commands implement graceful degradation when services are unavailable:

1. **Database Issues**: Use cached results when available
2. **API Failures**: Provide fallback responses
3. **Tool Unavailability**: Clear error messages with solutions

### User-Friendly Messages

All error messages are translated to user-friendly Ukrainian text:

```python
# Database errors
"❌ Виникла проблема з підключенням до бази даних. Спробуйте пізніше або зверніться до адміністратора."

# Network errors  
"❌ Проблема з мережевим підключенням. Перевірте інтернет-з'єднання та спробуйте пізніше."

# API errors
"❌ Сервіс тимчасово недоступний. Спробуйте пізніше або зверніться до адміністратора."
```

## Performance Optimization

### Resource Monitoring

The system monitors resource usage and provides optimization recommendations:

- Memory usage tracking per command
- CPU usage monitoring
- Database connection pool monitoring
- File system usage tracking

### Caching Strategy

Intelligent caching to reduce load:

- Analysis results caching
- Screenshot freshness validation
- Service health status caching

## Troubleshooting

### Common Issues

1. **High Error Rates**
   - Check service health with `/diagnostics services`
   - Review recent errors with `/diagnostics errors`
   - Validate configuration with `/diagnostics config`

2. **Performance Issues**
   - Monitor command metrics with `/diagnostics commands`
   - Check system resources with `/diagnostics`
   - Review service response times

3. **Configuration Problems**
   - Run configuration validation
   - Check environment variables
   - Verify external tool availability

### Debug Mode

Enable debug mode for detailed logging:

```python
import logging
logging.getLogger("enhanced_diagnostics").setLevel(logging.DEBUG)
```

## Integration Checklist

When integrating the enhanced diagnostics system:

- [ ] Initialize diagnostics system on application startup
- [ ] Replace existing command handlers with enhanced versions
- [ ] Add diagnostic commands for administrators
- [ ] Configure environment variables
- [ ] Set up monitoring and alerting
- [ ] Test error handling scenarios
- [ ] Validate configuration for all commands
- [ ] Set up log rotation and archival

## Future Enhancements

Planned improvements to the diagnostics system:

1. **Real-time Dashboards**: Web-based monitoring dashboard
2. **Alerting System**: Automated alerts for critical issues
3. **Performance Profiling**: Detailed performance analysis
4. **Predictive Analytics**: Proactive issue detection
5. **Integration APIs**: REST APIs for external monitoring tools

## Support

For issues or questions about the enhanced diagnostics system:

1. Check the diagnostic commands output
2. Review the structured logs
3. Validate system configuration
4. Check service health status
5. Contact the development team with diagnostic reports

---

This enhanced diagnostics system provides comprehensive monitoring, logging, and error handling capabilities that significantly improve the reliability and maintainability of the Telegram bot application.