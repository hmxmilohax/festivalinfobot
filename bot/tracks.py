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

class JamTrackHandler:
    def __init__(self) -> None:
        pass

    def remove_punctuation(self, text):
        return text.translate(str.maketrans('', '', string.punctuation.replace('_', '')))

    def fuzzy_search_tracks(self, tracks:list, search_term:str):
        search_term = self.remove_punctuation(search_term.lower())

        # Special case for 'i'
        if search_term == 'i':
            exact_matches = [track for track in tracks if track['track']['tt'].lower() == 'i']
            if exact_matches:
                return exact_matches

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
        self.daily_handler = helpers.DailyCommandHandler()
        self.shop_handler = helpers.ShopCommandHandler(bot)

    async def prompt_user_for_selection(self, interaction:discord.Interaction, matched_tracks):
        options = [f"{i + 1}. **{track['track']['tt']}** - *{track['track']['an']}*" for i, track in enumerate(matched_tracks)]
        options_message = "\n".join(options)
        finalized_options_message = f"Found multiple tracks matching your query. Please choose the correct one by typing the number:\n{options_message}"

        if len(finalized_options_message) > 2000:
            await interaction.edit_original_response(content="The result is too large. Please try another query, or use </tracklist filter artist:1287199873116143628>.")
            return None, None

        await interaction.edit_original_response(content=finalized_options_message)

        def check(m: discord.Message):
            return (m.author == interaction.user) and m.channel.id == interaction.channel.id

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
            if not msg.content.isdigit() or not 1 <= int(msg.content) <= len(matched_tracks):
                await interaction.edit_original_response(content="Search cancelled.")
                return

            chosen_index = int(msg.content) - 1
            chosen_track = matched_tracks[chosen_index]
            return msg, chosen_track

        except TimeoutError:
            await interaction.edit_original_response(content="You didn't respond in time. Search cancelled.")
            return None, None
    
    async def handle_imacat_search(self, interaction: discord.Interaction):
        with open('bot/imacat.json', 'r') as imacat_file:
            imacat_data = json.load(imacat_file)
        embed = self.embed_handler.generate_track_embed(imacat_data)
        embed.add_field(name="Status", value="Removed from API. This song has never been officially obtainable.", inline=False)
        await interaction.edit_original_response(embed=embed)

    async def handle_interaction(self, interaction: discord.Interaction, query:str):
        await interaction.response.defer() # edit_original_response

        # meow case for im a cat
        if query.lower() in {"i'm a cat", "im a cat", "imacat"}:
            await self.handle_imacat_search(interaction=interaction)
            return

        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.edit_original_response(content='Could not get Jam Tracks.', ephemeral=True)
            return

        weekly_tracks = self.daily_handler.fetch_daily_shortnames()
        shop_tracks = self.shop_handler.fetch_shop_tracks()

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, query)
        if not matched_tracks:
            await interaction.edit_original_response(content=f'No tracks were found matching \"{query}\"')
            return

        track = None
        message = None
        
        if len(matched_tracks) == 1:
            _track = matched_tracks[0]
            track = _track

            embed = self.embed_handler.generate_track_embed(_track)

            constants.add_fields(_track, embed, weekly_tracks, shop_tracks)
            
            message = await interaction.edit_original_response(embed=embed)
        else:
            message, chosen_track = await self.prompt_user_for_selection(interaction=interaction, matched_tracks=matched_tracks)
            if not message:
                return
            
            track = chosen_track

            embed = self.embed_handler.generate_track_embed(chosen_track)
            constants.add_fields(chosen_track, embed, weekly_tracks, shop_tracks)

            message = await message.reply(embed=embed, mention_author=False)

        try:
            if track and message:
                if track['track'].get('isrc', None):
                    spotify = self.jam_track_handler.get_spotify_link(track['track']['isrc'], str(interaction.user.id))

                    if spotify:
                        view_buttons = [Button(None, url=spotify, label="Listen on Spotify")]

                        song_dot_link = self.jam_track_handler.get_song_link_odesli(spotify)
                        if song_dot_link:
                            view_buttons.append(Button(None, url=song_dot_link, label="song.link"))

                        view = ButtonedView(user_id=interaction.user.id, buttons=view_buttons)

                        view.message = message
                        await message.edit(embed=embed, view=view)
        except Exception as e:
            logging.error('Error attempting to add Spotify link to message:', exc_info=e)
