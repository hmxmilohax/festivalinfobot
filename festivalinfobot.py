import os
import requests
from discord.ext import commands, tasks
import discord
import time
import json
from configparser import ConfigParser
from difflib import get_close_matches
from datetime import datetime, timezone, timedelta
import string
from discord.ext.commands import DefaultHelpCommand
import subprocess
import mido
import asyncio
import hashlib
import string

def generate_session_hash(user_id, song_name):
    """Generate a unique hash based on the user ID and song name to isolate sessions."""
    return hashlib.md5(f"{user_id}_{song_name}".encode()).hexdigest()

# Load configuration from config.ini
config = ConfigParser()
config.read('config.ini')

start_time = time.time()

# Folder where local JSON files are stored
LOCAL_JSON_FOLDER = "json/"

# Read the Discord bot token and channel IDs from the config file
DISCORD_TOKEN = config.get('discord', 'token')
CHANNEL_IDS = config.get('discord', 'channel_ids', fallback="").split(',')
COMMAND_CHANNEL_IDS = config.get('discord', 'command_channel_ids', fallback="").split(',')
USE_COMMAND_CHANNELS = config.getboolean('discord', 'use_command_channels', fallback=False)
COMMAND_PREFIX = config.get('discord', 'prefix', fallback="!").split(',')

# Convert channel IDs to integers and filter out any empty strings
CHANNEL_IDS = [int(id.strip()) for id in CHANNEL_IDS if id.strip()]
COMMAND_CHANNEL_IDS = [int(id.strip()) for id in COMMAND_CHANNEL_IDS if id.strip()]

# Bot configuration properties
CHECK_FOR_SONGS_INTERVAL = config.getint('bot', 'check_new_songs_interval', fallback=7)
CHECK_FOR_NEW_SONGS = config.getboolean('bot', 'check_for_new_songs', fallback=True)
DECRYPTION_ALLOWED = config.getboolean('bot', 'decryption', fallback=True)
PATHING_ALLOWED = config.getboolean('bot', 'pathing', fallback=True)
CHART_COMPARING_ALLOWED = config.getboolean('bot', 'chart_comparing', fallback=True)

# APIs which the bot uses to source its information
API_URL = 'https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks'
MODES_SMART_URL = 'https://api.nitestats.com/v1/epic/modes-smart'
SHOP_API_URL = 'https://fortnite-api.com/v2/shop'
LEADERBOARD_DB_URL = 'https://raw.githubusercontent.com/FNLookup/festival-leaderboards/main/'

# Files used to track songs
SONGS_FILE = 'known_tracks.json'  # File to save known songs
SHORTNAME_FILE = 'known_songs.json'  # File to save known shortnames

# Folder the bot uses to save temporary files
TEMP_FOLDER = "out"

# Define instrument alias mapping for CHOpt.exe
INSTRUMENT_MAP = {
    # Pro Lead
    'plasticguitar': 'guitar',
    'prolead': 'guitar',
    'pl': 'guitar',
    'proguitar': 'guitar',
    'pg': 'guitar',
    # Pro Bass
    'plasticbass': 'bass',
    'probass': 'bass',
    'pb': 'bass',
    # Pro Drums
    'plasticdrums': 'drums',
    'prodrums': 'drums',
    'prodrum': 'drums',
    'pd': 'drums', 
    # Lead
    'guitar': 'guitar',
    'gr': 'guitar',
    'lead': 'guitar',
    'ld': 'guitar',
    'g': 'guitar',
    'l': 'guitar',
    # Bass
    'bass': 'bass',
    'ba': 'bass',
    'b': 'bass',
    # Drums
    'drums': 'drums',
    'ds': 'drums',
    'd': 'drums',
    # Vocals
    'vocals': 'vocals',
    'vl': 'vocals',
    'v': 'vocals',
}

# Set up Discord bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

# Load prefixes from a JSON file
def load_prefixes():
    if os.path.exists("prefixes.json"):
        with open("prefixes.json", "r") as f:
            return json.load(f)
    return {}

# Save prefixes to a JSON file
def save_prefixes(prefixes):
    with open("prefixes.json", "w") as f:
        json.dump(prefixes, f, indent=4)

# Define the command prefix function that checks for a custom prefix per guild
def get_prefix(bot, message):
    prefixes = load_prefixes()
    guild_id = str(message.guild.id) if message.guild else None
    return prefixes.get(guild_id, COMMAND_PREFIX[0])  # Default to the global prefix if not found

class CustomHelpCommand(DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = 'Available Commands'
        self.command_attrs['help'] = 'Shows this help message'

    async def send_bot_help(self, mapping):
        ctx = self.context
        prefix = self.context.prefix  # Get the actual prefix being used in this context
        embed = discord.Embed(
            title="Festival Tracker Help",
            description=f"A simple and powerful bot to check Fortnite Festival song data. [Source code](https://github.com/hmxmilohax/festivalinfobot)\nUse `{prefix}help <command>` to get more information on a specific command.",
            color=0x8927A1
        )

        for cog, commands in mapping.items():
            if cog:
                name = cog.qualified_name
                filtered = await self.filter_commands(commands, sort=True)
                if filtered:
                    value = '\n'.join([f"`{prefix}{cmd.name}`: {cmd.short_doc}" for cmd in filtered])
                    embed.add_field(name=name, value=value, inline=False)
            else:
                filtered = await self.filter_commands(commands, sort=True)
                if filtered:
                    value = '\n'.join([f"`{prefix}{cmd.name}`: {cmd.short_doc}" for cmd in filtered])
                    embed.add_field(name=self.no_category, value=value, inline=False)

        channel = self.get_destination()
        await send_auto_publish_message(channel, embed)

    async def send_command_help(self, command):
        prefix = self.context.prefix
        embed = discord.Embed(
            title=f"Help with `{prefix}{command.name}`",
            description=command.help or "No description provided.",
            color=0x8927A1
        )

        # Properly format the usage with the command signature
        usage = f"`{prefix}{command.qualified_name} {command.signature}`" if command.signature else f"`{prefix}{command.qualified_name}`"
        embed.add_field(name="Usage", value=usage, inline=False)

        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(command.aliases), inline=False)

        channel = self.get_destination()
        await send_auto_publish_message(channel, embed)


bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=CustomHelpCommand()
)


class PaginatorView(discord.ui.View):
    def __init__(self, embeds, user_id):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.user_id = user_id
        self.current_page = 0
        self.total_pages = len(embeds)
        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        # "First" button
        self.add_item(FirstButton(style=discord.ButtonStyle.primary, label='First', user_id=self.user_id))
        
        # "Previous" button
        if self.current_page > 0:
            self.add_item(PreviousButton(style=discord.ButtonStyle.primary, label='Previous', user_id=self.user_id))
        else:
            self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, label='Previous', disabled=True, user_id=self.user_id))

        # "Page#" button
        self.add_item(PageNumberButton(label=f"Page {self.current_page + 1}/{self.total_pages}", user_id=self.user_id))

        # "Next" button
        if self.current_page < self.total_pages - 1:
            self.add_item(NextButton(style=discord.ButtonStyle.primary, label='Next', user_id=self.user_id))
        else:
            self.add_item(NextButton(style=discord.ButtonStyle.secondary, label='Next', disabled=True, user_id=self.user_id))
        
        # "Last" button
        self.add_item(LastButton(style=discord.ButtonStyle.primary, label='Last', user_id=self.user_id))

    def get_embed(self):
        return self.embeds[self.current_page]

    def update_buttons(self):
        self.add_buttons()

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            print("Message was not found when trying to edit after timeout.")
        except Exception as e:
            print(f"An error occurred during on_timeout: {e}")

class FirstButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page = 0
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class PreviousButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page -= 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class PageNumberButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

class NextButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page += 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class LastButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page = view.total_pages - 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

async def send_auto_publish_message(channel, embed):
    try:
        message = await channel.send(embed=embed)
        # Check if the channel is a TextChannel and if it's a news channel
        if isinstance(channel, discord.TextChannel) and channel.is_news():
            # Auto-publish the message
            await message.publish()
            print(f"Published message in announcement channel: {channel.name}")
    except Exception as e:
        print(f"Error sending or publishing message: {e}")

def is_running_in_command_channel(channel_id):
    if USE_COMMAND_CHANNELS:
        return channel_id in COMMAND_CHANNEL_IDS
    else:
        return True

# Function to map instrument aliases to user-friendly names
# Remember to update this if you change INSTRUMENT_MAP
def get_instrument_from_query(instrument):
    instrument = instrument.lower()
    if instrument in ['plasticguitar', 'prolead', 'pl', 'proguitar', 'pg']:
        return ('Pro Lead', 'Solo_PeripheralGuitar')
    elif instrument in ['plasticbass', 'probass', 'pb']:
        return ('Pro Bass', 'Solo_PeripheralBass')
    elif instrument in ['plasticdrums', 'prodrums', 'prodrum', 'pd']:
        return ('Pro Drums', 'Solo_PeripheralDrum')
    elif instrument in ['guitar', 'gr', 'lead', 'ld', 'g', 'l']:
        return ('Lead', 'Solo_Guitar')
    elif instrument in ['bass', 'ba', 'b']:
        return ('Bass', 'Solo_Bass')
    elif instrument in ['drums', 'ds', 'd']:
        return ('Drums', 'Solo_Drums')
    elif instrument in ['vocals', 'vl', 'v']:
        return ('Vocals', 'Solo_Vocals')
    return (instrument.capitalize(), None)  # Fallback for unknown instruments

