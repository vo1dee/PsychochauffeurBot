[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/vo1dee/PsychochauffeurBot)

# Telegram PsychochauffeurBot 🤖

A versatile Telegram bot that downloads videos and images from social media platforms, provides weather updates with AI-powered advice, offers GPT chat integration, and includes various utility features.

## 📋 Table of Contents
- [Features](#-features)
- [Test Suite Optimizer](#-test-suite-optimizer)
- [Setup](#-setup)
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
- **Reminders**:
  - `/remind` command
  - Flexible time parsing
  - Persistent storage
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

## 🧪 Test Suite Optimizer

This project includes a comprehensive **Test Suite Optimizer** - a powerful tool for analyzing and improving Python test suites. The optimizer helps identify test quality issues, coverage gaps, redundant tests, and provides actionable recommendations.

### Key Features
- **Coverage Analysis**: Identify untested code paths and critical gaps
- **Redundancy Detection**: Find duplicate, obsolete, and trivial tests
- **Test Quality Assessment**: Analyze assertion strength and test patterns
- **Automated Recommendations**: Get specific suggestions for improvements
- **Multiple Report Formats**: HTML, JSON, and Markdown outputs

### Quick Start
```python
from test_suite_optimizer_project import TestSuiteAnalyzer

# Analyze your test suite
analyzer = TestSuiteAnalyzer()
report = await analyzer.analyze(".")

print(f"Coverage: {report.coverage_report.total_coverage:.1f}%")
print(f"Issues found: {len(report.validation_issues)}")
```

### Project Structure
```
test_suite_optimizer_project/
├── src/                    # Source code
│   ├── core/              # Core analyzer and configuration
│   ├── analyzers/         # Coverage, quality, and complexity analysis
│   ├── detectors/         # Redundancy and duplicate detection
│   ├── reporters/         # Report generation (HTML, JSON, Markdown)
│   └── models/           # Data models and interfaces
├── examples/             # Real-world usage examples
├── demos/               # Feature demonstration scripts
├── reports/             # Generated analysis reports
└── analysis_results/    # Historical analysis data
```

### Documentation
- **[User Guide](docs/TEST_SUITE_OPTIMIZER_USER_GUIDE.md)** - Complete usage instructions
- **[API Documentation](docs/TEST_SUITE_OPTIMIZER_API_DOCUMENTATION.md)** - Full API reference
- **[Configuration Guide](docs/TEST_SUITE_OPTIMIZER_CONFIGURATION_GUIDE.md)** - Customization options
- **[Example Reports](docs/examples/)** - Sample analysis outputs and case studies

### Example Analysis Results
The optimizer has been used to analyze this project itself, achieving:
- **Coverage improvement**: 18% → 76% overall coverage
- **Issue detection**: 23 critical issues identified and resolved
- **Test quality**: Improved from 34/100 to 80/100 quality score
- **Redundancy cleanup**: 12 duplicate tests consolidated

See [ORGANIZATION_SUMMARY.md](ORGANIZATION_SUMMARY.md) for details on the project reorganization and structure.

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

5. Run the bot:
   ```bash
   python main.py
   ```

## ⚙️ Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `TOKEN` | Yes | Telegram Bot Token |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API Key |
| `OPENROUTER_BASE_URL` | Yes | OpenRouter API Base URL |
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
