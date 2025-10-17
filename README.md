[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/vo1dee/PsychochauffeurBot)

# Telegram PsychochauffeurBot 🤖

A versatile Telegram bot that downloads videos and images from social media platforms, provides weather updates with AI-powered advice, offers GPT chat integration, and includes various utility features.

## 📋 Table of Contents
- [Features](#-features)
- [Setup](#-setup)
- [Docker Setup](#-docker-setup)
- [Configuration](#-configuration)
- [Development](#-development)
- [Testing](#-testing)
- [Limitations](#-limitations)
- [Contributing](#-contributing)

## ✨ Features

### 🎥 Media Download
- **Supported Platforms**:
  - TikTok
  - YouTube Shorts and Clips
  - Twitter/X, Vimeo, Reddit
  - Twitch Clips
- **Features**:
  - Automatic video/image download
  - Direct chat delivery
  - URL shortening for AliExpress links
  - Maximum file size: 50MB

### 🤖 AI Integration
- **GPT Features**:
  - Direct responses on mention
  - `/ask` command for chat
  - `/analyze` for message summarization
  - Random responses (2% chance after 50+ messages)
  - Context-aware responses
  - Image analysis capability
- **Model**: GPT-4-mini with optimized parameters

### ☁️ Weather & Environment
- **Weather Commands**:
  - `/weather` - Current conditions with AI recommendations
  - `/flares` - Solar activity screenshots
  - Location-specific forecasts
  - Country flag emojis
- **Geomagnetic Activity**:
  - `/gm` command for current status
  - Regular updates on significant changes
  - Historical data tracking

### ⚙️ Utility Features
- **Message Processing**:
  - Content moderation
  - Keyboard layout translation
  - URL processing and shortening
  - Message history tracking
- **Other Commands**:
  - `/cat` - Random cat pictures
  - `/errors` - Error analytics (admin)
  - `/start` - Bot information

### 🧠 Analysis Caching (NEW)
- The `/analyze` command now caches results to reduce API usage and speed up repeated requests.
- **How it works:**
  - Results are cached per chat, time period, and message content hash.
  - Cached results are returned instantly for repeated analysis of the same data (default cache window: 24h).
  - Cache is invalidated if new messages are added in the analyzed period or via admin command.
- **Admin command:** `/analyze flush-cache` clears the cache for the current chat.
- **Config:**
  - `ENABLE_ANALYSIS_CACHE` (default: True)
  - `ANALYSIS_CACHE_TTL` (default: 86400 seconds)

## 🛠 Setup

### Prerequisites
- Python 3.10 or higher
- Telegram Bot Token
- OpenAI API Key
- (Optional) OpenWeather API Key
- Docker and Docker Compose (for containerized setup)

### 🐳 Quick Start with Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/PsychochauffeurBot.git
   cd PsychochauffeurBot
   ```

2. Configure your `.env` file (already included with sample values)

3. Start with automated setup:
   ```bash
   ./start.sh
   source .venv/bin/activate && python main.py
   ```

**That's it!** The database will be automatically created and configured.

### 🐳 Docker Setup Options

#### Option 1: Database Only (Recommended)
```bash
# Start PostgreSQL database
docker-compose up -d postgres

# Run bot locally
source .venv/bin/activate && python main.py
```

#### Option 2: Full Docker Setup
```bash
# Uncomment the bot service in docker-compose.yml, then:
docker-compose up --build
```

#### Option 3: Automated Script
```bash
# Use the provided startup script
./start.sh
```

### 📋 What Docker Provides

- **PostgreSQL Database**: Automatically configured with proper schema
- **Health Checks**: Ensures database is ready before bot starts
- **Persistent Storage**: Data survives container restarts
- **Easy Management**: Simple commands for backup, restore, and maintenance

See [DOCKER_SETUP.md](DOCKER_SETUP.md) for detailed Docker documentation.

### 🔧 Manual Installation (Alternative)

1. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your database (PostgreSQL recommended)

4. Configure `.env` file with your settings

5. Run the bot:
   ```bash
   python main.py
   ```

## 🐳 Docker Setup

### Quick Commands

```bash
# Start database only
docker-compose up -d postgres

# Start everything (uncomment bot service first)
docker-compose up --build

# Stop services
docker-compose down

# Reset everything (deletes data)
docker-compose down -v

# View logs
docker-compose logs -f postgres

# Connect to database
docker-compose exec postgres psql -U postgres -d telegram_bot
```

### Database Management

```bash
# Backup database
docker-compose exec postgres pg_dump -U postgres telegram_bot > backup.sql

# Restore database
docker-compose exec -T postgres psql -U postgres -d telegram_bot < backup.sql

# Check database status
docker-compose exec postgres pg_isready -U postgres -d telegram_bot
```

### Files Included

- **`docker-compose.yml`** - PostgreSQL service with auto-initialization
- **`Dockerfile`** - Bot container configuration
- **`init-db.sql`** - Database schema and setup
- **`start.sh`** - Automated startup script
- **`.dockerignore`** - Optimized build context

For detailed Docker setup instructions, see [DOCKER_SETUP.md](DOCKER_SETUP.md).

## ⚙️ Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram Bot Token |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API Key |
| `OPENROUTER_BASE_URL` | Yes | OpenRouter API Base URL |
| `DB_HOST` | Yes | Database host (localhost or postgres) |
| `DB_PORT` | Yes | Database port (5432) |
| `DB_NAME` | Yes | Database name (telegram_bot) |
| `DB_USER` | Yes | Database user (postgres) |
| `DB_PASSWORD` | Yes | Database password |
| `ERROR_CHANNEL_ID` | No | Channel for error logging |
| `OPENWEATHER_API_KEY` | No | Weather API key |
| `SHORTENER_MAX_CALLS_PER_MINUTE` | No | URL shortener rate limit |
| `YTDL_SERVICE_*` | No | YouTube download service config |
| `SPEECHMATICS_API_KEY` | No | Speech-to-text API key |

### Configuration Scopes
- `global`: Default configuration
- `private`: Per-user settings
- `group`: Per-group settings

## 💻 Development

### Project Structure
```
PsychochauffeurBot/
├── main.py              # Main entry point
├── api.py              # API endpoints
├── docker-compose.yml   # Docker services configuration
├── Dockerfile          # Bot container configuration
├── init-db.sql         # Database initialization
├── start.sh            # Automated startup script
├── .dockerignore       # Docker build optimization
├── DOCKER_SETUP.md     # Docker documentation
├── config/             # Configuration files
├── modules/            # Core functionality
│   ├── gpt.py         # GPT integration
│   ├── weather.py     # Weather features
│   ├── video_downloader.py
│   └── ...
├── tests/             # Test suite
├── utils/             # Utility functions
└── requirements.txt   # Dependencies
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints
- Document functions with docstrings
- Keep functions focused and small

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run without integration tests
pytest --ignore=tests/test_service.py

# Run specific test file
pytest tests/test_weather.py
```

### Test Coverage
```bash
# Generate coverage report
pytest --cov=modules tests/
```

## ⚠️ Limitations
- 50MB maximum video size
- GPT API rate limits
- Platform-specific restrictions
- URL shortener: 30 calls/minute
- Image analysis: specific file types only
- External API dependencies

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

For issues or suggestions, contact @vo1dee

## Speech-to-Text (Speechmatics) Integration

### Setup
1. Get your Speechmatics API key from https://www.speechmatics.com/
2. Add the following to your `.env` file:

    SPEECHMATICS_API_KEY=your_api_key_here

3. The bot will use this key for all speech-to-text requests.

### Enabling Speech Recognition
- By default, speech recognition is disabled in all chats.
- To enable, use the `/speech on` command (admin only by default).
- To disable, use `/speech off`.
- You can allow all users to toggle speech recognition by setting `allow_all_users` to `true` in the chat's config (see `config/global/global_config.json` or use the config API if available).

### Usage
- When enabled, any Telegram voice or video note message sent in the chat will be transcribed using Speechmatics.
- The transcription will be posted to the chat and logged in the chat history as:

    [User Name] (Speech): Transcribed Text

- Only `voice` and `video_note` messages are supported (not generic audio or video files).

### Requirements
- Ensure `httpx` and `python-dotenv` are installed (see `requirements.txt`).