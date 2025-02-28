from configparser import ConfigParser
from datetime import datetime
import enum
import hashlib
import json
import logging
import os

import discord
import requests

# Folder where local JSON files are stored
LOCAL_JSON_FOLDER = "json/"
if not os.path.exists(LOCAL_JSON_FOLDER):
    os.makedirs(LOCAL_JSON_FOLDER)

LOCAL_MIDI_FOLDER = "midi_files/"
if not os.path.exists(LOCAL_MIDI_FOLDER):
    os.makedirs(LOCAL_MIDI_FOLDER)

TEMP_FOLDER = "out/"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

BACKUP_FOLDER = 'backups/'
if not os.path.exists(BACKUP_FOLDER):
    os.makedirs(BACKUP_FOLDER)

config = ConfigParser()
config.read('config.ini')
BOT_OWNERS: list[int] = [int(uid) for uid in config.get('bot', 'bot_owners', fallback="").split(', ')]
TEST_GUILD: int = int(config.get('bot', 'testing_guild'))
ERR_CHANNEL: int = int(config.get('bot', 'error_channel'))
LOG_CHANNEL: int = int(config.get('bot', 'event_channel'))
SUG_CHANNEL: int = int(config.get('bot', 'suggest_channel'))
ANALYTICS_CHANNEL: int = int(config.get('bot', 'analytics_channel'))

SERVER_URL: str = config.get('bot', 'server_url')
BOT_TOKEN: str = config.get('bot', 'bot_token')

SPOTIFY_CLIENT_ID: str = config.get('bot', 'spotify_api_client')
SPOTIFY_CLIENT_PASS: str = config.get('bot', 'spotify_api_secret')

GITHUB_PAT: str = config.get('bot', 'github_pat')

EPIC_ACCOUNT_ID: str = config.get('bot', 'epic_account_id')
EPIC_DEVICE_ID: str = config.get('bot', 'epic_device_id')
EPIC_DEVICE_SECRET: str = config.get('bot', 'epic_device_secret')

SPARKS_MIDI_KEY: str = config.get('bot', 'sparks_midi_key') #b64


# Files used to track songs
SONGS_FILE = 'known_tracks.json'  # File to save known songs
SHORTNAME_FILE = 'known_songs.json'  # File to save known shortnames

# APIs which the bot uses to source its information
CONTENT_API = 'https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks'
DAILY_API = 'https://api.nitestats.com/v1/epic/modes-smart'
SHOP_API = 'https://fngw-mcp-gc-livefn.ol.epicgames.com/fortnite/api/storefront/v2/catalog'
LEADERBOARD_DB_URL = 'https://raw.githubusercontent.com/FNLookup/festival-leaderboards/main/' # unused

ERROR_EMOJI = '<:error:1327736288807358629>'
SUCCESS_EMOJI = '<:checkmark:1327738579287412897>'
PREVIOUS_EMOJI = '<:prevpage:1344510443657629768>'
NEXT_EMOJI = '<:nextpage:1344510452234977290>'
FIRST_EMOJI = '<:firstpage:1344510426830077952>'
LAST_EMOJI = '<:lastpage:1344510435256176740>'
UP_EMOJI = '<:up:1344510417896214528>'
DOWN_EMOJI = '<:down:1344510409050427463>'
SEARCH_EMOJI = '<:search:1344510399781011509>'
INFORMATION_EMOJI = '<:information:1344521974302507039>'
SEARCH_EMOJI = '<:search:1344510399781011509>'

EVENT_NAMES = {
    'added': "Track Added",
    'removed': "Track Removed",
    'modified': "Track Modified"
}

SIMPLE_COMPARISONS = {
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
    'isrc': 'International Standard Recording Code',
    'ar': 'ESRB Rating',
    'au': 'Album Art URL',
    'siv': 'Vocals Instrument',
    'sib': 'Bass Instrument',
    'sid': 'Drums Instrument',
    'sig': 'Guitar Instrument',
    'mt': 'BPM',
    'ld': 'Lip Sync',
    'mu': 'Chart URL',
    'ge': 'Genres',
    'gt': 'Gameplay Tags'
}

DIFFICULTY_COMPARISONS = {
    'pb': 'Pro Bass',
    'pd': 'Pro Drums',
    'pg': 'Pro Lead',
    'vl': 'Vocals',
    'gr': 'Lead',
    'ds': 'Drums',
    'ba': 'Bass'
}

