import os
import requests
from discord.ext import commands, tasks
import discord
import json
from configparser import ConfigParser
from difflib import get_close_matches
from datetime import datetime, timezone
import string
from discord.ext.commands import DefaultHelpCommand
import subprocess

# Load configuration from config.ini
config = ConfigParser()
config.read('config.ini')

# Read the Discord bot token and channel IDs from the config file
DISCORD_TOKEN = config.get('discord', 'token')
CHANNEL_IDS = config.get('discord', 'channel_ids', fallback="").split(',')
COMMAND_PREFIX = config.get('discord', 'prefix', fallback="!").split(',')

# Convert channel IDs to integers and filter out any empty strings
CHANNEL_IDS = [int(id.strip()) for id in CHANNEL_IDS if id.strip()]

API_URL = 'https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks'
MODES_SMART_URL = 'https://api.nitestats.com/v1/epic/modes-smart'
SHOP_API_URL = 'https://fortnite-api.com/v2/shop'
SONGS_FILE = 'known_tracks.json'  # File to save known songs
SHORTNAME_FILE = 'known_songs.json'  # File to save known shortnames
LEADERBOARD_DB_URL = 'https://raw.githubusercontent.com/FNLookup/festival-leaderboards/main/'

TEMP_FOLDER = "out"

# Set up Discord bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

