# PsychochauffeurBot Changelog & Cheatsheet

## Recent Changes

### API Provider Update
- Switched from OpenAI to OpenRouter as the API provider
- Updated environment variables:
  - Replaced `OPENAI_API_KEY` with `OPENROUTER_API_KEY`
  - Added `OPENROUTER_BASE_URL` configuration
- Updated API diagnostics tool to work with OpenRouter

### Chat Analysis Features
- Added new message analysis functions:
  - `get_messages_for_chat_today`
  - `get_last_n_messages_in_chat`
  - `get_messages_for_chat_last_n_days`
  - `get_messages_for_chat_date_period`
  - `get_messages_for_chat_single_date`
  - `get_user_chat_stats`

### Command Enhancements
- Enhanced `/analyze` command with multiple syntaxes
- Added new `/mystats` command for user statistics

## Command Cheatsheet

### Analysis Commands
| Command | Description | Example |
|---------|-------------|---------|
| `/analyze` | Analyze today's messages | `/analyze` |
| `/analyze last N messages` | Analyze last N messages | `/analyze last 50 messages` |
| `/analyze last N days` | Analyze messages from last N days | `/analyze last 7 days` |
| `/analyze period YYYY-MM-DD YYYY-MM-DD` | Analyze messages in date range | `/analyze period 2024-01-01 2024-01-31` |
| `/analyze date YYYY-MM-DD` | Analyze messages for specific date | `/analyze date 2024-01-15` |

### User Statistics
| Command | Description | Example |
|---------|-------------|---------|
| `/mystats` | Show your message statistics | `/mystats` |

### GPT Commands
| Command | Description | Example |
|---------|-------------|---------|
| `/gpt` | Ask GPT a question | `/gpt What is the weather like?` |
| `/gpt` | Start a conversation | `/gpt` |

### Weather Commands
| Command | Description | Example |
|---------|-------------|---------|
| `/weather` | Get current weather | `/weather Kyiv` |
| `/flares` | Get solar activity | `/flares` |
| `/gm` | Get geomagnetic status | `/gm` |

### Utility Commands
| Command | Description | Example |
|---------|-------------|---------|
| `/remind` | Set a reminder | `/remind Buy milk in 2 hours` |
| `/cat` | Get random cat picture | `/cat` |
| `/errors` | View error analytics (admin) | `/errors` |
| `/start` | Get bot information | `/start` |

## Environment Variables
```env
# Required
TOKEN=your_telegram_bot_token
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Optional but Recommended
ERROR_CHANNEL_ID=telegram_channel_id_for_errors
OPENWEATHER_API_KEY=openweather_api_key
SHORTENER_MAX_CALLS_PER_MINUTE=30

# YouTube Download Service
YTDL_SERVICE_API_KEY=your_ytdl_service_key
YTDL_SERVICE_URL=service_url
YTDL_MAX_RETRIES=3
YTDL_RETRY_DELAY=1
```

## Features Overview

### Media Download
- Supports multiple platforms:
  - TikTok, Instagram, Facebook
  - YouTube Shorts and Clips
  - Twitter/X, Vimeo, Reddit
  - Twitch Clips
- Maximum file size: 50MB

### AI Integration
- GPT-4-mini model with optimized parameters
- Context-aware responses
- Image analysis capability
- Random responses (2% chance after 50+ messages)

### Weather & Environment
- Current conditions with AI recommendations
- Solar activity monitoring
- Geomagnetic activity tracking
- Location-specific forecasts

### Utility Features
- Content moderation
- Keyboard layout translation
- URL processing and shortening
- Message history tracking
- Persistent reminders 