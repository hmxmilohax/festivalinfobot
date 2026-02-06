import asyncio
from datetime import datetime, timezone
import functools
import hashlib
import json
import logging
import os
import random
import shutil
import subprocess
from typing import List, Union
import concurrent
import concurrent.futures
import discord
from discord.ext import commands
import requests

from bot import constants
from bot import database
from bot.database import JamTrackEvents, SubscriptionChannel, SubscriptionObject, SubscriptionUser
from bot.embeds import SearchEmbedHandler, StatsCommandEmbedHandler
from bot.tools.midi import MidiArchiveTools
from bot.views import history_views as history_tools
from bot.views.previewpersist import PreviewButton
from bot.views.wishlistpersist import WishlistButton
from bot.tracks import JamTrackHandler

import bot.tools.compare_midi as midi_comparison

import bot.tools.sparks_tracks as sparks_tracks
# import cloudscraper # FUCK YOU CLOUDFLARE (jk i love you)

def save_known_songs(songs):
    # Fetch jam tracks using the API call
    # logging.debug(f'[GET] {constants.CONTENT_API}')
    # response = requests.get(constants.CONTENT_API)
    # response.raise_for_status()

    # data = response.json()
    data = constants.JAM_TRACK_CACHE

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H.%M.%S')
    unique_id = hashlib.md5(timestamp.encode()).hexdigest()[:6]

    file_prefix = "spark-tracks"
    file_name = f"{file_prefix}_{timestamp}Z_{unique_id}.json"
    
    folder_path = constants.LOCAL_JSON_FOLDER
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    json_files = sorted(
        [f for f in os.listdir(folder_path) if f.startswith("spark-tracks") and f.endswith(".json")],
        key=lambda x: os.path.getmtime(os.path.join(folder_path, x)),
        reverse=True
    )

    recent_files_content = [constants.load_json_from_file(os.path.join(folder_path, f)) for f in json_files[:3]]

    current_songs_data = [song['track']['sn'] for song in songs]
    current_tracks_data = songs

    current_songs_json = json.dumps(current_songs_data, sort_keys=True)

    known_tracks_file_path = constants.SONGS_FILE
    known_songs_file_path = constants.SHORTNAME_FILE
    
    if not os.path.exists(known_tracks_file_path):
        with open(known_tracks_file_path, 'w') as known_tracks_file:
            json.dump([], known_tracks_file, indent=4)
    if not os.path.exists(known_songs_file_path):
        with open(known_songs_file_path, 'w') as known_songs_file:
            json.dump([], known_songs_file, indent=4)

    with open(known_tracks_file_path, 'w') as known_tracks_file:
        json.dump(current_tracks_data, known_tracks_file, indent=4)

    with open(known_songs_file_path, 'w') as known_songs_file:
        json.dump(current_songs_data, known_songs_file, indent=4)

    for content in recent_files_content:
        if json.dumps(content, sort_keys=True) == json.dumps(data, sort_keys=True):
            return

    file_path = os.path.join(folder_path, file_name)
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
    logging.info(f"New file saved as {file_name}")

def load_known_songs(shortnames:bool = False):
    path = constants.SONGS_FILE if not shortnames else constants.SHORTNAME_FILE
    if os.path.exists(path):
        with open(path, 'r', encoding="utf-8") as file:
            return json.loads(file.read())
    return list()

