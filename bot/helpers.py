from datetime import datetime, timezone
import difflib
import logging
import math
import os
import random
import re

import discord
import requests
from bot import constants
from bot.constants import OneButtonSimpleView
from discord.ext import commands
from bot.embeds import SearchEmbedHandler
from bot.tools.midi import MidiArchiveTools

class WeeklySongsDisplay(discord.ui.Container):
    def __init__(self, tracks):
        super().__init__(accent_colour=constants.ACCENT_COLOUR) # im not sure how this is valid at all but in the end its python so whatever
        self.page = 0
        self.per_page = 3
        self.track_page_items: list[discord.ui.Section] = []
        self.track_separators: list[discord.ui.Separator] = []
        self.tracks = tracks

        self.add_item(discord.ui.TextDisplay("# Weekly Rotation Jam Tracks"))
        self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        self.credits = [
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# Festival Tracker")
        ]
        
    def create_page(self):
        for item in self.track_page_items:
            self.remove_item(item)

        for item in self.track_separators:
            self.remove_item(item)

        for item in self.credits:
            self.remove_item(item)

        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        current_tracks = self.tracks[start_idx:end_idx]

        if not current_tracks:
            self.add_item(discord.ui.TextDisplay("No tracks available"))
            return
        
        for track_data in current_tracks:
            track_metadata = track_data['metadata']
            ## ERROR HANDLIN NEEDED HERE
            track = track_metadata['track']
            title = track['tt']
            artist = track['an']
            album_art = track['au']
            vocals_diff = track['in'].get('vl', -1)
            guitar_diff = track['in'].get('gr', -1)
            bass_diff = track['in'].get('ba', -1)
            drums_diff = track['in'].get('ds', -1)
            pro_guitar_diff = track['in'].get('pg', -1)
            pro_bass_diff = track['in'].get('pb', -1)
            pro_drums_diff = track['in'].get('pd', -1)
            band_diff = track['in'].get('bd', -1)

            section = discord.ui.Section(
                accessory=discord.ui.Thumbnail(media=album_art)
            ).add_item(
                f"**{title}** - *{artist}*\n" +
                f"{constants.LEAD_EMOJI} `{constants.generate_difficulty_bar(guitar_diff)}` " +
                f"{constants.BASS_EMOJI} `{constants.generate_difficulty_bar(bass_diff)}` \n" +
                f"{constants.DRUMS_EMOJI} `{constants.generate_difficulty_bar(drums_diff)}` " +
                f"{constants.VOCALS_EMOJI} `{constants.generate_difficulty_bar(vocals_diff)}`\n" +
                f"{constants.PRO_LEAD_EMOJI} `{constants.generate_difficulty_bar(pro_guitar_diff)}` " +
                f"{constants.PRO_BASS_EMOJI} `{constants.generate_difficulty_bar(pro_bass_diff)}` \n" +
                f"{constants.PRO_DRUMS_EMOJI} `{constants.generate_difficulty_bar(pro_drums_diff)}`" +
                f"{constants.PRO_VOCALS_EMOJI} `{constants.generate_difficulty_bar(band_diff)}` "
            )

            is_last = (track_data == current_tracks[-1])

            self.track_page_items.append(section)
            self.add_item(section)
            if not is_last:
                separator = discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
                self.track_separators.append(separator)
                self.add_item(separator)

        for item in self.credits:
            self.add_item(item)

