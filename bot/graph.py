import logging
import os
import discord

from bot import constants
from bot.midi import MidiArchiveTools
from bot.tracks import JamTrackHandler
import os
import bot.constants as const
import mido
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

class GraphCommandsHandler():
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.midi_tool = MidiArchiveTools()

    async def handle_pdi_interaction(self, interaction:discord.Interaction, song:str):
        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)
        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        
        image_path = f'{short_name}_pdi_graph_{session_hash}.png'
        GraphingFuncs().generate_no_notes_pdi_chart(midi_path=midi_file, path=image_path, song_name=track_title, song_artist=artist_title)
        
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
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)
        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        
        image_path = f'{short_name}_lift_graph_{session_hash}.png'
        GraphingFuncs().generate_no_notes_pdi_chart(midi_path=midi_file, path=image_path, song_name=track_title, song_artist=artist_title, lifts=True)
        
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
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)

        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        
        image_path = f'{short_name}_nps_graph_{session_hash}.png'
        GraphingFuncs().generate_nps_chart(midi_path=midi_file, path=image_path, inst=chosen_instrument, diff=chosen_diff, song_name=track_title, song_artist=artist_title)
        
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
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        local_midi_file = self.midi_tool.download_and_archive_midi_file(song_url, short_name)

        midi_file = self.midi_tool.decrypt_dat_file(local_midi_file, session_hash)
        
        image_path = f'{short_name}_lanes_graph_{session_hash}.png'
        GraphingFuncs().generate_lanes_chart(midi_path=midi_file, spath=image_path, inst=chosen_instrument, diff=chosen_diff, song_name=track_title, song_artist=artist_title)
        
        embed = discord.Embed(title=f"Notes per lane graph for\n**{track_title}** - *{artist_title}*", color=0x8927A1)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

class GraphingFuncs():
    def __init__(self):
        pass

    def generate_nps_chart(self, midi_path : str, path : str, inst : const.Instrument, diff : const.Difficulty, song_name, song_artist):
        _notes = MidiToObj().midi_to_object(midi_file_path=midi_path)

        instrument_idx = 0
        for i, track in enumerate(_notes['tracks']):
            instrument_idx = i
            if track['name'] == inst.midi:
                break

        notes = _notes['tracks'][instrument_idx]['notes']
        filtered_notes_seconds = [(note["start_time"] / 1000) for note in notes if diff.pitch_ranges[0] <= note["note"] <= diff.pitch_ranges[1]]

        grouped_by_second = {}
        for note_time in filtered_notes_seconds:
            second = int(note_time)
            if second in grouped_by_second:
                grouped_by_second[second] += 1
            else:
                grouped_by_second[second] = 1

        seconds = sorted(grouped_by_second.keys())
        notes_per_second = [grouped_by_second[second] for second in seconds]

        max_nps = max(notes_per_second)
        max_nps_second = seconds[notes_per_second.index(max_nps)]

        window_size = 10
        df = pd.DataFrame({'nps': notes_per_second}, index=seconds)
        ema = df['nps'].ewm(span=window_size, adjust=False).mean()
        plt.figure(figsize=(10, 4))

        # Plot the original notes per second
        plt.plot(seconds, notes_per_second, color='black', linestyle='-', linewidth=1, label='Notes per second')

        # Plot the EMA
        plt.plot(ema.index, ema.values, color='purple', linestyle='--', linewidth=1, label='EMA (Average)')

        plt.text(max_nps_second, max_nps, f'{max_nps}', color='blue', fontsize=10, ha='center', va='bottom')

        plt.xlabel('Time (seconds)')
        plt.ylabel('Notes per second')
        plt.title(f'{song_name} - {song_artist}: NPS ({diff.english} {inst.english})')

        plt.xticks(np.arange(min(seconds), max(seconds)+1, 10))
        plt.xticks(rotation=90)
        plt.grid(axis='y')

        plt.legend()

        plt.tight_layout()
        plt.savefig(os.path.join(const.TEMP_FOLDER, path))

        plt.close()

    def generate_lanes_chart(self, midi_path : str, spath : str, inst : const.Instrument, diff : const.Difficulty, song_name, song_artist):
        labels = ['Green', 'Red', 'Yellow', 'Blue', 'Orange']
        notes = [0, 0, 0, 0, 0]

        mid = mido.MidiFile(midi_path)
        for track in mid.tracks:
            if track.name == inst.midi:
                for msg in track:
                    if msg.type == 'note_on':
                        start = diff.pitch_ranges[0]
                        end = diff.pitch_ranges[1]

                        if msg.note >= start and msg.note <= end:
                            lane = msg.note - start
                            notes[lane] += 1
        plt.bar(labels, notes, color=['green', 'red', 'yellow', 'blue', 'orange'])

        for i, value in enumerate(notes):
            plt.text(i, value + 3, str(value), ha='center')
        plt.xlabel('Lanes')
        plt.ylabel('Number of Notes')
        plt.title(f'{song_artist} - {song_name}: Notes per lane ({diff.english} {inst.english})')

        plt.savefig(os.path.join(const.TEMP_FOLDER, spath))

        plt.close()

    def generate_no_notes_pdi_chart(self, midi_path : str, path : str, song_name, song_artist, lifts : bool = False):
        labels = []
        easy = []
        medium = []
        hard = []
        expert = []
        mid = mido.MidiFile(midi_path)
        for instrument in const.Instruments.getall():
            if lifts:
                if instrument.plastic:
                    continue

            labels.append(instrument.english)
            for difficulty in const.Difficulties.getall():
                total_notes = 0

                for track in mid.tracks:
                    if track.name == instrument.midi:
                        for msg in track:
                            if msg.type == 'note_on':
                                start = difficulty.pitch_ranges[0]
                                end = difficulty.pitch_ranges[1]
                                if lifts:
                                    start += 6
                                    end += 6

                                if msg.note >= start and msg.note <= end:
                                    total_notes += 1

                if difficulty.chopt == 'expert':
                    expert.append(total_notes)
                elif difficulty.chopt == 'hard':
                    hard.append(total_notes)
                elif difficulty.chopt == 'medium':
                    medium.append(total_notes)
                elif difficulty.chopt == 'easy':
                    easy.append(total_notes)

        x = np.arange(len(labels))
        width = 0.2  # Width of bars

        fig, ax = plt.subplots(figsize=(10, 6))

        rects1 = ax.bar(x - 1.5*width, easy, width, label='Easy', color='orange')
        rects2 = ax.bar(x - 0.5*width, medium, width, label='Medium', color='blue')
        rects3 = ax.bar(x + 0.5*width, hard, width, label='Hard', color='green')
        rects4 = ax.bar(x + 1.5*width, expert, width, label='Expert', color='purple')

        ax.set_xlabel('Instrument')
        ax.set_ylabel('Notes')
        ax.set_title(f'{song_artist} - {song_name}: ' + ('Note counts' if not lifts else 'Lift counts'))
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        def add_bar_labels(rects):
            for rect in rects:
                height = rect.get_height()
                ax.text(
                    rect.get_x() + rect.get_width() / 2, height + 10,
                    f'{height}',
                    ha='center', va='bottom', color='black', rotation=90
                )

        add_bar_labels(rects1)
        add_bar_labels(rects2)
        add_bar_labels(rects3)
        add_bar_labels(rects4)

        # Display the graph
        # plt.tight_layout()
        plt.tight_layout()
        plt.savefig(os.path.join(const.TEMP_FOLDER, path))

        plt.close()