def fetch_leaderboard_of_track(shortname, instrument):
    season_number_request = requests.get(f'{LEADERBOARD_DB_URL}meta.json')
    current_season_number = season_number_request.json()['season']
    song_url = f'{LEADERBOARD_DB_URL}leaderboards/season{current_season_number}/{shortname}/'

    fetched_entries = []
    fetched_pages = 0
    while (fetched_pages < 5):
        json_url = f'{song_url}{instrument}_{fetched_pages}.json'
        try:
            response = requests.get(json_url)
            response.raise_for_status()
            data = response.json()
            fetched_entries.extend(data['entries'])
            fetched_pages += 1
        except Exception as e: # No more entries, the leaderboard isn't full yet
            print(f'There aren\'t enough entries to fetch: {e}')
            return fetched_entries
    else: # 5 pages have been fetched
        return fetched_entries

def remove_punctuation(text):
    return text.translate(str.maketrans('', '', string.punctuation.replace('_', '')))

def fuzzy_search_tracks(tracks, search_term):
    # Remove punctuation from the search term
    search_term = remove_punctuation(search_term.lower())  # Case-insensitive search

    # Special case for 'i'
    if search_term == 'i':
        exact_matches = [track for track in tracks.values() if track['track']['tt'].lower() == 'i']
        if exact_matches:
            return exact_matches

    exact_matches = []
    fuzzy_matches = []

    # Prioritize shortname searching
    exact_matches.extend([track for track in tracks.values() if track['track']['sn'].lower() == search_term])
    
    for track in tracks.values():
        title = remove_punctuation(track['track']['tt'].lower())
        artist = remove_punctuation(track['track']['an'].lower())
        
        # Check for exact matches first
        if search_term in title or search_term in artist:
            exact_matches.append(track)
        # Use fuzzy matching for close but not exact matches
        elif any(get_close_matches(search_term, [title, artist], n=1, cutoff=0.7)):
            fuzzy_matches.append(track)
    
    # Prioritize exact matches over fuzzy matches
    result = exact_matches if exact_matches else fuzzy_matches
    result_unique = []
    for track in result:
        # Check for duplicates
        if track not in result_unique: result_unique.append(track) 
    return result_unique

def set_fixed_size(string:str, intended_length: int = 30, right_to_left = False):
    if len(string) > intended_length:
        return string[:intended_length - 4] + '... '
    else:
        if right_to_left:
            return (' ' * (intended_length - len(string))) + string
        return string + (' ' * (intended_length - len(string)))
    
def format_stars(stars:int = 6):
    if stars > 5:
        stars = 5
        return '✪' * stars
    else:
        return '' + ('★' * stars) + ('☆' * (5-stars))

def generate_leaderboard_entry_embeds(entries, title, chunk_size=5):
    embeds = []

    for i in range(0, len(entries), chunk_size):
        embed = discord.Embed(title=title, color=0x8927A1)
        chunk = entries[i:i + chunk_size]
        field_text = '```'
        for entry in chunk:
            try:
                field_text += set_fixed_size(f"#{entry['rank']}", 5)
                field_text += set_fixed_size(entry['userName'] if entry['userName'] else '[Unknown]', 18)
                field_text += set_fixed_size(['E', 'M', 'H', 'X'][entry['best_run']['difficulty']], 2, right_to_left=True)
                field_text += set_fixed_size(f"{entry['best_run']['accuracy']}%", 5, right_to_left=True)
                field_text += set_fixed_size("FC" if entry['best_run']['fullcombo'] else "", 3, right_to_left=True)
                field_text += set_fixed_size(format_stars(entry['best_run']['stars']), 7, right_to_left=True)
                field_text += set_fixed_size(f"{entry['best_run']['score']}", 8, right_to_left=True)
            except Exception as e:
                pass
            field_text += '\n'
        field_text += '```'

        embed.add_field(name="", value=field_text, inline=False)
        embeds.append(embed)

    return embeds

def generate_leaderboard_embed(track_data, entry_data, instrument, is_new=False):
    track = track_data['track']
    title = track['tt']
    embed = discord.Embed(title="", description=f"**{title}** - *{track['an']}*", color=0x8927A1)
    
    field_text = '```'
    field_text += set_fixed_size('[' + ['Easy', 'Medium', 'Hard', 'Expert'][entry_data['best_run']['difficulty']] + ']', 18)
    field_text += set_fixed_size(f"{entry_data['best_run']['accuracy']}%", 7, right_to_left=True)
    field_text += set_fixed_size("FC" if entry_data['best_run']['fullcombo'] else "", 3, right_to_left=True)
    field_text += set_fixed_size(format_stars(entry_data['best_run']['stars']), 7, right_to_left=True)
    field_text += set_fixed_size(f"{entry_data['best_run']['score']}", 8, right_to_left=True)
    field_text += '```'

    # Add various fields to the embed
    embed.add_field(name="Player", value=entry_data['userName'] if entry_data['userName'] else '[Unknown]', inline=True)
    embed.add_field(name="Rank", value=f"#{entry_data['rank']}", inline=True)
    embed.add_field(name="Instrument", value=instrument, inline=True)
    embed.add_field(name="Best Run", value=field_text, inline=False)

    embed.add_field(name="Sessions", value="\n", inline=False)

    for session in entry_data['sessions']:
        date = session['time']
        session_field_text = '```'

        is_solo = len(session['stats']['players']) == 1
        for player in session['stats']['players']:
            try:
                username = entry_data['userName'] if player['is_valid_entry'] else f"[Band Member] {['L', 'B', 'V', 'D', 'PL', 'PB'][player['instrument']]}"
                session_field_text += set_fixed_size(username if username else '[Unknown]', 18)
                session_field_text += set_fixed_size(['E', 'M', 'H', 'X'][player['difficulty']], 2, right_to_left=True)
                session_field_text += set_fixed_size(f"{player['accuracy']}%", 5, right_to_left=True)
                session_field_text += set_fixed_size("FC" if player['fullcombo'] else "", 3, right_to_left=True)
                session_field_text += set_fixed_size(format_stars(player['stars']), 7, right_to_left=True)
                session_field_text += set_fixed_size(f"{player['score']}", 8, right_to_left=True)
            except Exception as e:
                print(e)
            session_field_text += '\n'

        # Add Band Score to the embed
        if not is_solo:
            band = session['stats']['band']
            session_field_text += set_fixed_size('[Band Score]', 18)
            session_field_text += set_fixed_size(f"{band['accuracy']}%", 7, right_to_left=True)
            session_field_text += set_fixed_size("FC" if band['fullcombo'] else "", 3, right_to_left=True)
            session_field_text += set_fixed_size(format_stars(band['stars']), 7, right_to_left=True)
            session_field_text += set_fixed_size(f"{band['scores']['total']}", 8, right_to_left=True)
            session_field_text += '\n'

        session_field_text += '```'

        # Create a Discord timestamp
        embed.add_field(name=f"<t:{int(date)}:R>", value=session_field_text, inline=False)
    
    return embed

def fetch_available_jam_tracks():
    try:
        response = requests.get(API_URL)
        data = response.json()

        # Ensure that the data is a dictionary and filter tracks that have the "track" property
        if isinstance(data, dict):
            available_tracks = {}
            for k, v in data.items():
                if isinstance(v, dict) and 'track' in v:
                    # Remove trailing spaces from relevant fields
                    v['track']['an'] = v['track']['an'].strip()
                    v['track']['tt'] = v['track']['tt'].strip()
                    available_tracks[k] = v
            return available_tracks
        else:
            print('Unexpected data format')
            return None
    except Exception as e:
        print(f'Error fetching available jam tracks: {e}')
        return None
    
def fetch_jam_tracks_file():
    try:
        response = requests.get(API_URL)
        data = response.json()

        # Return a better formatted spark-tracks file
        if isinstance(data, dict):
            available_tracks = []
            for k, v in data.items():
                if isinstance(v, dict) and 'track' in v:
                    available_tracks.append(v)
            return available_tracks
        else:
            print(f'Unexpected data format: {data}')
            return None
    except Exception as e:
        print(f'Error fetching available jam tracks: {e}')
        return None

def fetch_daily_shortnames():
    try:
        response = requests.get(MODES_SMART_URL)
        data = response.json()

        channels = data.get('channels', {})
        client_events_data = channels.get('client-events', {})
        states = client_events_data.get('states', [])

        # Current date with timezone awareness
        current_time = datetime.now(timezone.utc)
        
        # Filter and sort the states by validFrom date
        valid_states = [state for state in states if datetime.fromisoformat(state['validFrom'].replace('Z', '+00:00')) <= current_time]
        valid_states.sort(key=lambda x: datetime.fromisoformat(x['validFrom'].replace('Z', '+00:00')), reverse=True)

        if not valid_states:
            print("No valid states found")
            return None

        # Get the activeEvents from the most recent valid state
        active_events = valid_states[0].get('activeEvents', [])

        daily_tracks = {}
        for event in active_events:
            event_type = event.get('eventType', '')
            active_since = event.get('activeSince', '')
            active_until = event.get('activeUntil', '')

            # Convert dates to timezone-aware datetime objects
            active_since_date = datetime.fromisoformat(active_since.replace('Z', '+00:00')) if active_since else None
            active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00')) if active_until else None

            if event_type.startswith('PilgrimSong.') and active_since_date and active_until_date:
                # Check if the current date falls within the active period
                if active_since_date <= current_time <= active_until_date:
                    shortname = event_type.replace('PilgrimSong.', '')
                    daily_tracks[shortname] = {
                        'activeSince': active_since,
                        'activeUntil': active_until
                    }

        return daily_tracks

    except Exception as e:
        print(f'Error fetching daily shortnames: {e}')
        return None

