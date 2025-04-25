# Telegram PsychochauffeurBot 🤖

A versatile Telegram bot that downloads videos from social media platforms, provides weather updates with AI-powered advice, offers GPT chat integration, and includes various utility features.

## 🎥 Video Downloader

### Supported Platforms
- TikTok
- Meta (Instagram, Facebook)
- YouTube Shorts and Clips
- Twitter/X
- Vimeo
- Reddit
- Twitch Clips

### How to Use

Simply send a video link from any supported platform, and the bot will:
1. Process your request
2. Download the video
3. Send it directly in the chat

**Note**: Maximum video size is 50MB due to Telegram restrictions

### Platform-Specific Features
- **YouTube Shorts**: Bot downloads and sends the video
- **AliExpress Links**: Automatically shortens URLs, adds #aliexpress hashtag, and sends a sticker

## 🤖 GPT Integration
- Direct GPT responses when mentioned in messages
- `/gpt` command for direct AI chat
- `/analyze` command to summarize chat messages (add "yesterday" parameter for previous day)
- Random AI responses triggered after 50+ messages (2% probability)
- Contextual responses based on recent chat history
- Powered by GPT-4o-mini model with optimized parameters

## ☁️ Weather Features
- `/weather` - Get weather updates with temperature, "feels like" data, and emojis
- AI-powered clothing recommendations based on weather conditions
- Location-specific forecasts with country flag emojis
- User-specific and chat-specific location preferences
- `/flares` - Fetch weather screenshots from monitoring service
- Scheduled weather screenshot capture every 6 hours

## 🤖 Advanced Features

### Message Processing
- Automatic content moderation with character filtering
  - Automatic restriction for prohibited characters (ЫыЪъЭэЁё)
  - Smart message history tracking
- Enhanced GPT response system:
  - Direct responses when bot is mentioned
  - Random responses (2% chance after 50+ messages)
  - Silent image analysis capability
  - Contextual responses based on chat history
- Different behavior patterns for private and group chats
- Message history tracking for translation features

### URL Processing
- Automatic URL shortening with rate limiting (30 calls/minute)
- URL sanitization and security checks
- Smart link modification system
- Customized message construction for modified links
- Platform-specific link handling

### Reminder System
- `/remind` - Set and manage reminders
- Persistent reminder storage
- Flexible time format parsing
- Reminder notifications with customizable settings

### Geomagnetic Activity
- `/gm` - Get current geomagnetic activity status
- Regular updates on significant changes
- Integration with geomagnetic data sources
- Historical data tracking

## 🛠 Commands
- `/start` - Welcome message and bot info
- `/cat` - Random cat pictures from thecatapi.com
- `бля!` - Translates last message from English to Ukrainian keyboard layout
- `/errors` - Generate error analytics report (admin only)
- `/gm` - Check geomagnetic activity
- `/remind` - Set reminders
- `/analyze` - Analyze chat messages

## 🔧 Technical Features
- Comprehensive error analytics and reporting system
- User restriction system for inappropriate content
- Automatic chat logging with daily files per chat
- Interactive button interfaces with link keyboards
- Translation of messages written with wrong keyboard layout
- Specialized sticker responses for errors and specific triggers
- Advanced error handling system:
  - Error severity categorization
  - Automated error logging to designated channel
  - Comprehensive analytics via `/errors` command
- User management system:
  - Automatic content moderation
  - User message history tracking
  - Chat-specific behavior customization
- Rate limiting and protection systems:
  - URL shortener limits (30 calls/minute)
  - API call optimization
  - Resource usage monitoring

## 📦 Requirements
- Python 3.10+
- Telegram Bot Token
- OpenAI API Key
- Required packages:
  ```
spicified in requirements.txt
  ```


## 📝 Setup
1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Create `.env` file with your API keys:
## 🔧 Advanced Configuration
Environment variables:
```env
# Required
TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key

# Optional but Recommended
ERROR_CHANNEL_ID=telegram_channel_id_for_errors
OPENWEATHER_API_KEY=openweather_api_key
SHORTENER_MAX_CALLS_PER_MINUTE=30

# YouTube Download Service Configuration
YTDL_SERVICE_API_KEY=your_ytdl_service_key
YTDL_SERVICE_URL=service_url
YTDL_MAX_RETRIES=3
YTDL_RETRY_DELAY=1
YTDL_RETRY_DELAY=1RY_DELAY=1
   ```
3. Run the bot:
   ```bash
   python main.py
   ```

## 🧪 Running Tests
To run the test suite (excluding integration/service tests):
```bash
pytest --ignore=tests/test_service.py
```
To run all tests:
```bash
pytest
```

## ⚠️ Limitations
- 50MB maximum video size for Telegram uploads
- Rate limits for GPT API calls
- Some platforms may have additional restrictions
- Bot needs appropriate permissions in group chats
- URL shortener rate limit: 30 calls per minute
- Image analysis only available for specific file types
- Reminder system requires persistent storage
- Geomagnetic activity updates depend on external API availability

For issues or suggestions, please contact @vo1dee