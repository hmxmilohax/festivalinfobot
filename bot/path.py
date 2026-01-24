import logging
import os
import re
import subprocess
import discord

from bot import constants
from bot.tools.midi import MidiArchiveTools
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

        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        if os.name == 'nt':
            chopt_exe = os.path.join(script_dir, 'data', 'Binaries', 'Windows', 'CHOpt', 'CHOpt.exe')
        else:
            chopt_exe = os.path.join(script_dir, 'data', 'Binaries', 'Linux', 'CHOpt', 'CHOpt.sh')

        chopt_command = [
            chopt_exe, 
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

    async def handle_interaction(self, interaction:discord.Interaction, song:str, instrument:constants.Instruments, extra_args:list[bool], squeeze_percent: discord.app_commands.Range[int, 0, 100] = 20, difficulty:constants.Difficulties = constants.Difficulties.Expert):
        if not interaction.response.is_done():
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

        if not chosen_instrument.path_enabled:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"Paths are not supported for {chosen_instrument.english}. Please use a different instrument."))
            return

        tracklist = constants.get_jam_tracks(use_cache=False) # no caching for path generation
        if not tracklist:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"Could not get tracks."), ephemeral=True)
            return
        
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return


        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        command_instrument = chosen_instrument.chopt

        # Use the first matched track
        song_data = matched_tracks[0]

        chart_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')
        display_instrument = chosen_instrument.english

        midi_file = await self.midi_tool.save_chart(chart_url)

        modified_midi_file = None
        if chosen_instrument.replace != None:
            modified_midi_file = self.midi_tool.modify_midi_file(midi_file, chosen_instrument, session_hash, short_name)
            if not modified_midi_file:
                await interaction.edit_original_response(embed=constants.common_error_embed(f"Failed to modify MIDI for '{instrument}'."))
                return
            midi_file = modified_midi_file

        song_ini_w_path = f'{os.path.dirname(midi_file)}/song.ini'
        # print(song_ini_w_path)
        open(song_ini_w_path, 'w', encoding="utf-8").write("[song]\nname = " + track_title + "\n" + "artist = " + artist_title + "\n" + "charter = Festival Tracker")

        output_image = f"{short_name}_{chosen_instrument.chopt.lower()}_path_{session_hash}.png".replace(' ', '_')
        chopt_output = self.run_chopt(midi_file, command_instrument, output_image, squeeze_percent, instrument=chosen_instrument, difficulty=chosen_diff.chopt,extra_args=extra_arguments)

        filtered_output = '\n'.join([line for line in chopt_output.splitlines() if "Optimising, please wait..." not in line])

        description = (
            f"**Instrument & Diff.:** {display_instrument} ({chosen_diff.english})\n"
            f"**Squeeze %:** {squeeze_percent}%\n"
        )

        for arg in field_argument_descriptors:
            description += f'{arg}\n'

        if os.path.exists(os.path.join(constants.TEMP_FOLDER, output_image)):
            file = discord.File(os.path.join(constants.TEMP_FOLDER, output_image), filename=output_image)

            container = discord.ui.Container()
            container.accent_colour = constants.ACCENT_COLOUR
            
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay("# Path"),
                    discord.ui.TextDisplay(f"**{track_title}** - *{artist_title}*"),
                    discord.ui.TextDisplay(description),
                    accessory=discord.ui.Thumbnail(album_art_url)
                )
            )
            # container.add_item()
            container.add_item(discord.ui.Separator())

            # container.add_item(discord.ui.TextDisplay(""))

            # container.add_item(discord.ui.Separator())
            acts = filtered_output.split('\n')[0].replace('Path: ', '').split('-')
            total_acts = len(acts)
            phrases, overlaps = self.process_acts(acts)

            no_sp_score = filtered_output.split('\n')[1].split(' ').pop()
            total_score = filtered_output.split('\n')[2].split(' ').pop()

            stats_text = f"**Phrases:** {phrases}\n**Activations:** {total_acts}\n**Overlaps:** {overlaps}\n**No OD Score:** {no_sp_score}\n**Total Score:** {total_score}"
            # container.add_item(

            container.add_item(discord.ui.Section(
                discord.ui.TextDisplay(stats_text),
                accessory=discord.ui.Thumbnail(f'attachment://{output_image}')
            ))

            container.add_item(discord.ui.TextDisplay(f"CHOpt Output\n```{filtered_output}```"))

            instrument_drop_down = discord.ui.Select()
            for instrument in constants.Instruments.__members__.values():
                if instrument.value.path_enabled:
                    instrument_drop_down.add_option(
                        label=instrument.value.english,
                        value=instrument.value.lb_code,
                        emoji=instrument.value.emoji,
                        default=(instrument.value.lb_code == chosen_instrument.lb_code)
                    )

            async def on_select(new_interaction: discord.Interaction):
                if interaction.user.id != new_interaction.user.id:
                    await new_interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
                    return

                new_selected_instrument = None
                for instr in constants.Instruments.__members__.values():
                    if instr.value.lb_code == instrument_drop_down.values[0]:
                        new_selected_instrument = instr
                        break

                await self.handle_interaction(new_interaction, song, new_selected_instrument, extra_args, squeeze_percent, difficulty)
            instrument_drop_down.callback = on_select

            action_row = discord.ui.ActionRow(instrument_drop_down)

            container.add_item(action_row)

            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay("-# Festival Tracker"))
    
            view = discord.ui.LayoutView()
            view.add_item(container)

            await interaction.edit_original_response(view=view, attachments=[file])
        else:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"Failed to generate the path image for '{track_title}'."))

        constants.delete_session_files(session_hash)