def generate_shop_tracks_embeds(tracks, title, chunk_size=5):
    embeds = []

    for i in range(0, len(tracks), chunk_size):
        embed = discord.Embed(title=title, color=0x8927A1)
        chunk = tracks[i:i + chunk_size]
        for track in chunk:
            # Convert duration from seconds to a more readable format
            duration_minutes = track['duration'] // 60
            duration_seconds = track['duration'] % 60
            duration_str = f"{duration_minutes}m {duration_seconds}s"

            # Convert inDate and outDate to Discord timestamp format
            in_date_ts = int(datetime.fromisoformat(track['inDate'].replace('Z', '+00:00')).timestamp()) if track.get('inDate') else None
            out_date_ts = int(datetime.fromisoformat(track['outDate'].replace('Z', '+00:00')).timestamp()) if track.get('outDate') else None
            
            in_date_display = f"<t:{in_date_ts}:R>" if in_date_ts else "Unknown"
            out_date_display = f"<t:{out_date_ts}:R>" if out_date_ts else "Unknown"

            # Inline difficulty as boxes
            difficulty = track['difficulty']
            difficulty_str = (
                f"Lead: {generate_difficulty_bar(difficulty.get('guitar', 0))} "
                f"Bass: {generate_difficulty_bar(difficulty.get('bass', 0))} "
                f"Drums: {generate_difficulty_bar(difficulty.get('drums', 0))} "
                f"Vocals: {generate_difficulty_bar(difficulty.get('vocals', 0))} "
            )
            # Construct the difficulty string using generate_difficulty_bar
            difficulty_str = (
                f"Lead:      {generate_difficulty_bar(difficulty.get('guitar', 0))} "
                f"Bass:      {generate_difficulty_bar(difficulty.get('bass', 0))} "
                f"Drums:     {generate_difficulty_bar(difficulty.get('drums', 0))}\n"
                f"Pro Lead:  {generate_difficulty_bar(difficulty.get('proguitar', 0))} "
                f"Pro Bass:  {generate_difficulty_bar(difficulty.get('probass', 0))} "
                f"Vocals:    {generate_difficulty_bar(difficulty.get('vocals', 0))}"
            )

            embed.add_field(
                name="",
                value=(
                    f"**\\• {track['title']}** - *{track['artist']}*\n"
                    f"`{difficulty_str}`"
                    f"\nAdded {in_date_display} - Leaving {out_date_display}\n"
                ),
                inline=False
            )
        embeds.append(embed)

    return embeds

def generate_tracks_embeds(tracks, title, daily_shortnames, chunk_size=5):
    embeds = []
    
    for i in range(0, len(tracks), chunk_size):
        embed = discord.Embed(title=title, color=0x8927A1)
        chunk = tracks[i:i + chunk_size]
        for track in chunk:
            shortname = track['track']['sn']
            active_until = daily_shortnames.get(shortname)

            if active_until:
                active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00'))
                human_readable_until = active_until_date.strftime("%B %d, %Y, %I:%M %p UTC")
                embed.add_field(name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}*\nLeaving {human_readable_until}", inline=False)
            else:
                embed.add_field(name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}*", inline=False)
        embeds.append(embed)
    
    return embeds

def generate_difficulty_bar(difficulty, max_blocks=7):
    # Map difficulty from a 0-6 range to a 1-7 range
    scaled_difficulty = difficulty + 1  # Convert 0-6 range to 1-7
    filled_blocks = '■' * scaled_difficulty
    empty_blocks = '□' * (max_blocks - scaled_difficulty)
    return filled_blocks + empty_blocks

def generate_modified_track_embed(old, new):
    old_track_data = old['track']
    new_track_data = new['track']
    title = f"Track Modified:\n{new_track_data['tt']}"
    embed = discord.Embed(title="", description=f"**{title}** - *{new_track_data['an']}*", color=0x8927A1)

    simple_comparisons = {
        'tt': 'Title',
        'an': 'Artist',
        'ab': 'Album',
        'sn': 'Shortname',
        'ry': 'Release Year',
        'jc': 'Join Code',
        'ti': 'Placeholder ID',
        'mm': 'Mode',
        'mk': 'Key',
        'su': 'Event ID',
        'isrc': 'ISRC Code',
        'ar': 'ESRB Rating',
        'au': 'Album Art',
        'siv': 'Vocals Instrument',
        'sib': 'Bass Instrument',
        'sid': 'Drums Instrument',
        'sig': 'Guitar Instrument',
        'mt': 'BPM',
        'ld': 'Lipsync',
        'mu': 'Chart URL',
        'ge': 'Genres',
        'gt': 'Gameplay Tags'
    }

    difficulty_comparisons = {
        'pb': 'Pro Bass',
        'pd': 'Pro Drums',
        'pg': 'Pro Lead',
        'vl': 'Vocals',
        'gr': 'Lead',
        'ds': 'Drums',
        'ba': 'Bass'
    }

    for value, name in simple_comparisons.items():
        if old_track_data.get(value, '[N/A]') != new_track_data.get(value, '[N/A]'):
            embed.add_field(name=f"{name} changed", value=f"```Old: \"{old_track_data.get(value, '[N/A]')}\"\nNew: \"{new_track_data.get(value, '[N/A]')}\"```", inline=False)

    for value, name in difficulty_comparisons.items():
        if old_track_data['in'].get(value, 0) != new_track_data['in'].get(value, 0):
            embed.add_field(name=f"{name} difficulty changed", value=f"```Old: \"{generate_difficulty_bar(old_track_data['in'].get(value, 0))}\"\nNew: \"{generate_difficulty_bar(new_track_data['in'].get(value, 0))}\"```", inline=False)

    # check for mismatched difficulty properties
    for key in new_track_data['in'].keys():
        if not (key in difficulty_comparisons.keys()):
            if key != '_type':
                embed.add_field(name=f"{key} (*Mismatched Difficulty*)", value=f"```Found: {generate_difficulty_bar(new_track_data['in'][key])}```", inline=False)

    return embed

def decrypt_dat_file(dat_url, output_file):
    try:
        # Download the .dat file
        response = requests.get(dat_url)
        if response.status_code == 200:
            dat_file_path = os.path.join(TEMP_FOLDER, output_file)
            with open(dat_file_path, "wb") as file:
                file.write(response.content)

            # Call fnf-midcrypt.py to decrypt the .dat file to .midi
            decrypted_midi_path = os.path.join(TEMP_FOLDER, output_file.replace('.dat', '.mid'))
            subprocess.run(['python', 'fnf-midcrypt.py', '-d', dat_file_path])

            return decrypted_midi_path
        else:
            print(f"Failed to download .dat file from {dat_url}")
            return None
    except Exception as e:
        print(f"Error decrypting .dat file: {e}")
        return None

async def process_chart_url_change(old_url, new_url, channel, track_name, song_title, artist_name):
    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)

    # Decrypt old .dat to .midi
    old_midi_file = decrypt_dat_file(old_url, "base.dat")

    # Decrypt new .dat to .midi
    new_midi_file = decrypt_dat_file(new_url, "base_update.dat")

    if old_midi_file and new_midi_file:
        print(f"Decrypted MIDI files ready for comparison:\nOld: {old_midi_file}\nNew: {new_midi_file}")

        # Run the comparison script with the two MIDI files
        comparison_command = ['python', 'compare_midi.py', old_midi_file, new_midi_file]

        try:
            result = subprocess.run(comparison_command, check=True, capture_output=True, text=True)
            print(result.stdout)

            print(f"Looking for images in folder: {TEMP_FOLDER}")

            # Loop through the result to find the changed tracks
            for line in result.stdout.splitlines():
                if "Differences found in track" in line:
                    track_name = line.split("'")[1]  # Extract track name from the line
                    image_filename = f"{track_name}_changes.png".replace(' ', '_')  # Replace spaces with underscores
                    image_path = os.path.join(TEMP_FOLDER, image_filename)
                    
                    print(f"Looking for file: {image_path}")

                    if os.path.exists(image_path):
                        if channel:
                            # Send the image inside an embed with track details to the Discord channel
                            embed = discord.Embed(
                                title=f"Track Modified: {song_title} - {artist_name}",
                                description=f"Changes detected in the track: {track_name}",
                                color=0x8927A1
                            )
                            # Attach the image and set it as the main image in the embed
                            file = discord.File(image_path, filename=image_filename)
                            embed.set_image(url=f"attachment://{image_filename}")  # Embed the image in the message
                            await channel.send(embed=embed, file=file)
                            print(f"Image sent: {image_filename}")
                        else:
                            print(f"Channel not found, but image generated: {image_filename}")
                    else:
                        print(f"Expected image {image_filename} not found in {TEMP_FOLDER}.")
            
            # Clear the out folder after processing
            clear_out_folder(TEMP_FOLDER)

        except subprocess.CalledProcessError as e:
            print(f"Error running comparison script: {e}")
    else:
        print("Failed to decrypt one or both .dat files.")

