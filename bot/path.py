import logging
import os
import re
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
    def run_chopt(self, midi_file: str, command_instrument: str, output_image: str, squeeze_percent: int = 20, instrument: constants.Instrument = None, difficulty: str = 'expert', extra_args: list = []):
        engine = 'fnf'
        
        if instrument.midi == 'PLASTIC DRUMS':
            engine = 'ch' 
            # Sir Reginald's Jolly Good Rock 'n' Roll Ensemble Extravaganza: The Third Installment of Harmonious Merriment and Musical Shenanigans
            # this guy is broken

        chopt_command = [
            'chopt.exe', 
            '-f', midi_file, 
            '--engine', engine, 
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

        chopt_command.extend(extra_args)

        result = subprocess.run(chopt_command, text=True, capture_output=True)

        if result.returncode != 0:
            raise Exception("CHOpt Error: " + result.stderr)

        return result.stdout.strip()
    
    def process_acts(self, arr):
        sum_phrases = 0
        sum_overlaps = 0

        for string in arr:
            try:
                if "(" in string:
                    x, y = string.split("(")
                    y = y.replace(")", "")  # Remove closing parenthesis
                    sum_phrases += int(x)
                    sum_overlaps += int(y)
                else:
                    sum_phrases += int(string)
            except Exception as e:
                pass

        return sum_phrases, sum_overlaps

    async def handle_interaction(self, interaction:discord.Interaction, song:str, instrument:constants.Instruments, extra_args:list, squeeze_percent: discord.app_commands.Range[int, 0, 100] = 20, difficulty:constants.Difficulties = constants.Difficulties.Expert):
        await interaction.response.defer()

        extra_arguments = []
        field_argument_descriptors = []
        if extra_args[0]: # Lefty Flip
            extra_arguments.append('--lefty-flip')
            field_argument_descriptors.append('**Lefty Flip:** Yes')
        if extra_args[1]: # Act Opacity
            extra_arguments.append('--act-opacity')
            extra_arguments.append(str(extra_args[1] / 100))
            field_argument_descriptors.append(f'**Activation Opacity:** {extra_args[1]}%')
        if extra_args[2]: # No BPM
            extra_arguments.append('--no-bpms')
            field_argument_descriptors.append(f'**No BPMs:** Yes')
        if extra_args[3]: # No Solos
            extra_arguments.append('--no-solos')
            field_argument_descriptors.append(f'**No Solos:** Yes')
        if extra_args[4]: # No Time Sigs
            extra_arguments.append('--no-time-sigs')
            field_argument_descriptors.append(f'**No Time Signatures:** Yes')

        # basically the code from leaderboard.py
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value
        chosen_diff = constants.Difficulties[str(difficulty).replace('Difficulties.', '')].value

        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.edit_original_response(content=f"Could not get tracks.", ephemeral=True)
            return
        
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.edit_original_response(content=f"The search query \"{song}\" did not give any results.")
            return


        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        command_instrument = chosen_instrument.chopt

        # Use the first matched track
        song_data = matched_tracks[0]

        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')
        display_instrument = chosen_instrument.english

        dat_file = f"{session_hash}_{short_name}.dat"
        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)  # Download the .dat file

        if not local_midi_file:
            await interaction.edit_original_response(content=f"Failed to download the MIDI file for '{song}'.")
            return

        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        if not midi_file:
            await interaction.edit_original_response(content=f"Failed to decrypt the .dat file for '{song}'.")
            return

        modified_midi_file = None
        if chosen_instrument.replace != None:
            modified_midi_file = self.midi_tool.modify_midi_file(midi_file, chosen_instrument, session_hash, short_name)
            if not modified_midi_file:
                await interaction.edit_original_response(content=f"Failed to modify MIDI for '{instrument}'.")
                return
            midi_file = modified_midi_file

        output_image = f"{short_name}_{chosen_instrument.chopt.lower()}_path_{session_hash}.png".replace(' ', '_')
        chopt_output = self.run_chopt(midi_file, command_instrument, output_image, squeeze_percent, instrument=chosen_instrument, difficulty=chosen_diff.chopt,extra_args=extra_arguments)

        filtered_output = '\n'.join([line for line in chopt_output.splitlines() if "Optimising, please wait..." not in line])

        description = (
            f"**Instrument:** {display_instrument}\n"
            f"**Difficulty:** {chosen_diff.english}\n"
            f"**Squeeze:** {squeeze_percent}%\n"
        )

        for arg in field_argument_descriptors:
            description += f'{arg}\n'

        if os.path.exists(os.path.join(constants.TEMP_FOLDER, output_image)):
            file = discord.File(os.path.join(constants.TEMP_FOLDER, output_image), filename=output_image)
            embed = discord.Embed(
                title=f"Path for **{track_title}** - *{artist_title}*",
                description=description,
                color=0x8927A1
            )
            embed.add_field(name="CHOpt output", value=f"```{filtered_output}```", inline=False)

            acts = filtered_output.split('\n')[0].replace('Path: ', '').split('-')
            total_acts = len(acts)
            phrases, overlaps = self.process_acts(acts)

            no_sp_score = filtered_output.split('\n')[1].split(' ').pop()
            total_score = filtered_output.split('\n')[2].split(' ').pop()

            embed.add_field(name="Phrases", value=phrases)
            embed.add_field(name="Activations", value=total_acts)
            embed.add_field(name="Overlaps", value=overlaps)
            embed.add_field(name="No OD Score", value=no_sp_score)
            embed.add_field(name="Total Score", value=total_score)
            embed.set_footer(text="Tip: Use /suggestion to suggest new features!")

            embed.set_image(url=f"attachment://{output_image}")
            embed.set_thumbnail(url=album_art_url)
            await interaction.edit_original_response(embed=embed, attachments=[file])
        else:
            await interaction.edit_original_response(content=f"Failed to generate the path image for '{track_title}'.")

        constants.delete_session_files(session_hash)

        # await interaction.edit_original_response(content="Check ur console: " + song)
