from datetime import datetime, timezone
import difflib
import logging
import os
import random
import re

import discord
import requests
from bot import constants
from bot.constants import OneButtonSimpleView
from discord.ext import commands
from bot.embeds import SearchEmbedHandler

class DailyCommandHandler:
    def __init__(self, bot) -> None:
        self.bot = bot

    def create_daily_embeds(self, daily_tracks, chunk_size=8):
        embeds = []
        
        for i in range(0, len(daily_tracks), chunk_size):
            embed = discord.Embed(title="Weekly Rotation Tracks", color=0x8927A1)
            chunk = daily_tracks[i:i + chunk_size]
            
            for entry in chunk:
                embed.add_field(
                    name="",
                    value=f"**\\• {entry['title']}** - *{entry['artist']}*\n{entry['difficulty']}",
                    inline=False
                )
            embeds.append(embed)

        return embeds

    def fetch_daily_shortnames(self):
        try:
            logging.debug(f'[GET] {constants.DAILY_API}')
            headers = {
                'Authorization': self.bot.oauth_manager.session_token
            }
            response = requests.get(constants.DAILY_API, headers=headers)
            data = response.json()

            channels = data.get('channels', {})
            client_events_data = channels.get('client-events', {})
            states = client_events_data.get('states', [])

            current_time = datetime.now(timezone.utc)
            
            valid_states = [state for state in states if datetime.fromisoformat(state['validFrom'].replace('Z', '+00:00')) <= current_time]
            valid_states.sort(key=lambda x: datetime.fromisoformat(x['validFrom'].replace('Z', '+00:00')), reverse=True)

            if not valid_states:
                logging.error("No valid states found")
                return None

            active_events = valid_states[0].get('activeEvents', [])

            daily_tracks = []
            for event in active_events:
                event_type = event.get('eventType', '')
                active_since = event.get('activeSince', '')
                active_until = event.get('activeUntil', '')

                active_since_date = datetime.fromisoformat(active_since.replace('Z', '+00:00')) if active_since else None
                active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00')) if active_until else None

                if event_type.startswith('PilgrimSong.') and active_since_date and active_until_date:
                    if active_since_date <= current_time <= active_until_date:
                        shortname = event_type.replace('PilgrimSong.', '')
                        related_spotlight = discord.utils.find(lambda event: event['eventType'] == f'Sparks.Spotlight.{shortname}', active_events)
                        daily_tracks.append({
                            'shortname': shortname,
                            'in_spotlight': related_spotlight != None
                        })

            return daily_tracks
        except Exception as e:
            logging.error(exc_info=e)
            return {}
        
    async def handle_interaction(self, interaction: discord.Interaction):
        tracks = constants.get_jam_tracks() # Fix circular import...
        weekly_songs = self.fetch_daily_shortnames()

        if not tracks or not weekly_songs:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        daily_tracks = []
        
        weekly_songs.sort(key=lambda x: x['shortname'])

        for song in weekly_songs:
            track = discord.utils.find(lambda t: t['track']['sn'] == song['shortname'], tracks)
            if not track:
                continue

            title = track['track'].get('tt', 'Unknown Title')
            artist = track['track'].get('an', 'Unknown Artist')

            difficulty_str = constants.generate_difficulty_string(track['track'].get('in', {}))
            daily_tracks.append({
                'title': title,
                'artist': artist,
                'difficulty': difficulty_str
            })

        await interaction.response.defer()

        embeds = self.create_daily_embeds(daily_tracks)
        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        
