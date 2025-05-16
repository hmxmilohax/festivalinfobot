from datetime import datetime
from difflib import get_close_matches
import json
import logging
import random
import string
import discord
from discord.ext import commands
import requests
from bot import embeds
import bot.constants as constants
from bot.constants import Button, ButtonedView
from bot import helpers
from bot.tools.vmhandler import PreviewAudioMgr

class JamTrackHandler:
    def __init__(self) -> None:
        pass

    def remove_punctuation(self, text):
        return text.translate(str.maketrans('', '', string.punctuation.replace('_', '')))

    def fuzzy_search_tracks(self, tracks:list, search_term:str):
        search_term = self.remove_punctuation(search_term.lower())

        custom_results = {
            'i': ['i_kendrick'],
            'ttfaf': ['throughthefireandflames'],
            'btf': ['beyondtheflame'],
            'mop': ['masterofpuppets'],
            'dftr': ['dontfearthereaper'],
            'wtp': ['welcometoparadise'],
            'nggyu': ['nevergonnagiveyouup'],
            'mcls': ['magicalcureloveshot'], 
            'mlcs': ['magicalcureloveshot'], 
            'mscl': ['magicalcureloveshot'],
            'trash': ['showthemwhoweare', 'roar', 'thesoundofsilence', 'beautifulday'],
            'peak': ['larrysplace', 'nevergiveup', 'freebird'],
            'comingsoon': ['juicy'],
            'ralph': ['streetsignite'],
            'cowabunga': ['streetsignite'],
            'kog': ['streetsignite'],
            'one': ['one'],
            'latino': ['migente', 'ellabailasola', 'dakiti', 'titimepregunto', 'mia', 'tusa', 'qlona', 'cairo', 'okidoki', 'provenza'],
            '🥦': ['broccoli'],
            '🐦': ['freebird']
        }

        if search_term in custom_results.keys():
            premature_matches = []
            for result in custom_results.get(search_term, []):
                premature_matches.append(discord.utils.find(lambda track: track['track']['sn'] == result, tracks))

            return premature_matches

        if search_term == 'latest':
            return tracks[-1:-11:-1]

        if search_term == 'last':
            return [tracks[-1]]

        if search_term == 'longest':
            return sorted(tracks, key=lambda t: t['track']['dn'], reverse=True)[0:10]

        if search_term == 'shortest':
            return sorted(tracks, key=lambda t: t['track']['dn'])[0:10]

        if search_term == 'fastest':
            return sorted(tracks, key=lambda t: t['track']['mt'], reverse=True)[0:10]

        if search_term == 'slowest':
            return sorted(tracks, key=lambda t: t['track']['mt'])[0:10]

        if search_term == 'newest':
            return sorted(tracks, key=lambda t: t['track']['ry'], reverse=True)[0:10]

        if search_term == 'oldest':
            return sorted(tracks, key=lambda t: t['track']['ry'])[0:10]
            
        if search_term.isdigit():
            # template id search
            template_id_result = discord.utils.find(lambda track: int(track['track']['ti'].split('_')[-1]) == int(search_term), tracks)
            if template_id_result:
                return [template_id_result]

        exact_matches = []
        fuzzy_matches = []

        # Prioritize shortname searching
        exact_matches.extend([track for track in tracks if track['track']['sn'].lower() == search_term])
        
        for track in tracks:
            title = self.remove_punctuation(track['track']['tt'].lower())
            artist = self.remove_punctuation(track['track']['an'].lower())
            
            if search_term in title or search_term in artist:
                exact_matches.append(track)
            elif any(get_close_matches(search_term, [title, artist], n=1, cutoff=0.7)):
                fuzzy_matches.append(track)
        
        # Prioritize exact matches over fuzzy matches
        result = exact_matches if exact_matches else fuzzy_matches
        result_unique = []
        # Remember: Better languages have a .unique method!
        for track in result:
            # Check for duplicates
            if track not in result_unique: result_unique.append(track) 
        return result_unique
    
    def get_spotify_link(self, isrc: str, session : str):
        url = "https://accounts.spotify.com/api/token"
        logging.debug(f'[POST] {url}')

        authorize = requests.post(url, data=f"grant_type=client_credentials&client_id={constants.SPOTIFY_CLIENT_ID}&client_secret={constants.SPOTIFY_CLIENT_PASS}&state={session}", headers={'Content-Type': 'application/x-www-form-urlencoded'})

        song_url = f'https://api.spotify.com/v1/search?q=isrc%3A{isrc}&type=track&limit=1&offset=0'
        client_token = authorize.json()['access_token']
        logging.debug(f'[GET] {song_url}')
        link = requests.get(song_url, headers={'Authorization': f'Bearer {client_token}'})

        # print(link.text)

        try:
            link.raise_for_status()
        except Exception as e:
            logging.error(f'Spotify Link GET returned {link.status_code}', exc_info=e)
            return None
        
        result = link.json()
        items = result['tracks']['items']
        if len(items) > 0:
            return items[0]['external_urls'].get('spotify', None)
        
    def get_song_link_odesli(self, spotify_url: str):
        url = f"https://api.odesli.co/resolve?url={spotify_url}"
        logging.debug(f'[GET] {url}')

        odesli = requests.get(url)

        try:
            odesli.raise_for_status()
        except Exception as e:
            logging.error(f'Odesli Link GET returned {odesli.status_code}', exc_info=e)
            return None
        
        result = odesli.json()
        return f'https://{result["type"]}.link/s/{result["id"]}'

    def get_jam_tracks(self):
        return constants.get_jam_tracks()
        