class MidiToObj():
    def get_length_in_beats(self, _bpm, ticks_since_last, ppqn):
        #tempo  = mido.bpm2tempo(_bpm)

        #bpm = mido.tempo2bpm(tempo)
        bpm = _bpm

        try:
            beat_crochet = (60 / bpm)
        except:
            beat_crochet = 0
        try:
            length_in_beats_of_note = ticks_since_last / ppqn
        except ZeroDivisionError:
            length_in_beats_of_note = 0

        return beat_crochet * length_in_beats_of_note

    def get_length_in_beats_tempo(self, tempo, ticks_since_last, ppqn):
        try:
            bpm = mido.tempo2bpm(tempo)
        except Exception as e:
            logging.error(f'Failed to make bpm, tempo is {tempo}', exc_info=e)
            bpm = mido.tempo2bpm(500000)
        return self.get_length_in_beats(bpm, ticks_since_last, ppqn)

    def get_tempo(self, time, tempo_times):
        if not tempo_times:
            return None  # Handle empty tempo_times list

        # Check first tempo without decrementing i
        if time <= tempo_times[0][0]:
            return tempo_times[0]

        for i, tempo_change in enumerate(tempo_times[1:], start=1):
            check = i - 1
            if tempo_times[check][0] <= time and tempo_change[0] >= time:
                return tempo_times[check]
        # Return last tempo if no match is found
        return tempo_times[-1]

    def midi_to_object(self, midi_file_path):
        mid = mido.MidiFile(midi_file_path)
        
        midi_data = {
            'ticks_per_beat': mid.ticks_per_beat,
            "tempo": [],
            "time_signature": [],
            'tracks': []
        }

        # Extract tempo and time signature events
        tempo_times = []

        # Process tempo changes first
        for i, track in enumerate(mid.tracks):
            absolute_time = 0
            ticks_since_last_tempo = 0
            previous_tempo_change_bpm = 0
            tempo_change_times = 0

            for msg in track:
                absolute_time += msg.time
                ticks_since_last_tempo += msg.time

                if msg.type == "set_tempo":
                    # Tempo change times
                    tempo_change_times += self.get_length_in_beats(previous_tempo_change_bpm, ticks_since_last_tempo, mid.ticks_per_beat)

                    this_change_bpm = mido.tempo2bpm(msg.tempo)

                    midi_data["tempo"].append({
                        # "time_since_last": msg.time,
                        # "time_in_ticks": absolute_time,

                        'time': tempo_change_times * 1000,
                        "bpm": this_change_bpm,
                        "tempo": msg.tempo
                    })

                    ticks_since_last_tempo = 0

                    prev = previous_tempo_change_bpm

                    previous_tempo_change_bpm = this_change_bpm

                    tempo_times.append([
                        absolute_time, 
                        this_change_bpm,
                        tempo_change_times, 
                        msg.tempo, 
                        msg.time,
                        prev,
                        msg.time / mid.ticks_per_beat
                    ])

                # if msg.type == "time_signature":
                #     midi_data["time_signature"].append({
                #         "time_since_last": msg.time,
                #         "time_in_ticks": absolute_time,
                #         "time": msg.time,
                #         "numerator": msg.numerator,
                #         "denominator": msg.denominator,
                #         "click": msg.clocks_per_click,
                #         "notesQ": msg.notated_32nd_notes_per_beat
                #     })

        for i, track in enumerate(mid.tracks):
            track_data = {
                "name": track.name,
                "id": i,
                "events": [],
                "notes": []
            }
            active_notes = {}
            absolute_time = 0
            ticks_since_last_note_on = 0

            for msg in track:
                # On any event, the absolute time is still increasing.
                absolute_time += msg.time
                ticks_since_last_note_on += msg.time

                if msg.type == 'text':
                    event_text = msg.text

                    # Tempo of note
                    tempo_event = self.get_tempo(absolute_time, tempo_times)
                    event_bpm = tempo_event[1]
                    absolute_time_of_event = tempo_event[0]
                    time_event_began = tempo_event[2]
                    ticks_for_recalc = absolute_time - absolute_time_of_event

                    current_event_time_s = time_event_began + self.get_length_in_beats(event_bpm, ticks_for_recalc, mid.ticks_per_beat)
                    track_data['events'].append({
                        'time': current_event_time_s * 1000,
                        'text': event_text
                    })

                # If a note starts playing, write it down
                if msg.type == 'note_on':
                    # Get the time in beats and increment the value

                    # Tempo of note
                    tempo_event = self.get_tempo(absolute_time, tempo_times)
                    event_bpm = tempo_event[1]

                    absolute_time_of_event = tempo_event[0]

                    time_event_began = tempo_event[2]
                    
                    ticks_for_recalc = absolute_time - absolute_time_of_event

                    # if ticks_for_recalc < 0: the note uses the previous bpm
                    #ticks_for_recalc = 0

                    current_note_time_s = time_event_began + self.get_length_in_beats(event_bpm, ticks_for_recalc, mid.ticks_per_beat)

                    # Use the current ticks_since_last_note_on, where we know at which tick began since the last note_on event
                    # Because the  time ticks_since_last_note_on is still increasing, note_off events will not affect this.
                    active_notes[msg.note] = [
                        ticks_since_last_note_on,
                        current_note_time_s,
                        absolute_time,
                    ]

                    # Reset the ticks_since_last_note_on
                    ticks_since_last_note_on = 0

                    #time.sleep(0.1)
                    
                elif msg.type == 'note_off':
                    # Get the note_on event
                    note_on_event = active_notes.pop(msg.note, None)

                    if note_on_event is not None:
                        # Get the ticks since last note_on event at which this note began.
                        note_ticks_since_last = note_on_event[0]

                        # The time in beats this note began at
                        note_time = note_on_event[1]

                        # The absolute time the note began
                        absolute_time_note_began = note_on_event[2]

                        # When this note_off event starts, the duration will be the ticks since the last event
                        # (last event being note_on)
                        note_duration_ticks = absolute_time - absolute_time_note_began

                        tempo_event = self.get_tempo(absolute_time, tempo_times)
                        bpm_note = tempo_event[1]
                        #print(f'Tempo at note_on: {bpm_note}')

                        note_duration = self.get_length_in_beats(bpm_note, note_duration_ticks, mid.ticks_per_beat)

                        # A hold note will be longer than a step.
                        is_hold_note = note_duration_ticks > int(mid.ticks_per_beat / 4)

                        #print(int(mid.ticks_per_beat / 4))
                        
                        note_data = {
                            'note': msg.note,

                            # Compat values
                            'is_hold_note': is_hold_note,
                            'start_time': note_time * 1000,
                            'duration': note_duration * 1000
                            
                            # 'descriptor': dascription
                        }

                        track_data['notes'].append(note_data)
                        
            midi_data['tracks'].append(track_data)

        return midi_data