def generate_track_embed(track_data, is_new=False):
    track = track_data['track']
    title = f"New song found:\n{track['tt']}" if is_new else track['tt']
    placeholder_id = track.get('ti', 'sid_placeholder_00').split('_')[-1].zfill(2)  # Extract the placeholder ID
    embed = discord.Embed(title="", description=f"**{title}** - *{track['an']}*", color=0x8927A1)

    # Add various fields to the embed
    embed.add_field(name="\n", value="", inline=False)
    embed.add_field(name="Release Year", value=track.get('ry', 'Unknown'), inline=True)

    # Add Key and BPM to the embed
    key = track.get('mk', 'Unknown')  # Get the key
    mode = track.get('mm', 'Unknown')  # Get the mode

    # If mode is minor, append (Minor), else append (Major)
    if mode == 'Minor':
        key = f"{key} (Minor)"
    elif mode == 'Major':
        key = f"{key} (Major)"
    else:
        key = f"{key} ({mode})"

    embed.add_field(name="Key", value=key, inline=True)
    embed.add_field(name="BPM", value=str(track.get('mt', 'Unknown')), inline=True)


    embed.add_field(name="Album", value=track.get('ab', 'N/A'), inline=True)
    embed.add_field(name="Genre", value=", ".join(track.get('ge', ['N/A'])), inline=True)    

    duration = track.get('dn', 0)
    embed.add_field(name="Duration", value=f"{duration // 60}m {duration % 60}s", inline=True)
    embed.add_field(name="Shortname", value=track['sn'], inline=True)
    embed.add_field(name="Song ID", value=f"{placeholder_id}", inline=True)

    # Add Last Modified field if it exists and format it to be more human-readable
    if 'lastModified' in track_data:
        last_modified = datetime.fromisoformat(track_data['lastModified'].replace('Z', '+00:00'))
        human_readable_date = last_modified.strftime("%B %d, %Y")
        embed.add_field(name="Last Modified", value=human_readable_date, inline=True)
    
    # Add Song Rating
    rating = track.get('ar', 'N/A')
    if rating == 'T':
        rating_description = 'Mature'
    elif rating == 'E':
        rating_description = 'Everyone'
    else:
        rating_description = 'Unknown'
    
    embed.add_field(name="Rating", value=rating_description, inline=True)
    
    # Difficulty bars
    vocals_diff = track['in'].get('vl', 0)
    guitar_diff = track['in'].get('gr', 0)
    bass_diff = track['in'].get('ba', 0)
    drums_diff = track['in'].get('ds', 0)
    pro_vocals_diff = track['in'].get('pv', 0)
    pro_guitar_diff = track['in'].get('pg', 0)
    pro_bass_diff = track['in'].get('pb', 0)
    pro_drums_diff = track['in'].get('pd', 0)

    # Construct the vertical difficulty bars
    difficulties = (
        f"Lead:      {generate_difficulty_bar(guitar_diff)}\n"
        f"Bass:      {generate_difficulty_bar(bass_diff)}\n"
        f"Drums:     {generate_difficulty_bar(drums_diff)}\n"
        f"Vocals:    {generate_difficulty_bar(vocals_diff)}\n"
        f"Pro Lead:  {generate_difficulty_bar(pro_guitar_diff)}\n"
        f"Pro Bass:  {generate_difficulty_bar(pro_bass_diff)}\n"
        f"Pro Drums: {generate_difficulty_bar(pro_drums_diff)}"
    )

    # Add difficulties to embed
    embed.add_field(name="Difficulties", value=f"```{difficulties}```", inline=False)
    
    # Add the album art
    embed.set_thumbnail(url=track['au'])
    
    return embed

def save_known_songs_to_disk(songs, shortnames:bool = False):
    with open(SONGS_FILE if not shortnames else SHORTNAME_FILE, 'w') as file:
        json.dump(songs, file)

def load_known_songs_from_disk(shortnames:bool = False):
    path = SONGS_FILE if not shortnames else SHORTNAME_FILE
    if os.path.exists(path):
        with open(path, 'r') as file:
            return json.load(file)
    return list()

def fetch_shop_tracks():
    try:
        response = requests.get(SHOP_API_URL)
        data = response.json()

        # Check if 'data' and 'entries' keys exist in the response
        if 'data' in data and 'entries' in data['data']:
            entries = data['data']['entries']
            available_tracks = {}

            for entry in entries:
                in_date = entry.get('inDate')
                out_date = entry.get('outDate')
                
                if entry.get('tracks'):
                    for track in entry['tracks']:
                        dev_name = track.get("devName")
                        if dev_name and 'sid_placeholder' in track['id']:
                            if dev_name not in available_tracks:
                                available_tracks[dev_name] = {
                                    "id": track["id"],
                                    "devName": dev_name,
                                    "title": track.get("title", "Unknown Title").strip() if track.get("title") else "Unknown Title",
                                    "artist": track.get("artist", "Unknown Artist").strip() if track.get("artist") else "Unknown Artist",
                                    "releaseYear": track.get("releaseYear", "Unknown Year"),
                                    "duration": track.get("duration", 0),
                                    "difficulty": track.get("difficulty", {}),
                                    "inDate": in_date,  # Assign entry-level inDate
                                    "outDate": out_date  # Assign entry-level outDate
                                }

            if not available_tracks:
                print('No tracks found in the shop.')
                return None

            return available_tracks  # Return dictionary keyed by devName

    except Exception as e:
        print(f'Error fetching shop tracks: {e}')
        return None

@tasks.loop(minutes=CHECK_FOR_SONGS_INTERVAL)
async def check_for_new_songs():
    if not CHANNEL_IDS:
        print(f"No channel IDs provided; skipping the {CHECK_FOR_SONGS_INTERVAL}-minute probe.")
        return

    print("Checking for new songs...")

    # Run sparks_tracks.py alongside this script
    try:
        subprocess.Popen(["python", "sparks_tracks.py"])
        print("Running sparks_tracks.py")
    except Exception as e:
        print(f"Failed to run sparks_tracks.py: {e}")

    # Fetch current jam tracks
    tracks = fetch_jam_tracks_file()

    if not tracks:
        print('Could not fetch tracks.')
        return

    # Dynamically reload known tracks and shortnames from disk each time the task runs
    known_tracks = load_known_songs_from_disk()  # Reload known_tracks.json
    known_shortnames = load_known_songs_from_disk(shortnames=True)  # Reload known_songs.json

    # If known_songs.json doesn't exist, just save the current tracks and exit without sending any messages
    if not known_tracks:
        print("First run detected. Saving the current tracks as the initial known songs.")
        save_known_songs_to_disk(tracks)
        save_known_songs_to_disk([track['track']['sn'] for track in tracks], shortnames=True)
        return

    current_tracks_dict = {track['track']['sn']: track for track in tracks}
    known_tracks_dict = {track['track']['sn']: track for track in known_tracks}

    new_songs = []
    modified_songs = []

    for shortname, current_track in current_tracks_dict.items():
        if shortname not in known_tracks_dict:
            new_songs.append(current_track)
        else:
            known_track = known_tracks_dict[shortname]
            if current_track != known_track:
                modified_songs.append((known_track, current_track))

    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Channel with ID {channel_id} not found.")
            continue

        if new_songs:
            print(f"New songs detected!")
            for new_song in new_songs:
                embed = generate_track_embed(new_song, is_new=True)
                await send_auto_publish_message(channel, embed)
            save_known_songs_to_disk(tracks)
            save_known_songs_to_disk([track['track']['sn'] for track in tracks], shortnames=True)

        if modified_songs:
            print(f"Modified songs detected!")
            for old_song, new_song in modified_songs:
                old_url = old_song['track'].get('mu', '')
                new_url = new_song['track'].get('mu', '')
                track_name = new_song['track']['tt']  # Get track name for the embed
                artist_name = new_song['track']['an']  # Get track name for the embed

                if (old_url != new_url) and DECRYPTION_ALLOWED and CHART_COMPARING_ALLOWED:
                    print(f"Chart URL changed:")
                    print(f"Old: {old_url}")
                    print(f"New: {new_url}")

                    # Pass the track name to the process_chart_url_change function
                    await process_chart_url_change(old_url, new_url, channel, track_name, track_name, artist_name)

                embed = generate_modified_track_embed(old=old_song, new=new_song)
                await send_auto_publish_message(channel, embed)
            save_known_songs_to_disk(tracks)
            save_known_songs_to_disk([track['track']['sn'] for track in tracks], shortnames=True)

    print(f"Done checking for new songs:\nNew: {len(new_songs)}\nModified: {len(modified_songs)}")

