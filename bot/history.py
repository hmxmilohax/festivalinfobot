import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import discord
from discord.ext import commands
import requests

from bot import constants
from bot.config import JamTrackEvent
from bot.embeds import SearchEmbedHandler, StatsCommandEmbedHandler
from bot.midi import MidiArchiveTools
from bot.tracks import JamTrackHandler

def save_known_songs_to_disk(songs):
    # Fetch jam tracks using the API call
    print(f'[GET] {constants.CONTENT_API}')
    response = requests.get(constants.CONTENT_API)
    response.raise_for_status()

    data = response.json()
    # Generate timestamp in the required format (e.g., 2024-04-24T13.27.49)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H.%M.%S')
    unique_id = hashlib.md5(timestamp.encode()).hexdigest()[:6]

    # Generate the full filename based on the format (e.g., spark-tracks_2024-04-24T13.27.49Z_dcd7c.json)
    file_prefix = "spark-tracks"
    file_name = f"{file_prefix}_{timestamp}Z_{unique_id}.json"
    
    # Ensure the folder exists, create if not
    folder_path = constants.LOCAL_JSON_FOLDER
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)  # Create the folder if it doesn't exist
    
    # Check the 3 most recent files in the folder
    json_files = sorted(
        [f for f in os.listdir(folder_path) if f.startswith("spark-tracks") and f.endswith(".json")],
        key=lambda x: os.path.getmtime(os.path.join(folder_path, x)),
        reverse=True
    )

    # Load and compare the content of the most recent 3 files
    recent_files_content = [constants.load_json_from_file(os.path.join(folder_path, f)) for f in json_files[:3]]

    current_songs_data = [song['track']['sn'] for song in songs]
    current_tracks_data = songs

    # Convert current data to JSON for comparison
    current_songs_json = json.dumps(current_songs_data, sort_keys=True)

    # Ensure the master file (known_tracks.json or known_songs.json) is updated
    known_tracks_file_path = constants.SONGS_FILE
    known_songs_file_path = constants.SHORTNAME_FILE
    
    # Ensure the master file exists and create it if it doesn't
    if not os.path.exists(known_tracks_file_path):
        with open(known_tracks_file_path, 'w') as known_tracks_file:
            json.dump([], known_tracks_file, indent=4)  # Write an empty list initially
    if not os.path.exists(known_songs_file_path):
        with open(known_songs_file_path, 'w') as known_songs_file:
            json.dump([], known_songs_file, indent=4)  # Write an empty list initially

    # Always update the root known_tracks.json (for full songs) or known_songs.json (for shortnames)
    with open(known_tracks_file_path, 'w') as known_tracks_file:
        json.dump(current_tracks_data, known_tracks_file, indent=4)
    print(f"Updated: {known_tracks_file_path}")

    with open(known_songs_file_path, 'w') as known_songs_file:
        json.dump(current_songs_data, known_songs_file, indent=4)
    print(f"Updated: {known_songs_file_path}")

    # Check if any of the 3 most recent files match the current data
    for content in recent_files_content:
        if json.dumps(content, sort_keys=True) == json.dumps(data, sort_keys=True):
            print(f"No new sparks-tracks.json changes to save. Matches {file_name}.")
            return  # Exit without saving if there's a match

    # Save the new JSON file if no match was found
    file_path = os.path.join(folder_path, file_name)
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
    print(f"New file saved as {file_name}")