class HistoryHandler():
    def __init__(self, bot) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.midi_handler = MidiArchiveTools()
        self.search_embed_handler = SearchEmbedHandler()
        self.bot: commands.Bot = bot
        self.process_executor = concurrent.futures.ProcessPoolExecutor()
        pass

    async def track_midi_changes(self, json_files, shortname, session_hash):
        midi_file_changes = []
        seen_midi_files = {}
        json_files = [f for f in json_files if f.endswith('.json')]
        logging.debug(f"Total JSON files to process: {len(json_files)}")

        try:
            for idx, json_file in enumerate(json_files):
                file_path = os.path.join(constants.LOCAL_JSON_FOLDER, json_file)
                load_action = functools.partial(constants.load_json_from_file, file_path)
                file_content = await self.bot.loop.run_in_executor(None, load_action)
                if not file_content:
                    logging.warning(f"Failed to load content from {file_path}, skipping to next file.")
                    continue

                song_data = file_content.get(shortname)
                if not song_data or 'track' not in song_data:
                    continue

                midi_file_url = song_data['track'].get('mu', None)
                last_modified = song_data.get('lastModified', None)

                if midi_file_url and midi_file_url not in seen_midi_files:
                    seen_midi_files[midi_file_url] = True
                    local_midi_file = await self.midi_handler.save_chart(midi_file_url)
                    midi_file_changes.append((last_modified, local_midi_file))

        except Exception as e:
            logging.error(f"Error processing {json_file}", exc_info=e)
        
        return midi_file_changes
    
    def track_meta_changes(self, json_files, shortname, session_hash):
        changes = []
        json_files = [f for f in json_files if f.endswith('.json')]
        logging.debug(f"Total JSON files to process: {len(json_files)}")

        try:
            for idx, json_file in enumerate(json_files):
                file_path = os.path.join(constants.LOCAL_JSON_FOLDER, json_file)
                file_content = constants.load_json_from_file(file_path)
                if not file_content:
                    logging.error(f"Failed to load content from {file_path}, skipping to next file.")
                    continue

                song_data = file_content.get(shortname)
                if not song_data or 'track' not in song_data:
                    continue

                last_modified = song_data.get('lastModified', None)
                for key, value in song_data.get('track', {}).items():
                    change = (key, value)

                    all_changes = [value for date, value in changes]

                    if change and change not in all_changes:
                        changes.append((last_modified, change))

        except Exception as e:
            logging.error(f"Error processing {json_file}", exc_info=e)

        grouped_changes = {}
        for item in changes:
            key = item[0]
            if key not in grouped_changes:
                grouped_changes[key] = []
            grouped_changes[key].append(item[1])
        
        return grouped_changes
    
    def comparison_process(self, old_midi_file, new_midi_file, session_hash, track_name):
        return midi_comparison.run_comparison(old_midi_file, new_midi_file, session_hash, track_name)

    async def process_chart_url_change(self, old_url:str, new_url:str, track_name:str, last_modified_old, last_modified_new, session_hash:str):
        """
        # dict: song information
        # list(str): files
        this function now returns only a Tuple[Dict, List(str)]
        """
        old_midi_file = await self.midi_handler.save_chart(old_url)
        new_midi_file = await self.midi_handler.save_chart(new_url)

        if old_midi_file and new_midi_file:
            old_midi_out_path = os.path.join(constants.TEMP_FOLDER, f"{track_name}_old_{session_hash}.mid")
            new_midi_out_path = os.path.join(constants.TEMP_FOLDER, f"{track_name}_new_{session_hash}.mid")

            shutil.copy(old_midi_file, old_midi_out_path)
            shutil.copy(new_midi_file, new_midi_out_path)

            comparison = functools.partial(midi_comparison.run_comparison, old_midi_out_path, new_midi_out_path, session_hash, track_name)

            # comparison_command = ['python', 'compare_midi.py', old_midi_out_path, new_midi_out_path, session_hash, track_name]
            # result = subprocess.run(comparison_command, capture_output=True, text=True)
            # # Check the output for errors, just in case
            # if result.returncode != 0:
            #     return None

            comparison_result = await self.bot.loop.run_in_executor(self.process_executor, comparison)

            # Check for the completion flag in the output
            if comparison_result == True:
                # Now that comparison is complete, check for any image output
                comparison_images = [f for f in os.listdir(constants.TEMP_FOLDER) if f.endswith(f'{session_hash}.png')]

                logging.debug(comparison_images)

                last_modified_old_str = discord.utils.format_dt(datetime.fromisoformat(last_modified_old.replace('Z', '+00:00')), style='F')
                last_modified_new_str = discord.utils.format_dt(datetime.fromisoformat(last_modified_new.replace('Z', '+00:00')), style='F')

                if comparison_images:
                    list_of_images = []

                    for image in comparison_images:
                        image_path = os.path.abspath(os.path.join(constants.TEMP_FOLDER, image))
                        list_of_images.append(image_path)

                    return ({
                        'last_modified_old': last_modified_old_str,
                        'last_modified_new': last_modified_new_str,
                        'shortname': track_name
                    }, list_of_images)
        return ({}, [])

    def fetch_local_history(self):
        json_files = []
        try:
            for file_name in os.listdir(constants.LOCAL_JSON_FOLDER):
                if file_name.endswith('.json'):
                    json_files.append(file_name)
        except Exception as e:
            logging.error(f"Error reading local JSON files", exc_info=e)
        return sorted(json_files)

    async def handle_metahistory_interaction(self, interaction: discord.Interaction, song:str):
        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)
        logging.debug(f"Generated session hash: {session_hash} for user: {user_id}")

        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'))
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            # logging.error(f"No tracks found matching {song}.")
            await interaction.response.send_message(embed=constants.common_error_embed(f'The search query {song} did not give any results.'))
            return
        
        await interaction.response.defer()

        track_data = matched_tracks[0]
        album_art_url = track_data['track'].get('au')
        shortname = track_data['track'].get('sn')
        actual_title = track_data['track'].get('tt', 'Unknown Title')
        actual_artist = track_data['track'].get('an', 'Unknown Artist')

        json_files = self.fetch_local_history()
        if not json_files:
            await interaction.edit_original_response(embed=constants.common_error_embed("No local history files found."))
            return

        job = functools.partial(self.track_meta_changes, json_files, shortname, session_hash)
        metadata_changes = await self.bot.loop.run_in_executor(None, job) # prevents it from shitting itself
        
        if len(metadata_changes.keys()) <= 1: # You won't be able to get here
            await interaction.edit_original_response(embed=constants.common_error_embed(f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the metadata exists."))
            return
        
        changes = []
        for date, change in metadata_changes.items():
            props_of_change = {}
            for k, v in change:
                props_of_change[k] = v
            changes.append([date, props_of_change])

        embed_list = []
        
        for i, change in enumerate(changes):
            if i > 0:
                date = change[0]
                properties_that_changed = change[1]
                
                prev = changes[i - 1]
                prev_date = prev[0]
                prev_properties = prev[1]

                embed = discord.Embed(title=f"**{actual_title}** - *{actual_artist}*", description=f"**Logged metadata change:** \n{discord.utils.format_dt(StatsCommandEmbedHandler().iso_to_unix_timestamp(prev_date), style='R')} to {discord.utils.format_dt(StatsCommandEmbedHandler().iso_to_unix_timestamp(date), style='R')}", colour=constants.ACCENT_COLOUR)
                embed.set_thumbnail(url=album_art_url)

                for pk, pv in properties_that_changed.items():
                    previous_property = None
                    if not pk in prev_properties.keys():
                        prev_date = changes[0][0]
                        previous_property = changes[0][1].get(pk)
                    else:
                        previous_property = prev_properties.get(pk)

                    field_name = f"{constants.SIMPLE_COMPARISONS.get(pk, f'`{pk}`')} changed"
                    if pk == 'qi':
                        qi_comparisons = self.search_embed_handler.compare_qi_fields(previous_property, pv)
                        if qi_comparisons:
                            for field in qi_comparisons:
                                embed.add_field(name="QI Field Update", value=field, inline=False)
                    elif pk == 'in':
                            # Report changes in difficulty fields
                            for value, name in constants.DIFFICULTY_COMPARISONS.items():
                                if previous_property.get(value, -1) != pv.get(value, -1):
                                    embed.add_field(
                                        name=f"{name} difficulty changed", 
                                        value=f"```Old: \"{constants.generate_difficulty_bar(previous_property.get(value, -1))}\"\nNew: \"{constants.generate_difficulty_bar(pv.get(value, -1))}\"```", 
                                        inline=False
                                    )

                            for key in pv.keys():
                                if key not in constants.DIFFICULTY_COMPARISONS.keys() and key != '_type':
                                    embed.add_field(
                                        name=f"{key} (*Mismatched Difficulty*)", 
                                        value=f"```Found: {constants.generate_difficulty_bar(pv[key])}```", 
                                        inline=False
                                    )
                    else:
                        if pk == 'dn':
                            # duration field
                            previous_s = previous_property // 60
                            previous_m = previous_property % 60
                            current_s = pv // 60
                            current_m = pv % 60
                            prev_val = f"{previous_s}m {previous_m}s"
                            cur_val = f"{current_s}m {current_m}s"
                            embed.add_field(name=field_name, value=f"```Old: \"{previous_property}\" ({prev_val})\nNew: \"{pv}\" ({cur_val})```", inline=False)
                            continue

                        embed.add_field(name=field_name, value=f"```Old: \"{previous_property}\"\nNew: \"{pv}\"```", inline=False)

                embed_list.append(embed)

        view = constants.PaginatorView(embed_list, interaction.user.id)
        view.message = await interaction.original_response()
        await interaction.edit_original_response(view=view, embed=view.get_embed())

    async def process_all_midi_changes(self, midi_file_changes, shortname, actual_title, actual_artist, album_art_url, session_hash):
        results = []

        for i in range(1, len(midi_file_changes)):
            logging.info(f'{shortname} chart history is running as we speak step {i}')
            old_midi = midi_file_changes[i - 1]
            new_midi = midi_file_changes[i]
            old_midi_file = old_midi[1]
            new_midi_file = new_midi[1]

            real_session_hash = f"{session_hash}_{i}"

            this_res = await self.process_chart_url_change(
                old_midi_file, new_midi_file, shortname, old_midi[0], new_midi[0], real_session_hash
            )
            logging.info(this_res)
            results.append(this_res)
        return results

    async def handle_interaction(self, interaction: discord.Interaction, song:str, use_channel:bool = False):
        # await interaction.response.send_message(embed=constants.common_error_embed('This command is currently broken at the moment due to recent structure changes. Please wait until it is fixed. Thank you'))
        # return

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)
        logging.info(f"Generated session hash: {session_hash} for user: {user_id}")

        tracks = constants.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'))
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            # logging.error(f"No tracks found matching {song}.")
            await interaction.response.send_message(embed=constants.common_error_embed(f'The search query {song} did not give any results.'))
            return
        
        await interaction.response.defer()

        track_data = matched_tracks[0]
        album_art_url = track_data['track'].get('au')
        shortname = track_data['track'].get('sn')
        actual_title = track_data['track'].get('tt', 'Unknown Title')
        actual_artist = track_data['track'].get('an', 'Unknown Artist')

        json_files = self.fetch_local_history()
        if not json_files:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"No local history files found."))
            return

        midi_file_changes = await self.track_midi_changes(json_files, shortname, session_hash)
        logging.info(f"Found {len(midi_file_changes)} MIDI file changes for {shortname}.")

        await interaction.edit_original_response(embed=constants.common_success_embed(f"Processing the diff for **{actual_title}** - *{actual_artist}*, please wait...\n-# This operation can take more than a minute."))

        if len(midi_file_changes) <= 1:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the MIDI file exists."))
            return
        
        # array_of_tuples_of_embeds_and_files = [] # [(embed, file), (embed, file)]

        # Call the new function that uses asyncio.gather and a thread pool
        results = await self.process_all_midi_changes(midi_file_changes, shortname, actual_title, actual_artist, album_art_url, session_hash)
        logging.info(results)

        the_view_itself = history_tools.HistoryView(results, session_hash, interaction.user.id, track_data)
        fpaths = the_view_itself.update_components()
        attchs = [discord.File(fp, filename=os.path.basename(fp)) for fp in fpaths]

        await interaction.edit_original_response(embed=constants.common_success_embed("Please wait..."))
        msg = await interaction.followup.send(wait=True, view=the_view_itself, files=attchs)

        the_view_itself.message = msg