def clear_out_folder(folder_path):
    try:
        # Check if the folder exists
        if os.path.exists(folder_path):
            # List all files in the folder
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    # Recursively delete subfolders and files (optional)
                    clear_out_folder(file_path)
            print(f"Cleared all files in the folder: {folder_path}")
        else:
            print(f"Folder {folder_path} does not exist.")
    except Exception as e:
        print(f"Error clearing folder {folder_path}: {e}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    # Set up the rich presence activity without an image
    activity = discord.Activity(
        type=discord.ActivityType.playing, 
        name=f"!help"
    )

    # Apply the activity
    await bot.change_presence(activity=activity, status=discord.Status.online)
    
    # Start the song check loop
    if CHECK_FOR_NEW_SONGS:
        check_for_new_songs.start()

@bot.command(name='search', help='Search for a track by name or artist.')
async def search(ctx, *, query: str = None):
    if not is_running_in_command_channel(ctx.channel.id):
        return
    
    if query is None:
        await ctx.send("Please provide a search term.")
        return
    
    # Check if the search matches "I'm A Cat"
    if query.lower() == "i'm a cat" or query.lower() == "im a cat" or query.lower() == "imacat":
        # Load imacat.json for special handling
        with open('imacat.json', 'r') as imacat_file:
            imacat_data = json.load(imacat_file)
        embed = generate_track_embed(imacat_data)  # Use the local data from imacat.json
        embed.add_field(name="Status", value="Removed from API. This song has never been officially obtainable.", inline=False)
        await ctx.send(embed=embed)
        return

    # Fetch the tracks from the jam API
    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send('Could not fetch tracks.')
        return

    # Fetch the daily shortnames data for later comparison
    daily_shortnames_data = fetch_daily_shortnames()

    # Perform fuzzy search on the fetched tracks
    matched_tracks = fuzzy_search_tracks(tracks, query)
    if not matched_tracks:
        await ctx.send('No tracks found matching your search.')
        return

    # Fetch the shop tracks for later comparison
    shop_tracks = fetch_shop_tracks()

    if len(matched_tracks) == 1:
        embed = generate_track_embed(matched_tracks[0])
        track_devname = matched_tracks[0]['track']['sn']

        # Check if the song is currently in the shop
        if shop_tracks and track_devname in shop_tracks:
            out_date = shop_tracks[track_devname].get('outDate')
            if out_date:
                out_date_ts = datetime.fromisoformat(out_date.replace('Z', '+00:00'))
                human_readable_out_date = out_date_ts.strftime("%B %d, %Y")
                embed.add_field(name="Shop", value=f"Currently in the shop until {human_readable_out_date}.", inline=False)
            else:
                embed.add_field(name="Shop", value="Currently in the shop!", inline=False)

        # Check if the song is currently in the daily rotation
        if daily_shortnames_data and track_devname in daily_shortnames_data:
            active_until = daily_shortnames_data[track_devname]['activeUntil']
            active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00'))
            human_readable_until = active_until_date.strftime("%B %d, %Y")
            embed.add_field(name="Daily Jam Track", value=f"Free in daily rotation until {human_readable_until}.", inline=False)

        await ctx.send(embed=embed)
    else:
        # More than one match, prompt user to choose
        options = [f"{i + 1}. **{track['track']['tt']}** by *{track['track']['an']}*" for i, track in enumerate(matched_tracks)]
        options_message = "\n".join(options)
        await ctx.send(f"I found multiple tracks matching your search. Please choose the correct one by typing the number:\n{options_message}")
        
        def check(m):
            return m.author == ctx.author

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            if not msg.content.isdigit() or not 1 <= int(msg.content) <= len(matched_tracks):
                await ctx.send("Search cancelled.")
                return

            chosen_index = int(msg.content) - 1
            chosen_track = matched_tracks[chosen_index]
            embed = generate_track_embed(chosen_track)
            track_devname = chosen_track['track']['sn']

            # Check if the song is currently in the shop
            if shop_tracks and track_devname in shop_tracks:
                out_date = shop_tracks[track_devname].get('outDate')
                if out_date:
                    out_date_ts = datetime.fromisoformat(out_date.replace('Z', '+00:00'))
                    human_readable_out_date = out_date_ts.strftime("%B %d, %Y")
                    embed.add_field(name="Shop", value=f"Currently in the shop until {human_readable_out_date}.", inline=False)
                else:
                    embed.add_field(name="Shop", value="Currently in the shop!", inline=False)

            # Check if the song is currently in the daily rotation
            if daily_shortnames_data and track_devname in daily_shortnames_data:
                active_until = daily_shortnames_data[track_devname]['activeUntil']
                active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00'))
                human_readable_until = active_until_date.strftime("%B %d, %Y")
                embed.add_field(name="Daily Jam Track", value=f"Free in daily rotation until {human_readable_until}.", inline=False)

            await ctx.send(embed=embed)
        except TimeoutError:
            await ctx.send("You didn't respond in time. Search cancelled.")

@bot.command(name='daily', help='Display the tracks currently in daily rotation.')
async def daily_tracks(ctx):
    if not is_running_in_command_channel(ctx.channel.id):
        return
    
    tracks = fetch_available_jam_tracks()
    daily_shortnames_data = fetch_daily_shortnames()

    if not tracks or not daily_shortnames_data:
        await ctx.send('Could not fetch tracks or daily shortnames.')
        return
    
    daily_tracks = []
    for track in tracks.values():
        shortname = track['track'].get('sn')

        if shortname in daily_shortnames_data:
            event_data = daily_shortnames_data[shortname]

            # Extract both activeSince and activeUntil from the event_data dictionary
            active_since_iso = event_data.get('activeSince', '')
            active_until_iso = event_data.get('activeUntil', '')

            # Convert to unix timestamps for Discord
            active_until_ts = int(datetime.fromisoformat(active_until_iso.replace('Z', '+00:00')).timestamp()) if active_until_iso else None
            active_since_ts = int(datetime.fromisoformat(active_since_iso.replace('Z', '+00:00')).timestamp()) if active_since_iso else None

            title = track['track'].get('tt')
            artist = track['track'].get('an')

            # Fetch difficulty data
            difficulty_data = track['track'].get('in', {})  # Assuming difficulties are stored under 'in'

            # Construct the difficulty string using generate_difficulty_bar
            difficulty_str = (
                f"Lead:      {generate_difficulty_bar(difficulty_data.get('gr', 0))} "
                f"Bass:      {generate_difficulty_bar(difficulty_data.get('ba', 0))} "
                f"Drums:     {generate_difficulty_bar(difficulty_data.get('ds', 0))}\n"
                f"Pro Lead:  {generate_difficulty_bar(difficulty_data.get('pg', 0))} "
                f"Pro Bass:  {generate_difficulty_bar(difficulty_data.get('pb', 0))} "
                f"Vocals:    {generate_difficulty_bar(difficulty_data.get('vl', 0))}"
            )


            daily_tracks.append({
                'track': track,
                'title': title,
                'artist': artist,
                'difficulty': difficulty_str,
                'activeSince': active_since_ts,
                'activeUntil': active_until_ts
            })

    # Sort the tracks first by 'Leaving' time (activeUntil), then alphabetically by title
    daily_tracks.sort(key=lambda x: (x['activeUntil'] or float('inf'), x['title'].lower()))

    if daily_tracks:
        embeds = []
        chunk_size = 10  # Limit the number of tracks per embed to 10 for readability
        
        for i in range(0, len(daily_tracks), chunk_size):
            embed = discord.Embed(title="Daily Rotation Tracks", color=0x8927A1)
            chunk = daily_tracks[i:i + chunk_size]
            for entry in chunk:
                track = entry['track']
                active_since_ts = entry['activeSince']
                active_until_ts = entry['activeUntil']
                title = entry['title']
                artist = entry['artist']
                difficulty = entry['difficulty']

                # Format timestamps in Discord format
                active_since_display = f"<t:{active_since_ts}:R>" if active_since_ts else "Unknown"
                active_until_display = f"<t:{active_until_ts}:R>" if active_until_ts else "Unknown"
                embed.add_field(
                    name="",
                    value=f"**\\• {title if title else 'Unknown Title'}** - *{artist if artist else 'Unknown Artist'}*\n"
                          f"`Added:` {active_since_display} - `Leaving:` {active_until_display}"
                          f"```{difficulty}```\n",
                    inline=False
                )
            embeds.append(embed)

        view = PaginatorView(embeds, ctx.author.id)
        view.message = await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send("No daily tracks found.")

@bot.command(name='count', help='Show the total number of available tracks in Fortnite Festival.')
async def count_tracks(ctx):
    if not is_running_in_command_channel(ctx.channel.id):
        return
    
    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send('Could not fetch tracks.')
        return
    
    total_tracks = len(tracks)
    embed = discord.Embed(
        title="Total Available Songs",
        description=f"There are currently **{total_tracks}** available songs available in Fortnite Festival.",
        color=0x8927A1
    )

    await ctx.send(embed=embed)

@bot.command(name='tracklist', help='Browse through the full list of available tracks.')
async def tracklist(ctx):
    if not is_running_in_command_channel(ctx.channel.id):
        return

    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send('Could not fetch tracks.')
        return

    # Use a dictionary to ensure only unique tracks are included
    unique_tracks = {}
    for track_id, track in tracks.items():
        track_sn = track['track']['sn']  # Using the shortname as a unique identifier
        if track_sn not in unique_tracks:
            unique_tracks[track_sn] = track

    # Convert the unique_tracks dictionary to a list and sort it alphabetically by track title
    track_list = sorted(unique_tracks.values(), key=lambda x: x['track']['tt'].lower())

    if not track_list:
        await ctx.send('No tracks available.')
        return

    # Calculate total tracks and update the title
    total_tracks = len(track_list)
    title = f"Available Tracks (Total: {total_tracks})"

    # Generate paginated embeds with 10 tracks per embed
    embeds = generate_tracks_embeds(track_list, title, daily_shortnames={}, chunk_size=10)
    
    # Initialize the paginator view
    view = PaginatorView(embeds, ctx.author.id)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

@bot.command(name='shop', help='Browse through the tracks currently available in the shop.')
async def shop_tracks(ctx):
    if not is_running_in_command_channel(ctx.channel.id):
        return

    tracks = fetch_shop_tracks()  # Data from shop API
    track_data = fetch_available_jam_tracks()  # Data from jam API

    if not tracks:
        await ctx.send('Could not fetch shop tracks.')
        return

    # Sort the tracks alphabetically by title
    tracks = list(tracks.values())
    tracks.sort(key=lambda x: x['title'].lower() if x.get('title') else 'Unknown')

    if not tracks:
        await ctx.send('No tracks available in the shop.')
        return

    # Calculate total tracks and update the title
    total_tracks = len(tracks)
    title = f"Shop Tracks (Total: {total_tracks})"

    # Generate paginated embeds with 7 tracks per embed
    embeds = []
    chunk_size = 7
    for i in range(0, len(tracks), chunk_size):
        embed = discord.Embed(title=title, color=0x8927A1)
        chunk = tracks[i:i + chunk_size]

        for shop_track in chunk:
            # Convert duration from seconds to a more readable format
            duration_minutes = shop_track['duration'] // 60
            duration_seconds = shop_track['duration'] % 60
            duration_str = f"{duration_minutes}m {duration_seconds}s"

            # Convert inDate and outDate to Discord timestamp format
            in_date_ts = int(datetime.fromisoformat(shop_track['inDate'].replace('Z', '+00:00')).timestamp()) if shop_track.get('inDate') else None
            out_date_ts = int(datetime.fromisoformat(shop_track['outDate'].replace('Z', '+00:00')).timestamp()) if shop_track.get('outDate') else None

            in_date_display = f"<t:{in_date_ts}:R>" if in_date_ts else "Unknown"
            out_date_display = f"<t:{out_date_ts}:R>" if out_date_ts else "Unknown"

            # Match the shop track by shortname ('sn') for better mapping
            shortname = shop_track.get('devName')  # Adjust this if your shortname is stored differently
            jam_track = next((track for track in track_data.values() if track['track'].get('sn') == shortname), None)
            
            if jam_track:
                title = jam_track['track'].get('tt', 'Unknown Title')
                artist = jam_track['track'].get('an', 'Unknown Artist')

                # Fetch difficulty data from jam track
                difficulty_data = jam_track['track'].get('in', {})  # Assuming difficulties are stored under 'in'

                # Construct the difficulty string using generate_difficulty_bar
                difficulty_str = (
                    f"Lead:      {generate_difficulty_bar(difficulty_data.get('gr', 0))} "
                    f"Bass:      {generate_difficulty_bar(difficulty_data.get('ba', 0))} "
                    f"Drums:     {generate_difficulty_bar(difficulty_data.get('ds', 0))}\n"
                    f"Pro Lead:  {generate_difficulty_bar(difficulty_data.get('pg', 0))} "
                    f"Pro Bass:  {generate_difficulty_bar(difficulty_data.get('pb', 0))} "
                    f"Vocals:    {generate_difficulty_bar(difficulty_data.get('vl', 0))}"
                )
            else:
                title = shop_track.get('title', 'Unknown Title')
                artist = shop_track.get('artist', 'Unknown Artist')
                difficulty_str = "No difficulty data available"

            embed.add_field(
                name="",
                value=(
                    f"**\\• {title}** - *{artist}*\n"
                    f"`Added:` {in_date_display} - `Leaving:` {out_date_display}\n"
                    f"```{difficulty_str}```"
                ),
                inline=False
            )

        embeds.append(embed)

    # Initialize the paginator view
    view = PaginatorView(embeds, ctx.author.id)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

@bot.command(name='leaderboard', 
             help="""View the leaderboard of a specific song, and specific leaderboard entries. Updated roughly every 12 hours.\nAccepts a shortname, instrument, and optionally, a rank, username or Epic account ID.
To type a search query, enclose it in quotes (`"`)

[instrument] must be one of the supported instruments:
  * `plasticguitar`, `prolead`, `pl`, `proguitar`, `pg`: Pro Lead
  * `plasticbass`, `probass`, `pb`: Pro Bass
  * `vocals`, `vl`, `v`: Vocals
  * `guitar`, `gr`, `lead`, `ld`, `g`, `l`: Lead
  * `bass`, `ba`, `b`: Bass
  * `drums`, `ds`, `d`:  Drums
If a rank or account isn't given, a list of entries will be shown instead.
Only the first 500 entries of every leaderboard are available.""", 
             brief="View the leaderboard of a specific song, and leaderboard entries.",
             aliases=['lb'],
             usage="[shortname] [instrument] [rank/username/accountid]")
async def leaderboard(ctx, shortname: str = None, instrument: str = None, rank_or_account = None):
    if not is_running_in_command_channel(ctx.channel.id):
        return

    if shortname is None:
        await ctx.send("Please provide a shortname.")
        return
    if instrument is None:
        await ctx.send("Please provide an instrument.")
        return
    
    # Fetch the tracks from the jam API
    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send('Could not fetch tracks.')
        return
    
    # Use fuzzy search on the tracks to find a match for the shortname
    matched_tracks = fuzzy_search_tracks(tracks, shortname)

    if not matched_tracks:
        await ctx.send('No tracks found matching your search.')
        return
    
    # Use the first matched track
    matched_track = matched_tracks[0]
    instrument_display_name, instrument_codename = get_instrument_from_query(instrument)
    if not instrument_codename:
        await ctx.send('Unknown instrument.')
        return

    leaderboard_entries = fetch_leaderboard_of_track(matched_track['track']['sn'], instrument_codename)

    if len(leaderboard_entries) > 0:
        if not rank_or_account:
            title = f"Leaderboard for\n**{matched_track['track']['tt']}** - *{matched_track['track']['an']}* ({instrument_display_name})"
            embeds = generate_leaderboard_entry_embeds(leaderboard_entries, title, chunk_size=10)
            view = PaginatorView(embeds, ctx.author.id)
            view.message = await ctx.send(embed=view.get_embed(), view=view)
        else:
            # Handle rank or account search
            try:
                rank = int(rank_or_account)
                entries = [entry for entry in leaderboard_entries if entry['rank'] == rank]
                if entries:
                    await ctx.send(embed=generate_leaderboard_embed(matched_track, entries[0], instrument_display_name))
                else:
                    await ctx.send('No entries found.')
            except ValueError:
                entries = [entry for entry in leaderboard_entries if entry['userName'] == rank_or_account or entry['teamId'] == rank_or_account]
                if entries:
                    await ctx.send(embed=generate_leaderboard_embed(matched_track, entries[0], instrument_display_name))
                else:
                    await ctx.send('Player not found in leaderboard.')
    else:
        await ctx.send('No entries in leaderboard.')

# Helper function to modify the MIDI file for Pro Lead and Pro Bass and Pro Drum
def modify_midi_file(midi_file: str, instrument: str) -> str:
    try:
        print(f"Loading MIDI file: {midi_file}")
        mid = mido.MidiFile(midi_file)
        track_names_to_delete = []
        track_names_to_rename = {}

        # Check for Pro Lead, Pro Bass, or Pro Drums
        if instrument in ['plasticguitar', 'prolead', 'pl', 'proguitar', 'pg']:
            track_names_to_delete.append('PART GUITAR')
            track_names_to_rename['PLASTIC GUITAR'] = 'PART GUITAR'
        elif instrument in ['plasticbass', 'probass', 'pb']:
            track_names_to_delete.append('PART BASS')
            track_names_to_rename['PLASTIC BASS'] = 'PART BASS'
        elif instrument in ['plasticdrums', 'prodrums', 'prodrum', 'pd']:
            track_names_to_delete.append('PART DRUMS')
            track_names_to_rename['PLASTIC DRUMS'] = 'PART DRUMS'

        # Logging track modification intent
        print(f"Track names to delete: {track_names_to_delete}")
        print(f"Track names to rename: {track_names_to_rename}")

        # Modify the tracks
        new_tracks = []
        for track in mid.tracks:
            modified_track = mido.MidiTrack()  # Create a new track object
            for msg in track:
                if msg.type == 'track_name':
                    print(f"Processing track: {msg.name}")
                    if msg.name in track_names_to_delete:
                        print(f"Deleting track: {msg.name}")
                        continue  # Skip tracks we want to delete
                    elif msg.name in track_names_to_rename:
                        print(f"Renaming track {msg.name} to {track_names_to_rename[msg.name]}")
                        msg.name = track_names_to_rename[msg.name]  # Rename the track
                modified_track.append(msg)  # Append the message to the new track
            new_tracks.append(modified_track)

        # Assign modified tracks back to the MIDI file
        mid.tracks = new_tracks

        # Save the modified MIDI to a new file
        translator = str.maketrans('', '', string.punctuation.replace('_', '').replace('.', ''))
        modified_midi_file = midi_file.translate(translator).replace('.mid', '_modified.mid').replace(' ', '_')
        print(f"Saving modified MIDI to: {modified_midi_file}")
        mid.save(modified_midi_file)
        print(f"Modified MIDI saved successfully.")
        return modified_midi_file

    except Exception as e:
        print(f"Error modifying MIDI for {instrument}: {e}")
        return None

# Function to call chopt.exe and capture its output
def run_chopt(midi_file: str, command_instrument: str, output_image: str, squeeze_percent: int = 20, instrument: str = None, difficulty: str = 'expert'):
    chopt_command = [
        'chopt.exe', 
        '-f', midi_file, 
        '--engine', 'fnf', 
        '--squeeze', str(squeeze_percent),
        '--early-whammy', '0',
        '--diff', difficulty
    ]

    # Only add --no-pro-drums flag if it's NOT Pro Drums
    if instrument not in ['plasticdrums', 'prodrums', 'prodrum', 'pd']:
        chopt_command.append('--no-pro-drums')

    chopt_command.extend([
        '-i', command_instrument, 
        '-o', output_image
    ])

    result = subprocess.run(chopt_command, text=True, capture_output=True)
    
    if result.returncode != 0:
        return None, result.stderr

    return result.stdout.strip(), None

# Modify the path generation function
if PATHING_ALLOWED and DECRYPTION_ALLOWED:
    @bot.command(
        name='path',
        help="""
        Generate a path using [CHOpt](https://github.com/GenericMadScientist/CHOpt) for a given song and instrument.
        To type a search query, enclose it in quotes (`"`)

        - `[instrument]` must be one of the supported instruments:
        * `plasticguitar`, `prolead`, `pl`, `proguitar`, `pg`: for Pro Lead/Guitar
        * `plasticbass`, `probass`, `pb`: for Pro Bass
        * `plasticdrums`, `prodrums`, `prodrum`, `pd`: for Pro Drums
        * `vocals`, `vl`, `v`: for regular vocal parts
        * `guitar`, `gr`, `lead`, `ld`, `g`, `l`: for regular guitar parts
        * `bass`, `ba`, `b`: for regular bass parts
        * `drums`, `ds`, `d`: for regular drum parts

        Optional arguments:
        * `squeeze_percent`: A value between 0-100 to customize squeeze percent (default: 20).
        * `difficulty`: One of `easy`, `medium`, `hard`, or `expert`.
        """,
        brief="Generate a path for a given song and instrument.",
        usage="[shortname] [instrument] [squeeze_percent] [difficulty]"
    )
    async def generate_path(ctx, songname: str, instrument: str = 'guitar', *args):
        try:
            user_id = ctx.author.id
            session_hash = generate_session_hash(user_id, songname)  # Generate session hash

            squeeze_percent = 20  # Default squeeze percent
            difficulty = 'expert'  # Default difficulty

            # Handle arguments for difficulty and squeeze_percent
            for arg in args:
                if arg.isdigit():  # If the argument is a number, assume it's the squeeze percent
                    squeeze_percent = int(arg)
                    if squeeze_percent < 0 or squeeze_percent > 100:
                        await ctx.send("Squeeze percent must be between 0 and 100.")
                        return
                elif arg.lower() in ['easy', 'medium', 'hard', 'expert']:  # If it's a valid difficulty
                    difficulty = arg.lower()
                else:
                    await ctx.send(f"Invalid argument: {arg}. Expected difficulty (easy, medium, hard, expert) or a squeeze percent (0-100).")
                    return

            # Map the provided instrument alias to the valid instrument for chopt
            instrument = instrument.lower()
            if instrument in INSTRUMENT_MAP:
                command_instrument = INSTRUMENT_MAP[instrument]
            else:
                await ctx.send(f"Unsupported instrument: {instrument}")
                return

            if songname.lower() == "i'm a cat" or songname.lower() == "im a cat" or songname.lower() == "imacat":
                # Load imacat.json for special handling
                with open('imacat.json', 'r') as imacat_file:
                    imacat_data = json.load(imacat_file)
                    song_data = imacat_data
            else:
                # Step 1: Fetch song data from the API
                tracks = fetch_available_jam_tracks()
                if not tracks:
                    await ctx.send('Could not fetch tracks.')
                    return

                # Perform fuzzy search to find the matching song
                matched_tracks = fuzzy_search_tracks(tracks, songname)
                if not matched_tracks:
                    await ctx.send(f"No tracks found for '{songname}'.")
                    return
                # Use the first matched track
                song_data = matched_tracks[0]

            song_url = song_data['track'].get('mu')
            album_art_url = song_data['track'].get('au')  # Fetch album art URL
            track_title = song_data['track'].get('tt')  # Get the actual track title
            artist_title = song_data['track'].get('an')  # Get the actual artist title
            display_instrument, instrument_codename = get_instrument_from_query(instrument)  # Get user-friendly instrument name

            # Step 2: Decrypt the .dat file into a .mid file
            dat_file = f"{session_hash}_{songname}.dat"
            midi_file = decrypt_dat_file(song_url, dat_file)
            if not midi_file:
                await ctx.send(f"Failed to decrypt the .dat file for '{songname}'.")
                return

            # Step 3: Modify the MIDI file if necessary (Pro parts)
            modified_midi_file = None
            if 'Peripheral' in instrument_codename:
                modified_midi_file = modify_midi_file(midi_file, instrument)
                if not modified_midi_file:
                    await ctx.send(f"Failed to modify MIDI for '{instrument}'.")
                    return
                midi_file = modified_midi_file  # Use the modified MIDI file for chopt

            # Validate difficulty
            difficulty = difficulty.lower()
            if difficulty not in ['easy', 'medium', 'hard', 'expert']:
                await ctx.send("Difficulty must be one of: easy, medium, hard, expert.")
                return

            # Ensure squeeze_percent is within 0-100
            if squeeze_percent < 0 or squeeze_percent > 100:
                await ctx.send("Squeeze percent must be between 0 and 100.")
                return

            # Step 4: Generate the path image using chopt.exe
            translator = str.maketrans('', '', string.punctuation.replace('_', '').replace('.', ''))
            clean_songname = songname.translate(translator)
            output_image = f"{session_hash}_{clean_songname.strip()}_path.png".replace(' ', '_')
            chopt_output, chopt_error = run_chopt(midi_file, command_instrument, output_image, squeeze_percent, instrument, difficulty)

            if chopt_error:
                await ctx.send(f"An error occurred while running chopt: {chopt_error}")
                return

            # Step 5: Filter out "Optimising, please wait..." message from chopt output
            filtered_output = '\n'.join([line for line in chopt_output.splitlines() if "Optimising, please wait..." not in line])

            # Step 6: Send the generated image and filtered chopt output to the Discord channel
            if os.path.exists(output_image):
                # Attach the image
                file = discord.File(output_image, filename=output_image)
                # Embed the image in the message
                embed = discord.Embed(title=f"", color=0x8927A1)
                embed.add_field(name="", value=f"**{track_title}** - *{artist_title}*", inline=False)
                embed.add_field(name="", value=f"`Instrument:` **{display_instrument}**", inline=False)
                embed.add_field(name="", value=f"`Difficulty:` **{difficulty.capitalize()}**", inline=False)
                embed.add_field(name="", value=f"`Squeeze Percent:` **{squeeze_percent}%**", inline=False)
                embed.add_field(name="", value=f"```{filtered_output}```", inline=True)
                embed.set_image(url=f"attachment://{output_image}")
                
                # Set the album art as the thumbnail
                embed.set_thumbnail(url=album_art_url)

                # Send the message with the embed and the file
                await ctx.send(embed=embed, file=file)

                # Clean up the image file after sending
                os.remove(output_image)
            else:
                await ctx.send(f"Failed to generate the path image for '{track_title}'.")

            # Step 7: Clean up the generated MIDI and .dat files
            os.remove(midi_file)  # Clean up the original or modified MIDI file
            os.remove(os.path.join(TEMP_FOLDER, dat_file))    # Clean up the .dat file

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

# Function to calculate bot uptime
def get_uptime():
    current_time = time.time()
    uptime_seconds = int(current_time - start_time)
    uptime = str(timedelta(seconds=uptime_seconds))
    return uptime

# Function to get the current local commit hash
def get_local_commit_hash():
    try:
        # Run git command to get the latest commit hash
        commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode('utf-8')
        return commit_hash
    except Exception as e:
        print(f"Error getting local commit hash: {e}")
        return "Unknown"

# Function to fetch the latest commit hash from the GitHub repository
def fetch_latest_github_commit_hash():
    repo_url = "https://api.github.com/repos/hmxmilohax/festivalinfobot/commits"
    response = requests.get(repo_url)
    if response.status_code == 200:
        latest_commit = response.json()[0]
        commit_hash = latest_commit['sha']
        commit_time = latest_commit['commit']['author']['date']
        return commit_hash, commit_time
    return "Unknown", "Unknown"


# Convert uptime to a more human-readable format
def format_uptime(seconds):
    uptime_str = []
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        uptime_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        uptime_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not uptime_str:
        uptime_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ', '.join(uptime_str)

# Check if the local commit hash is up-to-date, behind, or ahead
def compare_commit_hashes(local_hash, remote_hash):
    if local_hash == remote_hash:
        return "Up-to-date"
    else:
        return "Out of sync"

# Convert ISO 8601 date to Unix timestamp for Discord's <t> formatting
def iso_to_unix_timestamp(iso_time_str):
    try:
        dt = datetime.fromisoformat(iso_time_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except ValueError:
        return None

@bot.command(name='stats', help='Displays Festival Tracker statistics.')
async def bot_stats(ctx):
    # Get the number of servers the bot is in
    server_count = len(bot.guilds)
    
    # Get the bot uptime
    current_time = time.time()
    uptime_seconds = int(current_time - start_time)
    uptime = format_uptime(uptime_seconds)
    
    # Get the last GitHub update and latest commit hash
    latest_commit_hash, last_update = fetch_latest_github_commit_hash()
    
    # Get the current local commit hash
    local_commit_hash = get_local_commit_hash()

    # Check if the local commit hash is up-to-date
    commit_status = compare_commit_hashes(local_commit_hash, latest_commit_hash)

    # Convert the last update time to a Unix timestamp
    last_update_timestamp = iso_to_unix_timestamp(last_update)
    if last_update_timestamp:
        last_update_formatted = f"<t:{last_update_timestamp}:R>"  # Use Discord's relative time format
    else:
        last_update_formatted = "Unknown"

    # Create an embed to display the statistics
    embed = discord.Embed(
        title="Festival Tracker Statistics",
        description="",
        color=0x8927A1
    )
    embed.add_field(name="Servers", value=f"{server_count} servers", inline=False)
    embed.add_field(name="Uptime", value=f"{uptime}", inline=False)
    embed.add_field(name="Last GitHub Update", value=f"{last_update_formatted}", inline=False)
    embed.add_field(name="Latest Commit Hash", value=f"`{latest_commit_hash}`", inline=False)
    embed.add_field(name="Current Local Commit Hash", value=f"`{local_commit_hash}` ({commit_status})", inline=False)

    # Send the statistics embed
    await ctx.send(embed=embed)

def fetch_revision_history():
    repo_commits_url = "https://api.github.com/repos/FNLookup/data/commits?path=festival/spark-tracks.json"
    commits = []
    page = 1

    while True:
        try:
            # Request the commits, paginating through all pages (max 100 per page)
            response = requests.get(f"{repo_commits_url}&per_page=100&page={page}")
            response.raise_for_status()
            data = response.json()
            
            # If no more commits are returned, we've reached the end of the history
            if not data:
                break
            
            commits.extend(data)
            page += 1  # Move to the next page of results
            
        except requests.RequestException as e:
            print(f"Error fetching commit history: {e}")
            return None

    return commits

def fetch_file_from_commit(commit_sha):
    # Fetch the spark-tracks.json file from a specific commit
    file_url = f"https://raw.githubusercontent.com/FNLookup/data/{commit_sha}/festival/spark-tracks.json"
    
    try:
        response = requests.get(file_url)
        response.raise_for_status()
        return response.json()  # Return the file's content as JSON
    except requests.RequestException as e:
        print(f"Error fetching file from commit {commit_sha}: {e}")
        return None

def fetch_local_history():
    json_files = []
    try:
        # List all files in the LOCAL_JSON_FOLDER
        for file_name in os.listdir(LOCAL_JSON_FOLDER):
            if file_name.endswith('.json'):
                json_files.append(file_name)
    except Exception as e:
        print(f"Error reading local JSON files: {e}")
    return sorted(json_files)

# Function to load JSON content from a specific file
def load_json_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON from file {file_path}: {e}")
        return None

@bot.command(
    name='history', 
    help="Check the history of a song's midi file and visually compare versions.\nThis may take a bit to generate while it searches a song's history.\nMay not include every single midi revision that has ever existed.",
    usage="[songname]"
)
async def history(ctx, *, song_name: str = None):
    if not is_running_in_command_channel(ctx.channel.id):
        return

    if not song_name:
        await ctx.send("Please provide a song name.")
        return

    user_id = ctx.author.id
    session_hash = generate_session_hash(user_id, song_name)  # Generate a unique hash for the session

    # Step 2: Fetch the current track data from the jam API to perform fuzzy search
    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send('Could not fetch tracks.')
        await thinking_message.delete()
        return

    # Perform fuzzy search to find the matching song
    matched_tracks = fuzzy_search_tracks(tracks, song_name)
    if not matched_tracks:
        await ctx.send(f"No tracks found for '{song_name}'.")
        await thinking_message.delete()
        return

    track_data = matched_tracks[0]
    album_art_url = track_data['track'].get('au')
    shortname = track_data['track'].get('sn')
    actual_title = track_data['track'].get('tt', 'Unknown Title')
    actual_artist = track_data['track'].get('an', 'Unknown Artist')

    # Send the "thinking" message to show the user the bot is working
    thinking_message = await ctx.send(f"Processing the history of **{actual_title}** - *{actual_artist}*\nPlease wait...")

    # Step 1: Fetch the local revision history of the song
    json_files = fetch_local_history()  # Fetch list of local JSON files

    if not json_files:
        await ctx.send("No local history files found.")
        await thinking_message.delete()
        return

    # Step 3: Track changes in MIDI file over all commits (from local files)
    midi_file_changes = []
    seen_midi_files = set()

    for json_file in json_files:
        file_path = os.path.join(LOCAL_JSON_FOLDER, json_file)
        file_content = load_json_from_file(file_path)
        if not file_content:
            continue

        # Check for the song in this file's spark-tracks.json
        song_data = file_content.get(shortname)
        if song_data and 'track' in song_data:
            midi_file_from_commit = song_data['track'].get('mu', None)
            last_modified = song_data.get('lastModified', None)

            # If it's a new version of the MIDI file, store it
            if midi_file_from_commit and midi_file_from_commit not in seen_midi_files:
                if last_modified:
                    last_modified_date = datetime.fromisoformat(last_modified.replace('Z', '+00:00')).strftime("%B %d, %Y")
                else:
                    last_modified_date = "Unknown"

                midi_file_changes.append((last_modified_date, midi_file_from_commit))
                seen_midi_files.add(midi_file_from_commit)

    # Handle the case where only one version exists
    if len(midi_file_changes) <= 1:
        await ctx.send(f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the MIDI file exists.")
        await thinking_message.delete()  # Clean up the thinking message
        return

    ## Step 4: Reverse and Compare MIDI Files from Oldest to Newest
    #midi_file_changes.reverse()

    for i in range(1, len(midi_file_changes)):
        old_midi_url = midi_file_changes[i - 1][1]
        new_midi_url = midi_file_changes[i][1]
        old_midi_date = midi_file_changes[i - 1][0]
        new_midi_date = midi_file_changes[i][0]

        # Use session_hash to uniquely name the MIDI files for this session
        old_midi_file = decrypt_dat_file(old_midi_url, f"version_{session_hash}_old_{i - 1}.dat")
        new_midi_file = decrypt_dat_file(new_midi_url, f"version_{session_hash}_new_{i}.dat")

        if old_midi_file and new_midi_file:
            # Add debug logging to confirm comparison command runs properly
            comparison_command = ['python', 'compare_midi.py', old_midi_file, new_midi_file]
            result = subprocess.run(comparison_command, capture_output=True, text=True)
            print(result.stdout)  # Log output of comparison script
            print(result.stderr)  # Log any errors

            # Assuming your comparison script generates images in the TEMP_FOLDER
            comparison_images = [f for f in os.listdir(TEMP_FOLDER) if f.endswith('.png')]
            
            image_sent = False

            for image in comparison_images:
                image_path = os.path.join(TEMP_FOLDER, image)
                
                # Extract session ID from the image filename
                image_session_id = image.split('_')[-1].replace('.png', '')  # Assuming the hash is at the end of the file name
                
                # Check if the image matches the current session ID
                if image_session_id == session_hash and os.path.getsize(image_path) > 0:  # Check if the image is non-empty
                    file = discord.File(image_path, filename=image)
                    embed = discord.Embed(
                        title=f"MIDI Comparison for {actual_title} - {actual_artist}",
                        description=f"Comparing MIDI from {old_midi_date} to {new_midi_date}"
                    )
                    embed.set_image(url=f"attachment://{image}")
                    embed.set_thumbnail(url=album_art_url)
                    await ctx.send(embed=embed, file=file)
                    image_sent = True
            if not image_sent:
                await ctx.send(f"Comparison between {old_midi_date} and {new_midi_date} passed all checks and appear unchanged.")
            
            # Clean up generated images
            clear_out_folder(TEMP_FOLDER)
        else:
            await ctx.send(f"Failed to decrypt one or both MIDI files for comparison between {old_midi_date} and {new_midi_date}.")

    # Step 5: Clean up the "thinking" message
    await thinking_message.delete()

@bot.command(name='fullhistory', help="only jnack can run this")
async def fullhistory(ctx):
    # Check if the user ID matches yours
    if ctx.author.id != 960524988824313876:
        await ctx.send("You are not authorized to run this command.")
        return

    # Fetch all available tracks
    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send("Could not fetch tracks.")
        return

    # Loop through all the tracks and run the history command for each
    for shortname, track in tracks.items():
        song_name = track['track']['tt']
        artist_name = track['track']['an']

        try:
            # Send a message indicating which song's history is being processed
            await ctx.send(f"Processing the history for **{song_name}** by *{artist_name}*...")

            # Call the history command with the song's title
            await history(ctx, song_name=song_name)

        except Exception as e:
            await ctx.send(f"Failed to process the history for **{song_name}**. Error: {e}")
            # Continue even if one song fails

    # Final message indicating the full history run is complete
    await ctx.send("Full history run completed.")

@bot.command(name='setprefix', help='Set a custom command prefix for your server.')
@commands.has_permissions(administrator=True)
async def set_prefix(ctx, prefix: str):
    if len(prefix) > 5:
        await ctx.send("The prefix is too long! Please choose a shorter prefix.")
        return

    prefixes = load_prefixes()
    guild_id = str(ctx.guild.id)
    prefixes[guild_id] = prefix
    save_prefixes(prefixes)

    await ctx.send(f"Prefix set to: `{prefix}`")

@bot.event
async def on_command_error(ctx, error):
    # Check if the error is MissingPermissions for the user
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have the necessary permissions to run this command. Only admins can use this command.")
        await ctx.message.add_reaction('❌')  # React with an 'X' emoji to indicate the bot lacks permissions

bot.run(DISCORD_TOKEN)