class WeeklySongsView(discord.ui.LayoutView):
    def __init__(self, tracks, user_id):
        super().__init__(timeout=60)
        
        self.container = WeeklySongsDisplay(tracks)
        self.add_item(self.container)

        self.page = 0
        self.per_page = 3
        self.total_pages = math.ceil(len(tracks) / self.per_page)
        self.user_id = user_id
        self.message: discord.Message

        self.action_row = ButtonActionRow(user_id=self.user_id, action=self.action)
        self.action_row.page_label.label = f"{self.page + 1}/{self.total_pages}"
        self.add_item(self.action_row)

        self.container.create_page()

    async def action(self, button: discord.ui.Button, interaction: discord.Interaction, action_id: int = -1):
        await interaction.response.defer()

        if action_id == 0: # first page
            self.page = 0

        elif action_id == 1: # previous page

            if self.page > 0:
                self.page -= 1

        elif action_id == 2: # next page
            
            if self.page < self.total_pages - 1:
                self.page += 1

        elif action_id == 3: # last page
            self.page = self.total_pages - 1

        if not (self.page > 0):
            self.action_row.first_button.disabled = True
            self.action_row.previous_button.disabled = True
        else:
            self.action_row.first_button.disabled = False
            self.action_row.previous_button.disabled = False

        if not (self.page < self.total_pages - 1):
            self.action_row.next_button.disabled = True
            self.action_row.last_button.disabled = True
        else:
            self.action_row.next_button.disabled = False
            self.action_row.last_button.disabled = False

        self.action_row.page_label.label = f"{self.page + 1}/{self.total_pages}"
        self.container.page = self.page
        self.container.create_page()

        await self.message.edit(view=self)

    async def on_timeout(self):
        try:
            for item in self.action_row.children:
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

    async def update_page(self, view: WeeklySongsView, interaction: discord.Interaction):
        await view.action(self, interaction, action_id=-1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: WeeklySongsView = self.view
        await self.update_page(view, interaction)

class FirstButton(PaginatorButton):
    async def update_page(self, view: WeeklySongsView, interaction: discord.Interaction):
        await view.action(self, interaction, action_id=0)

class PreviousButton(PaginatorButton):
    async def update_page(self, view: WeeklySongsView, interaction: discord.Interaction):
        await view.action(self, interaction, action_id=1)

class NextButton(PaginatorButton):
    async def update_page(self, view: WeeklySongsView, interaction: discord.Interaction):
        await view.action(self, interaction, action_id=2)

class LastButton(PaginatorButton):
    async def update_page(self, view: WeeklySongsView, interaction: discord.Interaction):
        await view.action(self, interaction, action_id=3)

class ButtonActionRow(discord.ui.ActionRow):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id', None)
        self.action_callback = kwargs.pop('action', None)
        super().__init__(*args, **kwargs)

        self.first_button = FirstButton(style=discord.ButtonStyle.secondary, emoji=constants.FIRST_EMOJI, user_id=self.user_id)
        self.previous_button = PreviousButton(style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, user_id=self.user_id)
        self.page_label = PaginatorButton(style=discord.ButtonStyle.primary, label="1/1",  user_id=self.user_id)
        self.next_button = NextButton(style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI, user_id=self.user_id)
        self.last_button = LastButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id)

        self.add_item(self.first_button)
        self.add_item(self.previous_button)
        self.add_item(self.page_label)
        self.add_item(self.next_button)
        self.add_item(self.last_button)

class DailyCommandHandler:
    def __init__(self, bot) -> None:
        self.bot = bot

    def create_daily_embeds(self, daily_tracks, chunk_size=8):
        embeds = []
        
        for i in range(0, len(daily_tracks), chunk_size):
            embed = discord.Embed(title="Weekly Rotation Tracks", colour=constants.ACCENT_COLOUR)
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

            track_list = constants.get_jam_tracks(use_cache=True)
            # open('response.json', 'w').write(response.text)

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

                if (event_type.startswith('PilgrimSong.') or event_type.startswith('Sparks.Spotlight.')) and active_since_date and active_until_date:
                    if active_since_date <= current_time <= active_until_date:
                        shortname = event_type.replace('PilgrimSong.', '').replace('Sparks.Spotlight.', '')
                        related_spotlight = discord.utils.find(lambda event: event['eventType'] == f'Sparks.Spotlight.{shortname}', active_events)
                        track_data = discord.utils.find(lambda t: t['track']['sn'] == shortname, track_list)
                        if track_data:
                            daily_tracks.append({
                                'metadata': track_data,
                                'in_spotlight': related_spotlight != None
                            })

            return daily_tracks
        except Exception as e:
            logging.error(exc_info=e)
            return []
        
    async def handle_interaction(self, interaction: discord.Interaction):
        # tracks = constants.get_jam_tracks() # Fix circular import...

        await interaction.response.defer()
        weekly_songs = self.fetch_daily_shortnames()

        # if not tracks or not weekly_songs:
        #     await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
        #     return

        # daily_tracks = []
        
        # weekly_songs.sort(key=lambda x: x['shortname'])

        # for song in weekly_songs:
        #     track = discord.utils.find(lambda t: t['track']['sn'] == song['shortname'], tracks)
        #     if not track:
        #         continue

        #     title = track['track'].get('tt', 'Unknown Title')
        #     artist = track['track'].get('an', 'Unknown Artist')

        #     difficulty_str = constants.generate_difficulty_string(track['track'].get('in', {}))
        #     daily_tracks.append({
        #         'title': title,
        #         'artist': artist,
        #         'difficulty': difficulty_str
        #     })

        # await interaction.response.defer()

        # embeds = self.create_daily_embeds(daily_tracks)
        view = WeeklySongsView(weekly_songs, interaction.user.id)
        view.message = await interaction.edit_original_response(view=view)
        
