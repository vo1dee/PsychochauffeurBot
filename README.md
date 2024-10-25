# PsychoChauffeurBot

PsychoChauffeur is a Telegram bot designed to enhance chat functionality by modifying links, handling commands, and interacting with users through various tasks. The bot supports modifying domain-specific links, restricting users based on certain criteria, providing weather information, taking screenshots, generating responses with GPT, and managing conversation history.

## Features

- **Link Modification**: Automatically modifies TikTok, Twitter and Instagram links based on predefined rules.
- **Trigger Word Detection**: Restricts users if certain words or phrases appear in the message.
- **GPT Integration (/gpt)**: Allows users to interact with GPT for various conversational tasks.
- **Message Analysis (/analyze)**: Summarizes and analyzes recent chat messages.
- **Weather Information (/weather <city>)**: Provides current weather conditions for a specified city.
- **Screenshot Command (/flares)**: Takes a screenshot and processes it based on user input.
- **Conversation History**: Maintains the context of conversations for a better user experience.

## Prerequisites

- Python 3.7+
- A valid Telegram bot token
- Additional Python libraries: asyncio, logging, nest_asyncio, pytz, python-telegram-bot

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/vo1dee/psychochauffeurbot.git
   ```

2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables for the bot token:

   Set your Telegram bot token in a `.env`.

4. Adjust the file paths for logging:

   - General log: `/var/log/psychochauffeurbot/bot.log`
   - Chat log: `/var/log/psychochauffeurbot/bot_chat.log`

5. Run the bot:

   ```bash
   python bot.py
   ```

## File Structure

- `bot.py`: Main script for running the bot.
- `const.py`: Contains constants and configuration variables.
- `utils.py`: Utility functions used throughout the bot.
- `modules/`: Contains various modules for bot functionality.
- `requirements.txt`: Lists the dependencies required for the bot.

## Usage

- Start the bot using `/start` and follow the prompts.
- Use `/gpt` to interact with GPT functionality.
- Get the current weather with `/weather <city>`.
- Analyze recent chat messages using `/analyze`.
- Modify supported links in messages automatically.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch.
3. Make your changes.
4. Submit a pull request.

## License

This project is licensed under the MIT License.