def load_known_songs_from_disk(shortnames:bool = False):
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
        print(f"Total JSON files to process: {len(json_files)}")

        try:
            for idx, json_file in enumerate(json_files):
                file_path = os.path.join(constants.LOCAL_JSON_FOLDER, json_file)
                file_content = constants.load_json_from_file(file_path)
                if not file_content:
                    print(f"Failed to load content from {file_path}, skipping to next file.")
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
            print(f"Error processing {json_file}: {e}")
        
        return midi_file_changes
    
    def track_meta_changes(self, json_files, shortname, session_hash):
        changes = []
        json_files = [f for f in json_files if f.endswith('.json')]
        print(f"Total JSON files to process: {len(json_files)}")

        try:
            for idx, json_file in enumerate(json_files):
                file_path = os.path.join(constants.LOCAL_JSON_FOLDER, json_file)
                file_content = constants.load_json_from_file(file_path)
                if not file_content:
                    print(f"Failed to load content from {file_path}, skipping to next file.")
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
            print(f"Error processing {json_file}: {e}")

        grouped_changes = {}
        for item in changes:
            key = item[0]
            if key not in grouped_changes:
                grouped_changes[key] = []
            grouped_changes[key].append(item[1])
        
        return grouped_changes

    async def process_chart_url_change(self, old_url:str, new_url:str, interaction : discord.Interaction, track_name:str, song_title:str, artist_name:str, album_art_url:str, last_modified_old, last_modified_new, session_hash:str, channel : discord.channel.TextChannel):
        # Decrypt old .dat to .midi
        old_midi_file = self.midi_handler.decrypt_dat_file(old_url, session_hash)

        # Decrypt new .dat to .midi
        new_midi_file = self.midi_handler.decrypt_dat_file(new_url, session_hash)

        if old_midi_file and new_midi_file:
            # Copy both MIDI files to the out folder for further processing
            old_midi_out_path = os.path.join(constants.TEMP_FOLDER, f"{track_name}_old_{session_hash}.mid")
            new_midi_out_path = os.path.join(constants.TEMP_FOLDER, f"{track_name}_new_{session_hash}.mid")

            shutil.copy(old_midi_file, old_midi_out_path)
            shutil.copy(new_midi_file, new_midi_out_path)

            # Run the comparison command and wait for it to finish
            comparison_command = ['python', 'compare_midi.py', old_midi_out_path, new_midi_out_path, session_hash]
            result = subprocess.run(comparison_command, capture_output=True, text=True)
            # Check the output for errors, just in case
            if result.returncode != 0:
                if not channel:
                    await interaction.edit_original_response(content=f"Comparison failed with error: {result.stderr}")
                else:
                    try:
                        await channel.send(content=f"Comparison failed with error: {result.stderr}")
                    except Exception as e:
                        print(f"Error sending message to channel {channel.id}: {e}")

                return

            # Check for the completion flag in the output
            if "MIDI comparison completed successfully" in result.stdout:
                # Now that comparison is complete, check for any image output
                comparison_images = [f for f in os.listdir(constants.TEMP_FOLDER) if f.endswith(f'{session_hash}.png')]

                last_modified_old_str = datetime.fromisoformat(last_modified_old.replace('Z', '+00:00')).strftime("%B %d, %Y")
                last_modified_new_str = datetime.fromisoformat(last_modified_new.replace('Z', '+00:00')).strftime("%B %d, %Y")

                if comparison_images:
                    if not channel:
                        await interaction.edit_original_response(content=f"Found {len(comparison_images)} MIDI Track changes:")
                    else:
                        try:
                            await channel.send(content=f"Found {len(comparison_images)} MIDI Track changes:")
                        except Exception as e:
                            print(f"Error sending message to channel {channel.id}: {e}")

                    # do not use edit_original_response here
                    for image in comparison_images:
                        image_path = os.path.abspath(os.path.join(constants.TEMP_FOLDER, image))
                        file = discord.File(image_path, filename=image)
                        embed = discord.Embed(
                            title=f"",
                            description=f"**{song_title}** - *{artist_name}*\nDetected changes between:\n`{last_modified_old_str}` and `{last_modified_new_str}`",
                            color=0x8927A1
                        )
                        embed.set_image(url=f"attachment://{image}")
                        embed.set_thumbnail(url=album_art_url)
                        try:

                            if not channel:
                                img_message = await interaction.channel.send(embed=embed, file=file)
                            else:
                                img_message = await channel.send(embed=embed, file=file)

                            if img_message.channel.is_news():
                                await img_message.publish()
                        except Exception as e:
                            print(f"Error sending embed to channel {channel.id if channel else 'N/A'}: {e}")
                    constants.delete_session_files(session_hash)
                else:
                    if not channel:
                        message = await interaction.edit_original_response(content=f"Comparison between `{last_modified_old_str}` and `{last_modified_new_str}` shows seemingly no visual changes.")
                    else:
                        try:
                            message = await channel.send(content=f"Comparison between `{last_modified_old_str}` and `{last_modified_new_str}` shows seemingly no visual changes.")
                            if message.channel.is_news():
                                await message.publish()
                        except Exception as e:
                            print(f"Error sending message to channel {channel.id}: {e}")
                    constants.delete_session_files(session_hash)
            else:
                if not channel:
                    message = await interaction.edit_original_response(content="MIDI comparison did not complete successfully.")
                else:
                    try:
                        message = await channel.send(content="MIDI comparison did not complete successfully.")
                    except Exception as e:
                        print(f"Error sending message to channel {channel.id}: {e}")
                constants.delete_session_files(session_hash)
        else:
            if not channel:
                await interaction.edit_original_response(content="Failed to decrypt MIDI files.")
            else:
                try:
                    await channel.send(content="Failed to decrypt MIDI files.")
                except Exception as e:
                    print(f"Error sending message to channel {channel.id}: {e}")
            constants.delete_session_files(session_hash)

    def fetch_local_history(self):
        json_files = []
        try:
            for file_name in os.listdir(constants.LOCAL_JSON_FOLDER):
                if file_name.endswith('.json'):
                    json_files.append(file_name)
        except Exception as e:
            print(f"Error reading local JSON files: {e}")
        return sorted(json_files)

    async def handle_interaction(self, interaction: discord.Interaction, song:str, channel : discord.channel.TextChannel = None, use_channel:bool = False):
        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)
        print(f"Generated session hash: {session_hash} for user: {user_id}")

        # Fetch track data from the API
        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            if not use_channel:
                await interaction.response.send_message(content="Could not fetch tracks.")
            else:
                try:
                    await channel.send(content="Could not fetch tracks.")
                except Exception as e:
                    print(f"Error sending message to channel {channel.id}: {e}")
            return

        # Perform fuzzy search to find the matching song
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            print(f"No tracks found matching {song}.")
            if not use_channel:
                await interaction.response.send_message(content=f"No tracks found for '{song}'.")
            else:
                try:
                    await channel.send(content=f"No tracks found for '{song}'.")
                except Exception as e:
                    print(f"Error sending message to channel {channel.id}: {e}")
            return
        
        if not use_channel:
            await interaction.response.defer(thinking=True)

        track_data = matched_tracks[0]
        album_art_url = track_data['track'].get('au')
        shortname = track_data['track'].get('sn')
        actual_title = track_data['track'].get('tt', 'Unknown Title')
        actual_artist = track_data['track'].get('an', 'Unknown Artist')

        # Fetch the local revision history of the song
        json_files = self.fetch_local_history()
        if not json_files:
            if not use_channel:
                await interaction.edit_original_response(content=f"No local history files found.")
            else:
                try:
                    await channel.send(content=f"No local history files found.")
                except Exception as e:
                    print(f"Error sending message to channel {channel.id}: {e}")
            return

        midi_file_changes = self.track_midi_changes(json_files, shortname, session_hash)
        print(f"Found {len(midi_file_changes)} MIDI file changes for {shortname}.")

        if len(midi_file_changes) <= 1:
            if not use_channel:
                await interaction.edit_original_response(content=f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the MIDI file exists.")
            else:
                try:
                    await channel.send(content=f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the MIDI file exists.")
                except Exception as e:
                    print(f"Error sending message to channel {channel.id}: {e}")
            return

        for i in range(1, len(midi_file_changes)):
            old_midi = midi_file_changes[i - 1]
            new_midi = midi_file_changes[i]

            old_midi_file = old_midi[1]
            new_midi_file = new_midi[1]

            if not use_channel:
                await self.process_chart_url_change(
                    old_midi_file, new_midi_file, interaction, shortname, actual_title, actual_artist, album_art_url, old_midi[0], new_midi[0], session_hash, channel=None
                )
            else:
                await self.process_chart_url_change(old_url=old_midi_file, new_url=new_midi_file, track_name=shortname, song_title=actual_title, artist_name=actual_artist, album_art_url=album_art_url, last_modified_old=old_midi[0], last_modified_new=new_midi[0], session_hash=session_hash, channel=channel, interaction=None)

    async def handle_metahistory_interaction(self, interaction: discord.Interaction, song:str):
        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)
        print(f"Generated session hash: {session_hash} for user: {user_id}")

        # Fetch track data from the API
        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content="Could not fetch tracks.")
            return

        # Perform fuzzy search to find the matching song
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            print(f"No tracks found matching {song}.")
            await interaction.response.send_message(content=f"No tracks found for '{song}'.")
            return
        
        await interaction.response.defer(thinking=True)

        track_data = matched_tracks[0]
        album_art_url = track_data['track'].get('au')
        shortname = track_data['track'].get('sn')
        actual_title = track_data['track'].get('tt', 'Unknown Title')
        actual_artist = track_data['track'].get('an', 'Unknown Artist')

        # Fetch the local revision history of the song
        json_files = self.fetch_local_history()
        if not json_files:
            await interaction.edit_original_response(content=f"No local history files found.")
            return

        metadata_changes = self.track_meta_changes(json_files, shortname, session_hash)
        if len(metadata_changes.keys()) <= 1: # You won't be able to get here
            await interaction.edit_original_response(content=f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the metadata exists.")
            return
        
        changes = []
        for date, change in metadata_changes.items():
            props_of_change = {}
            for k, v in change:
                props_of_change[k] = v
            changes.append([date, props_of_change])

        await interaction.edit_original_response(content=f"Found {len(changes)} metadata revisions for **{actual_title}** - *{actual_artist}*:")
        
        for i, change in enumerate(changes):
            if i > 0:
                date = change[0]
                properties_that_changed = change[1]
                
                prev = changes[i - 1]
                prev_date = prev[0]
                prev_properties = prev[1]

                embed = discord.Embed(title=f"**{actual_title}** - *{actual_artist}*", description=f"**Logged metadata change:** \n<t:{StatsCommandEmbedHandler().iso_to_unix_timestamp(prev_date)}:D> to <t:{StatsCommandEmbedHandler().iso_to_unix_timestamp(date)}:D>", color=0x8927A1)

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

                await interaction.channel.send(embed=embed)

    async def handle_interaction(self, interaction: discord.Interaction, song:str, channel : discord.channel.TextChannel = None, use_channel:bool = False):
        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)
        print(f"Generated session hash: {session_hash} for user: {user_id}")

        # Fetch track data from the API
        tracks = self.jam_track_handler.get_jam_tracks()
        if not tracks:
            await interaction.response.send_message(content="Could not fetch tracks.")
            return

        # Perform fuzzy search to find the matching song
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracks, song)
        if not matched_tracks:
            print(f"No tracks found matching {song}.")
            await interaction.response.send_message(content=f"No tracks found for '{song}'.")
            return
        
        if not use_channel:
            await interaction.response.defer(thinking=True)

        track_data = matched_tracks[0]
        album_art_url = track_data['track'].get('au')
        shortname = track_data['track'].get('sn')
        actual_title = track_data['track'].get('tt', 'Unknown Title')
        actual_artist = track_data['track'].get('an', 'Unknown Artist')

        # Fetch the local revision history of the song
        json_files = self.fetch_local_history()
        if not json_files:
            await interaction.edit_original_response(content=f"No local history files found.")
            return

        midi_file_changes = self.track_midi_changes(json_files, shortname, session_hash)
        print(f"Found {len(midi_file_changes)} MIDI file changes for {shortname}.")

        if len(midi_file_changes) <= 1:
            await interaction.edit_original_response(content=f"No changes detected for the song **{actual_title}** - *{actual_artist}*\nOnly one version of the MIDI file exists.")
            return

        for i in range(1, len(midi_file_changes)):
            old_midi = midi_file_changes[i - 1]
            new_midi = midi_file_changes[i]

            old_midi_file = old_midi[1]
            new_midi_file = new_midi[1]

            await self.process_chart_url_change(
                old_midi_file, new_midi_file, interaction, shortname, actual_title, actual_artist, album_art_url, old_midi[0], new_midi[0], session_hash, channel=None
            )