class ShopCommandHandler:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.search_embed_handler = SearchEmbedHandler()

    def create_embeds(self, shop_tracks, title, content_tracks):
        embeds = []

        for i in range(0, len(shop_tracks), 5):
            embed = discord.Embed(title=title, colour=constants.ACCENT_COLOUR)
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

    async def handle_interaction(self, interaction: discord.Interaction, pro_vocals_only: bool = False):
        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        
        await interaction.response.defer()
        
        if pro_vocals_only:
            midi_tool = MidiArchiveTools()

            filtered_tracks = []
            for track in tracks:
                midi_url = track['track'].get('mu', '')
                if midi_url:
                    midi_file = await midi_tool.save_chart(track['track']['mu'])
                    if os.path.exists(midi_file):
                        with open(midi_file, 'rb') as mf:
                            if b'PRO VOCALS' in mf.read():
                                filtered_tracks.append(track)

            tracks = filtered_tracks

        track_list = constants.sort_track_list(tracks)

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
                return discord.utils.find(lambda t: t['metadata']['track']['sn'] == sn, weekly_tracks) != None

            track_list = list(filter(indaily, track_list))

        async def re_roll():
            chosen_track = random.choice(track_list)
            embed = await self.search_embed_handler.generate_track_embed(chosen_track, is_random=True)
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
                return discord.utils.find(lambda t: t['metadata']['track']['sn'] == sn, daily_tracks) != None

            track_list = list(filter(indaily, track_list))

        async def re_roll():
            chosen_tracks = []
            for i in range(limit):
                chosen_tracks.append(random.choice(track_list))

            embed = discord.Embed(title="Your random setlist!", description=f"The {limit} tracks are...", colour=constants.ACCENT_COLOUR)
            embed.add_field(name="", value="\n".join([f'- **{str(track["track"]["tt"])}** - *{str(track["track"]["an"])}*' for track in chosen_tracks]))
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = OneButtonSimpleView(on_press=re_roll, user_id=interaction.user.id, label="Reroll Setlist")
        reroll_view.message = await interaction.original_response()

        await re_roll()

class ProVocalsHandler:
    def __init__(self, bot) -> None:
        self.bot = bot

    def get_pro_vocals_counts(self):
        tracks = constants.get_jam_tracks(use_cache=True)

        all_midi = [{'mid': f'{track['track']['mu'].split('/')[3].split('.')[0]}.mid', 'sn': track['track']['sn']} for track in tracks]
        missing_midi = []

        songs_with_pro_vocals = []
        songs_without_pro_vocals = []

        for t in all_midi:
            midi = t['mid']
            if not os.path.exists(constants.MIDI_FOLDER + midi):
                missing_midi.append(midi)
            else:
                mid = open(constants.MIDI_FOLDER + midi, 'rb')
                pro_vocals_track = b'PRO VOCALS' in mid.read() # the easiest way
                mid.close()
                if pro_vocals_track:
                    songs_with_pro_vocals.append(t)
                else:
                    songs_without_pro_vocals.append(t)

        return (songs_with_pro_vocals, songs_without_pro_vocals, missing_midi)