class SearchCommandHandler:
    def __init__(self, bot: commands.Bot) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.bot : commands.Bot = bot
        self.embed_handler = embeds.SearchEmbedHandler()
        self.daily_handler = helpers.DailyCommandHandler(bot)
        self.shop_handler = helpers.ShopCommandHandler(bot)

    async def prompt_user_for_selection(self, interaction:discord.Interaction, matched_tracks):
        view: ResultsJamTracks

        if len(matched_tracks) > 25:
            await interaction.edit_original_response(content="", embed=constants.common_error_embed("There are too many results. Please try another query, or use </tracklist filter artist:1287199873116143628>."))
            return None

        async def selected(new_interaction: discord.Interaction):
            if new_interaction:
                if new_interaction.user.id != interaction.user.id:
                    await interaction.edit_original_response(content="", embed=constants.common_error_embed("This is not your session. Please start your own session."))
                    return

                await new_interaction.response.defer()

            is_timed_out = len(view.select.values) < 1
            if is_timed_out:
                return None

            shortname = view.select.values[0]
            view.stop()
            return discord.utils.find(lambda t: t['track']['sn'] == shortname, matched_tracks)
        
        async def timed_out():
            await interaction.edit_original_response(content="", embed=constants.common_error_embed("You didn't respond in time. Search cancelled."), view=None)
            view.stop()

        view = ResultsJamTracks(matched_tracks, selected)
        view.on_timeout = timed_out
        await interaction.edit_original_response(view=view)
        await view.wait()

        return await selected(None)
    
    async def handle_imacat_search(self, interaction: discord.Interaction):
        with open('bot/imacat.json', 'r') as imacat_file:
            imacat_data = json.load(imacat_file)
        embed = self.embed_handler.generate_track_embed(imacat_data)
        embed.add_field(name="Status", value="Removed from API. This song has never been officially obtainable.", inline=False)
        message = await interaction.edit_original_response(embed=embed)

        async def something(interaction: discord.Interaction):
            view.buttons[0].disabled = True
            view.add_buttons()
            await interaction.message.edit(view=view)
            preview_audio_mgr = PreviewAudioMgr(self.bot, imacat_data, interaction)
            await preview_audio_mgr.reply_to_interaction_message()

        view: ButtonedView = ButtonedView(interaction.user.id, [Button(something, label="Preview")])
        view.message = message
        await message.edit(embed=embed, view=view)

    async def handle_interaction(self, interaction: discord.Interaction, query:str):
        await interaction.response.defer() # edit_original_response

        # meow case for im a cat
        if query.lower() in {"i'm a cat", "im a cat", "imacat"}:
            await self.handle_imacat_search(interaction=interaction)
            return

        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.edit_original_response(embed=constants.common_error_embed('Could not get Jam Tracks.'))
            return

        weekly_tracks = self.daily_handler.fetch_daily_shortnames()
        shop_tracks = self.shop_handler.fetch_shop_tracks()

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, query)
        if not matched_tracks:
            await interaction.edit_original_response(embed=constants.common_error_embed(f'No tracks were found matching \"{query}\"'))
            return

        track = None
        message = None
        
        if len(matched_tracks) != 1:
            track = await self.prompt_user_for_selection(interaction=interaction, matched_tracks=matched_tracks)
            if not track:
                return
        else:
            track = matched_tracks[0]

        embed = self.embed_handler.generate_track_embed(track)
        constants.add_fields(track, embed, weekly_tracks, shop_tracks)
        message = await interaction.edit_original_response(embed=embed)

        async def something(interaction: discord.Interaction):
            view.buttons[0].disabled = True
            view.add_buttons()
            await interaction.message.edit(view=view)
            preview_audio_mgr = PreviewAudioMgr(self.bot, track, interaction)
            await preview_audio_mgr.reply_to_interaction_message()

        view: ButtonedView = ButtonedView(interaction.user.id, [Button(something, label="Preview", thinking=True, emoji="🔊")])

        if shop_tracks:
            shop_entry = discord.utils.find(lambda offer: offer['meta']['templateId'] == track['track']['ti'], shop_tracks)
            if shop_entry:
                shop_entry_meta = shop_entry['meta']
                if shop_entry_meta.get('webURL', None):
                    view.buttons.append(Button(None, url=f"https://fortnite.com{shop_entry['meta'].get('webURL')}", label="Item Shop"))

        view.message = message
        await message.edit(embed=embed, view=view)

        try:
            if (not track) or (not message):
                return
            
            if track['track'].get('isrc', None):
                spotify = self.jam_track_handler.get_spotify_link(track['track']['isrc'], str(interaction.user.id))

                if not spotify:
                    return
                
                view_buttons = [Button(None, url=spotify, label="Listen on Spotify")]

                song_dot_link = self.jam_track_handler.get_song_link_odesli(spotify)
                if song_dot_link:
                    view_buttons.append(Button(None, url=song_dot_link, label="song.link"))

                view.buttons.extend(view_buttons)
                view.add_buttons()
                await message.edit(embed=embed, view=view)
        except Exception as e:
            logging.error('Error attempting to add Spotify link to message:', exc_info=e)

class ResultsJamTracks(discord.ui.View):
    def __init__(self, tracks: list, on_select):
        super().__init__(timeout=30)
        self.tracks = tracks
        self.select = ResultsJamTracksDropdown(tracks)
        self.add_item(self.select)
        self.select.callback = on_select

class ResultsJamTracksDropdown(discord.ui.Select):
    def __init__(self, tracks: list):
        self.tracks = tracks

        options = [discord.SelectOption(label=track['track']['tt'], value=track['track']['sn'], description=track['track']['an']) for track in tracks]
        super().__init__(placeholder="Select from results...", min_values=1, max_values=1, options=options)