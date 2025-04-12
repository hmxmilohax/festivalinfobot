import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import random
import shutil
import subprocess
from typing import List, Union
import concurrent
import discord
from discord.ext import commands
import requests

from bot import constants
from bot import config
from bot.config import JamTrackEvent, SubscriptionChannel, SubscriptionObject, SubscriptionUser
from bot.embeds import SearchEmbedHandler, StatsCommandEmbedHandler
from bot.midi import MidiArchiveTools
from bot.tools import history as history_tools
from bot.tools.previewpersist import PreviewButton
from bot.tracks import JamTrackHandler

import sparks_tracks

def save_known_songs(songs):
    # Fetch jam tracks using the API call
    logging.debug(f'[GET] {constants.CONTENT_API}')
    response = requests.get(constants.CONTENT_API)
    response.raise_for_status()

    data = response.json()
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
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.midi_handler = MidiArchiveTools()
        self.search_embed_handler = SearchEmbedHandler()
        pass

    def track_midi_changes(self, json_files, shortname, session_hash):
        midi_file_changes = []
        seen_midi_files = {}
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

                midi_file_url = song_data['track'].get('mu', None)
                last_modified = song_data.get('lastModified', None)

                if midi_file_url and midi_file_url not in seen_midi_files:
                    seen_midi_files[midi_file_url] = True
                    local_midi_file = self.midi_handler.download_and_archive_midi_file(midi_file_url, shortname)  # Download the .dat file
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

    async def process_chart_url_change(self, old_url:str, new_url:str, track_name:str, song_title:str, artist_name:str, album_art_url:str, last_modified_old, last_modified_new, session_hash:str):
        """
        this function now returns only a List[Tuple(Embed, File)]
        """
        old_midi_file = self.midi_handler.decrypt_dat_file(old_url, session_hash)

        new_midi_file = self.midi_handler.decrypt_dat_file(new_url, session_hash)

        if old_midi_file and new_midi_file:
            old_midi_out_path = os.path.join(constants.TEMP_FOLDER, f"{track_name}_old_{session_hash}.mid")
            new_midi_out_path = os.path.join(constants.TEMP_FOLDER, f"{track_name}_new_{session_hash}.mid")

            shutil.copy(old_midi_file, old_midi_out_path)
            shutil.copy(new_midi_file, new_midi_out_path)

            comparison_command = ['python', 'compare_midi.py', old_midi_out_path, new_midi_out_path, session_hash]
            result = subprocess.run(comparison_command, capture_output=True, text=True)
            # Check the output for errors, just in case
            if result.returncode != 0:
                return []

            # Check for the completion flag in the output
            if "MIDI comparison completed successfully" in result.stdout:
                # Now that comparison is complete, check for any image output
                comparison_images = [f for f in os.listdir(constants.TEMP_FOLDER) if f.endswith(f'{session_hash}.png')]

                last_modified_old_str = discord.utils.format_dt(datetime.fromisoformat(last_modified_old.replace('Z', '+00:00')), style='D')
                last_modified_new_str = discord.utils.format_dt(datetime.fromisoformat(last_modified_new.replace('Z', '+00:00')), style='D')

                if comparison_images:
                    tuple_of_embeds_and_files = []

                    # do not use edit_original_response here
                    for image in comparison_images:
                        image_path = os.path.abspath(os.path.join(constants.TEMP_FOLDER, image))
                        # file = discord.File(image_path, filename=image)
                        embed = discord.Embed(
                            title=f"",
                            description=f"**{song_title}** - *{artist_name}*\nDetected changes between:\n{last_modified_old_str} and {last_modified_new_str}",
                            color=0x8927A1
                        )
                        embed.set_image(url=f"attachment://{image}")
                        embed.set_thumbnail(url=album_art_url)
                        tuple_of_embeds_and_files.append((embed, image_path))
                        
                    return tuple_of_embeds_and_files
        return []

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

        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'))
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            logging.error(f"No tracks found matching {song}.")
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

        metadata_changes = self.track_meta_changes(json_files, shortname, session_hash)
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

                embed = discord.Embed(title=f"**{actual_title}** - *{actual_artist}*", description=f"**Logged metadata change:** \n{discord.utils.format_dt(StatsCommandEmbedHandler().iso_to_unix_timestamp(prev_date), style='R')} to {discord.utils.format_dt(StatsCommandEmbedHandler().iso_to_unix_timestamp(date), style='R')}", color=0x8927A1)

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
                                if previous_property.get(value, 0) != pv.get(value, 0):
                                    embed.add_field(
                                        name=f"{name} difficulty changed", 
                                        value=f"```Old: \"{constants.generate_difficulty_bar(previous_property.get(value, 0))}\"\nNew: \"{constants.generate_difficulty_bar(pv.get(value, 0))}\"```", 
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
                        embed.add_field(name=field_name, value=f"```Old: {previous_property}\nNew: {pv}```", inline=False)

                embed_list.append(embed)

        view = constants.PaginatorView(embed_list, interaction.user.id)
        view.message = await interaction.original_response()
        await interaction.edit_original_response(view=view, embed=view.get_embed())

    async def process_all_midi_changes(self, midi_file_changes, shortname, actual_title, actual_artist, album_art_url, session_hash):
        # assisted by gemini

        tasks = []
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool: # Create a thread pool
            for i in range(1, len(midi_file_changes)):
                print(f'{shortname} chart history is running as we speak step {i}')
                old_midi = midi_file_changes[i - 1]
                new_midi = midi_file_changes[i]
                old_midi_file = old_midi[1]
                new_midi_file = new_midi[1]

                #  Define a helper function to run in the thread.  This helper *awaits* the
                #  self.process_chart_url_change coroutine.
                async def run_in_thread():
                    return await self.process_chart_url_change(
                        old_midi_file, new_midi_file, shortname, actual_title, actual_artist, album_art_url, old_midi[0], new_midi[0], session_hash
                    )

                task = loop.run_in_executor(
                    pool,
                    lambda: asyncio.run(run_in_thread())  # Pass a function that runs the coroutine
                )
                tasks.append(task)

            # Use asyncio.gather to run all the tasks concurrently.
            # The results will be in the same order as the tasks were added.
            results = await asyncio.gather(*tasks)
        return results

    async def handle_interaction(self, interaction: discord.Interaction, song:str, use_channel:bool = False):
        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)
        logging.info(f"Generated session hash: {session_hash} for user: {user_id}")

        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'))
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            logging.error(f"No tracks found matching {song}.")
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

        midi_file_changes = self.track_midi_changes(json_files, shortname, session_hash)
        logging.info(f"Found {len(midi_file_changes)} MIDI file changes for {shortname}.")

        await interaction.edit_original_response(embed=constants.common_success_embed(f"Processing the diff for **{actual_title}** - *{actual_artist}*, please wait...\n-# This operation can take more than a minute."))

        if len(midi_file_changes) <= 1:
            await interaction.edit_original_response(embed=constants.common_error_embed("No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the MIDI file exists."))
            return
        
        array_of_tuples_of_embeds_and_files = [] # [(embed, file), (embed, file)]

        # Call the new function that uses asyncio.gather and a thread pool
        results = await self.process_all_midi_changes(midi_file_changes, shortname, actual_title, actual_artist, album_art_url, session_hash)
        array_of_tuples_of_embeds_and_files.extend(results) # simplification

        array_of_files_to_give_to_dpy = []
        array_of_embeds_to_give_to_view = []

        if len(array_of_tuples_of_embeds_and_files) == 0:
            await interaction.edit_original_response('There were no resulting images in this comparison, or an error has ocurred.')
            return

        logging.info(array_of_tuples_of_embeds_and_files)

        for comparison in array_of_tuples_of_embeds_and_files:
            for embed, _file in comparison:
                array_of_files_to_give_to_dpy.append(_file)
                array_of_embeds_to_give_to_view.append(embed)

        the_view_itself = history_tools.HistoryView(array_of_embeds_to_give_to_view, array_of_files_to_give_to_dpy, session_hash, interaction.user.id)

        if len(the_view_itself.attachments) == 0:
            await interaction.edit_original_response(embed=constants.common_error_embed('There are no attachments to display.'))
            return

        message = await interaction.original_response()
        the_view_itself.message = message

        # initial edit
        # the view manages it afterwards
        msg = await interaction.edit_original_response(content="", view=the_view_itself, attachments=[the_view_itself.get_cur_attch()], embed=the_view_itself.get_embed())

