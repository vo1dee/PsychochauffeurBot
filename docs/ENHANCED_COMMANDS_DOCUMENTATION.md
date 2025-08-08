# Enhanced Commands Documentation

This document provides comprehensive documentation for the enhanced `/analyze` and `/flares` commands implemented as part of the command fixes specification.

## Overview

The enhanced commands provide:
- **Comprehensive error handling** with user-friendly messages
- **Flexible date format support** for analyze command
- **Reliable screenshot generation** for flares command
- **Performance monitoring** and diagnostics
- **Detailed logging** for troubleshooting
- **Configuration validation** before execution

## Enhanced Analyze Command

### Command Syntax

```
/analyze                           # Analyze today's messages
/analyze last <N> messages         # Analyze last N messages
/analyze last <N> days             # Analyze messages from last N days
/analyze date <date>               # Analyze messages from specific date
/analyze period <date1> <date2>    # Analyze messages from date range
```

### Supported Date Formats

The enhanced analyze command supports multiple date formats for maximum user convenience:

| Format | Example | Description |
|--------|---------|-------------|
| `YYYY-MM-DD` | `2024-01-15` | ISO format (original) |
| `DD-MM-YYYY` | `15-01-2024` | European format (new) |
| `DD/MM/YYYY` | `15/01/2024` | Alternative European format (new) |

### Usage Examples

#### Basic Usage
```
/analyze                    # Today's messages
/analyze last 50 messages   # Last 50 messages
/analyze last 7 days        # Messages from last 7 days
```

#### Date-Specific Analysis
```
/analyze date 15-01-2024              # European format
/analyze date 2024-01-15              # ISO format
/analyze date 15/01/2024              # Alternative format
```

#### Period Analysis
```
/analyze period 01-01-2024 31-01-2024    # January 2024
/analyze period 2024-01-01 2024-01-31    # Same period, ISO format
/analyze period 01/01/2024 31/01/2024    # Alternative format
```

### Enhanced Features

#### 1. Intelligent Date Parsing
- **Automatic format detection**: Tries multiple formats automatically
- **Validation**: Checks for valid dates (no February 30th, etc.)
- **Range validation**: Ensures start date is before end date
- **Helpful error messages**: Shows supported formats with examples

#### 2. Comprehensive Error Handling
- **Database connection issues**: Automatic retry with exponential backoff
- **API failures**: Graceful handling with user-friendly messages
- **Configuration problems**: Validation before execution
- **No messages found**: Helpful suggestions for alternative periods

#### 3. Performance Optimization
- **Caching**: Results cached to avoid repeated API calls
- **Progress indicators**: Shows processing status for long operations
- **Metrics tracking**: Logs performance data for monitoring
- **Resource management**: Efficient memory and connection usage

#### 4. User Experience Improvements
- **Localized messages**: All messages in Ukrainian
- **Clear error descriptions**: Specific guidance for each error type
- **Format examples**: Shows correct usage in error messages
- **Status updates**: Progress indicators for long-running operations

### Error Messages and Solutions

#### Date Format Errors
```
❌ Помилка в форматі дати. Перевірте правильність:

📅 Підтримувані формати дат:
• YYYY-MM-DD (наприклад: 2024-01-15)
• DD-MM-YYYY (наприклад: 15-01-2024)
• DD/MM/YYYY (наприклад: 15/01/2024)

Приклад: /analyze date 15-01-2024
```

#### No Messages Found
```
📭 Не знайдено повідомлень для аналізу за вказаний період.

Можливі причини:
• В чаті немає повідомлень за цей період
• Вказана дата в майбутньому
• Період занадто вузький

Спробуйте:
• Розширити період пошуку
• Перевірити правильність дат
• Використати /analyze last 50 messages
```

#### Database Connection Issues
```
❌ Виникла проблема з підключенням до бази даних.

Що робити:
• Спробуйте через кілька хвилин
• Якщо проблема повторюється, зверніться до адміністратора

Код помилки: DATABASE_CONNECTION
```

## Enhanced Flares Command

### Command Syntax

```
/flares    # Get current solar flares screenshot
```

### Enhanced Features

#### 1. Smart Screenshot Management
- **Freshness checking**: Only generates new screenshots when needed (6-hour threshold)
- **Automatic generation**: Creates new screenshots when existing ones are outdated
- **Progress indicators**: Shows generation status to users
- **Metadata display**: Includes timestamp and next update time

