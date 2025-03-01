# Telegram PsychochauffeurBot 🤖

A versatile Telegram bot that downloads videos from social media platforms, provides weather updates with AI-powered advice, offers GPT chat integration, and includes various utility features.

## 🎥 Video Downloader

### Supported Platforms
- TikTok
- Instagram
- YouTube Shorts
- Facebook
- Twitter/X
- Vimeo
- Reddit

### How to Use
Simply send a video link from any supported platform, and the bot will:
1. Process your request
2. Download the video
3. Send it directly in the chat

**Note**: Maximum video size is 50MB due to Telegram restrictions

### Platform-Specific Features
- **YouTube Shorts**: Bot downloads and sends the video
- **YouTube Videos**: Bot replies with #youtube hashtag
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

## 🛠 Commands
- `/start` - Welcome message and bot info
- `/cat` - Random cat pictures from thecatapi.com
- `/blya` - Translates last message from English to Ukrainian keyboard layout
- `/errors` - Generate error analytics report (admin only)
- `/game` - Start word game [In Dev]
- `/endgame` - End current game 
- `/clearwords` - Clear game words
- `/hint` - Get game hint

## 🔧 Technical Features
- Comprehensive error analytics and reporting system
- User restriction system for inappropriate content
- Automatic chat logging with daily files per chat
- Interactive button interfaces with link keyboards
- Translation of messages written with wrong keyboard layout
- Specialized sticker responses for errors and specific triggers

## 📦 Requirements
- Python 3.7+
- Telegram Bot Token
- OpenAI API Key
- Required packages:
  ```
  python-telegram-bot
  openai
  yt-dlp
  pyshorteners
  nest_asyncio
  pytz
  imgkit
  requests
  schedule
  APScheduler
  ```

## 📝 Setup
1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Create `.env` file with your API keys:
   ```
   TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   ```
3. Run the bot:
   ```bash
   python main.py
   ```

## ⚠️ Limitations
- 50MB maximum video size for Telegram uploads
- Rate limits for GPT API calls
- Some platforms may have additional restrictions
- Bot needs appropriate permissions in group chats

For issues or suggestions, please contact @vo1dee
