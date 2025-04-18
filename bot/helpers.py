from datetime import datetime, timezone
import difflib
import logging
import random
import re

import discord
import requests
from bot import constants
from bot.constants import OneButtonSimpleView
from discord.ext import commands
from bot.embeds import SearchEmbedHandler

class DailyCommandHandler:
    def __init__(self) -> None:
        pass

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
            response = requests.get(constants.DAILY_API)
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

    async def handle_regex_interaction(self, interaction: discord.Interaction, regex:str, matched:str):
        if not regex:
            embed = discord.Embed(colour=0x8927A1, title="Regex help")
            embed.add_field(name="`regex` parameter", value="This is a common Regular expression. To match any song with \"Metallica\" on the matched queries `%an - %tt`, Provide `\\bMetallica\\b` in this parameter.", inline=False)
            embed.add_field(name="`query` parameter", value="This is the pattern, or query that the `regex` will be applied in.\nYou can provide any value, but we provide multiple *placeholders* for you.\nThese are as follows:\n\n- `tt` - Track Title\n- `mm` - Music Scale\n- `ry` - Release Year\n- `mt` - BPM\n- `mu` - Chart URL\n- `dn` - Duration\n- `isrc` - ISRC Code\n- `an` - Artist Name\n- `ar` - Rating\n- `au` - Album Art\n- `ti` - Song Item ID\n- `qi` - Streaming Metadata\n- `ld` - Lipsync Data URL\n- `jc` - Creative Join Code\n- `sn` - Shortname\n- `mk` - Music Key\n- `siv` - Vocals Instrument\n- `sib` - Bass Instrument\n- `sig` - Lead Instrument\n- `sid` - Drums Instrument\n\nBy default, `%an - %tt` is used. This means that your regex expression will be matched on \"Epic Games - Butter Barn Hoedown\", \"Epic Games - OG (Future Remix)\", etc.\nThese must be prefixed with `%`.", inline=False)
            embed.set_author(name="Festival Tracker")

            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()

        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks'), ephemeral=True)
            return

        track_list = constants.sort_track_list(tracks)
        # Escape the regex string to treat it as a literal string
        regex_pattern = re.compile(regex)

        # Create an empty list to store matching songs
        matching_songs = []

        # Iterate over the song list and apply the regex pattern
        for track in track_list:
            track_data = track['track']
            queried = matched.replace('%an', str(track_data.get('an'))).replace('%tt', str(track_data.get('tt'))).replace('%mm', str(track_data.get('mm'))).replace('%ry', str(track_data.get('ry'))).replace('%mt', str(track_data.get('mt'))).replace('%siv', str(track_data.get('siv'))).replace('%mu', str(track_data.get('mu'))).replace('%dn', str(track_data.get('dn'))).replace('%isrc', str(track_data.get('isrc'))).replace('%sib', str(track_data.get('sib'))).replace('%sig', str(track_data.get('sig'))).replace('%sid', str(track_data.get('sid'))).replace('%ar', str(track_data.get('ar'))).replace('%au', str(track_data.get('au'))).replace('%ti', str(track_data.get('ti'))).replace('%qi', str(track_data.get('qi'))).replace('%ld', str(track_data.get('ld'))).replace('%jc', str(track_data.get('jc'))).replace('%sn', str(track_data.get('sn'))).replace('%mk', str(track_data.get('mk')))
            if re.search(regex_pattern, queried):
                matching_songs.append(track)

        if len(matching_songs) > 0:
            embeds = constants.create_track_embeds(matching_songs, f"Matched tracklist result\nRegex: `{regex}`\nQuery: `{matched}`\nTotal: {len(matching_songs)}")    
            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.edit_original_response(embed=constants.common_error_embed('There were no results.'))

class GamblingHandler:
    def __init__(self, bot) -> None:
        self.search_embed_handler = SearchEmbedHandler()
        self.daily_handler = DailyCommandHandler()
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
                return obj['track']['sn'] in weekly_tracks
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