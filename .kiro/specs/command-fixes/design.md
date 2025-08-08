# Design Document

## Overview

This design addresses the critical issues with the `/analyze` and `/flares` commands by implementing robust error handling, improved date parsing, and reliable screenshot generation. The solution focuses on diagnosing root causes and implementing comprehensive fixes.

## Architecture

### Command Processing Flow
```
User Command → Command Handler → Business Logic → External Services → Response
     ↓              ↓                ↓              ↓              ↓
Error Handling → Validation → Database/API → Error Recovery → User Feedback
```

### Key Components
1. **Enhanced Command Handlers** - Improved error handling and validation
2. **Date Parser Utility** - Flexible date format support
3. **Database Connection Manager** - Robust connection handling with retries
4. **Screenshot Manager** - Reliable screenshot generation with fallbacks
5. **Error Recovery System** - Graceful degradation and user feedback

## Components and Interfaces

### 1. Enhanced Analyze Command Handler

**Location:** `modules/gpt.py` - `analyze_command` function

**Responsibilities:**
- Parse command arguments with flexible date formats
- Validate input parameters
- Handle database connection errors
- Provide detailed error messages
- Log execution metrics

**Key Changes:**
- Add date format detection (DD-MM-YYYY vs YYYY-MM-DD)
- Implement connection retry logic
- Add comprehensive error handling
- Improve user feedback messages

### 2. Date Parser Utility

**Location:** New utility in `modules/utils.py`

**Interface:**
```python
class DateParser:
    @staticmethod
    def parse_date(date_str: str) -> date:
        """Parse date string in multiple formats (DD-MM-YYYY, YYYY-MM-DD)"""
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> Tuple[date, date]:
        """Validate and parse date range"""
```

**Supported Formats:**
- YYYY-MM-DD (existing)
- DD-MM-YYYY (new requirement)
- DD/MM/YYYY (bonus)
- Automatic format detection

### 3. Database Connection Diagnostics

**Location:** `modules/database.py` - Enhanced `Database` class

**Enhancements:**
- Connection health checks
- Retry logic with exponential backoff
- Detailed error logging
- Connection pool monitoring
- Graceful degradation

**New Methods:**
```python
@classmethod
async def health_check(cls) -> bool:
    """Check database connectivity"""

@classmethod
async def get_pool_with_retry(cls, max_retries: int = 3) -> asyncpg.Pool:
    """Get pool with retry logic"""
```

### 4. Enhanced Screenshot Manager

**Location:** `modules/utils.py` - `ScreenshotManager` class

**Key Improvements:**
- Screenshot age validation (6-hour threshold)
- Robust error handling for wkhtmltoimage
- Directory creation with proper permissions
- Fallback mechanisms
- Progress indicators

**Enhanced Methods:**
```python
async def get_current_screenshot(self) -> Optional[str]:
    """Get current screenshot if fresh, otherwise generate new one"""

async def validate_screenshot_freshness(self, path: str) -> bool:
    """Check if screenshot is less than 6 hours old"""

async def ensure_screenshot_directory(self) -> None:
    """Ensure screenshot directory exists with proper permissions"""
```

### 5. Error Recovery and User Feedback

**Location:** Enhanced error handling across all command handlers

**Features:**
- Contextual error messages in Ukrainian
- Fallback options when primary methods fail
- Progress indicators for long-running operations
- Diagnostic information for administrators

## Data Models

### Error Context Model
```python
@dataclass
class CommandError:
    command: str
    error_type: str
    message: str
    user_message: str  # Localized message for user
    timestamp: datetime
    chat_id: int
    user_id: int
```

### Screenshot Metadata Model
```python
@dataclass
class ScreenshotInfo:
    path: str
    created_at: datetime
    is_fresh: bool
    next_update: datetime
    source_url: str
```

## Error Handling

### Database Connection Errors
1. **Detection:** Monitor connection pool health
2. **Recovery:** Implement exponential backoff retry
3. **Fallback:** Provide cached results when available
4. **User Feedback:** Clear error messages in Ukrainian

### Screenshot Generation Errors
1. **Missing Tool:** Check wkhtmltoimage availability
2. **Network Issues:** Retry with timeout handling
3. **Permission Issues:** Ensure directory permissions
4. **Fallback:** Return last available screenshot with warning

### Date Parsing Errors
1. **Format Detection:** Try multiple date formats
2. **Validation:** Check date ranges and logical constraints
3. **User Guidance:** Provide format examples in error messages

## Testing Strategy

### Unit Tests
- Date parser with various formats
- Database connection retry logic
- Screenshot freshness validation
- Error message generation

### Integration Tests
- End-to-end command execution
- Database connectivity scenarios
- Screenshot generation pipeline
- Error recovery workflows

### Error Simulation Tests
- Database connection failures
- Missing external tools
- Invalid user inputs
- Network timeouts

## Performance Considerations

### Database Optimization
- Connection pooling with health monitoring
- Query optimization for message retrieval
- Caching for frequently accessed data

### Screenshot Optimization
- Reuse fresh screenshots (< 6 hours)
- Async generation with progress feedback
- Efficient file system operations

### Memory Management
- Proper cleanup of database connections
- Efficient image processing
- Limited message history retention

## Security Considerations

### Input Validation
- Sanitize date inputs
- Validate chat and user IDs
- Prevent SQL injection

### File System Security
- Proper directory permissions
- Secure file path handling
- Cleanup of temporary files

### Error Information Disclosure
- Sanitize error messages for users
- Log detailed errors for administrators
- Prevent information leakage

## Monitoring and Logging

### Command Execution Metrics
- Success/failure rates
- Execution times
- Error categories
- User activity patterns

### Database Health Monitoring
- Connection pool status
- Query performance
- Error rates
- Recovery statistics

### Screenshot Generation Monitoring
- Generation frequency
- Success rates
- File system usage
- External service availability