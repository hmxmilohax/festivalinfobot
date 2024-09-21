import os
import subprocess
import discord

from bot import constants
from bot.midi import MidiArchiveTools
from bot.tracks import JamTrackHandler

class PathCommandHandler():
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.midi_tool = MidiArchiveTools()

    # Function to call chopt.exe and capture its output
    def run_chopt(self, midi_file: str, command_instrument: str, output_image: str, squeeze_percent: int = 20, instrument: constants.Instrument = None, difficulty: str = 'expert'):
        chopt_command = [
            'chopt.exe', 
            '-f', midi_file, 
            '--engine', 'fnf', 
            '--squeeze', str(squeeze_percent),
            '--early-whammy', '0',
            '--diff', difficulty
        ]

        # Only add --no-pro-drums flag if it's NOT Pro Drums
        if instrument.midi != 'PLASTIC DRUMS':
            chopt_command.append('--no-pro-drums')

        chopt_command.extend([
            '-i', command_instrument, 
            '-o', os.path.join(constants.TEMP_FOLDER, output_image)
        ])

        result = subprocess.run(chopt_command, text=True, capture_output=True)
        
        if result.returncode != 0:
            return None, result.stderr

        return result.stdout.strip(), None

    async def handle_interaction(self, interaction:discord.Interaction, song:str, instrument:constants.Instruments, squeeze_percent: discord.app_commands.Range[int, 0, 100] = 20, difficulty:constants.Difficulties = constants.Difficulties.Expert):
        # basically the code from leaderboard.py
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value
        chosen_diff = constants.Difficulties[str(difficulty).replace('Difficulties.', '')].value

        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return
        
        # Perform fuzzy search
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
            return

        await interaction.response.defer() # Makes the bot say Thinking...

        try:
            # Generate session hash for this path generation
            user_id = interaction.user.id
            session_hash = constants.generate_session_hash(user_id, song)  # Unique session identifier

            command_instrument = chosen_instrument.chopt

            # Use the first matched track
            song_data = matched_tracks[0]

            song_url = song_data['track'].get('mu')
            album_art_url = song_data['track'].get('au')  # Fetch album art URL
            track_title = song_data['track'].get('tt')
            short_name = song_data['track'].get('sn')
            artist_title = song_data['track'].get('an')
            display_instrument = chosen_instrument.english  # Get user-friendly instrument name

            # Step 1: Download and decrypt the .dat file into a .mid file
            dat_file = f"{session_hash}_{short_name}.dat"
            local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)  # Download the .dat file

            if not local_midi_file:
                await interaction.edit_original_response(content=f"Failed to download the MIDI file for '{song}'.")
                return

            # Step 2: Decrypt the .dat file into a .mid file for processing
            midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
            if not midi_file:
                await interaction.edit_original_response(content=f"Failed to decrypt the .dat file for '{song}'.")
                return

            # Step 3: Modify the MIDI file if necessary (e.g., Pro parts)
            modified_midi_file = None
            if chosen_instrument.plastic and chosen_instrument.replace != None:
                modified_midi_file = self.midi_tool.modify_midi_file(midi_file, chosen_instrument, session_hash, short_name)
                if not modified_midi_file:
                    await interaction.edit_original_response(content=f"Failed to modify MIDI for '{instrument}'.")
                    return
                midi_file = modified_midi_file  # Use the modified file

            # Step 4: Generate the path image using chopt.exe
            output_image = f"{short_name}_{chosen_instrument.chopt.lower()}_path_{session_hash}.png".replace(' ', '_')
            chopt_output, chopt_error = self.run_chopt(midi_file, command_instrument, output_image, squeeze_percent, instrument=chosen_instrument, difficulty=chosen_diff.chopt)

            if chopt_error:
                await interaction.edit_original_response(content=f"An error occurred while running chopt: {chopt_error}")
                return

            filtered_output = '\n'.join([line for line in chopt_output.splitlines() if "Optimising, please wait..." not in line])

            # Step 5: Check if path image is generated successfully and send it
            if os.path.exists(os.path.join(constants.TEMP_FOLDER, output_image)):
                file = discord.File(os.path.join(constants.TEMP_FOLDER, output_image), filename=output_image)
                embed = discord.Embed(
                    title=f"Path for **{track_title}** - *{artist_title}*",
                    description=(
                        f"`Instrument:` **{display_instrument}**\n"
                        f"`Difficulty:` **{chosen_diff.english}**\n"
                        f"`Squeeze Percent:` **{squeeze_percent}%**\n"
                        f"```{filtered_output}```"
                    ),
                    color=0x8927A1
                )
                embed.set_image(url=f"attachment://{output_image}")
                embed.set_thumbnail(url=album_art_url)
                await interaction.edit_original_response(embed=embed, attachments=[file])
            else:
                await interaction.edit_original_response(content=f"Failed to generate the path image for '{track_title}'.")

            # Clean up after processing
            constants.delete_session_files(session_hash)  # Clean up session files like MIDI and images

        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {str(e)}")

        # await interaction.edit_original_response(content="Check ur console: " + song)
