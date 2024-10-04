from datetime import datetime
from difflib import get_close_matches
import json
import string
import discord
from discord.ext import commands
import requests
from bot import embeds
import bot.constants as constants
from bot import helpers

class JamTrackHandler:
    def __init__(self) -> None:
        pass

    def remove_punctuation(self, text):
        return text.translate(str.maketrans('', '', string.punctuation.replace('_', '')))

    def fuzzy_search_tracks(self, tracks:list, search_term:str):
        # Remove punctuation from the search term
        search_term = self.remove_punctuation(search_term.lower())  # Case-insensitive search

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
            
            # Check for exact matches first
            if search_term in title or search_term in artist:
                exact_matches.append(track)
            # Use fuzzy matching for close but not exact matches
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

    def get_jam_tracks(self):
        return constants.get_jam_tracks() # Proxies into constants to fix circular imports
        
class SearchCommandHandler:
    def __init__(self, bot: commands.Bot) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.bot : commands.Bot = bot
        self.embed_handler = embeds.SearchEmbedHandler()
        self.daily_handler = helpers.DailyCommandHandler()
        self.shop_handler = helpers.ShopCommandHandler()

    async def prompt_user_for_selection(self, interaction:discord.Interaction, matched_tracks):
        options = [f"{i + 1}. **{track['track']['tt']}** - *{track['track']['an']}*" for i, track in enumerate(matched_tracks)]
        options_message = "\n".join(options)
        await interaction.response.send_message(content=f"I found multiple tracks matching your search. Please choose the correct one by typing the number:\n{options_message}")

        def check(m):
            return m.author == interaction.user

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

    def format_date(self, date_string):
        if date_string:
            date_ts = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return date_ts.strftime("%B %d, %Y")
        return "Currently in the shop!"
    
    async def handle_imacat_search(self, interaction: discord.Interaction):
        with open('imacat.json', 'r') as imacat_file:
            imacat_data = json.load(imacat_file)
        embed = self.embed_handler.generate_track_embed(imacat_data)
        embed.add_field(name="Status", value="Removed from API. This song has never been officially obtainable.", inline=False)
        await interaction.response.send_message(embed=embed)

    async def handle_interaction(self, interaction: discord.Interaction, query:str):
        # Special case for "I'm A Cat"
        if query.lower() in {"i'm a cat", "im a cat", "imacat"}:
            await self.handle_imacat_search(interaction=interaction)
            return

        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content='Could not get tracks.', ephemeral=True)
            return

        daily_shortnames_data = self.daily_handler.fetch_daily_shortnames()
        shop_tracks = self.shop_handler.fetch_shop_tracks()

        # Perform fuzzy search
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, query)
        if not matched_tracks:
            await interaction.response.send_message(content=f'No tracks were found matching \"{query}\"')
            return
        
        def add_fields(track_devname, embed):
            if daily_shortnames_data and track_devname in daily_shortnames_data:
                active_until = daily_shortnames_data[track_devname]['activeUntil']
                human_readable_until = self.format_date(active_until)
                embed.add_field(name="Daily Rotation", value=f"Free in daily rotation until {human_readable_until}.", inline=False)

            # Add shop information
            if shop_tracks and track_devname in shop_tracks:
                out_date = shop_tracks[track_devname].get('outDate')
                human_readable_out_date = self.format_date(out_date)
                embed.add_field(name="Shop Rotation", value=f"Currently in the shop until {human_readable_out_date}.", inline=False)
        
        if len(matched_tracks) == 1:
            embed = self.embed_handler.generate_track_embed(matched_tracks[0])

            track_devname = matched_tracks[0]['track']['sn']
            add_fields(track_devname=track_devname, embed=embed)
            
            await interaction.response.send_message(embed=embed)
        else:
            message, chosen_track = await self.prompt_user_for_selection(interaction=interaction, matched_tracks=matched_tracks)
            embed = self.embed_handler.generate_track_embed(chosen_track)
            
            track_devname = chosen_track['track']['sn']
            add_fields(track_devname=track_devname, embed=embed)

            await message.reply(embed=embed, mention_author=False)