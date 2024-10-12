import os
import discord

from bot import constants
from bot.midi import MidiArchiveTools
from bot.tracks import JamTrackHandler
import graphs

class GraphCommandsHandler():
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.midi_tool = MidiArchiveTools()

    async def handle_pdi_interaction(self, interaction:discord.Interaction, song:str):
        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)  # Unique session identifier

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')  # Fetch album art URL
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        # Step 1: Download and decrypt the .dat file into a .mid file
        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)  # Download the .dat file

        if not local_midi_file:
            await interaction.edit_original_response(content=f"Failed to download the MIDI file for '{song}'.")
            return

        # Step 2: Decrypt the .dat file into a .mid file for processing
        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        if not midi_file:
            await interaction.edit_original_response(content=f"Failed to decrypt the .dat file for '{song}'.")
            return
        
        image_path = f'{short_name}_pdi_graph_{session_hash}.png'
        try:
            graphs.generate_no_notes_pdi_chart(midi_path=midi_file, path=image_path, song_name=track_title, song_artist=artist_title)
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to generate the graph for '{song}'.")
            return
        
        embed = discord.Embed(title=f"Note counts for\n**{track_title}** - *{artist_title}*", color=0x8927A1)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

    async def handle_lift_interaction(self, interaction:discord.Interaction, song:str):
        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)  # Unique session identifier

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')  # Fetch album art URL
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        # Step 1: Download and decrypt the .dat file into a .mid file
        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)  # Download the .dat file

        if not local_midi_file:
            await interaction.edit_original_response(content=f"Failed to download the MIDI file for '{song}'.")
            return

        # Step 2: Decrypt the .dat file into a .mid file for processing
        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        if not midi_file:
            await interaction.edit_original_response(content=f"Failed to decrypt the .dat file for '{song}'.")
            return
        
        image_path = f'{short_name}_lift_graph_{session_hash}.png'
        try:
            graphs.generate_no_notes_pdi_chart(midi_path=midi_file, path=image_path, song_name=track_title, song_artist=artist_title, lifts=True)
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to generate the graph for '{song}': {e}.")
            return
        
        embed = discord.Embed(title=f"Lift counts for\n**{track_title}** - *{artist_title}*", color=0x8927A1)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

    async def handle_nps_interaction(self, interaction:discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value
        chosen_diff = constants.Difficulties[str(difficulty).replace('Difficulties.', '')].value

        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)  # Unique session identifier

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')  # Fetch album art URL
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        # Step 1: Download and decrypt the .dat file into a .mid file
        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)  # Download the .dat file

        if not local_midi_file:
            await interaction.edit_original_response(content=f"Failed to download the MIDI file for '{song}'.")
            return

        # Step 2: Decrypt the .dat file into a .mid file for processing
        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        if not midi_file:
            await interaction.edit_original_response(content=f"Failed to decrypt the .dat file for '{song}'.")
            return
        
        image_path = f'{short_name}_nps_graph_{session_hash}.png'
        try:
            graphs.generate_nps_chart(midi_path=midi_file, path=image_path, inst=chosen_instrument, diff=chosen_diff, song_name=track_title, song_artist=artist_title)
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to generate the graph for '{song}': {e}.")
            return
        
        embed = discord.Embed(title=f"NPS Graph for\n**{track_title}** - *{artist_title}*", color=0x8927A1)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

    async def handle_lanes_interaction(self, interaction:discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value
        chosen_diff = constants.Difficulties[str(difficulty).replace('Difficulties.', '')].value

        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)  # Unique session identifier

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')  # Fetch album art URL
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        # Step 1: Download and decrypt the .dat file into a .mid file
        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)  # Download the .dat file

        if not local_midi_file:
            await interaction.edit_original_response(content=f"Failed to download the MIDI file for '{song}'.")
            return

        # Step 2: Decrypt the .dat file into a .mid file for processing
        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        if not midi_file:
            await interaction.edit_original_response(content=f"Failed to decrypt the .dat file for '{song}'.")
            return
        
        image_path = f'{short_name}_lanes_graph_{session_hash}.png'
        try:
            graphs.generate_lanes_chart(midi_path=midi_file, spath=image_path, inst=chosen_instrument, diff=chosen_diff, song_name=track_title, song_artist=artist_title)
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to generate the graph for '{song}': {e}.")
            return
        
        embed = discord.Embed(title=f"Notes per lane graph for\n**{track_title}** - *{artist_title}*", color=0x8927A1)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)