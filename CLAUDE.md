# CLAUDE.md - PsychochauffeurBot Guidelines

## Commands
- **Run bot**: `python main.py`
- **Run tests**: `pytest tests/`
- **Run specific test**: `pytest tests/test_bot.py::TestBot::test_extract_urls`
- **Lint code**: `flake8 .`
- **Typecheck**: None (project doesn't use static typing tools yet)

## Code Style
- **Imports**: Group by standard lib → third-party → local modules
- **Formatting**: 4-space indentation, line length ~100 chars
- **Types**: Use type hints (List, Optional, etc.) on function parameters and returns
- **Naming**: PascalCase for classes, snake_case for functions/variables, UPPER_SNAKE_CASE for constants
- **Error handling**: Use specific exceptions, log errors with context, propagate when necessary
- **Docstrings**: Use triple-quotes with concise function/class descriptions
- **Logging**: Use appropriate logger (general_logger, chat_logger, error_logger)
- **Async**: Use async/await for I/O operations, handle exceptions properly
- **Project structure**: Keep modules organized by functionality

## Developer Notes
- Always log errors with context information
- Add type hints to new code
- Use consistent error handling patterns
- Follow existing patterns for new modules