#### 2. Robust Error Handling
- **Tool availability**: Checks for wkhtmltoimage before attempting generation
- **Network issues**: Handles API timeouts and connection problems
- **File system**: Manages directory creation and permissions
- **Fallback mechanisms**: Uses cached screenshots when generation fails

#### 3. User Experience
- **Status messages**: Clear progress indicators during generation
- **Detailed captions**: Shows screenshot age, next update time, and source
- **Error guidance**: Specific instructions for different error types
- **Performance info**: File size and generation time in logs

### Screenshot Information

Each screenshot includes comprehensive metadata:

```
🌞 Прогноз сонячних спалахів і магнітних бурь

📅 Час знімку: 14:30 15.01.2024
📊 Статус: актуальний
🔄 Наступне оновлення: 20:30 15.01.2024
📁 Розмір файлу: 1.2 MB

🔗 Джерело: api.meteoagent.com
```

### Error Messages and Solutions

#### Tool Unavailable
```
❌ Інструмент для створення знімків недоступний.

Проблема:
• Відсутній або некоректно налаштований wkhtmltoimage

Що робити:
• Зверніться до адміністратора для встановлення інструменту
• Проблема вирішується на рівні сервера

Код помилки: WKHTMLTOIMAGE_UNAVAILABLE
```

#### Generation Failed
```
❌ Не вдалося створити знімок сонячних спалахів.

Можливі причини:
• Проблеми з мережевим підключенням
• Тимчасова недоступність джерела даних
• Проблеми з файловою системою

Що робити:
• Спробуйте через кілька хвилин
• Перевірте інтернет-з'єднання
• Зверніться до адміністратора, якщо проблема повторюється

Код помилки: SCREENSHOT_GENERATION_FAILED
```

#### Network Issues
```
❌ Проблема з мережевим підключенням до сервісу прогнозів.

Що робити:
• Перевірте інтернет-з'єднання
• Спробуйте через кілька хвилин
• Можлива тимчасова недоступність api.meteoagent.com

Код помилки: NETWORK_CONNECTION_ERROR
```

## Technical Implementation

### Architecture Overview

```
User Command → Enhanced Handler → Validation → Business Logic → Response
     ↓              ↓                ↓              ↓              ↓
Error Handling → Config Check → Dependency Check → Execution → User Feedback
     ↓              ↓                ↓              ↓              ↓
Diagnostics → Performance Tracking → Logging → Metrics → Monitoring
```

### Key Components

#### 1. Enhanced Command Handlers
- **Location**: `modules/enhanced_analyze_command.py`, `modules/enhanced_flares_command.py`
- **Purpose**: Main command logic with comprehensive error handling
- **Features**: Validation, diagnostics, performance tracking

#### 2. Date Parser Utility
- **Location**: `modules/utils.py` - `DateParser` class
- **Purpose**: Flexible date format parsing and validation
- **Formats**: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY

#### 3. Screenshot Manager
- **Location**: `modules/utils.py` - `ScreenshotManager` class
- **Purpose**: Reliable screenshot generation and management
- **Features**: Freshness checking, tool validation, error handling

#### 4. Command Diagnostics
- **Location**: `modules/command_diagnostics.py`
- **Purpose**: Performance monitoring and health checks
- **Features**: API tracking, database monitoring, milestone logging

#### 5. Help Messages System
- **Location**: `modules/command_help_messages.py`
- **Purpose**: Centralized, consistent error and help messages
- **Features**: Localized messages, context-aware errors, format examples

### Database Integration

#### Enhanced Query Functions
- **Connection retry logic**: Automatic reconnection with exponential backoff
- **Health monitoring**: Regular connection pool health checks
- **Performance tracking**: Query execution time monitoring
- **Error recovery**: Graceful handling of connection failures

#### Supported Query Types
```python
# Today's messages
messages = await get_messages_for_chat_today(chat_id)

# Last N messages
messages = await get_last_n_messages_in_chat(chat_id, count)

# Last N days
messages = await get_messages_for_chat_last_n_days(chat_id, days)

# Specific date
messages = await get_messages_for_chat_date(chat_id, date)

# Date range
messages = await get_messages_for_chat_date_range(chat_id, start_date, end_date)
```

### Performance Monitoring

