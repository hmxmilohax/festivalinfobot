
# Festival Tracker

Festival Tracker is a Discord Bot that tracks when new Jam Tracks are added in Fortnite Festival every 7 minutes, among other features.

## Features

- **Song Tracking:** Checking Fortnite's API every 7 minutes and can show you all the details about each track.
- **Track Tracking:** Showing differences between track metadata edits.
- **Chart Comparing:** Comparing MIDI charts across two different versions of the same track.
- **Weekly Rotation:** Displaying a list of the weekly rotation.
- **Searching:** Search for songs by title or artist, and advanced search.
- **Path Generating:** Generating Paths ("Star-Power Optimisations") for any songs on-demand to rank higher in leaderboards with [CHOpt](https://github.com/GenericMadScientist/CHOpt).
- **Leaderboard:** View the leaderboard of any track and instrument.
- **Graphing:** Visually observe the ammount of notes in a song, or the notes per second as a song progresses.
- **Subscriptions:** Create subscriptions to channels or subscribe yourself to receive Jam Track Events (e.g. when a Jam Track is added to the API.)

## Setup

### Requirements

- Python 3.8+
- `discord.py` library
- `requests` library
- `mido` library, for analising MIDI files
- `matplotlib` library, for displaying graphs
- `pandas` library, for data analisis
- `aiosqlite` library, for managing subscriptions efficiently

### Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/hmxmilohax/festivalinfobot.git
    cd festivalinfobot
    ```

2. Install the required Python packages:

    ```bash
    pip install requests discord.py mido matplotlib pandas aiosqlite
    ```

3. Duplicate `config_default.ini` to `config.ini` file in the root directory of the project:
   - Replace `YOUR_DISCORD_BOT_TOKEN` with your actual Discord bot token.
   - Follow the comments to customize the configuration more

4. Run the bot:
    ```bash
    python festivalinfobot.py
    ```

    To view `discord.py`'s DEBUG level logs, you may append `-discord-debug` to your arguments.

## Commands

- Run `/help` to view a list of all available commands.
- Run `/stats` to view insights of the instance.
- `/admin` commands may only be run in the following conditions:

    User (who invokes the slash-command) must have been granted Administrator permission in the channel where the interaction (slash-command) is completed.

    When adding a subscription to a channel, the bot may require to possess the following permissions in the destination channel: <br>
      i. **View Channel** <br>
      ii. **Send Messages** <br>

## License

This project is licensed under the MIT License. For more information, view [LICENSE](./LICENSE)

## Contributing

If you want to contribute to this project, feel free to fork the repository and submit a Pull Request.

## Issues

If you encounter any issues, please open an issue on the GitHub repository. Otherwise, you may create a suggestion (`/suggestion`).

# Dependencies

This is currently only targetted to run for Windows as that is the environment it is developed and tested in.

To be able to fetch and generate paths you will need two things:

- [CHOpt](https://github.com/GenericMadScientist/CHOpt) CLI binary (CHOpt.exe) in the bot folder.

    For newer CHOpt versions, Qt6 dlls may be required to be copied as well. These files are present in the .gitignore.

Aditionally, the bot is unable to decrypt Festival MIDIs without the correct key.
