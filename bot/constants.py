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

# Files used to track songs
SONGS_FILE = 'known_tracks.json'  # File to save known songs
SHORTNAME_FILE = 'known_songs.json'  # File to save known shortnames

# APIs which the bot uses to source its information
CONTENT_API = 'https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks'
DAILY_API = 'https://api.nitestats.com/v1/epic/modes-smart'
SHOP_API = 'https://fortnite-api.com/v2/shop'
LEADERBOARD_DB_URL = 'https://raw.githubusercontent.com/FNLookup/festival-leaderboards/main/'

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
        self.guild_name: str = interaction.guild.name
        self.guild_id: int = interaction.guild.id
        self.command_name: str = None
        if interaction.command:
            self.command_name = interaction.command.qualified_name
        self.guild_member_count: int = interaction.guild.member_count
        self.interaction_language: str = interaction.locale
        self.interaction_data: dict = interaction.data
        self.time: datetime = interaction.created_at

    def __str__(self) -> str:
        return f"""
        Guild Name: {self.guild_name}
        Guild ID: {self.guild_id}
        Command Name: {self.command_name}
        Guild Member Count: {self.guild_member_count}
        Interaction Language: {self.interaction_language}
        Interaction Data: {self.interaction_data}
        Time: {self.time}
        """

class PaginatorView(discord.ui.View):
    def __init__(self, embeds, user_id):
        super().__init__(timeout=30)
        self.embeds = embeds
        self.user_id = user_id
        self.current_page = 0
        self.total_pages = len(embeds)
        self.add_buttons()
        self.message : discord.Message

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(FirstButton(style=discord.ButtonStyle.primary if self.current_page > 0 else discord.ButtonStyle.secondary, label='First', disabled=not (self.current_page > 0), user_id=self.user_id))
        self.add_item(PreviousButton(style=discord.ButtonStyle.primary if self.current_page > 0 else discord.ButtonStyle.secondary, label='Previous', disabled=not (self.current_page > 0), user_id=self.user_id))

        self.add_item(PageNumberButton(label=f"Page {self.current_page + 1}/{self.total_pages}", user_id=self.user_id))

        self.add_item(NextButton(style=discord.ButtonStyle.primary if self.current_page < self.total_pages - 1 else discord.ButtonStyle.secondary, label='Next', disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))
        self.add_item(LastButton(style=discord.ButtonStyle.primary if self.current_page < self.total_pages - 1 else discord.ButtonStyle.secondary, label='Last', disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))

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
            logging.error("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

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

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: PaginatorView = self.view
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)

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
        f"Lead:      {generate_difficulty_bar(difficulty_data.get('gr', 0))} "
        f"Bass:      {generate_difficulty_bar(difficulty_data.get('ba', 0))} "
        f"Drums:     {generate_difficulty_bar(difficulty_data.get('ds', 0))}\n"
        f"Pro Lead:  {generate_difficulty_bar(difficulty_data.get('pg', 0))} "
        f"Pro Bass:  {generate_difficulty_bar(difficulty_data.get('pb', 0))} "
        f"Vocals:    {generate_difficulty_bar(difficulty_data.get('vl', 0))}"
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