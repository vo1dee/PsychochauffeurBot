# PsychoChauffeurBot

PsychoChauffeur is a Telegram bot that enhances chat experience by providing link modification, GPT integration, weather updates, and various utility functions. The bot is designed to be simple to use and efficient in handling various chat-related tasks.

## Core Features

- **Link Modification**
  - Automatically modifies links from TikTok, Twitter, and Instagram
  - Removes original message and reposts with modified links
  - Preserves message context and user attribution
  - Special handling for AliExpress links (responds with a sticker)

- **GPT Integration**
  - Responds to direct mentions or private messages
  - Processes queries and provides AI-generated responses
  - Supports both command-based (`/gpt`) and mention-based interactions

- **Utility Commands**
  - `/weather <city>`: Current weather information with emojis
  - `/flares`: Daily screenshots of specified webpage (automated at 1 AM Kyiv time)
  - `/analyze`: Analyzes today's chat messages
  - `/cat`: Sends random cat pictures

- **Moderation Features**
  - Monitors messages for specific trigger words
  - Automatic user restriction for violating content
  - Sticker-based moderation triggers

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/vo1dee/psychochauffeurbot.git
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   Create a `.env` file with:
   ```
   TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   OPENWEATHER_API_KEY=your_openweather_api_key
   ```

4. Set up logging directory:

   ```bash
   sudo mkdir -p /var/log/psychochauffeurbot
   sudo chown your_user:your_group /var/log/psychochauffeurbot
   ```

5. Run the bot:

   ```bash
   python bot.py
   ```

## Requirements

- Python 3.10+
- Required packages:
  - python-telegram-bot==20.3
  - openai==1.52.2
  - imgkit==1.2.3
  - pytz==2023.3
  - Additional dependencies in requirements.txt

## File Structure

```
├── bot.py              # Main bot logic
├── const.py            # Constants and configurations
├── utils.py            # Utility functions
├── modules/
│   ├── gpt.py         # GPT integration
│   ├── weather.py     # Weather functionality
│   ├── file_manager.py # Logging and file operations
│   └── user_management.py # User moderation
└── requirements.txt
```

## Usage

1. **Link Modification**
   - Simply send a supported link in the chat
   - Bot will automatically modify and repost

2. **GPT Queries**
   - Mention bot: `@YourBot what is Python?`
   - Or use command: `/gpt explain async programming`

3. **Weather Updates**
   - Command: `/weather London`
   - Displays temperature, conditions, and relevant emojis

4. **Daily Screenshots**
   - Manual: `/flares`
   - Automatic: Daily at 2 AM Kyiv time

## Contributing

Feel free to submit issues and pull requests for new features or improvements.

## License

This project is licensed under the MIT License.
