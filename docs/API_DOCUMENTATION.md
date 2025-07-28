# API Documentation

This document provides comprehensive API documentation for the PsychoChauffeur Bot, including internal APIs, external integrations, and service interfaces.

## Table of Contents

1. [Overview](#overview)
2. [Internal Service APIs](#internal-service-apis)
3. [Configuration API](#configuration-api)
4. [Video Download API](#video-download-api)
5. [AI Service API](#ai-service-api)
6. [Weather Service API](#weather-service-api)
7. [Database API](#database-api)
8. [Error Handling API](#error-handling-api)
9. [Performance Monitoring API](#performance-monitoring-api)
10. [External API Integrations](#external-api-integrations)
11. [Webhook APIs](#webhook-apis)
12. [Authentication and Security](#authentication-and-security)

## Overview

The PsychoChauffeur Bot exposes several internal APIs for service communication and external APIs for integration with third-party services. All APIs follow RESTful principles where applicable and use JSON for data exchange.

### API Conventions

- **Base URL**: `http://localhost:8080/api/v1` (configurable)
- **Content-Type**: `application/json`
- **Authentication**: Bearer token or API key
- **Error Format**: Standardized error responses
- **Rate Limiting**: Applied per endpoint and user

### Standard Response Format

```json
{
  "success": true,
  "data": {
    // Response data
  },
  "error": null,
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

### Error Response Format

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "field": "user_id",
      "reason": "must be a positive integer"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

## Internal Service APIs

### Service Registry API

The Service Registry provides dependency injection and service management.

#### Get Service

```python
def get_service(name: str) -> Any
```

**Description**: Retrieve a registered service instance.

**Parameters**:
- `name` (str): The name of the service to retrieve

**Returns**: The service instance

**Raises**:
- `ValueError`: If service is not registered

**Example**:
```python
database_service = service_registry.get_service('database')
user_repo = service_registry.get_service('user_repository')
```

#### Register Service

```python
def register_singleton(
    name: str, 
    service_type: Type[T], 
    implementation: Optional[Type[T]] = None,
    dependencies: Optional[List[str]] = None
) -> 'ServiceRegistry'
```

**Description**: Register a singleton service.

**Parameters**:
- `name` (str): Unique service name
- `service_type` (Type[T]): Service interface type
- `implementation` (Optional[Type[T]]): Concrete implementation
- `dependencies` (Optional[List[str]]): List of dependency service names

**Returns**: ServiceRegistry instance for chaining

**Example**:
```python
service_registry.register_singleton(
    'user_service', 
    UserService, 
    dependencies=['database', 'cache']
)
```

#### Get Services by Type

```python
def get_services_by_type(service_type: Type[T]) -> List[T]
```

**Description**: Get all services implementing a specific interface.

**Parameters**:
- `service_type` (Type[T]): The interface type to search for

**Returns**: List of service instances

**Example**:
```python
repositories = service_registry.get_services_by_type(Repository)
```

## Configuration API

### Get Configuration

```http
GET /api/v1/config/{scope}/{config_id}
```

**Description**: Retrieve configuration for a specific scope and ID.

**Parameters**:
- `scope` (path): Configuration scope (global, chat, user, module)
- `config_id` (path): Configuration identifier

**Query Parameters**:
- `effective` (boolean): Return effective configuration with inheritance
- `include_metadata` (boolean): Include configuration metadata

**Response**:
```json
{
  "success": true,
  "data": {
    "config_id": "12345",
    "scope": "chat",
    "config": {
      "language": "en",
      "timezone": "UTC",
      "features_enabled": ["gpt", "weather"]
    },
    "metadata": {
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "version": 1
    }
  }
}
```

### Set Configuration

```http
PUT /api/v1/config/{scope}/{config_id}
```

**Description**: Update configuration for a specific scope and ID.

**Parameters**:
- `scope` (path): Configuration scope
- `config_id` (path): Configuration identifier

**Request Body**:
```json
{
  "config": {
    "language": "es",
    "timezone": "Europe/Madrid",
    "features_enabled": ["gpt", "weather", "video"]
  },
  "merge_strategy": "deep_merge"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "updated": true,
    "validation_result": {
      "valid": true,
      "errors": []
    }
  }
}
```

### List Configurations

```http
GET /api/v1/config/{scope}
```

**Description**: List all configurations for a specific scope.

**Parameters**:
- `scope` (path): Configuration scope

**Query Parameters**:
- `limit` (integer): Maximum number of results (default: 50)
- `offset` (integer): Pagination offset (default: 0)
- `filter` (string): Filter configurations by pattern

**Response**:
```json
{
  "success": true,
  "data": {
    "configurations": [
      {
        "config_id": "12345",
        "last_updated": "2024-01-15T10:30:00Z",
        "size": 1024
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

## Video Download API

### Download Video

```http
POST /api/v1/video/download
```

**Description**: Download a video from a supported platform.

**Request Body**:
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "quality": "720p",
  "audio_only": false,
  "max_file_size": 104857600,
  "max_duration": 3600
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "download_id": "dl_123456789",
    "status": "completed",
    "file_path": "/downloads/video_123.mp4",
    "title": "Never Gonna Give You Up",
    "duration": 212,
    "file_size": 15728640,
    "thumbnail": "/downloads/video_123_thumb.jpg",
    "metadata": {
      "uploader": "RickAstleyVEVO",
      "upload_date": "2009-10-25",
      "view_count": 1000000000
    }
  }
}
```

### Get Video Info

```http
GET /api/v1/video/info
```

**Description**: Get video information without downloading.

**Query Parameters**:
- `url` (string, required): Video URL

**Response**:
```json
{
  "success": true,
  "data": {
    "title": "Never Gonna Give You Up",
    "duration": 212,
    "uploader": "RickAstleyVEVO",
    "view_count": 1000000000,
    "upload_date": "2009-10-25",
    "available_formats": [
      {
        "format_id": "18",
        "ext": "mp4",
        "height": 360,
        "filesize": 8388608
      },
      {
        "format_id": "22",
        "ext": "mp4",
        "height": 720,
        "filesize": 25165824
      }
    ]
  }
}
```

### Get Download Status

```http
GET /api/v1/video/download/{download_id}/status
```

**Description**: Get the status of a download operation.

**Parameters**:
- `download_id` (path): Download operation ID

**Response**:
```json
{
  "success": true,
  "data": {
    "download_id": "dl_123456789",
    "status": "in_progress",
    "progress": 65.5,
    "estimated_time_remaining": 30,
    "download_speed": 1048576,
    "error": null
  }
}
```

### Cancel Download

```http
DELETE /api/v1/video/download/{download_id}
```

**Description**: Cancel an ongoing download operation.

**Parameters**:
- `download_id` (path): Download operation ID

**Response**:
```json
{
  "success": true,
  "data": {
    "cancelled": true,
    "cleanup_completed": true
  }
}
```

## AI Service API

### Generate Response

```http
POST /api/v1/ai/generate
```

**Description**: Generate AI response with optional context.

**Request Body**:
```json
{
  "prompt": "Explain quantum computing in simple terms",
  "context": {
    "conversation_history": [
      {
        "role": "user",
        "content": "What is quantum computing?"
      }
    ],
    "user_id": 12345,
    "chat_id": 67890
  },
  "parameters": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 1000,
    "system_prompt": "You are a helpful science teacher."
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "response": "Quantum computing is like having a super-powered calculator...",
    "model": "gpt-4",
    "tokens_used": 150,
    "response_time": 2.5,
    "confidence": 0.95,
    "metadata": {
      "finish_reason": "stop",
      "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 100,
        "total_tokens": 150
      }
    }
  }
}
```

### Analyze Image

```http
POST /api/v1/ai/analyze-image
```

**Description**: Analyze image content using AI vision models.

**Request Body** (multipart/form-data):
- `image`: Image file
- `prompt`: Analysis prompt (optional)
- `detail_level`: "low" | "high" (optional)

**Response**:
```json
{
  "success": true,
  "data": {
    "description": "The image shows a golden retriever playing in a park...",
    "objects": [
      {
        "name": "dog",
        "confidence": 0.98,
        "bounding_box": [100, 150, 300, 400]
      },
      {
        "name": "tree",
        "confidence": 0.85,
        "bounding_box": [50, 0, 200, 300]
      }
    ],
    "text_content": [],
    "metadata": {
      "model": "gpt-4-vision",
      "processing_time": 3.2
    }
  }
}
```

### Get AI Models

```http
GET /api/v1/ai/models
```

**Description**: Get list of available AI models.

**Response**:
```json
{
  "success": true,
  "data": {
    "models": [
      {
        "id": "gpt-4",
        "name": "GPT-4",
        "description": "Most capable GPT model",
        "max_tokens": 8192,
        "supports_vision": true,
        "cost_per_token": 0.00003
      },
      {
        "id": "gpt-3.5-turbo",
        "name": "GPT-3.5 Turbo",
        "description": "Fast and efficient model",
        "max_tokens": 4096,
        "supports_vision": false,
        "cost_per_token": 0.000002
      }
    ]
  }
}
```

## Weather Service API

### Get Current Weather

```http
GET /api/v1/weather/current
```

**Description**: Get current weather for a location.

**Query Parameters**:
- `location` (string, required): Location name or coordinates
- `units` (string): "metric" | "imperial" | "kelvin" (default: "metric")
- `language` (string): Language code for descriptions (default: "en")

**Response**:
```json
{
  "success": true,
  "data": {
    "location": {
      "name": "London",
      "country": "GB",
      "coordinates": {
        "lat": 51.5074,
        "lon": -0.1278
      }
    },
    "current": {
      "temperature": 15.5,
      "feels_like": 14.2,
      "humidity": 65,
      "pressure": 1013,
      "visibility": 10000,
      "uv_index": 3,
      "description": "partly cloudy",
      "icon": "02d"
    },
    "wind": {
      "speed": 3.2,
      "direction": 180,
      "gust": 5.1
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Get Weather Forecast

```http
GET /api/v1/weather/forecast
```

**Description**: Get weather forecast for a location.

**Query Parameters**:
- `location` (string, required): Location name or coordinates
- `days` (integer): Number of forecast days (1-7, default: 5)
- `units` (string): Unit system (default: "metric")

**Response**:
```json
{
  "success": true,
  "data": {
    "location": {
      "name": "London",
      "country": "GB"
    },
    "forecast": [
      {
        "date": "2024-01-15",
        "temperature": {
          "min": 8.0,
          "max": 18.0,
          "morning": 12.0,
          "afternoon": 16.0,
          "evening": 14.0,
          "night": 10.0
        },
        "description": "light rain",
        "precipitation": {
          "probability": 80,
          "amount": 2.5
        },
        "wind": {
          "speed": 4.1,
          "direction": 220
        },
        "humidity": 75
      }
    ]
  }
}
```

### Get Weather Alerts

```http
GET /api/v1/weather/alerts
```

**Description**: Get weather alerts for a location.

**Query Parameters**:
- `location` (string, required): Location name or coordinates
- `severity` (string): Filter by severity level

**Response**:
```json
{
  "success": true,
  "data": {
    "alerts": [
      {
        "id": "alert_123",
        "event": "Severe Thunderstorm Warning",
        "severity": "moderate",
        "urgency": "immediate",
        "certainty": "likely",
        "start": "2024-01-15T14:00:00Z",
        "end": "2024-01-15T18:00:00Z",
        "description": "Severe thunderstorms with damaging winds and large hail possible.",
        "areas": ["London", "Greater London"],
        "sender": "Met Office"
      }
    ]
  }
}
```

## Database API

### Execute Query

```python
async def execute(query: str, *params) -> None
```

**Description**: Execute a database query with parameters.

**Parameters**:
- `query` (str): SQL query with parameter placeholders
- `*params`: Query parameters

**Example**:
```python
await database.execute(
    "INSERT INTO users (id, username) VALUES (?, ?)",
    user_id, username
)
```

### Fetch Records

```python
async def fetch(query: str, *params) -> List[Dict[str, Any]]
```

**Description**: Fetch multiple records from the database.

**Parameters**:
- `query` (str): SQL query
- `*params`: Query parameters

**Returns**: List of records as dictionaries

**Example**:
```python
users = await database.fetch(
    "SELECT * FROM users WHERE active = ?", True
)
```

### Fetch Single Record

```python
async def fetchrow(query: str, *params) -> Optional[Dict[str, Any]]
```

**Description**: Fetch a single record from the database.

**Parameters**:
- `query` (str): SQL query
- `*params`: Query parameters

**Returns**: Single record as dictionary or None

**Example**:
```python
user = await database.fetchrow(
    "SELECT * FROM users WHERE id = ?", user_id
)
```

### Transaction Context

```python
async def transaction() -> AsyncContextManager
```

**Description**: Create a database transaction context.

**Returns**: Async context manager for transaction

**Example**:
```python
async with database.transaction():
    await database.execute("INSERT INTO users ...")
    await database.execute("INSERT INTO profiles ...")
    # Automatically commits on success, rolls back on error
```

## Error Handling API

### Standard Error Response

All API endpoints return errors in a consistent format:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "specific_field",
      "reason": "validation_failed",
      "expected": "string",
      "received": "number"
    },
    "trace_id": "trace_123456789"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

### Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Request validation failed | 400 |
| `AUTHENTICATION_ERROR` | Authentication failed | 401 |
| `AUTHORIZATION_ERROR` | Insufficient permissions | 403 |
| `NOT_FOUND` | Resource not found | 404 |
| `RATE_LIMIT_EXCEEDED` | Rate limit exceeded | 429 |
| `INTERNAL_ERROR` | Internal server error | 500 |
| `SERVICE_UNAVAILABLE` | External service unavailable | 503 |

### Error Handling Decorators

```python
@handle_api_errors(
    error_mapping={
        ValueError: ("VALIDATION_ERROR", 400),
        PermissionError: ("AUTHORIZATION_ERROR", 403),
        ConnectionError: ("SERVICE_UNAVAILABLE", 503)
    }
)
async def api_endpoint():
    """API endpoint with automatic error handling."""
    pass
```

## Performance Monitoring API

### Get Performance Metrics

```http
GET /api/v1/metrics
```

**Description**: Get current performance metrics.

**Query Parameters**:
- `timeframe` (string): Time range ("1h", "24h", "7d", "30d")
- `metrics` (string): Comma-separated list of metric names

**Response**:
```json
{
  "success": true,
  "data": {
    "system": {
      "cpu_usage": 45.2,
      "memory_usage": 67.8,
      "disk_usage": 23.1,
      "network_io": {
        "bytes_sent": 1048576,
        "bytes_received": 2097152
      }
    },
    "application": {
      "requests_per_second": 12.5,
      "average_response_time": 150.3,
      "error_rate": 0.02,
      "active_connections": 25
    },
    "services": {
      "database": {
        "connection_pool_usage": 30,
        "query_time_avg": 25.6,
        "slow_queries": 2
      },
      "cache": {
        "hit_rate": 85.2,
        "memory_usage": 45.6,
        "evictions": 10
      }
    }
  }
}
```

### Get Health Status

```http
GET /api/v1/health
```

**Description**: Get system health status.

**Response**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "uptime": 86400,
    "version": "2.1.0",
    "services": {
      "database": {
        "status": "healthy",
        "response_time": 5.2,
        "last_check": "2024-01-15T10:29:55Z"
      },
      "cache": {
        "status": "healthy",
        "response_time": 1.1,
        "last_check": "2024-01-15T10:29:55Z"
      },
      "external_apis": {
        "telegram": {
          "status": "healthy",
          "response_time": 120.5
        },
        "openai": {
          "status": "degraded",
          "response_time": 2500.0,
          "error": "High latency detected"
        }
      }
    }
  }
}
```

## External API Integrations

### Telegram Bot API

The bot integrates with the Telegram Bot API for message handling.

**Base URL**: `https://api.telegram.org/bot{token}`

**Key Endpoints Used**:
- `getUpdates`: Receive incoming updates
- `sendMessage`: Send text messages
- `sendPhoto`: Send photos
- `sendDocument`: Send files
- `editMessageText`: Edit existing messages

### OpenAI API

Integration with OpenAI for AI-powered features.

**Base URL**: `https://api.openai.com/v1`

**Key Endpoints Used**:
- `chat/completions`: Generate chat responses
- `images/generations`: Generate images
- `audio/transcriptions`: Transcribe audio

### Weather APIs

Integration with weather service providers.

**OpenWeatherMap API**:
- Base URL: `https://api.openweathermap.org/data/2.5`
- Endpoints: `weather`, `forecast`, `alerts`

## Webhook APIs

### Telegram Webhook

```http
POST /webhook/telegram
```

**Description**: Receive updates from Telegram via webhook.

**Request Body**: Telegram Update object

**Response**:
```json
{
  "ok": true
}
```

### Configuration Webhook

```http
POST /webhook/config-update
```

**Description**: Receive configuration update notifications.

**Request Body**:
```json
{
  "scope": "chat",
  "config_id": "12345",
  "action": "updated",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Authentication and Security

### API Key Authentication

Include API key in request headers:

```http
Authorization: Bearer your_api_key_here
```

### Rate Limiting

Rate limits are applied per endpoint and user:

- **Default**: 100 requests per minute
- **AI endpoints**: 10 requests per minute
- **Download endpoints**: 5 requests per minute

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642694460
```

### Request Validation

All requests are validated for:
- Required parameters
- Parameter types and formats
- Value ranges and constraints
- Authentication and authorization

### Security Headers

All responses include security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## SDK and Client Libraries

### Python SDK

```python
from psychochauffeur_bot import BotClient

client = BotClient(api_key="your_api_key")

# Download video
result = await client.video.download("https://youtube.com/watch?v=...")

# Generate AI response
response = await client.ai.generate("Hello, how are you?")

# Get weather
weather = await client.weather.current("London")
```

### JavaScript SDK

```javascript
import { BotClient } from 'psychochauffeur-bot-js';

const client = new BotClient({ apiKey: 'your_api_key' });

// Download video
const result = await client.video.download('https://youtube.com/watch?v=...');

// Generate AI response
const response = await client.ai.generate('Hello, how are you?');

// Get weather
const weather = await client.weather.current('London');
```

## Error Handling Best Practices

1. **Always check the `success` field** in responses
2. **Handle rate limiting** with exponential backoff
3. **Implement retry logic** for transient errors
4. **Log error details** for debugging
5. **Provide user-friendly error messages**

## Conclusion

This API documentation provides comprehensive coverage of all available endpoints and integration patterns. For additional support or questions, please refer to the developer documentation or contact the development team.