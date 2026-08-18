from os import access
from datetime import tzinfo
import re
from bot.tracks import JamTrackHandler
from requests.models import HTTPError
from datetime import datetime, timedelta, timezone
from os import makedirs
import os
from bot import constants
import logging
import discord
import requests
import json
import urllib.parse

# this class handles the streaming services option in action menu dropdown
class StreamingServicesManager:
    def __init__(self):
        self.oauth_manager = constants.OAUTH_MANAGER
        self.do_not_request_odesli_until: datetime = None
        self.supported_countries = [
            "US",
            "GB",
            "BG",
            "CN",
            "TW",
            "HR",
            'CZ',
            'ID',
            'DK',
            'NL',
            'FI',
            'FR',
            'DE',
            'GR',
            'IN',
            'HU',
            'IT',
            'JP',
            'KR',
            'US',
            'LT',
            'NO',
            'PL',
            'BR',
            'RO',
            'RU',
            'SE',
            'TH',
            'TR',
            'UA',
            'VN',
            'ES'
        ]
        self.emojis_per_distributor = {
            'spotify': '<:spotify:1539109510981886072>',
            'appleMusic': '<:appleMusic:1539109509782577214>',
            'youtube': '<:youtube:1539109508599517274>',
            'youtubeMusic': '<:youtubeMusic:1539109507614122034>',
            'deezer': '<:deezer:1539109506565546156>',
            'tidal': '<:tidal:1539109505785274469>',
            'amazonMusic': '<:amazonMusic:1539109504443093042>',
            'soundcloud': '<:soundcloud:1539109503092523028>',
            'yandex': '<:yandex:1539109502320906310>',
            'audius': '<:audius:1539109501385310248>',
            'anghami': '<:anghami:1539109500324151426>',
            'boomplay': '<:boomplay:1539109499510722581>',
            'audiomack': '<:audiomack:1539109498608943124>'
        }
        self.search_handler = JamTrackHandler(None)

    def get_spotify_data(self, track_data: any, isrc: str, market: str | None = None):
        if not self.oauth_manager:
            raise ValueError('OAuthManager instance is required to get Spotify link.')
        
        normalized_isrc = isrc.lstrip().rstrip()

        params = {
            "q": f'isrc:{normalized_isrc}',
            "type": "track",
            "limit": 15,
            "offset": 0
        }

        if market:
            params['market'] = market

        song_url = f'https://api.spotify.com/v1/search?{urllib.parse.urlencode(params)}'

        client_token = self.oauth_manager._spotify_access_token
        logging.debug(f'[GET] {song_url}')
        link = requests.get(song_url, headers={'Authorization': f'Bearer {client_token}'})

        try:
            link.raise_for_status()
        except Exception as e:
            logging.error(f'Spotify Link GET returned {link.status_code}', exc_info=e)
            return None
        
        result = link.json()

        with open('spotify_result.json', 'w') as f:
            f.write(json.dumps(result, indent=4))

        return result

    def get_album(self, spotify_album_id: str, market: str | None = None):
        if not self.oauth_manager:
            raise ValueError('OAuthManager instance is required to get Spotify link.')
        
        normalized_album_id = spotify_album_id.lstrip().rstrip()

        album_url = f'https://api.spotify.com/v1/albums/{normalized_album_id}'
        if market:
            album_url += f'?market={market}'

        client_token = self.oauth_manager._spotify_access_token
        logging.debug(f'[GET] {album_url}')
        album = requests.get(album_url, headers={'Authorization': f'Bearer {client_token}'})

        try:
            album.raise_for_status()
        except Exception as e:
            logging.error(f'Spotify Album GET returned {album.status_code}', exc_info=e)
            return None
        
        result = album.json()

        with open('spotify_album_result.json', 'w') as f:
            f.write(json.dumps(result, indent=4))

        return result
        
    def fetch_odesli_data(self, spotify_uri: str, user_country: str):
        url = f"https://api.odesli.co/matches?url={spotify_uri}&userCountry={user_country}&key={constants.ODESLI_API_KEY}"
        logging.debug(f'[GET] {url}')

        odesli = requests.get(url)
        odesli.raise_for_status()
        result = odesli.json()
        return result

    def get_cached_odesli_data(self, shortname: str, spotify_uri: str, file_sub_identifier: str, user_country: str, auto_fetch: bool = False):
        cache_file = os.path.join(constants.CACHE_FOLDER, 'odesli', f'{shortname}.{user_country}.json')
        if file_sub_identifier:
            cache_file = os.path.join(constants.CACHE_FOLDER, 'odesli', f'{shortname}.{user_country}.{file_sub_identifier}.json')

        if user_country not in self.supported_countries:
            user_country = "US"

        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        else:
            if not auto_fetch:
                return None

            try:
                if self.do_not_request_odesli_until:
                    if datetime.now(timezone.utc) < self.do_not_request_odesli_until:
                        return None
                    self.do_not_request_odesli_until = None
                    
                odesli_data = self.fetch_odesli_data(spotify_uri, user_country)
            except HTTPError as e:
                if e.response.status_code == 429:
                    logging.error(exc_info=e)
                    self.do_not_request_odesli_until = datetime.now(timezone.utc) + timedelta(minutes=1, seconds=5)

                    # try US fallback
                    if user_country != 'US':
                        return self.get_cached_odesli_data(shortname=shortname, spotify_uri=spotify_uri, user_country="US")
                    else:
                        # try any other country
                        for country in self.supported_countries:
                            country_path = os.path.join(constants.CACHE_FOLDER, 'odesli', f'{shortname}.{country}.json')
                            if os.path.exists(country_path):
                                return json.load(open(country_path, 'r'))

                return None

            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(odesli_data, f, indent=4)
            return odesli_data

    def get_user_country(self, locale: str):
        return {
            'en-US': 'US',
            'en-GB': 'GB',
            'bg': 'BG',
            'zh-CN': 'CN',
            'zh-TW': 'TW',
            'hr': 'HR',
            'cs': 'CZ',
            'id': 'ID',
            'da': 'DK',
            'nl': 'NL',
            'fi': 'FI',
            'fr': 'FR',
            'de': 'DE',
            'el': 'GR',
            'hi': 'IN',
            'hu': 'HU',
            'it': 'IT',
            'ja': 'JP',
            'ko': 'KR',
            'es-419': 'US',
            'lt': 'LT',
            'no': 'NO',
            'pl': 'PL',
            'pt-BR': 'BR',
            'ro': 'RO',
            'ru': 'RU',
            'sv': 'SE',
            'th': 'TH',
            'tr': 'TR',
            'uk': 'UA',
            'vi': 'VN',
            'es-ES': 'ES'
        }.get(locale, 'US')

    async def handle_track_interaction(self, interaction: discord.Interaction, track_shortname: str, private: bool = True):
        await interaction.response.defer(thinking=private, ephemeral=private)
        
        tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=600)
        matched_track = self.search_handler.fuzzy_search_tracks(tracks, track_shortname)
        if not matched_track:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"The search query \"{track_shortname}\" did not yield any results."))
            return
        track = matched_track[0]

        track_shortname = track['track']['sn']
        
        # for now, all we do is spotify and song.link
        # we can add more later
        
        # craft cv2 view
        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_colour=constants.ACCENT_COLOUR)
        new_container = discord.ui.Container(accent_colour=constants.ACCENT_COLOUR)
        view.add_item(container)

        market = self.get_user_country(interaction.locale.value)
        isrc = track['track'].get('isrc', None)
        shortname = track['track']['sn']

        if isrc:
            normalized_isrc = isrc.lstrip().rstrip()
            spotify_data = self.get_spotify_data(track_data=track, isrc=normalized_isrc, market=market)
            if not spotify_data:
                return

            items = spotify_data['tracks']['items']
            if len(items) > 0:
                # find first that is the isrc result
                item = discord.utils.find(lambda i: i.get('external_ids', {}).get('isrc', '') == normalized_isrc, items)
                print(item)
                spotify_url = item['external_urls'].get('spotify', None)
                spotify_uri = item['uri']
                odesli_data = self.get_cached_odesli_data(
                    shortname=shortname, 
                    file_sub_identifier=None,
                    spotify_uri=spotify_uri, 
                    user_country=market,
                    auto_fetch=True
                )

                explicit_label = "<:explicit:1539105312542564372>" if item.get('explicit', False) else ""

                container.add_item(
                    discord.ui.Section(
                        # TODO: explicit emoji
                        discord.ui.TextDisplay(f"## Stream Track"),
                        discord.ui.TextDisplay(f"{explicit_label} **{track['track']['tt']}**\n*{track['track']['an']}*"),
                        discord.ui.TextDisplay(f"<:pow1:1539103869471162458><:pow2:1539103868154159175><:pow3:1539103867193524344><:pow4:1539103866274971759>\n<:pow5:1539103865503227924><:pow6:1539103864723079198><:pow7:1539103863938879508><:pow8:1539103863049814116>"),
                        accessory=discord.ui.Thumbnail(
                            track['track']['au']
                        )
                    )
                )

                container.add_item(discord.ui.Separator())

                if odesli_data:
                    current_row = discord.ui.ActionRow()
                    if odesli_data.get('pageUrl'):
                        current_row.add_item(
                            discord.ui.Button(
                                emoji="<:odesli:1539110592097554483>",
                                url=odesli_data['pageUrl'],
                                style=discord.ButtonStyle.link
                            )
                        )

                    prohibited_providers = [
                        "itunes",
                        "amazonStore",
                        "googleStore",
                        "google",
                        "napster",
                        "pandora",
                        "spinrilla"
                    ]

                    for provider, data in odesli_data.get('links', {}).items():
                        if provider in prohibited_providers:
                            continue

                        provider_url = data.get('url', None)
                        if not provider_url:
                            continue

                        if len(current_row.children) >= 4:
                            container.add_item(current_row)
                            current_row = discord.ui.ActionRow()

                        current_row.add_item(
                            discord.ui.Button(
                                emoji=self.emojis_per_distributor.get(provider, '<:music:1539115077028937738>'),
                                url=provider_url,
                                style=discord.ButtonStyle.link
                            )
                        )

                    if len(current_row.children) > 0:
                        container.add_item(current_row)

                # container.add_item(discord.ui.Separator())
                view.add_item(new_container)
                new_container.add_item(discord.ui.TextDisplay(f"## Featured in"))

                # find all 'single' and 'album' album types
                items_with_albums = list(filter(lambda item: item.get('album', {}).get('album_type', None) in ['single', 'album'], items))
                for a_item in items_with_albums:
                    # print(album)
                    album = a_item['album']
                    artists_list = list(map(lambda a: f'{a["name"]}', album['artists']))
                    artists_txt = ', '.join(artists_list)

                    pos_text = f"Track {a_item['track_number']} of {album['total_tracks']}"
                    if album['album_type'] == 'single':
                        pos_text = 'Single'

                    text1 = discord.ui.TextDisplay(
                        f"**{album['name']}**\n" +
                        f"*{artists_txt}*\n" +
                        album['release_date'].split('-')[0] + ' · ' + pos_text
                    )

                    section = discord.ui.Section(text1, accessory=StreamingViewButton('a', track_shortname, interaction.user.id, '1', album['id']))
                    new_container.add_item(section)

                    # container.add_item()

                new_container.add_item(discord.ui.Separator())
                new_container.add_item(
                    discord.ui.TextDisplay(
                        "-# Festival Tracker"
                    )
                )
            else:
                view = discord.ui.LayoutView(timeout=None)
                container.accent_colour = constants.ERROR_COLOUR
                container.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(f"## Stream Track"),
                        discord.ui.TextDisplay(f"**{track['track']['tt']}**\n*{track['track']['an']}*"),
                        discord.ui.TextDisplay(
                            f"{constants.ERROR_EMOJI} **Weird...** We can't seem to find any streaming links for this track."
                        ),
                        accessory=discord.ui.Thumbnail(
                            track['track']['au']
                        )
                    )
                )
                view.add_item(container)
        else:
            view = discord.ui.LayoutView(timeout=None)
            container.accent_colour = constants.ERROR_COLOUR
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(f"## Stream Track"),
                    discord.ui.TextDisplay(f"**{track['track']['tt']}**\n*{track['track']['an']}*"),
                    discord.ui.TextDisplay(
                        f"{constants.ERROR_EMOJI} **Unfortunately, we don't have an ISRC.** We can't find any streaming links for this track."
                    ),
                    accessory=discord.ui.Thumbnail(
                        track['track']['au']
                    )
                )
            )
            view.add_item(container)

        await interaction.edit_original_response(view=view)

    async def handle_album_interaction(self, interaction: discord.Interaction, track_shortname: str, private: bool = True, spotify_id: str = None):
        await interaction.response.defer(thinking=private, ephemeral=private)

        tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=600)
        matched_tracks = self.search_handler.fuzzy_search_tracks(tracks, track_shortname)
        if not matched_tracks:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"The search query \"{track_shortname}\" did not yield any results."))
            return
        track = matched_tracks[0]

        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container()
        container.accent_colour = constants.ACCENT_COLOUR
        view.add_item(container)

        market = self.get_user_country(interaction.locale.value)
        isrc = track['track'].get('isrc', None)
        shortname = track['track']['sn']

        # get spotify data
        album_data = self.get_album(spotify_album_id=spotify_id, market=market)
        artists = f"*{', '.join(map(lambda a: a['name'], album_data['artists']))}*"
        r_date = album_data['release_date']
        date_released = datetime.fromisoformat(r_date).astimezone(timezone.utc)
        date_formatted = discord.utils.format_dt(date_released, style='D')
        total_tracks = album_data['total_tracks']
        track_text = ''
        if album_data['album_type'] != 'single':
            track_text = f'{total_tracks} tracks'
        else:
            track_text = 'Single'

        initial_section = discord.ui.Section(
            discord.ui.TextDisplay(f"## Stream Album"),
            discord.ui.TextDisplay(f"**{album_data['name']}**\n{artists}\n{date_formatted} • {track_text}"),
            discord.ui.TextDisplay(f"<:pow1:1539103869471162458><:pow2:1539103868154159175><:pow3:1539103867193524344><:pow4:1539103866274971759>\n<:pow5:1539103865503227924><:pow6:1539103864723079198><:pow7:1539103863938879508><:pow8:1539103863049814116>"),
            # TODO: animated album art
            accessory=discord.ui.Thumbnail(
                album_data['images'][0]['url']
            )
        )

        spotify_uri = album_data['uri']
        spotify_id = album_data['id']
        odesli_data = self.get_cached_odesli_data(
            shortname=shortname, 
            spotify_uri=spotify_uri, 
            file_sub_identifier=f"album.{spotify_id}",
            user_country=market,
            auto_fetch=True
        )

        
        container.add_item(initial_section)
        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay(f"## {self.emojis_per_distributor['spotify']} Track List"))

        track_list_text = []

        for track in album_data['tracks']['items']:
            track_number = track['track_number']

            track_artists = []
            for artist in track['artists']:
                track_artists.append(f"[*{artist['name']}*]({artist['external_urls']['spotify']})")
            track_artists = ', '.join(track_artists)
            hyperlinked_track_name = f"[**{track['name']}**](https://song.link/s/{track['id']})"
            track_text = f"{track_number}. {hyperlinked_track_name} • {track_artists}"
            track_list_text.append(track_text)

        container.add_item(discord.ui.TextDisplay('\n'.join(track_list_text)))

        container.add_item(discord.ui.Separator())

        if odesli_data:
            current_row = discord.ui.ActionRow()
            if odesli_data.get('pageUrl'):
                current_row.add_item(
                    discord.ui.Button(
                        emoji="<:odesli:1539110592097554483>",
                        url=odesli_data['pageUrl'],
                        style=discord.ButtonStyle.link
                    )
                )

            prohibited_providers = [
                "itunes",
                "amazonStore",
                "googleStore",
                "google",
                "napster",
                "pandora",
                "spinrilla"
            ]

            for provider, data in odesli_data.get('links', {}).items():
                if provider in prohibited_providers:
                    continue

                provider_url = data.get('url', None)
                if not provider_url:
                    continue

                if len(current_row.children) >= 4:
                    container.add_item(current_row)
                    current_row = discord.ui.ActionRow()

                current_row.add_item(
                    discord.ui.Button(
                        emoji=self.emojis_per_distributor.get(provider, '<:music:1539115077028937738>'),
                        url=provider_url,
                        style=discord.ButtonStyle.link
                    )
                )

            if len(current_row.children) > 0:
                container.add_item(current_row)

        container.add_item(discord.ui.Separator())
    
        container.add_item(
            discord.ui.Section(
                discord.ui.TextDisplay(f"-# Festival Tracker"),
                accessory=StreamingViewButton("t", track_shortname, interaction.user.id, version="1")
            )
        )

        await interaction.edit_original_response(view=view)

