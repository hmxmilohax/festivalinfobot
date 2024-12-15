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

class DailyCommandEmbedHandler():
    def __init__(self) -> None:
        pass

    def create_daily_embeds(self, daily_tracks, chunk_size=3):
        embeds = []
        
        for i in range(0, len(daily_tracks), chunk_size):
            embed = discord.Embed(title="Weekly Rotation Tracks", color=0x8927A1)
            chunk = daily_tracks[i:i + chunk_size]
            
            for entry in chunk:
                active_until_display = discord.utils.format_dt(datetime.fromtimestamp(entry['activeUntil']), style="R") if entry['activeUntil'] else "Unknown"
                
                embed.add_field(
                    name="",
                    value=f"**\\• {entry['title']}** - *{entry['artist']}* - Leaving: {active_until_display}\n"
                        f"```{entry['difficulty']}```\n",
                    inline=False
                )
            embeds.append(embed)

        return embeds

class DailyCommandHandler:
    def __init__(self) -> None:
        self.daily_embed_handler = DailyCommandEmbedHandler()

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

            daily_tracks = {}
            for event in active_events:
                event_type = event.get('eventType', '')
                active_since = event.get('activeSince', '')
                active_until = event.get('activeUntil', '')

                active_since_date = datetime.fromisoformat(active_since.replace('Z', '+00:00')) if active_since else None
                active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00')) if active_until else None

                if event_type.startswith('PilgrimSong.') and active_since_date and active_until_date:
                    if active_since_date <= current_time <= active_until_date:
                        shortname = event_type.replace('PilgrimSong.', '')
                        daily_tracks[shortname] = {
                            'activeSince': active_since,
                            'activeUntil': active_until
                        }

            return daily_tracks
        except Exception as e:
            logging.error(exc_info=e)
            return {}
    
    def convert_iso_to_timestamp(self, event_data):
        active_since_iso = event_data.get('activeSince', '')
        active_until_iso = event_data.get('activeUntil', '')

        active_until_ts = int(datetime.fromisoformat(active_until_iso.replace('Z', '+00:00')).timestamp()) if active_until_iso else None
        active_since_ts = int(datetime.fromisoformat(active_since_iso.replace('Z', '+00:00')).timestamp()) if active_since_iso else None

        return active_since_ts, active_until_ts
        
    def process_daily_tracks(self, tracks, daily_shortnames_data):
        daily_tracks = []
        
        for track in tracks:
            shortname = track['track'].get('sn')

            if shortname in daily_shortnames_data:
                event_data = daily_shortnames_data[shortname]
                active_since_ts, active_until_ts = self.convert_iso_to_timestamp(event_data)

                title = track['track'].get('tt', 'Unknown Title')
                artist = track['track'].get('an', 'Unknown Artist')

                difficulty_str = constants.generate_difficulty_string(track['track'].get('in', {}))

                daily_tracks.append({
                    'track': track,
                    'title': title,
                    'artist': artist,
                    'difficulty': difficulty_str,
                    'activeSince': active_since_ts,
                    'activeUntil': active_until_ts
                })

        # Sort the tracks first by 'Leaving' time (activeUntil), then alphabetically by title
        daily_tracks.sort(key=lambda x: (x['activeUntil'] or float('inf'), x['title'].lower()))
        return daily_tracks
        
    async def handle_interaction(self, interaction: discord.Interaction):
        tracks = constants.get_jam_tracks() # Fix circular import...
        daily_shortnames_data = self.fetch_daily_shortnames()

        if not tracks or not daily_shortnames_data:
            await interaction.response.send_message(content='Could not fetch tracks.', ephemeral=True)
            return

        daily_tracks = self.process_daily_tracks(tracks, daily_shortnames_data)

        if daily_tracks:
            await interaction.response.defer() # Makes it say thinking, and also avoids a timeout error on PaginatorView

            embeds = self.daily_embed_handler.create_daily_embeds(daily_tracks)
            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.response.send_message(content="No daily tracks found.")
        
