import os
import requests
from discord.ext import commands, tasks
import discord
import json
from configparser import ConfigParser
from difflib import get_close_matches

# Load configuration from config.ini
config = ConfigParser()
config.read('config.ini')

# Read the Discord bot token and channel IDs from the config file
DISCORD_TOKEN = config.get('discord', 'token')
CHANNEL_IDS = config.get('discord', 'channel_ids', fallback="").split(',')

# Convert channel IDs to integers and filter out any empty strings
CHANNEL_IDS = [int(id.strip()) for id in CHANNEL_IDS if id.strip()]

API_URL = 'https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks'
SHORTNAMES_URL = 'https://raw.githubusercontent.com/FNFestival/fnfestival.github.io/main/data/jam_tracks.json'
SONGS_FILE = 'known_songs.json'  # File to save known songs

# Set up Discord bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

bot = commands.Bot(command_prefix='!', intents=intents)

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
        if self.current_page > 0:
            self.add_item(PreviousButton(style=discord.ButtonStyle.primary, label='Previous', user_id=self.user_id))
        else:
            self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, label='Previous', disabled=True, user_id=self.user_id))
        
        if self.current_page < self.total_pages - 1:
            self.add_item(NextButton(style=discord.ButtonStyle.primary, label='Next', user_id=self.user_id))
        else:
            self.add_item(NextButton(style=discord.ButtonStyle.secondary, label='Next', disabled=True, user_id=self.user_id))

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
            # Handle the case where the message no longer exists
            print("Message was not found when trying to edit after timeout.")
        except Exception as e:
            # Log any other exceptions that might occur
            print(f"An error occurred during on_timeout: {e}")

class NextButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You did not trigger this list. Use the !daily to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page += 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class PreviousButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You did not trigger this list. Use the !daily to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page -= 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

def fuzzy_search_tracks(tracks, search_term):
    search_term = search_term.lower()  # Case-insensitive search
    exact_matches = []
    fuzzy_matches = []
    
    for track in tracks.values():
        title = track['track']['tt'].lower()
        artist = track['track']['an'].lower()
        
        # Check for exact matches first
        if search_term in title or search_term in artist:
            exact_matches.append(track)
        # Use fuzzy matching for close but not exact matches
        elif any(get_close_matches(search_term, [title, artist], n=1, cutoff=0.7)):
            fuzzy_matches.append(track)
    
    # Prioritize exact matches over fuzzy matches
    return exact_matches if exact_matches else fuzzy_matches

def fetch_available_jam_tracks():
    try:
        response = requests.get(API_URL)
        data = response.json()

        # Ensure that the data is a dictionary and filter tracks that have the "track" property
        if isinstance(data, dict):
            available_tracks = {k: v for k, v in data.items() if isinstance(v, dict) and 'track' in v}
            return available_tracks
        else:
            print('Unexpected data format')
            return None
    except Exception as e:
        print(f'Error fetching available jam tracks: {e}')
        return None

def fetch_shortnames_data():
    try:
        response = requests.get(SHORTNAMES_URL)
        data = response.json()
        return data
    except Exception as e:
        print(f'Error fetching shortnames data: {e}')
        return None

def generate_tracks_embeds(tracks, title):
    embeds = []
    chunk_size = 5  # Limit the number of tracks per embed to 5 for readability
    
    for i in range(0, len(tracks), chunk_size):
        embed = discord.Embed(title=title, color=0x00ff00)
        chunk = tracks[i:i + chunk_size]
        for track in chunk:
            embed.add_field(name=track['track']['tt'], value=f"{track['track']['an']}", inline=False)
        embeds.append(embed)
    
    return embeds

def generate_difficulty_bar(difficulty, max_blocks=7):
    filled_blocks = '■' * difficulty
    empty_blocks = '□' * (max_blocks - difficulty)
    return filled_blocks + empty_blocks

