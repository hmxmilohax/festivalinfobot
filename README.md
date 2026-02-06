
# [Festival Tracker]((https://festivaltracker.org))

Festival Tracker is a Discord Bot that tracks when new Jam Tracks are added in Fortnite Festival every minute, among other features.

Follow Us: [X (Twitter)](https://x.festivaltracker.org/)

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

- Python (latest)
- `discord.py`
- `requests`
- `mido`
- `matplotlib`
- `pandas`
- `aiosqlite`
- `pycryptodome`
- `pydub`
- `xmltodict`
- `numpy`

OR in `requirements.txt` file

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

### Dependencies

Festival Tracker is intended to run primarily on Windows, but it can run on Linux/Docker.

- To run in Docker, use `docker-compose up -d --build`

You can create a virtual environment to run the bot in, but it is not required.

To be able to fetch and generate paths you will need two things:

- [CHOpt](https://github.com/GenericMadScientist/CHOpt) CLI binary in the `bot/data/Binaries/` folder. Follow instructions there.

    For newer CHOpt versions, Qt6 .dlls may be required to be copied as well. These files are also present in the .gitignore, so you won't have to worry about committing these.

- FFmpeg and FFprobe (binaries) in the `bot/data/Binaries/` folder. Follow instructions there.

Aditionally, the bot is unable to decrypt Festival MIDIs without the correct key. You **WILL** experience a LOT of errors if the key is not provided.

## Commands

- Run `/help` to view a list of all available commands.

## License

This project is licensed under the MIT License. For more information, view [LICENSE](./LICENSE)

## Contributing

If you want to contribute to this project, feel free to fork the repository and submit a Pull Request.

## Issues

If you encounter any issues, please open an issue on the GitHub repository. Otherwise, you can send us feedback (`/feedback`).