class ShopCommandHandler:
    def __init__(self) -> None:
        self.search_embed_handler = SearchEmbedHandler()

    async def handle_interaction(self, interaction:discord.Interaction):
        tracks = self.fetch_shop_tracks()
        jam_tracks = constants.get_jam_tracks() # Fix circular import...

        await interaction.response.defer()

        if not tracks:
            await interaction.edit_original_response(content='Could not fetch tracks.', ephemeral=True)
            return

        track_list = self.prepare_track_list(tracks, shop=True)

        if not track_list:
            await interaction.edit_original_response(content='No tracks available in the shop.', ephemeral=True)
            return

        total_tracks = len(track_list)
        title = f"Shop Jam Tracks (Total: {total_tracks})"

        embeds = self.search_embed_handler.create_track_embeds(track_list, title, shop=True, jam_tracks=jam_tracks)
        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

    def prepare_track_list(self, tracks, shop=False):
        unique_tracks = {}
        
        if type(tracks) == dict:
            for track in tracks.values():
                track_sn = track['devName'] if shop else track['track']['sn']
                if track_sn not in unique_tracks:
                    unique_tracks[track_sn] = track
        else:
            for track in tracks:
                track_sn = track['devName'] if shop else track['track']['sn']
                if track_sn not in unique_tracks:
                    unique_tracks[track_sn] = track

        return sorted(unique_tracks.values(), key=lambda x: x['title'].lower() if shop else x['track']['tt'].lower())

    def fetch_shop_tracks(self):
        try:
            logging.debug(f'[GET] {constants.SHOP_API}')
            response = requests.get(constants.SHOP_API)
            data = response.json()

            # Check if 'data' and 'entries' keys exist in the response
            if 'data' in data and 'entries' in data['data']:
                entries = data['data']['entries']
                available_tracks = {}

                for entry in entries:
                    in_date = entry.get('inDate')
                    out_date = entry.get('outDate')
                    
                    if entry.get('tracks'):
                        for track in entry['tracks']:
                            dev_name = track.get("devName")
                            if dev_name and 'sid_placeholder' in track['id']:
                                if dev_name not in available_tracks:
                                    available_tracks[dev_name] = {
                                        "id": track["id"],
                                        "devName": dev_name,
                                        "title": track.get("title", "Unknown Title").strip() if track.get("title") else "Unknown Title",
                                        "artist": track.get("artist", "Unknown Artist").strip() if track.get("artist") else "Unknown Artist",
                                        "releaseYear": track.get("releaseYear", "Unknown Year"),
                                        "duration": track.get("duration", 0),
                                        "difficulty": track.get("difficulty", {}),
                                        "inDate": in_date,  # Assign entry-level inDate
                                        "outDate": out_date  # Assign entry-level outDate
                                    }

                if not available_tracks:
                    logging.error('No tracks found in the shop.')
                    return None

                return available_tracks  # Return dictionary keyed by devName

        except Exception as e:
            logging.error(f'Error fetching shop tracks', exc_info=e)
            return None
        
class TracklistHandler:
    def __init__(self) -> None:
        self.shop_handler = ShopCommandHandler()
        self.search_embed_handler = SearchEmbedHandler()

    async def handle_interaction(self, interaction: discord.Interaction):
        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content='Could not get tracks.', ephemeral=True)
            return

        track_list = self.shop_handler.prepare_track_list(tracks)

        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return
        
        await interaction.response.defer()

        total_tracks = len(track_list)
        title = f"Available Tracks (Total: {total_tracks})"

        embeds = self.search_embed_handler.create_track_embeds(track_list, title)
        
        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

    async def handle_artist_interaction(self, interaction: discord.Interaction, artist:str):
        await interaction.response.defer()

        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content='Could not get tracks.', ephemeral=True)
            return

        track_list = self.shop_handler.prepare_track_list(tracks)

        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return

        matched = []

        for track in track_list:            
            if artist in track['track']['an'].lower():
                matched.append(track)
            # Use fuzzy matching for close but not exact matches
            elif any(difflib.get_close_matches(artist, [track['track']['an'].lower()], n=1, cutoff=0.7)):
                matched.append(track)

        total_tracks = len(matched)
        title = f"Filtered tracks for {artist} (Total: {total_tracks})"

        embeds = self.search_embed_handler.create_track_embeds(matched, title)
        
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
            await interaction.response.send_message(content='Could not get tracks.', ephemeral=True)
            return

        track_list = self.shop_handler.prepare_track_list(tracks)

        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return

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
            embeds = self.search_embed_handler.create_track_embeds(matching_songs, f"Matched tracklist result\nRegex: `{regex}`\nQuery: `{matched}`\nTotal: {len(matching_songs)}")    
            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.edit_original_response(content="There were no results! Try another pattern.")

class GamblingHandler:
    def __init__(self) -> None:
        self.search_embed_handler = SearchEmbedHandler()
        self.daily_handler = DailyCommandHandler()
        self.shop_handler = ShopCommandHandler()

    def format_date(self, date_string):
        if date_string:
            date_ts = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return discord.utils.format_dt(date_ts, 'D')
        return "Currently in the shop!"

    async def handle_random_track_interaction(self, interaction: discord.Interaction, shop: bool = False, daily: bool = False):
        await interaction.response.defer()

        track_list = constants.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return
        
        if shop:
            shop_tracks = self.shop_handler.fetch_shop_tracks()
            def inshop(obj):
                return obj['track']['sn'] in shop_tracks

            track_list = list(filter(inshop, track_list))

        if daily:
            daily_tracks = self.daily_handler.fetch_daily_shortnames()
            def indaily(obj):
                return obj['track']['sn'] in daily_tracks

            track_list = list(filter(indaily, track_list))

        daily_shortnames_data = self.daily_handler.fetch_daily_shortnames()
        shop_tracks = self.shop_handler.fetch_shop_tracks()

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

        async def re_roll():
            chosen_track = random.choice(track_list)
            embed = self.search_embed_handler.generate_track_embed(chosen_track, is_random=True)
            add_fields(chosen_track['track']['sn'], embed)
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = OneButtonSimpleView(on_press=re_roll, user_id=interaction.user.id, label="Reroll Track")
        reroll_view.message = await interaction.original_response()

        await re_roll()

    async def handle_random_setlist_interaction(self, interaction: discord.Interaction, shop:bool = False, daily: bool = False, limit:int = 4):
        await interaction.response.defer()

        track_list = constants.get_jam_tracks()
        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return
        
        if shop:
            shop_tracks = self.shop_handler.fetch_shop_tracks()
            def inshop(obj):
                return obj['track']['sn'] in shop_tracks

            track_list = list(filter(inshop, track_list))

        if daily:
            daily_tracks = self.daily_handler.fetch_daily_shortnames()
            def indaily(obj):
                return obj['track']['sn'] in daily_tracks

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