# Psychochauffeur Telegram Bot

This bot can modify and handle various types of messages, including TikTok, Twitter, and Instagram links, and forward YouTube links to a Discord channel. It also has features to restrict users and take screenshots of a specific webpage.

## Features

- **Link Modification:** Automatically modifies TikTok, Twitter, and Instagram links.
- **User Restriction:** Restricts users for a random period when specific keywords like "5€" are detected.
- **YouTube Link Forwarding:** Forwards YouTube links to a specified Discord channel.         #Doesn't work yet
- **Screenshot Functionality:** Takes and saves screenshots of a specified webpage at request /flares.

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/vo1dee/PsychochauffeurBot.git
cd Psychochauffeur
```

### 2. Create and Activate a Virtual Environment

#### Windows

```bash
python -m venv newenv
newenv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv newenv
source newenv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` File

Create a `.env` file in the root directory of the project with the following content:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DISCORD_WEBHOOK_URL=your_discord_webhook_url
OPENWEATHER_API_KEY=your_openweather_api_key
```

Replace `your_telegram_bot_token`, `your_openweather_api_key` and `your_discord_webhook_url` with your actual credentials.

### 5. Run the Bot

Run the bot script:

```bash
python bot.py
```

## Usage

- **Start Command:** `/start` - Sends a welcome message to the user.
- **Link Modification:** Send TikTok, Twitter, or Instagram links, and the bot will respond with modified links.
- **User Restriction:** If a user sends a message containing "5€", they will be restricted for a random period.
- **Screenshot Command:** `/flares` - Takes and sends a screenshot of a solar storms widget.
- **Weather Command:** `/weather <city>` - Sends a current weather report based on city provided


## TODO

- **Fix Discord Integration:** Currently, the bot may not correctly forward YouTube links to the Discord channel.
- **Improve Screenshot Handling:** Ensure that screenshots are taken at the appropriate time considering timezone differences. Done
- **Export banwords to separate file


## License

This project is licensed under the pohuy License.

