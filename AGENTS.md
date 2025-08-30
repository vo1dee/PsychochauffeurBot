# Agent Guidelines for PsychochauffeurBot

## Build/Lint/Test Commands

### Testing
- **Run all tests**: `pytest`
- **Run single test file**: `pytest tests/test_filename.py`
- **Run single test**: `pytest tests/test_filename.py::TestClass::test_method`
- **Run with coverage**: `pytest --cov=modules --cov=config --cov-report=html`
- **Run async tests**: `pytest -m async`
- **Run unit tests only**: `pytest -m unit`
- **Run integration tests**: `pytest -m integration`

### Type Checking
- **Type check**: `python -m mypy modules/ config/ --ignore-missing-imports`

### Linting
- **Lint (strict)**: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- **Lint (full)**: `flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics`

### Formatting
- **Format code**: `black .`
- **Check formatting**: `black --check .`

## Code Style Guidelines

### Python Version & Typing
- Target Python 3.9+
- Use type hints for all function parameters and return values
- Use `typing` module imports: `from typing import Optional, Dict, List, Any`
- Avoid `Any` when possible; use specific types
- Use `Union` for multiple possible types

### Imports
```python
# Standard library imports
import asyncio
import logging
from typing import Optional, Dict, Any

# Third-party imports
from telegram import Bot
from telegram.ext import Application

# Local imports
from modules.database import DatabaseService
from modules.const import Config
```

### Naming Conventions
- **Functions/Methods**: `snake_case`
- **Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Modules**: `snake_case`
- **Private members**: `_leading_underscore`

### Code Structure
- Max line length: 127 characters
- Max complexity: 10 (flake8)
- Use 4 spaces for indentation (Black default)
- Use async/await for asynchronous operations
- Use context managers (`with` statements) for resource management

### Error Handling
```python
try:
    result = await some_async_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### Documentation
- Use docstrings for all public functions, classes, and modules
- Follow Google docstring format
- Include type hints in docstrings when not obvious

### Async Patterns
- Use `asyncio` for concurrent operations
- Prefer `asyncio.gather()` for multiple concurrent tasks
- Use `asyncio.Lock()` for shared resource protection
- Handle cancellation with `asyncio.CancelledError`

### Database Operations
- Use async database operations with `asyncpg`
- Always use parameterized queries
- Handle connection pooling properly
- Use transactions for multi-step operations

### Logging
- Use structured logging with appropriate levels
- Include context in log messages
- Use `logger.error()` with `exc_info=True` for exceptions
- Avoid logging sensitive information

### Security
- Never log API keys, tokens, or passwords
- Use environment variables for sensitive configuration
- Validate all user inputs
- Use HTTPS for external API calls

## Development Workflow

1. Write code with proper type hints
2. Run type checking: `python -m mypy modules/ config/ --ignore-missing-imports`
3. Format code: `black .`
4. Lint code: `flake8 . --max-line-length=127 --max-complexity=10`
5. Run tests: `pytest --cov=modules --cov=config`
6. Commit changes with descriptive messages