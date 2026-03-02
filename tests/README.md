# Test Suite for PsychoChauffeur Bot

This directory contains a comprehensive test suite organized by functionality.

## Directory Structure

```
tests/
├── config/                 # Configuration system tests
│   ├── test_config_manager.py    # ConfigManager functionality
│   └── test_gpt_config.py        # GPT config inheritance
├── core/                   # Core bot functionality tests  
│   ├── test_weather_and_utils.py # Weather commands, utils, file management
│   ├── test_service.py          # Service layer tests
│   └── test_error_handler.py    # Error handling tests
├── modules/               # Individual module tests
│   ├── test_gm.py              # Geomagnetic API tests
│   ├── test_url_utils.py       # URL utility tests
│   └── test_video_downloader.py # Video download tests
├── api/                   # API and callback tests
│   ├── test_config_api.py      # Configuration API tests
│   ├── test_button_callback.py  # Button callback tests
│   └── test_error_analytics.py  # Error analytics tests
└── README.md              # This file
```

## Running Tests

**All tests:**
```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v
```

**By category:**
```bash
# Configuration tests
python -m pytest tests/config/

# Core functionality tests  
python -m pytest tests/core/

# Module tests
python -m pytest tests/modules/

# API tests
python -m pytest tests/api/
```

**Individual test files:**
```bash
# Configuration system
python tests/config/test_config_manager.py
python tests/config/test_gpt_config.py

# Core functionality
python tests/core/test_weather_and_utils.py
python tests/core/test_error_handler.py

# Specific modules
python tests/modules/test_reminders.py
python tests/modules/test_gm.py
```

## Test Categories

### 🔧 Configuration Tests (`config/`)
- **ConfigManager** - Global/custom config loading, inheritance, merging
- **GPT Config** - Ukrainian prompts preservation, system prompt inheritance

### 🤖 Core Tests (`core/`)
- **Bot Core** - Main bot functionality, utils, weather commands, file management
- **Service Layer** - Service architecture tests
- **Error Handling** - Error handling and recovery mechanisms

### 📦 Module Tests (`modules/`)
- **Reminders** - Reminder system, parsing, scheduling, models
- **Geomagnetic** - Geomagnetic data API and formatting
- **URL Utils** - URL extraction and processing utilities
- **Video Downloader** - Video download functionality

### 🔌 API Tests (`api/`)
- **Config API** - Configuration API endpoints
- **Button Callbacks** - Telegram button callback handling
- **Error Analytics** - Error tracking and analytics

## Test Coverage

✅ **Configuration System** - Global configs, custom overrides, module inheritance  
✅ **Ukrainian Prompts** - Custom prompt preservation and functionality  
✅ **Reminder System** - Parsing, scheduling, database operations  
✅ **Weather Commands** - City handling, data formatting, chat-specific settings  
✅ **File Management** - CSV operations, directory handling, location saving  
✅ **URL Processing** - Link extraction, validation, utility functions  
✅ **Error Handling** - Graceful error recovery, analytics, logging  
✅ **API Endpoints** - Configuration API, callback processing  
✅ **Geomagnetic Data** - API integration, data formatting, Ukrainian localization  
✅ **Core Utilities** - Text processing, emoji handling, internationalization  

## Adding New Tests

When adding new functionality:

1. **Choose the right category** - Place tests in the appropriate folder
2. **Follow naming conventions** - Use `test_` prefix for all test files  
3. **Update this README** - Document new test files and their purpose
4. **Use appropriate test framework** - `unittest` or `pytest` based on existing patterns
5. **Mock external dependencies** - Use mocks for APIs, databases, file operations

## Test Environment

Tests use:
- **pytest** for async test support and advanced features
- **unittest.mock** for mocking external dependencies  
- **Temporary directories** for file operation tests
- **In-memory databases** for database operation tests
- **Mock Telegram objects** for bot functionality tests