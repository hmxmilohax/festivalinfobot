
# Festival Info Bot

Festival Info is a Discord bot that tracks and reports new songs in Fortnite Festival. The bot checks every 15 minutes for new tracks and can also provide information about daily tracks and perform search queries for specific songs.

## Features

- **Real-Time Song Tracking:** The bot checks Fortnite Festival every 7 minutes and reports new songs to specified Discord channels.
- **Track Tracking:** The bot can show differences between track metadata edits.
- **Chart Comparing:** The bot can compare charts across two different versions of the same track.
- **Daily Tracks Report:** The bot can generate a list of daily tracks and display them in Discord.
- **Search Functionality:** The bot allows users to search for songs by title or artist.
- **Path Generating:** The bot can generate Overdrive paths to any songs using [CHOpt](https://github.com/GenericMadScientist/CHOpt).
- **Leaderboard:** The bot can show the leaderboard of any song and instrument.

## Setup

### Requirements

- Python 3.8+
- `discord.py` library
- `requests` library
- `mido` library
- `matplotlib` library

### Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/hmxmilohax/festivalinfobot.git
    cd festivalinfobot
    ```

2. Install the required Python packages:

    ```bash
    pip install requests discord.py mido matplotlib
    ```

3. Duplicate `config_default.ini` to `config.ini` file in the root directory of the project with the following content:

    ```ini
    ;copy this file to config.ini and fill out options
    [discord]
    # your bot token, duplicate this file to config.ini and add it there
    token = YOUR_DISCORD_BOT_TOKEN_HERE
    # the command prefix the bot will use
    prefix = !
    # the channel ids the bot is allowed to be triggered by a command in
    command_channel_ids = 123456789012345678, 234567890123456789
    # change this to true if you want the bot to be triggered only in the channels above
    use_command_channels = false

    [bot]
    # change this to false if you don't want decryption
    decryption = true
    # change this to false if you don't want the bot to check for new songs
    check_for_new_songs = true
    # interval (minutes) which the bot checks for new songs 
    # (requires check_for_new_songs)
    check_new_songs_interval = 7
    # change this to false if you don't want chart comparing 
    # (requires decryption and check_for_new_songs)
    chart_comparing = true
    # change this to false if you don't want pathing 
    # (requires decryption)
    pathing = true
    ```

   - Replace `YOUR_DISCORD_BOT_TOKEN` with your actual Discord bot token.
   - Follow the comments to customize the configuration more

4. Run the bot:

    ```bash
    python festivalinfobot.py
    ```

## Commands

- `!count` - Show the total number of available tracks in Fortnite Festival.
- `!daily` - Display the tracks currently in daily rotation.
- `!leaderboard [shortname] [instrument] [rank/username]` - View the leaderboard of a specific song, and leaderboard entries.
- `!path` - Generate a path for a given song and instrument.
- `!search [query]` - Search for a track by name or artist.
- `!shop` - Browse through the tracks currently available in the shop.
- `!tracklist` - Browse through the full list of available tracks.

## License

This project is licensed under the MIT License. 

## Contributing

If you want to contribute to this project, feel free to fork the repository and submit a pull request.

## Issues

If you encounter any issues, please open an issue on the GitHub repository.

# Dependencies

This bot is currently only targetted to run for windows as that is my personal environment.

To be able to fetch and generate paths you will need two things:

[CHOpt](https://github.com/GenericMadScientist/CHOpt) CLI binary (CHOpt.exe) in the bot folder.

fnf-midcrypt.py in the bot folder to decrypt midi files. This is not provided for you.

The bot is unable to decrypt festival midis by itself.