# user id is used here because idk
class StreamingViewButton(discord.ui.DynamicItem[discord.ui.Button], template=r'strm:(?P<view_type>a|t):(?P<version>\d+):(?P<shortname>[a-zA-Z0-9_]+):(?P<user_id>\d+):(?P<spotify_id>[a-zA-Z0-9_]+)'):
    def __init__(self, view_type: str, track_shortname: str, user_id: int, version: str = '1', spotify_id: str = None) -> None:
        super().__init__(
            discord.ui.Button(
                label='View Album' if view_type == "a" else "View Track",
                style=discord.ButtonStyle.secondary,
                custom_id=f'strm:{view_type}:{version}:{track_shortname}:{user_id}:{spotify_id}',
                emoji='<:music:1539115077028937738>',
            )
        )
        self.view_type: str = view_type
        self.track_shortname: str = track_shortname
        self.user_id: int = user_id
        self.version: str = version
        self.spotify_id: str = spotify_id
        self.streaming_services_manager = StreamingServicesManager()

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        view_type = match['view_type']
        track_shortname = match['shortname']
        user_id = int(match['user_id'])
        version = match['version']
        spotify_id = match['spotify_id']
        return cls(view_type, track_shortname, user_id, version, spotify_id)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.user_id != interaction.user.id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)

        if self.view_type == 'a':
            await self.streaming_services_manager.handle_album_interaction(interaction, self.track_shortname, private=False, spotify_id=self.spotify_id)
        elif self.view_type == 't':
            await self.streaming_services_manager.handle_track_interaction(interaction, self.track_shortname, private=False)