class LoopCheckHandler():
    def __init__(self, bot : commands.Bot) -> None:
        self.bot = bot
        self.embed_handler = SearchEmbedHandler()
        self.history_handler = HistoryHandler()
        self.midi_tools = MidiArchiveTools()
        self.jam_track_handler = JamTrackHandler()

    async def handle_activity_task(self):
        tracks = self.jam_track_handler.get_jam_tracks()
        num_tracks = len(tracks)
        random_jam_track = random.choice(tracks)

        servers = random.choice([True, False]) # bruh

        activity = discord.Activity(
            type=discord.ActivityType.watching if servers else discord.ActivityType.playing,
            name=f"{len(self.bot.guilds)} servers" if servers else f"{num_tracks} Jam Tracks",
            state=f"{random_jam_track['track']['tt']} - {random_jam_track['track']['an']}",
        )

        await self.bot.change_presence(activity=activity, status=discord.Status.online)

        logging.info("Presence updated successfully.")

    async def handle_task(self):
        tracks = self.jam_track_handler.get_jam_tracks()

        if not tracks:
            logging.error('Could not fetch tracks.')
            return

        session_hash = constants.generate_session_hash(self.bot.start_time, self.bot.start_time)

        logging.info("Checking for new songs...")

        try:
            sparks_tracks.main()
        except Exception as e:
            logging.error(f"Failed to use the spark_tracks.py module", exc_info=e)

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

        bot_config: config.Config = self.bot.config

        combined_channels: list[SubscriptionObject] = await bot_config.get_all()

        start = datetime.now()

        if len(new_songs) != 0 or len(modified_songs) != 0 or len(removed_songs) != 0:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(f"Sending to {len(combined_channels)} channels a total of {(len(new_songs) + len(modified_songs) + len(removed_songs)) * len(combined_channels)} messages")

        session_hashes_all = [session_hash]

        modified_songs_data = [] # [(modified metadata embed, [(embed, file), (embed, file)])]
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
            local_midi_file_old = self.midi_tools.download_and_archive_midi_file(old_url, short_name)
            local_midi_file_new = self.midi_tools.download_and_archive_midi_file(new_url, short_name)

            embed_list_diff = []

            if (old_url != new_url) and self.bot.DECRYPTION_ALLOWED and self.bot.CHART_COMPARING_ALLOWED:
                logging.info(f"Chart URL changed:")
                logging.info(f"Old: {local_midi_file_old}")
                logging.info(f"New: {local_midi_file_new}")

                logging.debug(f"Running process_chart_url_change for {local_midi_file_old} and {local_midi_file_new}")
                embed_list_diff = await self.history_handler.process_chart_url_change(old_url=local_midi_file_old, new_url=local_midi_file_new, track_name=short_name, song_title=track_name, artist_name=artist_name, album_art_url=album_art_url, last_modified_old=last_modified_old, last_modified_new=last_modified_new, session_hash=session_hash) # this makes me dizzy lol

            embed = self.embed_handler.generate_modified_track_embed(old=old_song, new=new_song)

            modified_songs_data.append((embed, embed_list_diff))

        for channel_to_send in combined_channels:
            if channel_to_send.type == 'channel':
                channel = self.bot.get_channel(channel_to_send.id)
            elif channel_to_send.type == 'user':
                channel = self.bot.get_user(channel_to_send.id)
            else:
                channel = None

            if not channel:
                logging.error(f"{channel_to_send.type.capitalize()} with ID {channel_to_send.id} not found.")
                continue

            if isinstance(channel, discord.abc.GuildChannel):
                if channel.permissions_for(channel.guild.me).send_messages == False:
                    logging.error(f"We do not have permission to send messages to {channel.id}, skipping.")
                    continue

            content = ""
            if isinstance(channel_to_send, SubscriptionChannel):
                role_pings = []
                for role in channel_to_send.roles:
                    role_pings.append(f"<@&{role}>")
                content = " ".join(role_pings)

            if new_songs and JamTrackEvent.Added.value in channel_to_send.events:
                logging.info(f"New songs sending to channel {channel.id}")
                for new_song in new_songs:
                    embed = self.embed_handler.generate_track_embed(new_song, is_new=True)

                    view = discord.ui.View(timeout=None)
                    view.add_item(PreviewButton(new_song['track']['sn']))

                    try:
                        message = await channel.send(content=content, embed=embed, view=view)

                    except discord.Forbidden as e:
                        logging.error(f"Channel {channel.id} cannot be sent messages to, skipped", exc_info=e)
                        break
                        
                    except Exception as e:
                        logging.error(f"Error sending message to channel {channel.id}", exc_info=e)

            if removed_songs and JamTrackEvent.Removed.value in channel_to_send.events:
                logging.info(f"Removed songs sending to channel {channel.id}")
                for removed_song in removed_songs:
                    embed = self.embed_handler.generate_track_embed(removed_song, is_removed=True)
                    try:
                        message = await channel.send(content=content, embed=embed)

                    except discord.Forbidden as e:
                        logging.error(f"Channel {channel.id} cannot be sent messages to, skipped", exc_info=e)
                        break

                    except Exception as e:
                        logging.error(f"Error sending message to channel {channel.id}", exc_info=e)

            if modified_songs and JamTrackEvent.Modified.value in channel_to_send.events:
                logging.info(f"Modified songs sending to channel {channel.id}")
                
                for song_metadata_diff_embed, chart_diffs_embeds in modified_songs_data:

                    for diff_embed, diff_filename in chart_diffs_embeds:
                        try:
                            msg = await channel.send(embed=diff_embed, file=discord.File(diff_filename))
                        except Exception as e:
                            logging.error(f'Cannot send modified chart embed to {channel.id}', exc_info=e)

                    try:
                        message = await channel.send(content=content, embed=song_metadata_diff_embed)

                    except discord.Forbidden as e:
                        logging.error(f"Channel {channel.id} cannot be sent messages to, skipped", exc_info=e)
                        break

                    except Exception as e:
                        logging.error(f"Error sending message to channel {channel.id}", exc_info=e)

        logging.info(f"Done checking for new songs: New: {len(new_songs)} | Modified: {len(modified_songs)} | Removed: {len(removed_songs)}")

        if len(new_songs) != 0 or len(modified_songs) != 0 or len(removed_songs) != 0:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(f"Sending completed for {len(combined_channels)} channels! Took {(datetime.now() - start).seconds}s")

        for _hash in session_hashes_all:
            constants.delete_session_files(str(_hash))

class HistoryException(Exception):
    def __init__(self, desc, *args: object) -> None:
        self.desc = desc
        super().__init__(*args)