#### Metrics Tracked
- **Command execution time**: Total time from request to response
- **Database query time**: Individual query performance
- **API call duration**: External service response times
- **Message processing**: Number of messages analyzed
- **Cache hit rates**: Analysis result caching effectiveness

#### Logging Levels
- **Milestones**: Key execution points (parsing, validation, execution)
- **Performance**: Timing and resource usage metrics
- **Errors**: Detailed error context and stack traces
- **User actions**: Command usage patterns and success rates

### Configuration Management

#### Validation Checks
- **Command configuration**: Validates command-specific settings
- **Dependency health**: Checks external service availability
- **Resource availability**: Verifies required tools and permissions
- **API connectivity**: Tests external API endpoints

#### Configuration Structure
```json
{
  "commands": {
    "analyze": {
      "enabled": true,
      "cache_enabled": true,
      "cache_ttl": 3600,
      "max_messages": 10000,
      "timeout": 30
    },
    "flares": {
      "enabled": true,
      "freshness_threshold": 6,
      "screenshot_directory": "python-web-screenshots",
      "tool_path": "/usr/bin/wkhtmltoimage",
      "timeout": 30
    }
  }
}
```

## Migration from Original Commands

### Backward Compatibility
- **Command syntax**: All original command formats still work
- **Response format**: Enhanced with additional information
- **Error handling**: Improved but maintains expected behavior
- **Performance**: Better with caching and optimization

### New Features
- **Multiple date formats**: DD-MM-YYYY and DD/MM/YYYY support
- **Better error messages**: Detailed, localized, with examples
- **Progress indicators**: Status updates for long operations
- **Diagnostics**: Comprehensive logging and monitoring
- **Reliability**: Retry logic and fallback mechanisms

### Upgrade Benefits
- **User experience**: Clearer messages and better guidance
- **Reliability**: Fewer failures and better error recovery
- **Performance**: Faster responses through caching
- **Maintainability**: Better logging and diagnostics
- **Monitoring**: Detailed metrics for system health

## Best Practices

### For Users
1. **Use clear date formats**: Stick to supported formats for consistency
2. **Check error messages**: Read the detailed guidance provided
3. **Be patient**: Allow time for screenshot generation
4. **Report issues**: Include error codes when contacting support

### For Administrators
1. **Monitor logs**: Regular review of error and performance logs
2. **Check dependencies**: Ensure wkhtmltoimage and other tools are available
3. **Database maintenance**: Regular connection pool and query optimization
4. **Configuration validation**: Periodic checks of command configuration

### For Developers
1. **Use diagnostics**: Leverage the comprehensive logging system
2. **Handle errors gracefully**: Follow the established error handling patterns
3. **Add metrics**: Include performance tracking for new features
4. **Test thoroughly**: Use the provided test utilities and scenarios

## Troubleshooting

For detailed troubleshooting procedures, see:
- [Command Fixes Troubleshooting Guide](COMMAND_FIXES_TROUBLESHOOTING.md)
- [General Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)

### Quick Diagnostics

```bash
# Test enhanced commands
python -c "
from modules.enhanced_analyze_command import enhanced_analyze_command
from modules.enhanced_flares_command import enhanced_flares_command
print('Enhanced commands loaded successfully')
"

# Test date parser
python -c "
from modules.utils import DateParser
print(DateParser.parse_date('15-01-2024'))
"

# Test screenshot manager
python -c "
from modules.utils import ScreenshotManager
manager = ScreenshotManager()
print(f'Tool available: {manager._check_wkhtmltoimage_availability()}')
"
```

## Support and Feedback

### Getting Help
- **Documentation**: This guide and troubleshooting documentation
- **Error codes**: Specific codes provided in error messages
- **Logs**: Detailed logging for issue diagnosis
- **Contact**: @vo1dee for direct support

### Reporting Issues
When reporting issues, please include:
1. **Exact command used**
2. **Error message received**
3. **Expected vs actual behavior**
4. **Error code (if provided)**
5. **Relevant log excerpts**

### Feature Requests
The enhanced commands are designed to be extensible. Feature requests should include:
1. **Use case description**
2. **Expected behavior**
3. **Backward compatibility considerations**
4. **Performance implications**

---

*This documentation covers the enhanced command functionality implemented as part of the command fixes specification. For general bot documentation, see the main user guide.*