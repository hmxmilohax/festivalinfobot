
# Festival Info Bot

Festival Info is a Discord bot that tracks and reports new songs in Fortnite Festival. The bot checks every 15 minutes for new tracks and can also provide information about daily tracks and perform search queries for specific songs.

## Features

- **Real-Time Song Tracking:** The bot checks Fortnite Festival every 15 minutes and reports new songs to specified Discord channels.
- **Daily Tracks Report:** The bot can generate a list of daily tracks and display them in Discord.
- **Search Functionality:** The bot allows users to search for songs by title or artist.

## Setup

### Requirements

- Python 3.8+
- `discord.py` library
- `requests` library

### Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/yourusername/festival-tracker.git
    cd festival-tracker
    ```

2. Install the required Python packages:

    ```bash
    pip install requests discord.py
    ```

3. Duplicate `config_default.ini` to `config.ini` file in the root directory of the project with the following content:

    ```ini
    [discord]
    token = YOUR_DISCORD_BOT_TOKEN_HERE
    channel_ids = 123456789012345678, 234567890123456789
    ```

   - Replace `YOUR_DISCORD_BOT_TOKEN` with your actual Discord bot token.
   - Replace the `channel_ids` with the IDs of the channels where you want the bot to report new songs.

4. Run the bot:

    ```bash
    python festivalinfobot.py
    ```

## Commands

- `!daily` - Displays the current daily rotation tracks.
- `!search <query>` - Searches for tracks by title or artist name.

## License

This project is licensed under the MIT License. 

## Contributing

If you want to contribute to this project, feel free to fork the repository and submit a pull request.

## Issues

If you encounter any issues, please open an issue on the GitHub repository.
