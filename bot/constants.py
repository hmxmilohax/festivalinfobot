import sys
import importlib
import subprocess
from typing import Literal
from configparser import ConfigParser
from datetime import datetime, timezone
import enum
import hashlib
import json
import logging
import os

import discord
import requests
import secrets

from discord.ext import commands, tasks
from bot import database

class BotExt(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.config: database.Config
        super().__init__(*args, **kwargs)

RAW_JAM_TRACK_CACHE = None
JAM_TRACK_CACHE = None
JAM_TRACK_CACHED_AT: datetime = datetime.now(timezone.utc)

# Folder where local JSON files are stored
LOCAL_JSON_FOLDER = "json/"
if not os.path.exists(LOCAL_JSON_FOLDER):
    os.makedirs(LOCAL_JSON_FOLDER)

CACHE_FOLDER = "cache/"
if not os.path.exists(CACHE_FOLDER):
    os.makedirs(CACHE_FOLDER)

MIDI_FOLDER = "cache/midi/"
if not os.path.exists(MIDI_FOLDER):
    os.makedirs(MIDI_FOLDER)

PREVIEW_FOLDER = "cache/previews/"
if not os.path.exists(PREVIEW_FOLDER):
    os.makedirs(PREVIEW_FOLDER)

TEMP_FOLDER = "temp/"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

config = ConfigParser()
config.read('config.ini')
BOT_OWNERS: list[int] = [int(uid) for uid in config.get('bot', 'bot_owners', fallback="").split(', ')]
TEST_GUILD: int = int(config.get('bot', 'testing_guild'))
ERR_CHANNEL: int = int(config.get('bot', 'error_channel'))
LOG_CHANNEL: int = int(config.get('bot', 'event_channel'))
SUG_CHANNEL: int = int(config.get('bot', 'suggest_channel'))
ANALYTICS_CHANNEL: int = int(config.get('bot', 'analytics_channel'))

SPOTIFY_CLIENT_ID: str = config.get('bot', 'spotify_api_client')
SPOTIFY_CLIENT_PASS: str = config.get('bot', 'spotify_api_secret')

GITHUB_PAT: str = config.get('bot', 'github_pat')
ODESLI_API_KEY: str = config.get('bot', 'odesli_api_key')

EPIC_ACCOUNT_ID: str = config.get('bot', 'epic_account_id')
EPIC_DEVICE_ID: str = config.get('bot', 'epic_device_id')
EPIC_DEVICE_SECRET: str = config.get('bot', 'epic_device_secret')
EPIC_DEVICE_AUTH_CLIENT_ID: str = config.get('bot', 'epic_device_auth_client_id')
EPIC_DEVICE_AUTH_CLIENT_SECRET: str = config.get('bot', 'epic_device_auth_client_secret')

IS_DEVELOPER_ENVIRONMENT = config.getboolean('bot', 'is_developer_environment', fallback=False)

SPARKS_MIDI_KEY: str = config.get('bot', 'sparks_midi_key') #b64
AGREEMENTS_DATA = json.loads(open('bot/agreements/index.json', 'r').read())

SEASONS = {
    1: 'evergreen',
    2: 'season002',
    3: 'season003',
    4: 'season004',
    5: 'season005',
    6: 'season006',
    7: 'season007',
    8: 'season008',
    9: 'season009',
    10: 'season010',
    11: 'season011',
    12: 'season012',
    13: 'season013',
    14: 'season014',
    15: 'season015'
}
SEASON_NUMBER = 15

ERROR_COLOUR = 0xbe2625
SUCCESS_COLOUR = 0x3AB00B

keyart_config = ConfigParser()
keyart_config.read('bot/data/KeyArt/KeyArtOptions.ini')
KEYART_FNAME: str = f"{keyart_config.get('keyart', 'fname')}.{keyart_config.get('keyart', 'ext')}"
KEYART_PATH: str = f"bot/data/KeyArt/{KEYART_FNAME}"

def get_season_lb_str(season: int = SEASON_NUMBER) -> str:
    return SEASONS[season]

# Files used to track songs
SONGS_FILE = 'known_tracks.json'  # File to save known songs
SHORTNAME_FILE = 'known_songs.json'  # File to save known shortnames

# APIs which the bot uses to source its information
FN_CONTENT = 'https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks'
FN_CALENDAR = 'https://fngw-mcp-gc-livefn.ol.epicgames.com/fortnite/api/calendar/v1/timeline'
FN_CATALOG = 'https://fngw-mcp-gc-livefn.ol.epicgames.com/fortnite/api/storefront/v2/catalog'

ERROR_EMOJI = '<:error:1349038414644641864>'
SUCCESS_EMOJI = '<:checkmark:1349038447385645157>'
PREVIOUS_EMOJI = '<:prevpage:1349038290640175184>'
NEXT_EMOJI = '<:nextpage:1349038328296636448>'
FIRST_EMOJI = '<:firstpage:1349038244624339066>'
LAST_EMOJI = '<:lastpage:1349038218430906368>'
UP_EMOJI = '<:up:1349038214203179088>'
DOWN_EMOJI = '<:down:1349038099447021680>'
SEARCH_EMOJI = '<:search:1349038056006746162>'
INFORMATION_EMOJI = '<:information:1349037772765139065>'

LEAD_EMOJI = '<:guitar:1349038583125639261>'
BASS_EMOJI = '<:bass:1349038611944837140>'
DRUMS_EMOJI = '<:drums:1349038567502123128>'
VOCALS_EMOJI = '<:vocals:1349038596841279539>'
PRO_LEAD_EMOJI = '<:proguitar:1349038539517591606>'
PRO_BASS_EMOJI = '<:probass:1349038554797310096>'
PRO_DRUMS_EMOJI = '<:drums:1349038567502123128>'
PRO_VOCALS_EMOJI = '<:vocals:1349038596841279539>'
PRO_KEYTAR_EMOJI = '<:prokeyar:1349038526968102993>'

# brand                 (139, 79, 176)
# [13] chappell         (241, 138, 181)
# [14] laufey           (71, 132, 178)
# [14] esdeekid         (0, 0, 0)
# [14] olivia rodrigo   (246, 192, 215)
# [15] lil tecca        (45, 52, 80)
# [15] addiSON rae      (251, 131, 202)
SEASON_COLOUR = (45, 52, 80)

# DO NOT USE
SEASON_COLOUR_COPY = tuple(c for c in SEASON_COLOUR)

# invert the colour if in developer environment 
if IS_DEVELOPER_ENVIRONMENT:
    SEASON_COLOUR = tuple(255 - c for c in SEASON_COLOUR)

ACCENT_COLOUR = (SEASON_COLOUR[0] << 16) + (SEASON_COLOUR[1] << 8) + SEASON_COLOUR[2]

VOTING_IS_ENABLED = False

# lil tecca
HEADLINER_SONGS = [
    'ransom',
    'darkthoughts',
    'loveme',
    'fivehundredlbs'
]

# no collab at the moment
HEADLINER_COLLAB_SONGS = []

SIMPLE_COMPARISONS = {
    'tt': 'Title',
    'an': 'Artist',
    'ab': 'Album',
    'sn': 'Shortname',
    'ry': 'Release Year',
    'dn': 'Duration',
    'jc': 'Jam Loop Mnemonic Code',
    'ti': 'Placeholder ID',
    'mm': 'Mode',
    'mk': 'Key',
    'su': 'Leaderboard Event ID',
    'isrc': 'International Standard Recording Code',
    'ar': 'ESRB Rating',
    'au': 'Album Art URL',
    'siv': 'Tap Vocals Starting Instrument',
    'sib': 'Bass Starting Instrument',
    'sid': 'Drums Starting Instrument',
    'sig': 'Guitar Starting Instrument',
    'mt': 'BPM',
    'ld': 'Lip Sync Asset URL',
    'mu': 'Chart URL',
    'ge': 'Genres',
    'gt': 'Gameplay Tags',
    'mmo': 'Music Moment Offset',
    'nu': 'New Until Date',
    'tb': 'Quest Thumbnail',
    'sm': 'Stage Mood',
    'ag': 'Animation Genre',
    'ci': 'Count-in Duration'
}

DIFFICULTY_COMPARISONS = {
    'pb': 'Pro Bass',
    'pd': 'Pro Drums',
    'pg': 'Pro Lead',
    'vl': 'Tap Vocals',
    'gr': 'Lead',
    'ds': 'Drums',
    'ba': 'Bass',
    'bd': 'Karaoke'
}

EXTRA_COMPARISONS = {
    'dn': 'Track Number',
    '_type': 'Track Type',
    '_noIndex': 'No Index Flag',
    '_activeDate': 'Active Date',
    '_locale': 'Locale',
    '_templateName': 'Template Name'
}

from bot.tools.oauthmanager import OAuthManager
OAUTH_MANAGER: OAuthManager = None

from bot.tools.taskregistry import TASK_REGISTRY, register_task

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

class StandaloneSimpleBtn(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.callback = kwargs.pop('on_press')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if self.callback:
            await self.callback(interaction)

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
    def __init__(self, on_press:any, label:str, emoji: str = None, restrict: bool = True, url: str = None, style: discord.ButtonStyle = None, disabled: bool = False, thinking: bool = False, ephmeral: bool = False):
        self.on_press = on_press
        self.label = label
        self.emoji = emoji
        self.restrict = restrict
        self.url = url
        self.style = style
        self.disabled = disabled
        self.thinking = thinking
        self.ephmeral = ephmeral

class ViewButton(discord.ui.Button):
    def __init__(self, on_press:any, label:str, emoji: str = None, restrict: bool = True, url: str = None, style: discord.ButtonStyle = None, disabled: bool = False, thinking: bool = False, ephmeral: bool = False):
        self._on_press = on_press
        self._restrict = restrict
        self._url = url
        self._style = style or discord.ButtonStyle.primary
        self._label = label
        self._emoji = emoji
        self._disabled = disabled
        self._thinking = thinking
        self._ephmeral = ephmeral

        super().__init__(style=self._style, label=self._label, url=self._url, emoji=self._emoji, disabled=self._disabled)

    async def callback(self, interaction: discord.Interaction):
        view: ButtonedView = self.view
        if interaction.user.id != view.user_id and self._restrict:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view.add_buttons()
        await interaction.response.defer(ephemeral=self._ephmeral, thinking=self._thinking)
        if self._on_press:
            await self._on_press(interaction)

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
                disabled=button.disabled,
                thinking=button.thinking,
                ephmeral=button.ephmeral
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
    def __init__(self, 
    english:str = "Tap Vocals", 
    lb_code:str = "Solo_Vocals", 
    plastic:bool = False, 
    chopt:str = "vocals", 
    midi:str = "PART VOCALS", 
    replace:str = None, 
    lb_enabled:bool = True, 
    path_enabled: bool = True, 
    emoji: str = None,
    binary_id: int = 1
    ) -> None:
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
        self.path_enabled = path_enabled
        self.emoji = emoji
        self.binary_id = binary_id

    def __str__(self) -> str:
        return f"Instrument({self.english=}, {self.lb_code=}, {self.plastic=}, {self.chopt=}, {self.midi=}, {self.replace=}, {self.lb_enabled=}, {self.path_enabled=}, {self.emoji=}, {self.binary_id=})".replace('self.', '')
    
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

class BandType:
    def __init__(self, english:str = "Duos", code: str = 'Duets') -> None:
        self.english = english
        self.code = code

    def __str__(self) -> str:
        return f"BandType({self.english=}, {self.code=})".replace('self.', '')
    
class AllTimeLBType:
    def __init__(self, english:str = "Lead", code: str = 'Solo_Guitar', is_band = False) -> None:
        self.english = english
        self.code = code
        self.is_band = is_band

    def __str__(self) -> str:
        return f"AllTimeLBType({self.english=}, {self.code=})".replace('self.', '')

class KeyType:
    def __init__(self, english:str = "A", code: str = 'A') -> None:
        self.english = english
        self.code = code

    def __str__(self) -> str:
        return f"KeyType({self.english=}, {self.code=})".replace('self.', '')
        
class ModeType:
    def __init__(self, english:str = "Major", code: str = 'Major') -> None:
        self.english = english
        self.code = code

    def __str__(self) -> str:
        return f"ModeType({self.english=}, {self.code=})".replace('self.', '')

class Instruments(enum.Enum):
    MicVocals = Instrument(
        english="Karaoke", 
        lb_code="Solo_PeripheralVocals", 
        plastic=True, 
        chopt="karaoke", 
        midi="PRO VOCALS", 
        lb_enabled=True,
        emoji="<:provocals:1464755018052931708>"
        )
    Lead = Instrument(
        english="Lead", 
        lb_code="Solo_Guitar", 
        chopt="guitar", 
        midi="PART GUITAR", 
        emoji="<:guitar:1327742677856420003>"
        )
    Bass = Instrument(
        english="Bass", 
        lb_code="Solo_Bass", 
        chopt="bass", 
        midi="PART BASS", 
        emoji="<:bass:1327742687025168555>"
        )
    Drums = Instrument(
        english="Drums", 
        lb_code="Solo_Drums", 
        chopt="drums", 
        midi="PART DRUMS", 
        emoji="<:drums:1327742563762835598>"
        )
    Vocals = Instrument(
        english="Tap Vocals", 
        lb_code="Solo_Vocals", 
        chopt="vocals", 
        midi="PART VOCALS", 
        emoji="<:vocals:1327742697695350936>"
        )
    ProLead = Instrument(
        english="Pro Lead", 
        lb_code="Solo_PeripheralGuitar", 
        plastic=True, 
        chopt="proguitar", 
        midi="PLASTIC GUITAR", 
        emoji="<:proguitar:1327742543571583179>"
        )
    ProBass = Instrument(
        english="Pro Bass", 
        lb_code="Solo_PeripheralBass", 
        plastic=True, 
        chopt="probass", 
        midi="PLASTIC BASS", 
        emoji="<:probass:1327742553558093858>"
        )
    ProDrums = Instrument(
        english="Pro Drums", 
        lb_code="Solo_PeripheralDrum", 
        plastic=True, 
        chopt="prodrums", 
        midi="PLASTIC DRUMS", 
        lb_enabled=True, 
        emoji="<:prodrums:1464755636796526776>"
        )
    ProCymbals = Instrument(
        english="Pro Drums + Cymbals", 
        lb_code="Solo_PeripheralCymbals", 
        plastic=True, 
        chopt="prodrums", 
        midi="PLASTIC DRUMS", 
        lb_enabled=True,
        path_enabled=False, 
        emoji="<:prodrums:1464755636796526776>"
        )

    # The @classmethod decorator just works!
    @classmethod
    def getall(self) -> list[Instrument]:
        return [self.ProLead.value, self.ProBass.value, self.ProDrums.value, self.ProCymbals.value, self.Bass.value, self.Lead.value, self.Drums.value, self.Vocals.value, self.MicVocals.value]

class Difficulties(enum.Enum):
    Expert = Difficulty()
    Hard = Difficulty(english="Hard", chopt="hard", pitch_ranges=[84, 88], diff_4k=True)
    Medium = Difficulty(english="Medium", chopt="medium", pitch_ranges=[72, 76], diff_4k=True)
    Easy = Difficulty(english="Easy", chopt="easy", pitch_ranges=[60, 64], diff_4k=True)

    @classmethod
    def getall(self) -> list[Difficulty]:
        return [self.Expert.value, self.Hard.value, self.Medium.value, self.Easy.value]
    
class BandTypes(enum.Enum):
    Duos = BandType()
    Trios = BandType(english="Trios", code="Trios")
    Squads = BandType(english="Squads", code="Quad")

    # The @classmethod decorator just works!
    @classmethod
    def getall(self) -> list[Instrument]:
        return [self.Duos.value, self.Trios.value, self.Squads.value]
    
class AllTimeLBTypes(enum.Enum):
    Lead = AllTimeLBType()
    Drums = AllTimeLBType(english="Drums", code="Solo_Drums")
    Bass = AllTimeLBType(english="Bass", code="Solo_Bass")
    Vocals = AllTimeLBType(english="Tap Vocals", code="Solo_Vocals")
    ProLead = AllTimeLBType(english="Pro Lead", code="Solo_PeripheralGuitar")
    ProBass = AllTimeLBType(english="Pro Bass", code="Solo_PeripheralBass")
    ProDrums = AllTimeLBType(english="Pro Drums", code="Solo_PeripheralDrum")
    ProCymbals = AllTimeLBType(english="Pro Drums + Cymbals", code="Solo_PeripheralCymbals")
    MicVocals = AllTimeLBType(english="Karaoke", code="Solo_PeripheralVocals")
    BandDuos = AllTimeLBType(english="Band Duos", code="Band_Duets", is_band=True)
    BandTrios = AllTimeLBType(english="Band Trios", code="Band_Trios", is_band=True)
    BandSquads = AllTimeLBType(english="Band Squads", code="Band_Quad", is_band=True)
    
class KeyTypes(enum.Enum):
    A =         KeyType(english="A", code="A")
    BbASharp =  KeyType(english="A# / B♭", code="Bb")
    B =         KeyType(english="B", code="B")
    C =         KeyType(english="C", code="C")
    DbCSharp =  KeyType(english="C# / D♭", code="Db")
    D =         KeyType(english="D", code="D")
    EbDSharp =  KeyType(english="D# / E♭", code="Eb")
    E =         KeyType(english="E", code="E")
    F =         KeyType(english="F", code="F")
    GbFSharp =  KeyType(english="F# / G♭", code="Gb")
    G =         KeyType(english="G", code="G")
    AbGSharp =  KeyType(english="G# / A♭", code="Ab")

    # The @classmethod decorator just works!
    @classmethod
    def getall(self) -> list[KeyType]:
        return [self.A.value,
            self.BbASharp.value,
            self.B.value,
            self.C.value,
            self.DbCSharp.value,
            self.D.value,
            self.EbDSharp.value,
            self.E.value,
            self.F.value,
            self.GbFSharp.value,
            self.G.value,
            self.AbGSharp.value]
    
class ModeTypes(enum.Enum):
    Major = ModeType(english="Major", code="Major")
    Minor = ModeType(english="Minor", code="Minor")

    @classmethod
    def getall(self) -> list[ModeType]:
        return [self.Major.value, self.Minor.value]

def get_jam_tracks(use_cache: bool = False, max_cache_age: int = 300):
    max_cache_age = max_cache_age - 2 # the libraries are too accurate man

    global JAM_TRACK_CACHE, JAM_TRACK_CACHED_AT
    content_url = FN_CONTENT

    logging.debug(f'[GET] {content_url}')
    try:
        cache_age_too_old = False
        if JAM_TRACK_CACHED_AT is not None:
            cache_age = (datetime.now(timezone.utc) - JAM_TRACK_CACHED_AT).total_seconds()
            cache_age_too_old = cache_age > max_cache_age

        if use_cache and JAM_TRACK_CACHE is not None and not cache_age_too_old:
            data = JAM_TRACK_CACHE
            logging.debug('[JTC] Using cached data')
        else:
            response = requests.get(content_url)
            response.raise_for_status()
            data = response.json()
            
            if use_cache:
                logging.debug('[JTC] Cache will be updated')
                JAM_TRACK_CACHED_AT = datetime.now(timezone.utc)

        JAM_TRACK_CACHE = data

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
        f"<:guitar:1349038583125639261> {difficulty_data.get('gr', 0) + 1}/7 "
        f"<:bass:1349038611944837140> {difficulty_data.get('ba', 0) + 1}/7 "
        f"<:drums:1349038567502123128> {difficulty_data.get('ds', 0) + 1}/7 "
        f"<:proguitar:1349038539517591606> {difficulty_data.get('pg', 0) + 1}/7 "
        f"<:probass:1349038554797310096> {difficulty_data.get('pb', 0) + 1}/7 "
        f"<:vocals:1349038596841279539> {difficulty_data.get('vl', 0) + 1}/7"
    )

def generate_difficulty_bar(difficulty, max_blocks=7, append_real_diff: bool = False):
    scaled_difficulty = min(difficulty, 6) + 1
    filled_blocks = '■' * scaled_difficulty
    empty_blocks = '□' * (max_blocks - scaled_difficulty)
    if append_real_diff:
        return filled_blocks + empty_blocks + f" [{scaled_difficulty}/7]"
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
        embed = discord.Embed(title=title, colour=ACCENT_COLOUR)
        chunk = track_list[i:i + chunk_size]

        for track in chunk:
            embed.add_field(
                name="",
                value=f"**\\• {track['track']['tt']}** - *{track['track']['an']}*",
                inline=False
            )

        embeds.append(embed)

    return embeds

def format_date(date_string, fmt: Literal['D', 'F', 'R', 'T', 'd', 'f', 't'] = 'D'):
    if date_string:
        date_ts = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return discord.utils.format_dt(date_ts, fmt)
    return "Unknown"

def add_fields(track_data, embed, weekly_tracks, shop_tracks):
    track_devname = track_data['track']['sn']
    weekly_track = discord.utils.find(lambda offer: offer['metadata']['track']['sn'] == track_devname, weekly_tracks)

    status_text = []

    if weekly_track != None:
        text = "* Currently in the Free Jam Track Rotation"

        if weekly_track['in_spotlight'] == True:
            text += " and Spotlight"

        text += "."
        
        status_text.append(text)

    shop_entry = discord.utils.find(lambda offer: offer['meta']['templateId'] == track_data['track']['ti'], shop_tracks)

    if shop_entry:
        out_date = shop_entry['meta'].get('outDate')
        status_text.append(f"* Currently in the Shop until {format_date(out_date)}.")

    if len(status_text) > 0:
        embed.add_field(name="Item Shop & Rotation", value="\n".join(status_text), inline=False)
    
def common_error_embed(text) -> discord.Embed:
    return discord.Embed(colour=0xbe2625, title="Error", description=f"{ERROR_EMOJI} {text}")

def common_success_embed(text) -> discord.Embed:
    return discord.Embed(colour=0x3AB00B, title="Success", description=f"{SUCCESS_EMOJI} {text}")

def tz():
    return f'[`{datetime.now(timezone.utc).isoformat().replace('T', ' ').replace('Z', '').replace('+00:00', '')[:-3]}`]'

def rand_hex(from_str: str) -> str:
    return secrets.token_hex(len(from_str) // 2)

async def msg_log(bot_instance: discord.Client, log_str: str):
    await bot_instance.get_partial_messageable(LOG_CHANNEL).send(content=f"{tz()} {log_str}")

def get_remote_url():
    try:
        return subprocess.check_output(['git', 'config', '--get', 'remote.origin.url']).strip().decode('utf-8')
    except Exception:
        return "Unknown"

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

def fetch_latest_github_commit_hash():
    repo_url = "https://api.github.com/repos/hmxmilohax/festivalinfobot/commits"
    logging.debug(f'[GET] {repo_url}')
    response = requests.get(repo_url)
    if response.status_code == 200:
        latest_commit = response.json()[0]
        commit_hash = latest_commit['sha']
        return commit_hash
    return "Unknown"

def get_local_commit_hash():
    try:
        commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode('utf-8')
        return commit_hash
    except Exception as e:
        logging.error(f"Error getting local commit info", exc_info=e)
        return "Unknown"

def get_loaded_package_versions() -> dict[str, str]:
    module_to_dist = importlib.metadata.packages_distributions()
    
    package_versions = {}
    for loaded_module in list(sys.modules.keys()):
        top_level = loaded_module.split('.')[0]
        
        if top_level.startswith('_'):
            continue
            
        dists = module_to_dist.get(top_level)
        if dists:
            for dist in dists:
                if dist not in package_versions:
                    try:
                        package_versions[dist] = importlib.metadata.version(dist)
                    except importlib.metadata.PackageNotFoundError:
                        pass

    return dict(sorted(package_versions.items()))

def iso_to_unix_timestamp(iso_time_str):
    try:
        dt = datetime.fromisoformat(iso_time_str.replace('Z', '+00:00'))
        return dt
    except ValueError:
        return None

def fast_check_note_in_midi(file_path: str = None, file_bytes: bytes = None, note: int = 95) -> bool:
    # written by gemini because midi is the worst file format ever (mido is slow)
    data = None

    if file_path:
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
        except IOError:
            print(f"Error reading {file_path}")
            return False
    
    if file_bytes is not None:
        data = file_bytes
    
    elif not data:
        raise ValueError("No file_path or file_bytes provided")

    try:
        # Check for MThd (Standard MIDI File Header)
        if data[0:4] != b'MThd':
            return False
            
        # Standard MThd is usually 14 bytes (4 magic, 4 length, 6 data)
        idx = 14 
        length = len(data)

        # Iterate through chunks (MTrk)
        while idx < length:
            chunk_type = data[idx:idx+4]
            chunk_len = int.from_bytes(data[idx+4:idx+8], 'big')
            idx += 8
            
            if chunk_type == b'MTrk':
                track_end = idx + chunk_len
                status = 0 # Holds the current Running Status
                
                while idx < track_end:
                    # 1. Skip Delta Time (Variable Length Quantity)
                    # High bit (0x80) indicates another byte follows
                    while data[idx] & 0x80:
                        idx += 1
                    idx += 1 
                    
                    if idx >= track_end: 
                        break
                    
                    # 2. Check for Event Status Byte
                    event_byte = data[idx]
                    if event_byte & 0x80:
                        status = event_byte
                        idx += 1
                    # If the high bit is 0, it's a "Running Status" 
                    
                    if idx >= track_end: 
                        break
                    
                    # 3. Process Event based on Status
                    event_type = status & 0xF0
                    
                    if event_type == 0x90 or event_type == 0x80: 
                        # Note On (0x90) or Note Off (0x80)
                        if data[idx] == note:
                            return True # Short-circuit
                        idx += 2 # Skip the note and velocity bytes
                        
                    elif event_type in (0xA0, 0xB0, 0xE0):
                        # Aftertouch, Control Change, Pitch Bend (all 2 data bytes)
                        idx += 2 
                        
                    elif event_type in (0xC0, 0xD0):
                        # Program Change, Channel Pressure (all 1 data byte)
                        idx += 1 
                        
                    elif status == 0xFF: 
                        # Meta Event
                        idx += 1 # Skip Meta Type byte
                        
                        # Parse VLQ to find the length of the meta event data
                        vlq_len = 0
                        while True:
                            b = data[idx]
                            idx += 1
                            vlq_len = (vlq_len << 7) | (b & 0x7F)
                            if not (b & 0x80): 
                                break
                        idx += vlq_len # Jump over the meta text/data
                        
                    elif status in (0xF0, 0xF7): 
                        # SysEx Event
                        # Parse VLQ to find the length of the SysEx data
                        vlq_len = 0
                        while True:
                            b = data[idx]
                            idx += 1
                            vlq_len = (vlq_len << 7) | (b & 0x7F)
                            if not (b & 0x80): 
                                break
                        idx += vlq_len # Jump over the SysEx data
            else:
                # If it's a non-MTrk chunk (like proprietary sequencer data), skip it completely
                idx += chunk_len
                
    except IndexError:
        print(f'midi length is {len(data)}')
        pass
        
    return False