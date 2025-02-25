# Telegram PsychochauffeurBot Bot 🤖

A Telegram bot that downloads videos from various social media platforms and provides additional utility features.

## 🎥 Supported Platforms
- TikTok
- Instagram
- YouTube Shorts
- Facebook
- Twitter/X
- Vimeo
- Reddit

## 🚀 How to Use

### Video Downloads
Simply send a video link from any supported platform, and the bot will:
1. Process your request
2. Download the video
3. Send it directly in the chat

**Note**: Maximum video size is 50MB due to Telegram restrictions

### YouTube Links
- For YouTube Shorts: Bot downloads and sends the video
- For regular YouTube videos: Bot replies with #youtube hashtag

### AliExpress Links
- Automatically shortens long URLs
- Adds #aliexpress hashtag
- Sends a sticker

## 🛠 Commands
- `/start` - Welcome message and bot info
- `/gpt` - Chat with GPT
- `/weather` - Get weather updates
- `/cat` - Random cat pictures
- `/game` - Start word game [In Dev]
- `/endgame` - End current game 
- `/clearwords` - Clear game words
- `/hint` - Get game hint

## 🔧 Technical Requirements
- Python 3.7+
- Telegram Bot Token
- Required packages:
  ```
  python-telegram-bot
  yt-dlp
  pyshorteners
  nest_asyncio
  pytz
  ```

## 📝 Setup
1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Create `.env` file with your bot token:
   ```
   TOKEN=your_telegram_bot_token
   ```
3. Run the bot:
   ```bash
   python main.py
   ```

## ⚠️ Limitations
- 50MB maximum video size
- Some platforms may have additional restrictions
- Bot needs appropriate permissions in group chats

For issues or suggestions, please contact @vo1dee
