# Telegram PsychochauffeurBot 🤖

A versatile Telegram bot that downloads videos and images from social media platforms, provides weather updates with AI-powered advice, offers GPT chat integration, and includes various utility features.

## 📋 Table of Contents
- [Features](#-features)
- [Setup](#-setup)
- [Configuration](#-configuration)
- [Development](#-development)
- [Testing](#-testing)
- [Limitations](#-limitations)
- [Contributing](#-contributing)

## ✨ Features

### 🎥 Media Download
- **Supported Platforms**:
  - TikTok, Instagram, Facebook
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
  - `/gpt` command for chat
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
- **Reminders**:
  - `/remind` command
  - Flexible time parsing
  - Persistent storage
- **Other Commands**:
  - `/cat` - Random cat pictures
  - `/errors` - Error analytics (admin)
  - `/start` - Bot information

## 🛠 Setup

### Prerequisites
- Python 3.10 or higher
- Telegram Bot Token
- OpenAI API Key
- (Optional) OpenWeather API Key

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/PsychochauffeurBot.git
   cd PsychochauffeurBot
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file:
   ```env
   # Required
   TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key

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

5. Run the bot:
   ```bash
   python main.py
   ```

## ⚙️ Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `TOKEN` | Yes | Telegram Bot Token |
| `OPENAI_API_KEY` | Yes | OpenAI API Key |
| `ERROR_CHANNEL_ID` | No | Channel for error logging |
| `OPENWEATHER_API_KEY` | No | Weather API key |
| `SHORTENER_MAX_CALLS_PER_MINUTE` | No | URL shortener rate limit |
| `YTDL_SERVICE_*` | No | YouTube download service config |

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
- Requires persistent storage for reminders
- External API dependencies

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

For issues or suggestions, contact @vo1dee