from datetime import datetime, timezone
import logging
import random

import discord
import requests
from bot import constants
from discord.ext import commands
from bot.embeds import SearchEmbedHandler, DailyCommandEmbedHandler

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

            # Current date with timezone awareness
            current_time = datetime.now(timezone.utc)
            
            # Filter and sort the states by validFrom date
            valid_states = [state for state in states if datetime.fromisoformat(state['validFrom'].replace('Z', '+00:00')) <= current_time]
            valid_states.sort(key=lambda x: datetime.fromisoformat(x['validFrom'].replace('Z', '+00:00')), reverse=True)

            if not valid_states:
                logging.error("No valid states found")
                return None

            # Get the activeEvents from the most recent valid state
            active_events = valid_states[0].get('activeEvents', [])

            daily_tracks = {}
            for event in active_events:
                event_type = event.get('eventType', '')
                active_since = event.get('activeSince', '')
                active_until = event.get('activeUntil', '')

                # Convert dates to timezone-aware datetime objects
                active_since_date = datetime.fromisoformat(active_since.replace('Z', '+00:00')) if active_since else None
                active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00')) if active_until else None

                if event_type.startswith('PilgrimSong.') and active_since_date and active_until_date:
                    # Check if the current date falls within the active period
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

class RerollTrackView(discord.ui.View):
    def __init__(self, re_roll_callback, user_id):
        super().__init__(timeout=30)  # No timeout for the view
        self.re_roll_callback = re_roll_callback
        self.user_id = user_id

    @discord.ui.button(label='Reroll', style=discord.ButtonStyle.primary, emoji="🔁")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Call the re_roll function when the button is pressed
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        await interaction.response.defer() 
        await self.re_roll_callback()

class RerollSetlistView(discord.ui.View):
    def __init__(self, re_roll_callback, user_id):
        super().__init__(timeout=30)  # No timeout for the view
        self.re_roll_callback = re_roll_callback
        self.user_id = user_id

    @discord.ui.button(label='Reroll', style=discord.ButtonStyle.primary, emoji="🔁")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Call the re_roll function when the button is pressed
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        # Call the re_roll function when the button is pressed
        await interaction.response.defer() 
        await self.re_roll_callback()

class GamblingHandler:
    def __init__(self) -> None:
        self.search_embed_handler = SearchEmbedHandler()

    async def handle_random_track_interaction(self, interaction: discord.Interaction):
        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content='Could not get tracks.', ephemeral=True)
            return

        track_list = constants.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return
        
        await interaction.response.defer()

        async def re_roll():
            chosen_track = random.choice(track_list)
            embed = self.search_embed_handler.generate_track_embed(chosen_track, is_random=True)
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = RerollTrackView(re_roll, user_id=interaction.user.id)

        await re_roll()

    async def handle_random_setlist_interaction(self, interaction: discord.Interaction):
        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content='Could not get tracks.', ephemeral=True)
            return

        track_list = constants.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(content='No tracks available.', ephemeral=True)
            return
        
        await interaction.response.defer()

        async def re_roll():
            chosen_tracks = [random.choice(track_list),random.choice(track_list),random.choice(track_list),random.choice(track_list)]
            embed = discord.Embed(title="Your random setlist!", description="The 4 tracks are...", color=0x8927A1)
            embed.add_field(name="", value="\n".join([f'- **{str(track["track"]["tt"])}** - *{str(track["track"]["an"])}*' for track in chosen_tracks]))
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = RerollSetlistView(re_roll, user_id=interaction.user.id)

        await re_roll()