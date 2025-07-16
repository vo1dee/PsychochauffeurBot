# Developer Onboarding Guide - PsychoChauffeur Bot

Welcome to the PsychoChauffeur Bot development team! This guide will help you get up to speed with the codebase, development practices, and contribution workflow.

## Table of Contents
1. [Project Overview](#project-overview)
2. [Development Environment Setup](#development-environment-setup)
3. [Codebase Architecture](#codebase-architecture)
4. [Development Workflow](#development-workflow)
5. [Testing Guidelines](#testing-guidelines)
6. [Code Quality Standards](#code-quality-standards)
7. [Deployment Process](#deployment-process)
8. [Common Tasks](#common-tasks)

## Project Overview

### What is PsychoChauffeur Bot?
PsychoChauffeur Bot is a feature-rich Telegram bot that provides:
- **Video Downloads**: From TikTok, YouTube, Twitter, and other platforms
- **AI Integration**: GPT-powered responses and image analysis
- **Weather Services**: Real-time weather information
- **Utility Features**: Reminders, geomagnetic data, and more
- **Multi-language Support**: Configurable per chat/user

### Technology Stack
- **Language**: Python 3.10+
- **Framework**: python-telegram-bot
- **Database**: PostgreSQL with asyncpg
- **AI Services**: OpenAI GPT-4
- **External APIs**: Weather, video downloaders
- **Testing**: pytest, pytest-asyncio
- **Code Quality**: black, flake8, mypy

### Key Statistics
- **~15,000+ lines of code**
- **50+ modules**
- **100+ test cases**
- **Multi-platform deployment**

## Development Environment Setup

### Prerequisites
- Python 3.10 or higher
- PostgreSQL 12+
- Git
- Code editor (VS Code recommended)

### Step 1: Clone and Setup
```bash
# Clone the repository
git clone https://github.com/your-org/psychochauffeur-bot.git
cd psychochauffeur-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt  # If exists, or:
pip install pytest pytest-asyncio black flake8 mypy
```

### Step 2: Database Setup
```bash
# Create database
createdb telegram_bot

# Set up database schema
python scripts/init_database.py

# Run migrations
python scripts/migrate_db.py
```

### Step 3: Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values
nano .env
```

Required environment variables:
```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
ERROR_CHANNEL_ID=your_error_channel_id

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=telegram_bot
DB_USER=postgres
DB_PASSWORD=your_password

# External APIs
OPENAI_API_KEY=your_openai_key
WEATHER_API_KEY=your_weather_key
```

### Step 4: Verify Setup
```bash
# Run health check
python scripts/health_check.py

# Run tests
python -m pytest tests/ -v

# Start the bot (test mode)
python main.py
```

### Development Tools Setup

#### VS Code Configuration
Create `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### Pre-commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Set up hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

## Codebase Architecture

### Directory Structure
```
psychochauffeur-bot/
├── main.py                 # Application entry point
├── modules/               # Core functionality
│   ├── __init__.py
│   ├── database.py        # Database operations
│   ├── gpt.py            # AI integration
│   ├── video_downloader.py # Video download logic
│   ├── weather.py        # Weather services
│   ├── error_handler.py  # Error management
│   ├── logger.py         # Logging system
│   └── handlers/         # Command handlers
├── config/               # Configuration management
│   ├── config_manager.py # Config system
│   ├── global/          # Global configurations
│   └── schemas/         # Config schemas
├── tests/               # Test suites
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── fixtures/       # Test data
├── scripts/            # Utility scripts
├── docs/              # Documentation
└── logs/              # Application logs
```

### Key Components

#### 1. Main Application (`main.py`)
- Bot initialization and configuration
- Handler registration
- Message routing and processing
- Error handling and logging

#### 2. Database Layer (`modules/database.py`)
- Async database operations
- Connection pooling
- Query optimization
- Data models

#### 3. AI Integration (`modules/gpt.py`)
- OpenAI API integration
- Prompt management
- Response processing
- Image analysis

#### 4. Configuration System (`config/`)
- Hierarchical configuration (global/chat/user)
- Dynamic configuration updates
- Schema validation
- Migration support

#### 5. Error Handling (`modules/error_handler.py`)
- Centralized error management
- Error categorization and reporting
- User-friendly error messages
- Error analytics

### Design Patterns Used

#### 1. Dependency Injection
```python
class ServiceRegistry:
    def __init__(self):
        self._services = {}
    
    def register(self, name: str, service: Any):
        self._services[name] = service
    
    def get(self, name: str) -> Any:
        return self._services.get(name)
```

#### 2. Command Pattern
```python
class CommandHandler:
    async def handle(self, update: Update, context: CallbackContext):
        # Command processing logic
        pass
```

#### 3. Factory Pattern
```python
class HandlerFactory:
    @staticmethod
    def create_handler(command_type: str) -> CommandHandler:
        handlers = {
            'gpt': GPTHandler,
            'weather': WeatherHandler,
            'video': VideoHandler
        }
        return handlers[command_type]()
```

#### 4. Observer Pattern
```python
class EventSystem:
    def __init__(self):
        self._observers = []
    
    def subscribe(self, observer):
        self._observers.append(observer)
    
    def notify(self, event):
        for observer in self._observers:
            observer.handle(event)
```

## Development Workflow

### Git Workflow
We use a modified Git Flow:

1. **Main Branch**: Production-ready code
2. **Develop Branch**: Integration branch for features
3. **Feature Branches**: Individual feature development
4. **Hotfix Branches**: Critical production fixes

### Branch Naming Convention
- `feature/description-of-feature`
- `bugfix/description-of-bug`
- `hotfix/critical-issue-fix`
- `refactor/component-name`

### Commit Message Format
```
type(scope): brief description

Detailed description if needed

- List any breaking changes
- Reference issues: Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Process

#### 1. Before Creating PR
```bash
# Update your branch
git checkout develop
git pull origin develop
git checkout your-feature-branch
git rebase develop

# Run quality checks
python -m pytest tests/
python -m flake8 .
python -m black --check .
python -m mypy .
```

#### 2. PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

#### 3. Review Process
- At least one approval required
- All CI checks must pass
- No merge conflicts
- Documentation updated if needed

## Testing Guidelines

### Test Structure
```
tests/
├── unit/                 # Fast, isolated tests
│   ├── test_database.py
│   ├── test_gpt.py
│   └── test_config.py
├── integration/          # Component interaction tests
│   ├── test_bot_integration.py
│   └── test_api_integration.py
├── fixtures/            # Test data and utilities
│   ├── mock_data.py
│   └── test_helpers.py
└── conftest.py         # Pytest configuration
```

### Writing Tests

#### Unit Test Example
```python
import pytest
from unittest.mock import AsyncMock, patch
from modules.gpt import GPTHandler

class TestGPTHandler:
    @pytest.fixture
    def gpt_handler(self):
        return GPTHandler()
    
    @pytest.mark.asyncio
    async def test_generate_response(self, gpt_handler):
        # Arrange
        prompt = "Test prompt"
        expected_response = "Test response"
        
        with patch('openai.ChatCompletion.acreate') as mock_openai:
            mock_openai.return_value = {
                'choices': [{'message': {'content': expected_response}}]
            }
            
            # Act
            result = await gpt_handler.generate_response(prompt)
            
            # Assert
            assert result == expected_response
            mock_openai.assert_called_once()
```

#### Integration Test Example
```python
import pytest
from telegram import Update, Message, Chat, User
from main import handle_message

class TestMessageHandling:
    @pytest.mark.asyncio
    async def test_gpt_command_integration(self, mock_update, mock_context):
        # Arrange
        mock_update.message.text = "/ask What is Python?"
        
        # Act
        await handle_message(mock_update, mock_context)
        
        # Assert
        mock_context.bot.send_message.assert_called_once()
        args, kwargs = mock_context.bot.send_message.call_args
        assert "Python" in kwargs['text']
```

### Test Data Management
```python
# tests/fixtures/mock_data.py
import pytest
from telegram import Update, Message, Chat, User

@pytest.fixture
def mock_user():
    return User(
        id=12345,
        first_name="Test",
        last_name="User",
        username="testuser",
        is_bot=False
    )

@pytest.fixture
def mock_chat():
    return Chat(
        id=-1001234567890,
        type="supergroup",
        title="Test Chat"
    )

@pytest.fixture
def mock_update(mock_user, mock_chat):
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=mock_chat,
        from_user=mock_user,
        text="Test message"
    )
    return Update(update_id=1, message=message)
```

### Running Tests
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/unit/test_gpt.py

# Run with coverage
python -m pytest --cov=modules tests/

# Run integration tests only
python -m pytest tests/integration/

# Run tests matching pattern
python -m pytest -k "test_gpt"

# Verbose output
python -m pytest -v

# Stop on first failure
python -m pytest -x
```

## Code Quality Standards

### Code Style
We use Black for code formatting:
```bash
# Format code
python -m black .

# Check formatting
python -m black --check .
```

### Linting
We use flake8 for linting:
```bash
# Run linter
python -m flake8 .

# Configuration in setup.cfg or .flake8
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = .git,__pycache__,.venv
```

### Type Checking
We use mypy for type checking:
```bash
# Run type checker
python -m mypy .

# Configuration in mypy.ini
[mypy]
python_version = 3.10
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

### Documentation Standards

#### Docstring Format
```python
def process_message(message: str, user_id: int) -> Dict[str, Any]:
    """
    Process incoming message and generate response.
    
    Args:
        message: The incoming message text
        user_id: ID of the user sending the message
        
    Returns:
        Dictionary containing response data and metadata
        
    Raises:
        ValueError: If message is empty or invalid
        APIError: If external service call fails
        
    Example:
        >>> result = process_message("Hello", 12345)
        >>> print(result['response'])
        "Hello! How can I help you?"
    """
    if not message.strip():
        raise ValueError("Message cannot be empty")
    
    # Processing logic here
    return {
        'response': response_text,
        'user_id': user_id,
        'timestamp': datetime.now()
    }
```

#### Code Comments
```python
# Good comments explain WHY, not WHAT
def calculate_rate_limit(user_id: int) -> bool:
    # Check if user has exceeded rate limit to prevent abuse
    # We use a sliding window approach for better UX
    current_time = time.time()
    user_requests = get_user_requests(user_id)
    
    # Remove requests older than the time window
    recent_requests = [
        req for req in user_requests 
        if current_time - req.timestamp < RATE_LIMIT_WINDOW
    ]
    
    return len(recent_requests) < MAX_REQUESTS_PER_WINDOW
```

### Performance Guidelines

#### Database Queries
```python
# Good: Use async and proper indexing
async def get_user_messages(user_id: int, limit: int = 50) -> List[Message]:
    async with Database.get_connection() as conn:
        # Use parameterized queries and LIMIT
        return await conn.fetch(
            "SELECT * FROM messages WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2",
            user_id, limit
        )

# Bad: Synchronous and no limits
def get_all_user_messages(user_id: int):
    return conn.fetch(f"SELECT * FROM messages WHERE user_id = {user_id}")
```

#### Memory Management
```python
# Good: Use generators for large datasets
def process_large_dataset():
    for item in get_data_generator():
        yield process_item(item)

# Bad: Load everything into memory
def process_large_dataset():
    all_data = get_all_data()  # Could be millions of records
    return [process_item(item) for item in all_data]
```

#### Async Best Practices
```python
# Good: Proper async/await usage
async def handle_multiple_requests(requests: List[Request]):
    tasks = [process_request(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# Bad: Sequential processing
async def handle_multiple_requests(requests: List[Request]):
    results = []
    for req in requests:
        result = await process_request(req)  # Blocks other requests
        results.append(result)
    return results
```

## Deployment Process

### Environments
1. **Development**: Local development environment
2. **Staging**: Pre-production testing environment
3. **Production**: Live bot serving users

### Deployment Steps

#### 1. Staging Deployment
```bash
# Deploy to staging
git checkout develop
git pull origin develop
./scripts/deploy_staging.sh

# Run smoke tests
python scripts/smoke_tests.py --environment=staging

# Manual testing
# Test critical features manually
```

#### 2. Production Deployment
```bash
# Create release branch
git checkout -b release/v1.2.3 develop

# Update version
echo "1.2.3" > VERSION

# Final testing
python -m pytest tests/
python scripts/security_audit.py

# Merge to main
git checkout main
git merge release/v1.2.3
git tag v1.2.3

# Deploy to production
./scripts/deploy_production.sh

# Monitor deployment
python scripts/health_check.py --environment=production
```

### Rollback Procedure
```bash
# Quick rollback
./scripts/rollback.sh v1.2.2

# Or manual rollback
git checkout v1.2.2
./scripts/deploy_production.sh
```

## Common Tasks

### Adding a New Command

#### 1. Create Command Handler
```python
# modules/handlers/new_command.py
from telegram import Update
from telegram.ext import CallbackContext
from modules.error_decorators import handle_errors

@handle_errors(feedback_message="An error occurred in /newcommand.")
async def new_command(update: Update, context: CallbackContext) -> None:
    """Handle the /newcommand command."""
    # Command logic here
    await update.message.reply_text("New command response")
```

#### 2. Register Handler
```python
# main.py - in register_handlers function
from modules.handlers.new_command import new_command

def register_handlers(application: Application):
    # ... existing handlers ...
    application.add_handler(CommandHandler("newcommand", new_command))
```

#### 3. Add Tests
```python
# tests/unit/test_new_command.py
import pytest
from modules.handlers.new_command import new_command

class TestNewCommand:
    @pytest.mark.asyncio
    async def test_new_command_response(self, mock_update, mock_context):
        await new_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with("New command response")
```

#### 4. Update Documentation
```markdown
# docs/API_DOCUMENTATION.md
## /newcommand
Description of the new command and its usage.
```

### Adding a New Module

#### 1. Create Module File
```python
# modules/new_module.py
"""
New module for specific functionality.
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class NewModule:
    """New module class."""
    
    def __init__(self):
        self.initialized = False
    
    async def initialize(self) -> None:
        """Initialize the module."""
        # Initialization logic
        self.initialized = True
        logger.info("New module initialized")
    
    async def process(self, data: Dict[str, Any]) -> Optional[str]:
        """Process data and return result."""
        if not self.initialized:
            raise RuntimeError("Module not initialized")
        
        # Processing logic
        return "processed_result"
```

#### 2. Add Configuration
```json
// config/modules/new_module.json
{
    "enabled": true,
    "settings": {
        "option1": "value1",
        "option2": 42
    }
}
```

#### 3. Integration
```python
# main.py - in initialize_all_components
from modules.new_module import NewModule

async def initialize_all_components():
    # ... existing initialization ...
    new_module = NewModule()
    await new_module.initialize()
```

### Database Schema Changes

#### 1. Create Migration Script
```python
# scripts/migrations/001_add_new_table.py
"""
Migration: Add new table for feature X
"""

UP_SQL = """
CREATE TABLE new_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_new_table_name ON new_table(name);
"""

DOWN_SQL = """
DROP INDEX IF EXISTS idx_new_table_name;
DROP TABLE IF EXISTS new_table;
"""

async def up(connection):
    await connection.execute(UP_SQL)

async def down(connection):
    await connection.execute(DOWN_SQL)
```

#### 2. Run Migration
```bash
python scripts/migrate_db.py --up
```

#### 3. Update Database Module
```python
# modules/database.py
@classmethod
async def save_new_entity(cls, name: str) -> int:
    """Save new entity and return ID."""
    async with cls.get_connection() as conn:
        entity_id = await conn.fetchval(
            "INSERT INTO new_table (name) VALUES ($1) RETURNING id",
            name
        )
        return entity_id
```

### Performance Optimization

#### 1. Identify Bottleneck
```bash
# Run performance test
python scripts/simple_performance_test.py

# Profile specific function
python -m cProfile -o profile.stats main.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(10)"
```

#### 2. Implement Optimization
```python
# Before: Slow database query
async def get_user_stats(user_id: int):
    messages = await get_all_user_messages(user_id)  # Loads everything
    return len(messages)

# After: Optimized query
async def get_user_stats(user_id: int):
    async with Database.get_connection() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE user_id = $1",
            user_id
        )
        return count
```

#### 3. Measure Improvement
```bash
# Compare before and after
python scripts/simple_performance_test.py --compare
```

## Resources and References

### Documentation
- [Python Telegram Bot Library](https://python-telegram-bot.readthedocs.io/)
- [AsyncPG Documentation](https://magicstack.github.io/asyncpg/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Internal Documentation
- [API Documentation](./API_DOCUMENTATION.md)
- [Architecture Overview](./ARCHITECTURE.md)
- [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md)
- [Security Guidelines](./SECURITY_AUDIT_REPORT.md)

### Development Tools
- [VS Code Python Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [Black Code Formatter](https://black.readthedocs.io/)
- [Flake8 Linter](https://flake8.pycqa.org/)
- [MyPy Type Checker](https://mypy.readthedocs.io/)

### Community
- **Team Chat**: [Internal Slack/Discord]
- **Code Reviews**: GitHub Pull Requests
- **Issue Tracking**: GitHub Issues
- **Documentation**: Internal Wiki

## Getting Help

### For Technical Issues
1. Check the [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md)
2. Search existing GitHub issues
3. Ask in team chat
4. Create a detailed issue with logs and reproduction steps

### For Code Reviews
1. Create a pull request with detailed description
2. Request review from team members
3. Address feedback promptly
4. Update documentation if needed

### For Architecture Decisions
1. Discuss in team meetings
2. Create RFC (Request for Comments) document
3. Get consensus before implementation
4. Document decisions in ADR (Architecture Decision Records)

---

Welcome to the team! Don't hesitate to ask questions and contribute your ideas. We're here to help you succeed and build amazing features together.

*This guide is a living document. Please update it as the project evolves.*