def generate_track_embed(track_data, is_new=False):
    track = track_data['track']
    title = f"New song in API:\n{track['tt']}" if is_new else track['tt']
    embed = discord.Embed(title=title, description=f"By {track['an']}", color=0x00ff00)
    
    # Add various fields to the embed
    embed.add_field(name="Release Year", value=track['ry'], inline=True)
    embed.add_field(name="Album", value=track.get('ab', 'N/A'), inline=True)
    embed.add_field(name="Genre", value=", ".join(track.get('ge', ['N/A'])), inline=True)
    embed.add_field(name="Duration", value=f"{track['dn'] // 60}m {track['dn'] % 60}s", inline=True)
    
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
        f"Lead:     {generate_difficulty_bar(guitar_diff)}\n"
        f"Bass:     {generate_difficulty_bar(bass_diff)}\n"
        f"Drums:    {generate_difficulty_bar(drums_diff)}\n"
        f"Vocals:   {generate_difficulty_bar(vocals_diff)}\n"
        f"Pro Lead: {generate_difficulty_bar(pro_guitar_diff)}\n"
        f"Pro Bass: {generate_difficulty_bar(pro_bass_diff)}\n"
        f"Pro Drums: {generate_difficulty_bar(pro_drums_diff)}"
    )

    # Add difficulties to embed
    embed.add_field(name="Difficulties", value=f"```{difficulties}```", inline=False)
    
    # Add the album art
    embed.set_thumbnail(url=track['au'])
    
    return embed

def save_known_songs_to_disk(songs):
    with open(SONGS_FILE, 'w') as file:
        json.dump(list(songs), file)

def load_known_songs_from_disk():
    if os.path.exists(SONGS_FILE):
        with open(SONGS_FILE, 'r') as file:
            return set(json.load(file))
    return set()

CHANNEL_IDS = [1131046106067902464, 1250804344194859220]  # Replace with your channel IDs

@tasks.loop(minutes=1)
async def check_for_new_songs():
    if not CHANNEL_IDS:
        print("No channel IDs provided; skipping the 1-minute probe.")
        return

    tracks = fetch_available_jam_tracks()

    if not tracks:
        print('Could not fetch tracks.')
        return

    # Load known songs from disk (moved here to ensure the latest known songs are loaded)
    known_songs = load_known_songs_from_disk()

    current_songs = {track['track']['sn'] for track in tracks.values()}  # Get shortnames of current songs

    # Find new songs
    new_songs = current_songs - known_songs

    if new_songs:
        print(f"New songs detected: {new_songs}")
        for new_song_sn in new_songs:
            track_data = next((track for track in tracks.values() if track['track']['sn'] == new_song_sn), None)
            if track_data:
                embed = generate_track_embed(track_data, is_new=True)
                for channel_id in CHANNEL_IDS:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(embed=embed)

    # Save the current songs to disk
    save_known_songs_to_disk(current_songs)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if CHANNEL_IDS:
        check_for_new_songs.start()  # Start the song check loop only if there are channel IDs

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    # Start the song check loop
    check_for_new_songs.start()

@bot.command(name='search')
async def search(ctx, *, query: str):
    tracks = fetch_available_jam_tracks()
    if not tracks:
        await ctx.send('Could not fetch tracks.')
        return

    matched_tracks = fuzzy_search_tracks(tracks, query)
    if not matched_tracks:
        await ctx.send('No tracks found matching your search.')
        return
    
    if len(matched_tracks) == 1:
        embed = generate_track_embed(matched_tracks[0])
        await ctx.send(embed=embed)
    else:
        # More than one match, prompt user to choose
        options = [f"{i + 1}. **{track['track']['tt']}** by {track['track']['an']}" for i, track in enumerate(matched_tracks)]
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
            await ctx.send(embed=embed)
        except TimeoutError:
            await ctx.send("You didn't respond in time. Search cancelled.")

@bot.command(name='daily')
async def daily_tracks(ctx):
    tracks = fetch_available_jam_tracks()
    shortnames_data = fetch_shortnames_data()
    if not tracks or not shortnames_data:
        await ctx.send('Could not fetch tracks or shortnames.')
        return
    
    daily_track_shortnames = shortnames_data.get('dailyTracks', [])
    daily_tracks = [track for track in tracks.values() if track['track']['sn'] in daily_track_shortnames]

    # Sort the daily tracks alphabetically by title (tt)
    daily_tracks.sort(key=lambda x: x['track']['tt'].lower())

    if daily_tracks:
        embeds = generate_tracks_embeds(daily_tracks, "Daily Rotation Tracks")
        view = PaginatorView(embeds, ctx.author.id)
        view.message = await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send("No daily tracks found.")

bot.run(DISCORD_TOKEN)