class LoopCheckHandler():
    def __init__(self, bot : commands.Bot) -> None:
        self.bot = bot
        self.embed_handler = SearchEmbedHandler()
        self.history_handler = HistoryHandler()
        self.midi_tools = MidiArchiveTools()
        self.jam_track_handler = JamTrackHandler()

    async def handle_task(self):
        if not self.bot.config:
            print(f"No config provided; skipping the {self.bot.CHECK_FOR_SONGS_INTERVAL}-minute probe.")
            return

        # Remove duplicates from self.bot.config.channels and self.bot.config.users
        def remove_duplicates_by_id(items):
            print("Attempting to remove duplicates...")
            seen_ids = set()
            unique_items = []
            for item in items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    unique_items.append(item)
            return unique_items

        # Clean up duplicates and save the config if changes were made
        original_channel_count = len(self.bot.config.channels)
        original_user_count = len(self.bot.config.users)

        self.bot.config.channels = remove_duplicates_by_id(self.bot.config.channels)
        self.bot.config.users = remove_duplicates_by_id(self.bot.config.users)

        if len(self.bot.config.channels) != original_channel_count or len(self.bot.config.users) != original_user_count:
            print("Duplicates found in config; cleaning up and saving.")
            self.bot.config.save_config()

        session_hash = constants.generate_session_hash(self.bot.start_time, self.bot.start_time)  # Unique session identifier

        print("Checking for new songs...")

        # Run sparks_tracks.py alongside this script
        try:
            subprocess.Popen(["python", "sparks_tracks.py"])
            print("Running sparks_tracks.py")
        except Exception as e:
            print(f"Failed to run sparks_tracks.py: {e}")

        # Fetch current jam tracks
        tracks = self.jam_track_handler.get_jam_tracks()

        if not tracks:
            print('Could not fetch tracks.')
            return

        # Dynamically reload known tracks and shortnames from disk each time the task runs
        known_tracks = load_known_songs_from_disk()  # Reload known_tracks.json
        known_shortnames = load_known_songs_from_disk(shortnames=True)  # Reload known_songs.json

        save_known_songs_to_disk(tracks)

        current_tracks_dict = {track['track']['sn']: track for track in tracks}
        known_tracks_dict = {track['track']['sn']: track for track in known_tracks}

        new_songs = []
        modified_songs = []

        removed_songs = []

        # Check for removed songs
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

        combined_channels = self.bot.config.channels + self.bot.config.users

        already_sent_to = []
        duplicates = []

        for channel_to_send in combined_channels:
            # check for duplicates
            if channel_to_send.id in already_sent_to:
                print(f'DUPLICATE DETECTED: {channel_to_send.id}')
                duplicates.append(channel_to_send.id)
                continue
            else:
                already_sent_to.append(channel_to_send.id)

            if channel_to_send.type == 'channel':
                channel = self.bot.get_channel(channel_to_send.id)
            elif channel_to_send.type == 'user':
                channel = self.bot.get_user(channel_to_send.id)
            else:
                channel = None

            if not channel:
                print(f"Channel with ID {channel_to_send.id} not found.")
                continue

            content = ""
            if channel_to_send.roles:
                role_pings = []
                for role in channel_to_send.roles:
                    role_pings.append(f"<@&{role}>")
                content = " ".join(role_pings)

            if new_songs and JamTrackEvent.Added.value in channel_to_send.events:
                print(f"New songs detected!")
                for new_song in new_songs:
                    embed = self.embed_handler.generate_track_embed(new_song, is_new=True)
                    try:
                        message = await channel.send(content=content, embed=embed)
                        if isinstance(channel, discord.TextChannel):
                            if channel.is_news():
                                await message.publish()
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"Error sending message to channel {channel.id}: {e}")
                save_known_songs_to_disk(tracks)

            if removed_songs and JamTrackEvent.Removed.value in channel_to_send.events:
                print(f"Removed songs detected!")
                for removed_song in removed_songs:
                    embed = self.embed_handler.generate_track_embed(removed_song, is_removed=True)
                    try:
                        message = await channel.send(content=content, embed=embed)
                        if isinstance(channel, discord.TextChannel):
                            if channel.is_news():
                                await message.publish()
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"Error sending message to channel {channel.id}: {e}")
                save_known_songs_to_disk(tracks)

            if modified_songs and JamTrackEvent.Modified.value in channel_to_send.events:
                print(f"Modified songs detected!")
                for old_song, new_song in modified_songs:
                    old_url = old_song['track'].get('mu', '')
                    new_url = new_song['track'].get('mu', '')
                    track_name = new_song['track']['tt']  # Get track name for the embed
                    short_name = new_song['track']['sn']  # Get track name for the embed
                    artist_name = new_song['track']['an']  # Get track name for the embed
                    album_art_url = new_song['track']['au']  # Get track name for the embed
                    last_modified_old = old_song.get('lastModified', None)
                    last_modified_new = new_song.get('lastModified', None)
                    local_midi_file_old = self.midi_tools.download_and_archive_midi_file(old_url, short_name)
                    local_midi_file_new = self.midi_tools.download_and_archive_midi_file(new_url, short_name)

                    if (old_url != new_url) and self.bot.DECRYPTION_ALLOWED and self.bot.CHART_COMPARING_ALLOWED:
                        print(f"Chart URL changed:")
                        print(f"Old: {local_midi_file_old}")
                        print(f"New: {local_midi_file_new}")

                        # Pass the track name to the process_chart_url_change function
                        print(f"Running process_chart_url_change for {local_midi_file_old} and {local_midi_file_new}")
                        await self.history_handler.process_chart_url_change(old_url=local_midi_file_old, new_url=local_midi_file_new, interaction=None, track_name=short_name, song_title=track_name, artist_name=artist_name, album_art_url=album_art_url, last_modified_old=last_modified_old, last_modified_new=last_modified_new, session_hash=session_hash, channel=channel)

                    embed = self.embed_handler.generate_modified_track_embed(old=old_song, new=new_song)
                    try:
                        message = await channel.send(content=content, embed=embed)
                        if isinstance(channel, discord.TextChannel):
                            if channel.is_news():
                                await message.publish()
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"Error sending message to channel {channel.id}: {e}")
                save_known_songs_to_disk(tracks)

        if len(duplicates) > 0:
            print('Warning: Duplicates detected!')
            print('Please check!\n' * 10)
            print('Duplicates: ' + ', '.join([str(_id) for _id in duplicates]))

        print(f"Done checking for new songs:\nNew: {len(new_songs)}\nModified: {len(modified_songs)}\nRemoved: {len(removed_songs)}")