EXTRA_COMPARISONS = {
    'dn': 'Track Number',
    '_type': 'Track Type',
    '_noIndex': 'No Index Flag',
    '_activeDate': 'Active Date',
    '_locale': 'Locale',
    '_templateName': 'Template Name'
}

class Analytic:
    def __init__(self, interaction: discord.Interaction):
        self.is_dm: bool = interaction.guild == None
        self.guild_name: str = "DMs"
        self.guild_id: int = None
        self.command_name: str = None
        self.guild_member_count: int = 0
        if not self.is_dm:
            self.guild_name = interaction.guild.name
        if not self.is_dm:
            self.guild_id = interaction.guild.id
        if not self.is_dm:
            self.guild_member_count = interaction.guild.member_count
        if interaction.command:
            self.command_name = interaction.command.qualified_name
        self.interaction_language: str = interaction.locale
        self.interaction_data: dict = interaction.data
        self.time: datetime = interaction.created_at

class PaginatorView(discord.ui.View):
    def __init__(self, embeds, user_id):
        super().__init__(timeout=30)
        self.embeds = embeds
        self.user_id = user_id
        self.current_page = 0
        self.total_pages = len(embeds)
        self.add_buttons()
        self.message : discord.Message

    def update_buttons(self):
        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(FirstButton(style=discord.ButtonStyle.secondary, emoji=FIRST_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))
        self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, emoji=PREVIOUS_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))

        self.add_item(PaginatorButton(label=f"{self.current_page + 1}/{self.total_pages}", user_id=self.user_id, style=discord.ButtonStyle.primary))

        self.add_item(NextButton(style=discord.ButtonStyle.secondary, emoji=NEXT_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))
        self.add_item(LastButton(style=discord.ButtonStyle.secondary, emoji=LAST_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))

    def get_embed(self):
        if self.current_page < 0:
            self.current_page = 0
        elif self.current_page > self.total_pages - 1:
            self.current_page = self.total_pages - 1

        return self.embeds[self.current_page]

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            logging.error("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

class PaginatorButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    def update_page(self, view: PaginatorView):
        pass

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        self.update_page(view)
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class FirstButton(PaginatorButton):
    def update_page(self, view: PaginatorView):
        view.current_page = 0

class PreviousButton(PaginatorButton):
    def update_page(self, view: PaginatorView):
        view.current_page -= 1

class NextButton(PaginatorButton):
    def update_page(self, view: PaginatorView):
        view.current_page += 1

class LastButton(PaginatorButton):
    def update_page(self, view: PaginatorView):
        view.current_page = view.total_pages - 1

class OneButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        view: OneButtonSimpleView = self.view
        if interaction.user.id != self.user_id and view.restrict:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view.add_buttons()
        await interaction.response.defer()
        if view.on_press:
            await view.on_press()

class OneButtonSimpleView(discord.ui.View):
    def __init__(self, on_press, user_id, label = "No label", emoji = "🔁", link = None, restrict_only_to_creator = True):
        super().__init__(timeout=30)  # No timeout for the view
        self.on_press = on_press
        self.user_id = user_id
        self.label_text = label
        self.btn_emoji = emoji
        self.message : discord.Message
        self.link = link
        self.restrict = restrict_only_to_creator
        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(OneButton(user_id=self.user_id, style=discord.ButtonStyle.primary, label=self.label_text, disabled=False, emoji=self.btn_emoji, url=self.link))

    async def on_timeout(self):
        if self.link != None:
            return

        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            logging.error("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

class Button:
    def __init__(self, on_press:any, label:str, emoji: str = None, restrict: bool = True, url: str = None, style: discord.ButtonStyle = None, disabled: bool = False):
        self.on_press = on_press
        self.label = label
        self.emoji = emoji
        self.restrict = restrict
        self.url = url
        self.style = style
        self.disabled = disabled

class ViewButton(discord.ui.Button):
    def __init__(self, on_press:any, label:str, emoji: str = None, restrict: bool = True, url: str = None, style: discord.ButtonStyle = None, disabled: bool = False):
        self._on_press = on_press
        self._restrict = restrict
        self._url = url
        self._style = style or discord.ButtonStyle.primary
        self._label = label
        self._emoji = emoji
        self._disabled = disabled

        super().__init__(style=self._style, label=self._label, url=self._url, emoji=self._emoji, disabled=self._disabled)

    async def callback(self, interaction: discord.Interaction):
        view: ButtonedView = self.view
        if interaction.user.id != view.user_id and self._restrict:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view.add_buttons()
        await interaction.response.defer()
        if self._on_press:
            await self._on_press()

class ButtonedView(discord.ui.View):
    def __init__(self, user_id: int, buttons: list[Button]):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.buttons = buttons
        self.message : discord.Message

        self.add_buttons()

    def add_buttons(self):
        self.clear_items()

        for button in self.buttons:
            self.add_item(ViewButton(
                on_press=button.on_press,
                label=button.label,
                emoji=button.emoji,
                url=button.url,
                style=button.style,   
                restrict=button.restrict,
                disabled=button.disabled
            ))

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            logging.error("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

class Instrument:
    def __init__(self, english:str = "Vocals", lb_code:str = "Solo_Vocals", plastic:bool = False, chopt:str = "vocals", midi:str = "PART VOCALS", replace:str = None, lb_enabled:bool = True) -> None:
        """Creates an instrument, for easier internal handling.

        Properties:
            `english` The instrument name in English, used for embeds.
            `lb_code` The codename for the leaderboard api, e.g `Solo_[lb_code]`.
            `plastic` If the instrument is Pro, `False` if not.
            `chopt` The instrument code given to CHOpt.exe.
            `midi` The instrument track name in MIDI files. Also used to replace when using CHOpt.exe.
            `replace` The instrument track name which this instrument is replaced with when using CHOpt.exe.
            `lb_enabled` Is the instrument allowed to be used for leaderboards.
        """

        self.english = english
        self.lb_code = lb_code
        self.plastic = plastic
        self.chopt = chopt
        self.midi = midi
        self.replace = replace
        self.lb_enabled = lb_enabled

    def __str__(self) -> str:
        return f"Instrument({self.english=}, {self.lb_code=}, {self.plastic=}, {self.chopt=}, {self.midi=}, {self.replace=}, {self.lb_enabled=})".replace('self.', '')
    
class Difficulty:
    def __init__(self, english:str = "Expert", chopt:str = "expert", pitch_ranges = [96, 100], diff_4k:bool = False) -> None:
        """Creates a difficulty, for easier internal handling.

        Properties:
            `english` The difficulty name in English, used for embeds.
            `chopt` The difficuly code given to CHOpt.exe.
            `pitch_ranges` From what note to what note does this difficulty cover
            `diff_4k` If this difficulty is a 4k difficulty on normal parts
        """

        self.english = english
        self.chopt = chopt
        self.pitch_ranges = pitch_ranges
        self.diff_4k = diff_4k

    def __str__(self) -> str:
        return f"Difficulty({self.english=}, {self.chopt=}, {self.pitch_ranges=}, {self.diff_4k=})".replace('self.', '')

class Instruments(enum.Enum):
    ProLead = Instrument(english="Pro Lead", lb_code="Solo_PeripheralGuitar", plastic=True, chopt="proguitar", midi="PLASTIC GUITAR")
    ProBass = Instrument(english="Pro Bass", lb_code="Solo_PeripheralBass", plastic=True, chopt="probass", midi="PLASTIC BASS")
    ProDrums = Instrument(english="Pro Drums", lb_code="Solo_PeripheralDrum", plastic=True, chopt="drums", midi="PLASTIC DRUMS", replace="PART DRUMS", lb_enabled=False)
    Bass = Instrument(english="Bass", lb_code="Solo_Bass", chopt="bass", midi="PART BASS")
    Lead = Instrument(english="Lead", lb_code="Solo_Guitar", chopt="guitar", midi="PART GUITAR")
    Drums = Instrument(english="Drums", lb_code="Solo_Drums", chopt="drums", midi="PART DRUMS")
    Vocals = Instrument(english="Vocals", lb_code="Solo_Vocals", chopt="vocals", midi="PART VOCALS")

    # The @classmethod decorator just works!
    @classmethod
    def getall(self) -> list[Instrument]:
        return [self.ProLead.value, self.ProBass.value, self.ProDrums.value, self.Bass.value, self.Lead.value, self.Drums.value, self.Vocals.value]

class Difficulties(enum.Enum):
    Expert = Difficulty()
    Hard = Difficulty(english="Hard", chopt="hard", pitch_ranges=[84, 88], diff_4k=True)
    Medium = Difficulty(english="Medium", chopt="medium", pitch_ranges=[72, 76], diff_4k=True)
    Easy = Difficulty(english="Easy", chopt="easy", pitch_ranges=[60, 64], diff_4k=True)

    @classmethod
    def getall(self) -> list[Difficulty]:
        return [self.Expert.value, self.Hard.value, self.Medium.value, self.Easy.value]

def get_jam_tracks():
    content_url = CONTENT_API

    logging.debug(f'[GET] {content_url}')
    try:
        response = requests.get(content_url)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            available_tracks = []
            for k, v in data.items():
                if isinstance(v, dict) and 'track' in v:
                    available_tracks.append(v)
            return available_tracks
        else:
            logging.error(f'Unexpected data format: {type(data)}')
            return []
    except Exception as e:
        logging.error(f'Error getting jam tracks', exc_info=e)
        return []
    
def generate_difficulty_string(difficulty_data):
    return (
        f"<:lead:1327742677856420003> {difficulty_data.get('gr', 0) + 1}/7 "
        f"<:bass:1327742687025168555> {difficulty_data.get('ba', 0) + 1}/7 "
        f"<:drums:1327742563762835598> {difficulty_data.get('ds', 0) + 1}/7 "
        f"<:proguitar:1327742543571583179> {difficulty_data.get('pg', 0) + 1}/7 "
        f"<:probass:1327742553558093858> {difficulty_data.get('pb', 0) + 1}/7 "
        f"<:vocals:1327742697695350936> {difficulty_data.get('vl', 0) + 1}/7"
    )

def generate_difficulty_bar(difficulty, max_blocks=7):
    scaled_difficulty = difficulty + 1
    filled_blocks = '■' * scaled_difficulty
    empty_blocks = '□' * (max_blocks - scaled_difficulty)
    return filled_blocks + empty_blocks

def generate_session_hash(user_id, song_name):
    # Generate the md5 hash and convert it to an integer
    hash_int = int(hashlib.md5(f"{user_id}_{song_name}".encode()).hexdigest(), 16)

    return str(hash_int % 10**8).zfill(8)

def delete_session_files(session_hash):
    try:
        for file_name in os.listdir(TEMP_FOLDER):
            if session_hash in file_name:
                file_path = os.path.join(TEMP_FOLDER, file_name)
                os.remove(file_path)
                logging.info(f"Deleted file: {file_path}")
    except Exception as e:
        logging.error(f"Error while cleaning up files for session {session_hash}", exc_info=e)

def load_json_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading JSON from file {file_path}",exc_info=e)
        return None
    
def sort_track_list(tracks):
    return sorted(tracks, key=lambda x: x['track']['tt'].lower())

def create_track_embeds(track_list, title, chunk_size=10):
    embeds = []

    for i in range(0, len(track_list), chunk_size):
        embed = discord.Embed(title=title, color=0x8927A1)
        chunk = track_list[i:i + chunk_size]

        for track in chunk:
            embed.add_field(
                name="",
                value=f"**\\• {track['track']['tt']}** - *{track['track']['an']}*",
                inline=False
            )

        embeds.append(embed)

    return embeds

def format_date(date_string):
    if date_string:
        date_ts = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return discord.utils.format_dt(date_ts, 'D')
    return "Unknown"

def add_fields(track_data, embed, weekly_tracks, shop_tracks):
    track_devname = track_data['track']['sn']
    if weekly_tracks and track_devname in weekly_tracks:
        active_until = weekly_tracks[track_devname]['activeUntil']
        embed.add_field(name="Weekly Rotation", value=f"Free until {format_date(active_until)}.", inline=False)

    shop_entry = discord.utils.find(lambda offer: offer['meta']['templateId'] == track_data['track']['ti'], shop_tracks)

    if shop_entry:
        out_date = shop_entry['meta'].get('outDate')
        embed.add_field(name="Item Shop", value=f"Currently in the shop until {format_date(out_date)}.", inline=False)
    
def common_error_embed(text) -> discord.Embed:
    return discord.Embed(colour=0xbe2625, title="Error", description=f"{ERROR_EMOJI} {text}")

def common_success_embed(text) -> discord.Embed:
    return discord.Embed(colour=0x3AB00B, title="Success", description=f"{SUCCESS_EMOJI} {text}")