class LoopCheckHandler():
    def __init__(self, bot : commands.Bot) -> None:
        self.bot = bot
        self.embed_handler = SearchEmbedHandler()
        self.history_handler = HistoryHandler(bot)
        self.midi_tools = MidiArchiveTools()
        self.jam_track_handler = JamTrackHandler()

    async def handle_activity_task(self):
        tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=600)
        num_tracks = len(tracks)
        random_jam_track = random.choice(tracks)

        servers = random.choice([True, False]) # bruh

        activity = discord.Activity(
            type=discord.ActivityType.watching if servers else discord.ActivityType.playing,
            name=f"{len(self.bot.guilds)} servers" if servers else f"{num_tracks} Jam Tracks",
            state=f"{random_jam_track['track']['tt']} - {random_jam_track['track']['an']}",
        )

        # activity = discord.Game("IMPORTANT-Read bio")

        await self.bot.change_presence(activity=activity, status=discord.Status.online)

        logging.info("Presence updated successfully.")

    async def handle_task(self):
        logging.info("Checking for new songs...")
        tracks = constants.get_jam_tracks() # no cache here

        if not tracks:
            # logging.error('Could not fetch tracks.')
            return
        
        for track in tracks:
            await self.midi_tools.save_chart(track['track']['mu'], decrypt=True, log=False)

        # web_catalog_url = 'https://www.fortnite.com/item-shop/jam-tracks?lang=en-US&_data=routes%2Fitem-shop.jam-tracks._index'

        # logging.debug(f'[GET] {web_catalog_url}')
        # reqs = cloudscraper.create_scraper()
        # req = reqs.get(web_catalog_url)

        # if req.ok:
        #     web_catalog_response_path = f'{constants.CACHE_FOLDER}WebCatalog.json'
        #     with open(web_catalog_response_path, 'w', encoding='utf-8') as f:
        #         f.write(req.text)
        # else:
        #     logging.error(f"Failed to fetch web catalog: {req.status_code} - {req.reason} {req.text}")

        session_hash = constants.generate_session_hash(self.bot.start_time, self.bot.start_time)

        try:
            await sparks_tracks.main()
        except Exception as e:
            logging.error("", exc_info=e)

        known_tracks = load_known_songs()
        known_shortnames = load_known_songs(shortnames=True)

        save_known_songs(tracks)

        current_tracks_dict = {track['track']['sn']: track for track in tracks}
        known_tracks_dict = {track['track']['sn']: track for track in known_tracks}

        new_songs = []
        modified_songs = []
        removed_songs = []

        for shortname, known_track in known_tracks_dict.items():
            if shortname not in current_tracks_dict:
                removed_songs.append(known_track)

        for shortname, current_track in current_tracks_dict.items():
            if shortname not in known_tracks_dict:
                new_songs.append(current_track)
            else:
                known_track = known_tracks_dict[shortname]
                if current_track != known_track:
                    modified_songs.append((known_track, current_track))

        bot_config: database.Config = self.bot.config
        combined_channels: list[SubscriptionObject] = await bot_config.get_all()
        target_id = 1328391774720229517
        obj = discord.utils.find(lambda x: x.id == target_id, combined_channels)
        if obj:
            idx = combined_channels.index(obj)
            if idx is not None:
                target = combined_channels.pop(idx)
                random.shuffle(combined_channels)
                combined_channels.insert(0, target)
            else:
                random.shuffle(combined_channels)

        start = datetime.now()

        if len(new_songs) != 0 or len(modified_songs) != 0 or len(removed_songs) != 0:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(f"Sending to {len(combined_channels)} channels")

        session_hashes_all = [session_hash]

        modified_songs_data = [] # [(modified metadata CV2 container, ( dict, list(file) ))]

        # here we encounter a bug
        # handle_task can run for over 90 minutes
        # that's why its in a separate ""thread""
        # but unfortunately, this means that the underlying functions
        # (process_chart_url_change > comparison_process > run_comparison)
        # that use matplotlib will experience race conditions
        # if multiple batches are processed at the same time
        # plots rendered by matplotlib (which takes a while)
        # will be cleared or end up malformed
        # so we "can't have" two songs processing at the same time or else we risk
        # malformed plots
        for old_song, new_song in modified_songs:
            # session_hash = constants.generate_session_hash(self.bot.start_time, self.bot.start_time)
            session_hash = constants.generate_session_hash(self.bot.start_time, datetime.now().timestamp())
            session_hashes_all.append(session_hash)
            old_url = old_song['track'].get('mu', '')
            new_url = new_song['track'].get('mu', '')
            track_name = new_song['track']['tt']
            short_name = new_song['track']['sn']
            artist_name = new_song['track']['an']
            album_art_url = new_song['track']['au']
            last_modified_old = old_song.get('lastModified', None)
            last_modified_new = new_song.get('lastModified', None)
            local_midi_file_old = await self.midi_tools.save_chart(old_url)
            local_midi_file_new = await self.midi_tools.save_chart(new_url)

            file_diffs = None

            if (old_url != new_url):
                logging.info(f"Chart URL changed:")
                logging.info(f"Old: {local_midi_file_old}")
                logging.info(f"New: {local_midi_file_new}")

                logging.debug(f"Running process_chart_url_change for {local_midi_file_old} and {local_midi_file_new}")
                file_diffs = await self.history_handler.process_chart_url_change(
                    old_url=local_midi_file_old, 
                    new_url=local_midi_file_new, 
                    track_name=short_name, 
                    last_modified_old=last_modified_old, 
                    last_modified_new=last_modified_new, 
                    session_hash=session_hash
                ) # this makes me dizzy lol

            container = self.embed_handler.generate_modified_track_embed(old=old_song, new=new_song)

            modified_songs_data.append((container, file_diffs))

        for channel_to_send in combined_channels:
            if channel_to_send.type == 'channel':
                channel = self.bot.get_channel(channel_to_send.id)
                # if not channel:
                #     try:
                #         channel = await self.bot.fetch_channel(channel_to_send.id)
                #     except discord.NotFound:
                #         channel = None
                #     except discord.Forbidden:
                #         logging.warning(f"Forbidden to fetch channel {channel_to_send.id}, skipping.")
                #     except discord.HTTPException as e:
                #         logging.error(f"HTTPException when fetching channel {channel_to_send.id}, skipping.", exc_info=e)
                #     except discord.InvalidData as e:
                #         logging.error(f"InvalidData when fetching channel {channel_to_send.id}, skipping.", exc_info=e)
                #     except Exception as e:
                #         logging.error(f"Unexpected error when fetching channel {channel_to_send.id}, skipping.", exc_info=e)
            elif channel_to_send.type == 'user':
                channel = self.bot.get_user(channel_to_send.id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_user(channel_to_send.id)
                    except discord.NotFound:
                        channel = None
                    except discord.HTTPException:
                        logging.error(f"HTTPException when fetching user {channel_to_send.id}, skipping.", exc_info=e)
                    except Exception as e:
                        logging.error(f"Unexpected error when fetching user {channel_to_send.id}, skipping.", exc_info=e)
            else:
                channel = None

            if not channel:
                logging.warning(f"{channel_to_send.type.capitalize()} with ID {channel_to_send.id} not found.")
                continue

            if isinstance(channel, discord.abc.GuildChannel):
                if channel.permissions_for(channel.guild.me).send_messages == False:
                    logging.warning(f"We do not have permission to send messages to {channel.id}, skipping.")
                    continue

            content = ""
            if isinstance(channel_to_send, SubscriptionChannel):
                role_pings = []
                for role in channel_to_send.roles:
                    role_pings.append(f"<@&{role}>")
                content = " ".join(role_pings)

            if new_songs and JamTrackEvents.Added.value.id in channel_to_send.events:
                logging.info(f"New songs sending to channel {channel.id}")
                for new_song in new_songs:
                    embed = await self.embed_handler.generate_track_embed(new_song, is_new=True)

                    view = discord.ui.View(timeout=None)
                    view.add_item(PreviewButton(new_song['track']['sn']))
                    view.add_item(WishlistButton(new_song['track']['sn'], 'add', channel.id))

                    try:
                        message = await channel.send(content=content, embed=embed, view=view)

                    except discord.Forbidden as e:
                        logging.warning(f"Channel {channel.id} cannot be sent messages to, skipped", exc_info=e)
                        break
                        
                    except Exception as e:
                        logging.warning(f"Error sending message to channel {channel.id}", exc_info=e)

            if modified_songs and JamTrackEvents.Modified.value.id in channel_to_send.events:
                logging.info(f"Modified songs sending to channel {channel.id}")

                if len(modified_songs_data) > 0:
                    if content != "":
                        message = await channel.send(content=content)
                
                for song_metadata_diff_container, chart_diffs_data in modified_songs_data:
                    view: discord.ui.LayoutView = discord.ui.LayoutView()
                    view.add_item(song_metadata_diff_container)
                    files: list[str] = []

                    if chart_diffs_data:
                        song_data = chart_diffs_data[0]
                        files = chart_diffs_data[1]

                        track_data = discord.utils.find(lambda x: x['track']['sn'] == song_data['shortname'], tracks)
                        container = discord.ui.Container(
                                discord.ui.Section(
                                    discord.ui.TextDisplay(f'**{track_data["track"]["tt"]}** - *{track_data["track"]["an"]}*\nDetected changes between:\n{song_data['last_modified_old']} and {song_data['last_modified_new']}',),
                                    accessory=discord.ui.Thumbnail(track_data['track']['au'])
                                ),
                                discord.ui.MediaGallery(
                                    *[discord.MediaGalleryItem(media=f'attachment://{os.path.basename(file)}') for file in files[:10]]
                                ),
                                accent_colour=constants.ACCENT_COLOUR
                            )
                        if len(files) > 10:
                            container.add_item(discord.ui.TextDisplay(f"*{len(files) - 10} more images not included*"))
                        view.add_item(
                            container   
                        )

                    try:
                        message = await channel.send(view=view, files=[discord.File(fpath) for fpath in files[:10]] if files else None)

                    except discord.Forbidden as e:
                        logging.warning(f"Channel {channel.id} cannot be sent messages to, skipped", exc_info=e)
                        break

                    except Exception as e:
                        logging.warning(f"Error sending message to channel {channel.id}", exc_info=e)

            if removed_songs and JamTrackEvents.Removed.value.id in channel_to_send.events:
                logging.info(f"Removed songs sending to channel {channel.id}")
                for removed_song in removed_songs:
                    embed = await self.embed_handler.generate_track_embed(removed_song, is_removed=True)
                    try:
                        message = await channel.send(content=content, embed=embed)

                    except discord.Forbidden as e:
                        logging.warning(f"Channel {channel.id} cannot be sent messages to, skipped", exc_info=e)
                        break

                    except Exception as e:
                        logging.warning(f"Error sending message to channel {channel.id}", exc_info=e)

        logging.info(f"Done checking for new songs: New: {len(new_songs)} | Modified: {len(modified_songs)} | Removed: {len(removed_songs)}")

        if len(new_songs) != 0 or len(modified_songs) != 0 or len(removed_songs) != 0:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(f"Sending completed for {len(combined_channels)} channels! Took {(datetime.now() - start).seconds}s")

        for _hash in session_hashes_all:
            constants.delete_session_files(str(_hash))

class HistoryException(Exception):
    def __init__(self, desc, *args: object) -> None:
        self.desc = desc
        super().__init__(*args)