class CustomHelpCommand(DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = 'Available Commands'
        self.command_attrs['help'] = 'Shows this help message'

    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="Festival Tracker Help",
            description="A simple bot to check Fortnite Festival song data. [Source](https://github.com/hmxmilohax/festivalinfobot)",
            color=0x8927A1
        )

        for cog, commands in mapping.items():
            if cog:
                name = cog.qualified_name
                filtered = await self.filter_commands(commands, sort=True)
                if filtered:
                    value = '\n'.join([f"`{COMMAND_PREFIX[0]}{cmd.name}`: {cmd.short_doc}" for cmd in filtered])
                    embed.add_field(name=name, value=value, inline=False)
            else:
                filtered = await self.filter_commands(commands, sort=True)
                if filtered:
                    value = '\n'.join([f"`{COMMAND_PREFIX[0]}{cmd.name}`: {cmd.short_doc}" for cmd in filtered])
                    embed.add_field(name=self.no_category, value=value, inline=False)

        embed.set_footer(text=f"Type {COMMAND_PREFIX[0]}help <command> for more details on a command.")
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Help with `{COMMAND_PREFIX[0]}{command.name}`",
            description=command.help or "No description provided.",
            color=0x8927A1
        )

        # Properly format the usage with the command signature
        usage = f"`{COMMAND_PREFIX[0]}{command.qualified_name} {command.signature}`" if command.signature else f"`{COMMAND_PREFIX[0]}{command.qualified_name}`"
        embed.add_field(name="Usage", value=usage, inline=False)

        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(command.aliases), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX, 
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
            await interaction.response.send_message(f"This is not your session. Please use the {COMMAND_PREFIX[0]}tracklist command to start your own session.", ephemeral=True)
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
            await interaction.response.send_message(f"This is not your session. Please use the {COMMAND_PREFIX[0]}tracklist command to start your own session.", ephemeral=True)
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
            await interaction.response.send_message(f"This is not your session. Please use the {COMMAND_PREFIX[0]}tracklist command to start your own session.", ephemeral=True)
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
            await interaction.response.send_message(f"This is not your session. Please use the {COMMAND_PREFIX[0]}tracklist command to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page = view.total_pages - 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

def get_instrument(query):
    query = query.lower()
    if query in ['plasticguitar', 'prolead', 'pl', 'proguitar', 'pg']:
        return ['Solo_PeripheralGuitar', 'Pro Lead']
    elif query in ['plasticbass', 'probass', 'pb']:
        return ['Solo_PeripheralBass', 'Pro Bass']
    elif query in ['vocals', 'vl', 'v']:
        return ['Solo_Vocals', 'Vocals']
    elif query in ['guitar', 'gr', 'lead', 'ld', 'g', 'l']:
        return ['Solo_Guitar', 'Lead']
    elif query in ['bass', 'ba', 'b']:
        return ['Solo_Bass', 'Bass']
    elif query in ['drums', 'ds', 'd']:
        return ['Solo_Drums', 'Drums']
    return None

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
        except Exception as e: # No more jsons
            print(f'There aren\'t enough entries to fetch: {e}')
            return fetched_entries
    else:
        return fetched_entries

def remove_punctuation(text):
    return text.translate(str.maketrans('', '', string.punctuation))

def fuzzy_search_tracks(tracks, search_term):
    # Remove punctuation from the search term
    search_term = remove_punctuation(search_term.lower())  # Case-insensitive search
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

            embed.add_field(
                name="",
                value=(
                    f"**\\- {track['title']}**\n*{track['artist']}*, {track['releaseYear']} - {duration_str}\n"
                    f"Added {in_date_display} - Leaving {out_date_display}\n"
                    f"`{difficulty_str}`"
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
                embed.add_field(name="", value=f"{track['track']['tt']} - *{track['track']['an']}*\nLeaving {human_readable_until}", inline=False)
            else:
                embed.add_field(name="", value=f"{track['track']['tt']} - *{track['track']['an']}*", inline=False)
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
            embed.add_field(name=f"{name} difficulty changed", value=f"```Old: \"{generate_difficulty_bar(old_track_data['in'][value])}\"\nNew: \"{generate_difficulty_bar(new_track_data['in'][value])}\"```", inline=False)

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
                    image_filename = f"{track_name}_changes.png"  # Construct the expected image filename
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

@tasks.loop(minutes=7)
async def check_for_new_songs():
    if not CHANNEL_IDS:
        print("No channel IDs provided; skipping the 7-minute probe.")
        return

    print("Checking for new songs...")

    # Fetch current jam tracks
    tracks = fetch_jam_tracks_file()

    if not tracks:
        print('Could not fetch tracks.')
        return

    # Dynamically reload known tracks and shortnames from disk each time the task runs
    known_tracks = load_known_songs_from_disk()  # Reload known_tracks.json
    known_shortnames = load_known_songs_from_disk(shortnames=True)  # Reload known_songs.json

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
                await channel.send(embed=embed)
            save_known_songs_to_disk(tracks)
            save_known_songs_to_disk([track['track']['sn'] for track in tracks], shortnames=True)

        if modified_songs:
            print(f"Modified songs detected!")
            for old_song, new_song in modified_songs:
                old_url = old_song['track'].get('mu', '')
                new_url = new_song['track'].get('mu', '')
                track_name = new_song['track']['tt']  # Get track name for the embed
                artist_name = new_song['track']['an']  # Get track name for the embed

                if old_url != new_url:
                    print(f"Chart URL changed:")
                    print(f"Old: {old_url}")
                    print(f"New: {new_url}")

                    # Pass the track name to the process_chart_url_change function
                    await process_chart_url_change(old_url, new_url, channel, track_name, track_name, artist_name)


                embed = generate_modified_track_embed(old=old_song, new=new_song)
                await channel.send(embed=embed)
            save_known_songs_to_disk(tracks)
            save_known_songs_to_disk([track['track']['sn'] for track in tracks], shortnames=True)

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
    # Start the song check loop
    check_for_new_songs.start()

@bot.command(name='search', help='Search for a track by name or artist.')
async def search(ctx, *, query: str = None):
    if query is None:
        await ctx.send("Please provide a search term.")
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

            daily_tracks.append({
                'track': track,
                'title': title,
                'artist': artist,
                'activeSince': active_since_ts,
                'activeUntil': active_until_ts
            })

    # Sort the tracks first by 'Leaving' time (activeUntil), then alphabetically by title
    daily_tracks.sort(key=lambda x: (x['activeUntil'] or float('inf'), x['title'].lower()))

    if daily_tracks:
        embeds = []
        chunk_size = 10  # Limit the number of tracks per embed to 5 for readability
        
        for i in range(0, len(daily_tracks), chunk_size):
            embed = discord.Embed(title="Daily Rotation Tracks", color=0x8927A1)
            chunk = daily_tracks[i:i + chunk_size]
            for entry in chunk:
                track = entry['track']
                active_since_ts = entry['activeSince']
                active_until_ts = entry['activeUntil']
                title = entry['title']
                artist = entry['artist']

                # Format timestamps in Discord format
                active_since_display = f"<t:{active_since_ts}:R>" if active_since_ts else "Unknown"
                active_until_display = f"<t:{active_until_ts}:R>" if active_until_ts else "Unknown"
                embed.add_field(
                    name="",
                    value=f"**\\- {title if title else 'Unknown Title'}**\n*{artist if artist else 'Unknown Artist'}*\nAdded: {active_since_display} - Leaving: {active_until_display}",
                    inline=False
                )
            embeds.append(embed)

        view = PaginatorView(embeds, ctx.author.id)
        view.message = await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send("No daily tracks found.")

@bot.command(name='count', help='Show the total number of available tracks in Fortnite Festival.')
async def count_tracks(ctx):
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
    tracks = fetch_shop_tracks()
    if not tracks:
        await ctx.send('Could not fetch shop tracks.')
        return
    
    # Sort the tracks alphabetically by title
    tracks = list(tracks.values())
    tracks.sort(key=lambda x: x['title'].lower())

    if not tracks:
        await ctx.send('No tracks available in the shop.')
        return

    # Calculate total tracks and update the title
    total_tracks = len(tracks)
    title = f"Shop Tracks (Total: {total_tracks})"

    # Generate paginated embeds with 7 tracks per embed
    embeds = generate_shop_tracks_embeds(tracks, title, chunk_size=7)
    
    # Initialize the paginator view
    view = PaginatorView(embeds, ctx.author.id)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

@bot.command(name='leaderboard', 
             help="""View the leaderboard of a specific song, and specific leaderboard entries. Updated roughly every 12 hours.\nAccepts a shortname, instrument, and optionally, a rank, username or Epic account ID.
Instruments:

- `plasticguitar`, `prolead`, `pl`, `proguitar`, `pg`: Pro Lead
- `plasticbass`, `probass`, `pb`: Pro Bass
- `vocals`, `vl`, `v`: Vocals
- `guitar`, `gr`, `lead`, `ld`, `g`, `l`: Lead
- `bass`, `ba`, `b`: Bass
- `drums`, `ds`, `d`:  Drums
If the third argument is not present, a list of entries will be shown instead.
Only the first 500 entries of every leaderboard are available.""", 
             aliases=['lb'],
             usage="[shortname] [instrument] [rank/username/accountid]")
async def leaderboard(ctx, shortname :str = None, instrument :str = None, rank_or_account = None):
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
    
    matched_tracks = fuzzy_search_tracks(tracks, shortname)

    if not matched_tracks:
        await ctx.send('No tracks found matching your search.')
        return
    
    if len(matched_tracks) > 0:
        matched_track = matched_tracks[0]
        
        instrument_codename = get_instrument(instrument)
        if not instrument_codename:
            await ctx.send('Unknown instrument.')
            return

        leaderboard_entries = fetch_leaderboard_of_track(shortname, instrument_codename[0])

        if len(leaderboard_entries) > 0:
            # View all the entries
            if not rank_or_account:
                title = f"Leaderboard for\n**{matched_track['track']['tt']}** - *{matched_track['track']['an']}* ({instrument_codename[1]})"

                # Generate paginated embeds with 10 entries per embed
                embeds = generate_leaderboard_entry_embeds(leaderboard_entries, title, chunk_size=10)
                
                # Initialize the paginator view
                view = PaginatorView(embeds, ctx.author.id)
                view.message = await ctx.send(embed=view.get_embed(), view=view)
            else:
                try:
                    rank = int(rank_or_account)
                    if rank:
                        entries = [entry for entry in leaderboard_entries if entry['rank'] == rank]
                        if len(entries) > 0:
                            await ctx.send(embed=generate_leaderboard_embed(matched_track, entries[0], instrument_codename[1]))
                        else:
                            await ctx.send('No entries found.')
                except ValueError:
                    if type(rank_or_account) == str:
                        entries = [entry for entry in leaderboard_entries if entry['userName'] == rank_or_account or entry['teamId'] == rank_or_account]
                        if len(entries) > 0:
                            await ctx.send(embed=generate_leaderboard_embed(matched_track, entries[0], instrument_codename[1]))
                        else:
                            await ctx.send('Player not found in leaderboard.')
                    else:
                        await ctx.send('Invalid rank or account.')
        else:
            await ctx.send('No entries in leaderboard.')

bot.run(DISCORD_TOKEN)