class ShopCommandHandler:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.search_embed_handler = SearchEmbedHandler()

    def create_embeds(self, shop_tracks, title, content_tracks):
        embeds = []

        for i in range(0, len(shop_tracks), 5):
            embed = discord.Embed(title=title, color=0x8927A1)
            chunk = shop_tracks[i:i + 5]

            for track in chunk: # track is in epic format
                in_date = track['meta'].get('inDate')
                out_date = track['meta'].get('outDate')
                in_date_display = constants.format_date(in_date)
                out_date_display = constants.format_date(out_date)
                
                template_id = track['meta'].get('templateId')
                jam_track = discord.utils.find(lambda jt: jt['track']['ti'] == template_id, content_tracks)

                if jam_track:
                    difficulty_data = jam_track['track'].get('in', {})
                    difficulty_str = constants.generate_difficulty_string(difficulty_data)
                else:
                    difficulty_str = "No difficulty data available"

                embed.add_field(
                    name="",
                    value=f"**\\• {jam_track['track']['tt']}** - *{jam_track['track']['an']}*\nAvailable {in_date_display} through {out_date_display}\n"
                        f"{difficulty_str}",
                    inline=False
                )

            embeds.append(embed)

        return embeds

    async def handle_interaction(self, interaction:discord.Interaction):
        shop_tracks = self.fetch_shop_tracks()
        jam_tracks = constants.get_jam_tracks() # Fix circular import...

        await interaction.response.defer()

        def title_from_template_id(template_id) -> str:
            return discord.utils.find(lambda jt: jt['track']['ti'] == template_id, jam_tracks)['track']['tt']
        
        shop_tracks.sort(key=lambda offer: title_from_template_id(offer['meta']['templateId']).lower())

        total_tracks = len(shop_tracks)
        title = f"Shop Jam Tracks (Total: {total_tracks})"

        embeds = self.create_embeds(shop_tracks, title, jam_tracks)
        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

    def fetch_shop_tracks(self) -> list:
        logging.debug(f'[GET] {constants.SHOP_API}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        response = requests.get(constants.SHOP_API, headers=headers)
        if response.status_code == 401 or response.status_code == 403:
            self.bot.oauth_manager._create_token()
            raise Exception('Please try again.')

        data = response.json()

        storefront = discord.utils.find(lambda storefront: storefront['name'] == 'BRWeeklyStorefront', data['storefronts'])
        shop_tracks = list(filter(lambda item: item['meta']['templateId'].startswith('SparksSong:'), storefront['catalogEntries']))
        return shop_tracks
        
class TracklistHandler:
    def __init__(self, bot) -> None:
        self.search_embed_handler = SearchEmbedHandler()

    async def handle_interaction(self, interaction: discord.Interaction):
        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        track_list = constants.sort_track_list(tracks)
        await interaction.response.defer()

        total_tracks = len(track_list)
        title = f"Available Tracks (Total: {total_tracks})"

        embeds = constants.create_track_embeds(track_list, title)
        
        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

    async def handle_artist_interaction(self, interaction: discord.Interaction, artist:str):
        await interaction.response.defer()

        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks'), ephemeral=True)
            return
        
        track_list = constants.sort_track_list(tracks)
        matched = []

        for track in track_list:            
            if artist in track['track']['an'].lower():
                matched.append(track)
            # Use fuzzy matching for close but not exact matches
            elif any(difflib.get_close_matches(artist, [track['track']['an'].lower()], n=1, cutoff=0.7)):
                matched.append(track)

        total_tracks = len(matched)
        title = f"Filtered tracks for {artist} (Total: {total_tracks})"

        embeds = constants.create_track_embeds(matched, title)
        
        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

class GamblingHandler:
    def __init__(self, bot) -> None:
        self.search_embed_handler = SearchEmbedHandler()
        self.daily_handler = DailyCommandHandler(bot)
        self.shop_handler = ShopCommandHandler(bot)

    async def handle_random_track_interaction(self, interaction: discord.Interaction, shop: bool = False, daily: bool = False):
        await interaction.response.defer()

        track_list = constants.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        
        shop_tracks = self.shop_handler.fetch_shop_tracks()
        weekly_tracks = self.daily_handler.fetch_daily_shortnames()

        if shop:
            def inshop(obj):
                return discord.utils.find(lambda offer: offer['meta']['templateId'] == obj['track']['ti'], shop_tracks)
            track_list = list(filter(inshop, track_list))

        if daily:
            def indaily(obj):
                sn = obj['track']['sn']
                return discord.utils.find(lambda t: t['shortname'] == sn, weekly_tracks) != None

            track_list = list(filter(indaily, track_list))

        async def re_roll():
            chosen_track = random.choice(track_list)
            embed = self.search_embed_handler.generate_track_embed(chosen_track, is_random=True)
            constants.add_fields(chosen_track, embed, weekly_tracks, shop_tracks)
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = OneButtonSimpleView(on_press=re_roll, user_id=interaction.user.id, label="Reroll Track")
        reroll_view.message = await interaction.original_response()

        await re_roll()

    async def handle_random_setlist_interaction(self, interaction: discord.Interaction, shop:bool = False, daily: bool = False, limit:int = 4):
        await interaction.response.defer()

        track_list = constants.get_jam_tracks()
        if not track_list:
            await interaction.response.send_message(cembed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        
        shop_tracks = self.shop_handler.fetch_shop_tracks()
        daily_tracks = self.daily_handler.fetch_daily_shortnames()

        if shop:
            def inshop(obj):
                return discord.utils.find(lambda offer: offer['meta']['templateId'] == obj['track']['ti'], shop_tracks)
            track_list = list(filter(inshop, track_list))

        if daily:
            def indaily(obj):
                sn = obj['track']['sn']
                return discord.utils.find(lambda t: t['shortname'] == sn, daily_tracks) != None

            track_list = list(filter(indaily, track_list))

        async def re_roll():
            chosen_tracks = []
            for i in range(limit):
                chosen_tracks.append(random.choice(track_list))

            embed = discord.Embed(title="Your random setlist!", description=f"The {limit} tracks are...", color=0x8927A1)
            embed.add_field(name="", value="\n".join([f'- **{str(track["track"]["tt"])}** - *{str(track["track"]["an"])}*' for track in chosen_tracks]))
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = OneButtonSimpleView(on_press=re_roll, user_id=interaction.user.id, label="Reroll Setlist")
        reroll_view.message = await interaction.original_response()

        await re_roll()

class ProVocalsHandler:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.search_embed_handler = SearchEmbedHandler()

    async def handle_interaction(self, interaction: discord.Interaction):
        await interaction.response.defer()

        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks'), ephemeral=True)
            return

        all_midi = [f'{track['track']['mu'].split('/')[3].split('.')[0]}.mid' for track in tracks]
        missing_midi = []

        songs_with_pro_vocals = 0
        songs_without_pro_vocals = 0

        for midi in all_midi:
            if not os.path.exists(constants.MIDI_FOLDER + midi):
                missing_midi.append(midi)
            else:
                mid = open(constants.MIDI_FOLDER + midi, 'rb')
                pro_vocals_track = b'PRO VOCALS' in mid.read()
                mid.close()
                if pro_vocals_track:
                    songs_with_pro_vocals += 1
                else:
                    songs_without_pro_vocals += 1

        embed = discord.Embed(
            title="Songs with Pro Vocals",
            description=f"There are currently **{songs_with_pro_vocals}**/**{len(all_midi)}** songs with Pro Vocals in Fortnite Festival. **{songs_without_pro_vocals}** songs do not have Pro Vocals yet.",
            color=0x8927A1
        )
        if len(missing_midi) > 0:
            embed.add_field(name="Missing files", value=f"{len(missing_midi)} files not found, these were not counted", inline=False)

        await interaction.edit_original_response(embed=embed)
