# Type Annotations Guide

This guide provides comprehensive information about using type annotations in the PsychoChauffeur Bot project.

## Table of Contents

1. [Overview](#overview)
2. [Basic Type Annotations](#basic-type-annotations)
3. [Advanced Type Annotations](#advanced-type-annotations)
4. [Custom Types](#custom-types)
5. [Generic Types](#generic-types)
6. [Protocol and Structural Typing](#protocol-and-structural-typing)
7. [Async Type Annotations](#async-type-annotations)
8. [Error Handling Types](#error-handling-types)
9. [Configuration Types](#configuration-types)
10. [Best Practices](#best-practices)
11. [Type Checking Tools](#type-checking-tools)

## Overview

Type annotations in Python provide several benefits:
- **Better IDE support**: Autocomplete, refactoring, and error detection
- **Documentation**: Types serve as inline documentation
- **Error prevention**: Catch type-related bugs before runtime
- **Code clarity**: Make function contracts explicit

## Basic Type Annotations

### Function Parameters and Return Types

```python
from typing import Optional, List, Dict, Any, Union

def process_user_data(
    user_id: int,
    username: str,
    preferences: Optional[Dict[str, Any]] = None
) -> Dict[str, Union[str, int]]:
    """Process user data and return formatted result."""
    if preferences is None:
        preferences = {}
    
    return {
        'user_id': user_id,
        'username': username,
        'preference_count': len(preferences)
    }
```

### Variable Annotations

```python
from typing import List, Dict, Optional

# Basic variable annotations
user_count: int = 0
active_users: List[str] = []
user_preferences: Dict[str, Any] = {}

# Optional values
current_user: Optional[str] = None

# Class attributes
class UserManager:
    users: Dict[int, str]
    active_sessions: List[int]
    
    def __init__(self):
        self.users = {}
        self.active_sessions = []
```

## Advanced Type Annotations

### Union Types

```python
from typing import Union, Optional

# Union for multiple possible types
def format_id(user_id: Union[int, str]) -> str:
    """Format user ID as string regardless of input type."""
    return str(user_id)

# Optional is shorthand for Union[T, None]
def get_user_name(user_id: int) -> Optional[str]:
    """Get username or None if not found."""
    return users.get(user_id)

# Python 3.10+ union syntax
def process_data(data: int | str | float) -> str:
    """Process numeric data of various types."""
    return str(data)
```

### Literal Types

```python
from typing import Literal

# Restrict to specific string values
ChatType = Literal['private', 'group', 'supergroup', 'channel']
LogLevel = Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

def set_log_level(level: LogLevel) -> None:
    """Set logging level to one of the allowed values."""
    logging.getLogger().setLevel(level)

def create_chat(chat_type: ChatType, chat_id: int) -> Chat:
    """Create a chat of the specified type."""
    return Chat(id=chat_id, type=chat_type)
```

### TypedDict for Structured Data

```python
from typing import TypedDict, Optional, List

class UserData(TypedDict):
    """Type definition for user data structure."""
    user_id: int
    username: str
    first_name: str
    last_name: Optional[str]
    is_active: bool

class ChatConfig(TypedDict, total=False):
    """Chat configuration with optional fields."""
    language: str
    timezone: str
    features_enabled: List[str]
    custom_commands: Dict[str, str]

def process_user(user_data: UserData) -> str:
    """Process user data with type safety."""
    name = user_data['first_name']
    if user_data.get('last_name'):
        name += f" {user_data['last_name']}"
    return name
```

## Custom Types

### Type Aliases

```python
from typing import Dict, List, Callable, Awaitable

# Simple type aliases
UserId = int
ChatId = int
MessageId = int

# Complex type aliases
UserPreferences = Dict[str, Any]
CommandHandler = Callable[[Update, CallbackContext], Awaitable[None]]
ConfigUpdateCallback = Callable[[str, Dict[str, Any]], None]

# Using type aliases
def get_user_preferences(user_id: UserId) -> UserPreferences:
    """Get user preferences by ID."""
    return preferences_db.get(user_id, {})

def register_command(name: str, handler: CommandHandler) -> None:
    """Register a command handler."""
    command_registry[name] = handler
```

### NewType for Type Safety

```python
from typing import NewType

# Create distinct types for better type safety
UserId = NewType('UserId', int)
ChatId = NewType('ChatId', int)
MessageId = NewType('MessageId', int)

def get_user(user_id: UserId) -> Optional[User]:
    """Get user by ID."""
    return users.get(user_id)

def send_message(chat_id: ChatId, text: str) -> MessageId:
    """Send message and return message ID."""
    # Implementation here
    return MessageId(12345)

# Type checker will catch misuse
user_id = UserId(12345)
chat_id = ChatId(67890)

# This would be a type error:
# get_user(chat_id)  # Error: Expected UserId, got ChatId
```

## Generic Types

### Generic Classes

```python
from typing import TypeVar, Generic, List, Optional

T = TypeVar('T')

class Repository(Generic[T]):
    """Generic repository for any data type."""
    
    def __init__(self):
        self._data: Dict[int, T] = {}
    
    def save(self, item_id: int, item: T) -> None:
        """Save an item to the repository."""
        self._data[item_id] = item
    
    def get(self, item_id: int) -> Optional[T]:
        """Get an item from the repository."""
        return self._data.get(item_id)
    
    def get_all(self) -> List[T]:
        """Get all items from the repository."""
        return list(self._data.values())

# Usage with specific types
user_repo: Repository[User] = Repository()
chat_repo: Repository[Chat] = Repository()

user_repo.save(1, User(id=1, name="John"))
chat_repo.save(1, Chat(id=1, title="General"))
```

### Generic Functions

```python
from typing import TypeVar, List, Callable

T = TypeVar('T')
U = TypeVar('U')

def map_list(items: List[T], func: Callable[[T], U]) -> List[U]:
    """Apply function to each item in list."""
    return [func(item) for item in items]

def filter_list(items: List[T], predicate: Callable[[T], bool]) -> List[T]:
    """Filter list based on predicate."""
    return [item for item in items if predicate(item)]

# Usage
numbers = [1, 2, 3, 4, 5]
strings = map_list(numbers, str)  # List[str]
evens = filter_list(numbers, lambda x: x % 2 == 0)  # List[int]
```

## Protocol and Structural Typing

### Defining Protocols

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Drawable(Protocol):
    """Protocol for objects that can be drawn."""
    
    def draw(self) -> None:
        """Draw the object."""
        ...
    
    def get_area(self) -> float:
        """Get the area of the object."""
        ...

class Circle:
    """Circle implementation that satisfies Drawable protocol."""
    
    def __init__(self, radius: float):
        self.radius = radius
    
    def draw(self) -> None:
        print(f"Drawing circle with radius {self.radius}")
    
    def get_area(self) -> float:
        return 3.14159 * self.radius ** 2

def render_shape(shape: Drawable) -> None:
    """Render any drawable shape."""
    shape.draw()
    print(f"Area: {shape.get_area()}")

# Usage
circle = Circle(5.0)
render_shape(circle)  # Works because Circle satisfies Drawable protocol
```

### Service Protocols

```python
from typing import Protocol, Any, Dict, List

class ConfigService(Protocol):
    """Protocol for configuration services."""
    
    async def get_config(self, scope: str, key: str) -> Dict[str, Any]:
        """Get configuration value."""
        ...
    
    async def set_config(self, scope: str, key: str, value: Dict[str, Any]) -> bool:
        """Set configuration value."""
        ...

class CacheService(Protocol):
    """Protocol for caching services."""
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        ...
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        ...
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        ...

def create_user_service(
    config: ConfigService,
    cache: CacheService
) -> UserService:
    """Create user service with injected dependencies."""
    return UserService(config, cache)
```

## Async Type Annotations

### Async Functions and Coroutines

```python
import asyncio
from typing import Awaitable, Coroutine, AsyncIterator, AsyncGenerator

async def fetch_user_data(user_id: int) -> Dict[str, Any]:
    """Fetch user data asynchronously."""
    # Simulate async operation
    await asyncio.sleep(0.1)
    return {'user_id': user_id, 'name': 'John'}

async def process_users(user_ids: List[int]) -> List[Dict[str, Any]]:
    """Process multiple users concurrently."""
    tasks = [fetch_user_data(user_id) for user_id in user_ids]
    return await asyncio.gather(*tasks)

# Function that returns a coroutine
def create_user_task(user_id: int) -> Coroutine[Any, Any, Dict[str, Any]]:
    """Create a coroutine for fetching user data."""
    return fetch_user_data(user_id)
```

### Async Generators and Iterators

```python
from typing import AsyncIterator, AsyncGenerator

async def stream_messages(chat_id: int) -> AsyncIterator[Message]:
    """Stream messages from a chat."""
    while True:
        messages = await fetch_new_messages(chat_id)
        for message in messages:
            yield message
        await asyncio.sleep(1)

async def process_message_stream(
    chat_id: int
) -> AsyncGenerator[ProcessedMessage, None]:
    """Process messages as they arrive."""
    async for message in stream_messages(chat_id):
        processed = await process_message(message)
        yield processed

# Usage
async def handle_messages():
    async for processed_msg in process_message_stream(12345):
        await send_response(processed_msg)
```

### Async Context Managers

```python
from typing import AsyncContextManager
from contextlib import asynccontextmanager

@asynccontextmanager
async def database_transaction() -> AsyncIterator[DatabaseConnection]:
    """Async context manager for database transactions."""
    conn = await get_database_connection()
    transaction = await conn.begin()
    try:
        yield conn
        await transaction.commit()
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await conn.close()

# Usage
async def update_user_data(user_id: int, data: Dict[str, Any]) -> None:
    async with database_transaction() as conn:
        await conn.execute("UPDATE users SET ... WHERE id = ?", user_id)
```

## Error Handling Types

### Exception Type Annotations

```python
from typing import Type, Union, Optional, NoReturn

class BotError(Exception):
    """Base exception for bot errors."""
    pass

class ConfigurationError(BotError):
    """Configuration-related errors."""
    pass

class ServiceError(BotError):
    """Service-related errors."""
    pass

def handle_error(
    error: Exception,
    error_types: List[Type[Exception]],
    fallback_message: Optional[str] = None
) -> str:
    """Handle errors of specific types."""
    for error_type in error_types:
        if isinstance(error, error_type):
            return f"Handled {error_type.__name__}: {error}"
    
    return fallback_message or "Unknown error occurred"

def raise_configuration_error(message: str) -> NoReturn:
    """Raise a configuration error (never returns)."""
    raise ConfigurationError(message)
```

### Result Types

```python
from typing import Union, Generic, TypeVar
from dataclasses import dataclass

T = TypeVar('T')
E = TypeVar('E', bound=Exception)

@dataclass
class Success(Generic[T]):
    """Successful result containing a value."""
    value: T

@dataclass
class Failure(Generic[E]):
    """Failed result containing an error."""
    error: E

Result = Union[Success[T], Failure[E]]

def safe_divide(a: float, b: float) -> Result[float, ValueError]:
    """Safely divide two numbers."""
    if b == 0:
        return Failure(ValueError("Division by zero"))
    return Success(a / b)

def handle_result(result: Result[float, ValueError]) -> str:
    """Handle a result value."""
    match result:
        case Success(value):
            return f"Result: {value}"
        case Failure(error):
            return f"Error: {error}"
```

## Configuration Types

### Configuration Schemas

```python
from typing import TypedDict, Optional, List, Literal
from dataclasses import dataclass

class DatabaseConfig(TypedDict):
    """Database configuration schema."""
    url: str
    pool_size: int
    timeout: float
    retry_attempts: int

class AIConfig(TypedDict):
    """AI service configuration schema."""
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    timeout: float

class BotConfig(TypedDict):
    """Main bot configuration schema."""
    telegram_token: str
    database: DatabaseConfig
    ai: AIConfig
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']
    features_enabled: List[str]

@dataclass
class RuntimeConfig:
    """Runtime configuration with validation."""
    telegram_token: str
    database_url: str
    ai_api_key: str
    log_level: str = 'INFO'
    
    def __post_init__(self):
        if not self.telegram_token:
            raise ValueError("Telegram token is required")
        if not self.database_url:
            raise ValueError("Database URL is required")
```

## Best Practices

### 1. Use Specific Types

```python
# Bad: Too generic
def process_data(data: Any) -> Any:
    pass

# Good: Specific types
def process_user_data(data: Dict[str, Union[str, int]]) -> UserProfile:
    pass
```

### 2. Use Optional for Nullable Values

```python
# Bad: Unclear if None is allowed
def get_user_name(user_id: int) -> str:
    pass

# Good: Explicit about None possibility
def get_user_name(user_id: int) -> Optional[str]:
    pass
```

### 3. Use TypedDict for Structured Data

```python
# Bad: Generic dict
def create_user(user_data: Dict[str, Any]) -> User:
    pass

# Good: Structured type
class UserData(TypedDict):
    username: str
    email: str
    age: int

def create_user(user_data: UserData) -> User:
    pass
```

### 4. Use Protocols for Interfaces

```python
# Bad: Concrete dependency
def save_data(database: PostgreSQLDatabase, data: Any) -> None:
    pass

# Good: Protocol-based interface
class Database(Protocol):
    def save(self, data: Any) -> None: ...

def save_data(database: Database, data: Any) -> None:
    pass
```

### 5. Use Generic Types for Reusability

```python
# Bad: Separate classes for each type
class UserRepository:
    def get(self, id: int) -> Optional[User]: ...

class ChatRepository:
    def get(self, id: int) -> Optional[Chat]: ...

# Good: Generic repository
T = TypeVar('T')

class Repository(Generic[T]):
    def get(self, id: int) -> Optional[T]: ...

user_repo: Repository[User] = Repository()
chat_repo: Repository[Chat] = Repository()
```

## Type Checking Tools

### MyPy Configuration

Create a `mypy.ini` file:

```ini
[mypy]
python_version = 3.10
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True

[mypy-tests.*]
disallow_untyped_defs = False
```

### Running Type Checks

```bash
# Check all files
mypy modules/

# Check specific file
mypy modules/service_registry.py

# Check with strict mode
mypy --strict modules/

# Generate HTML report
mypy --html-report mypy-report modules/
```

### IDE Integration

Most modern IDEs support type checking:

- **PyCharm**: Built-in type checking
- **VS Code**: Python extension with Pylance
- **Vim/Neovim**: ALE or coc.nvim with mypy

### Type Checking in CI/CD

```yaml
# .github/workflows/type-check.yml
name: Type Check
on: [push, pull_request]

jobs:
  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - name: Install dependencies
        run: |
          pip install mypy
          pip install -r requirements.txt
      - name: Run type checking
        run: mypy modules/
```

## Common Type Checking Issues

### 1. Missing Return Type

```python
# Error: Function is missing a return type annotation
def get_user(user_id: int):  # Missing -> Optional[User]
    return users.get(user_id)
```

### 2. Incompatible Types

```python
# Error: Incompatible types in assignment
user_id: int = "12345"  # Should be int, not str
```

### 3. Optional Type Handling

```python
# Error: Item "None" has no attribute "name"
def get_user_name(user_id: int) -> str:
    user = get_user(user_id)  # Returns Optional[User]
    return user.name  # Error: user might be None

# Fix: Handle None case
def get_user_name(user_id: int) -> Optional[str]:
    user = get_user(user_id)
    return user.name if user else None
```

### 4. Any Type Usage

```python
# Warning: Returning Any from function declared to return str
def process_data(data: Any) -> str:
    return data  # data could be anything, not necessarily str

# Fix: Use proper type conversion
def process_data(data: Any) -> str:
    return str(data)
```

## Conclusion

Type annotations are a powerful tool for improving code quality, documentation, and developer experience. By following these guidelines and best practices, you can create more maintainable and robust code that's easier to understand and debug.

Remember:
- Start with basic type annotations and gradually add more complex types
- Use type checking tools like mypy to catch errors early
- Prefer specific types over generic ones when possible
- Use protocols for flexible interfaces
- Document complex type relationships clearly

Type annotations are not just about catching bugs—they're about making your code more expressive and self-documenting.