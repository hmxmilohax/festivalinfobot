
# Festival Tracker

Festival Tracker is a Discord Bot that tracks when new Jam Tracks are added in Fortnite Festival every minute, among other features.

Follow Us: [X (Twitter)](https://x.festivaltracker.org/) [Bluesky](https://bsky.festivaltracker.org/)

## Features

- **Song Tracking:** Checking Fortnite's API every minute and can show you all the details about each track.
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
- `discord.py`

    Run this command: `pip install -U git+https://github.com/Rapptz/discord.py.git@refs/pull/10166/merge`
- `requests`
- `mido`
- `matplotlib`
- `pandas`
- `aiosqlite`
- `pycryptodome`
- `pydub`
- `xmltodict`
- `matplotlib`
- `pandas`
- `numpy`

### Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/hmxmilohax/festivalinfobot.git
    cd festivalinfobot
    ```

2. Install the required Python packages from the requirements above

3. Duplicate `config_default.ini` to `config.ini` file in the root directory of the project:
   - Follow the comments to setup the bot

4. Run the bot:
    ```bash
    python festivalinfobot.py
    ```

    To view `discord.py`'s DEBUG level logs, you can add `-discord-debug` to your arguments.

## Commands

- Run `/help` to view a list of all available commands.
- Run `/stats` to view insights of the instance.

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

    For newer CHOpt versions, Qt6 .dlls may be required to be copied as well. These files are present in the .gitignore.

To be able to produce audio previews, any build of FFmpeg and FFprobe (executables) in the root is required.

Aditionally, the bot is unable to decrypt Festival MIDIs without the correct key.
