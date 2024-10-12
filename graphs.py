import os
import bot.constants as const
import mido
from midi_to_milliseconds import midi_to_object
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def generate_nps_chart(midi_path : str, path : str, inst : const.Instrument, diff : const.Difficulty, song_name, song_artist):
    _notes = midi_to_object(midi_file_path=midi_path)

    instrument_idx = 0
    for i, track in enumerate(_notes['tracks']):
        instrument_idx = i
        if track['name'] == inst.midi:
            break

    notes = _notes['tracks'][instrument_idx]['notes']
    filtered_notes_seconds = [(note["start_time"] / 1000) for note in notes if diff.pitch_ranges[0] <= note["note"] <= diff.pitch_ranges[1]]

    # Group by seconds (integer part of the start time in seconds)
    grouped_by_second = {}
    for note_time in filtered_notes_seconds:
        second = int(note_time)  # Group by whole second
        if second in grouped_by_second:
            grouped_by_second[second] += 1
        else:
            grouped_by_second[second] = 1

    # Prepare data for plotting
    seconds = sorted(grouped_by_second.keys())
    notes_per_second = [grouped_by_second[second] for second in seconds]

    max_nps = max(notes_per_second)
    max_nps_second = seconds[notes_per_second.index(max_nps)]

    # Calculate Exponential Moving Average (EMA)
    window_size = 10  # Can adjust as needed
    df = pd.DataFrame({'nps': notes_per_second}, index=seconds)
    ema = df['nps'].ewm(span=window_size, adjust=False).mean()  # EMA calculation

    # Plotting
    plt.figure(figsize=(10, 4))

    # Plot the original notes per second
    plt.plot(seconds, notes_per_second, color='black', linestyle='-', linewidth=1, label='Notes per second')

    # Plot the EMA
    plt.plot(ema.index, ema.values, color='purple', linestyle='--', linewidth=1, label='EMA (Average)')

    plt.text(max_nps_second, max_nps, f'{max_nps}', color='blue', fontsize=10, ha='center', va='bottom')

    # Setting labels
    plt.xlabel('Time (seconds)')
    plt.ylabel('Notes per second')
    plt.title(f'{song_name} - {song_artist}: NPS ({diff.english} {inst.english})')

    # Reduce the frequency of the x-ticks, e.g., every 10 seconds
    plt.xticks(np.arange(min(seconds), max(seconds)+1, 10))

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=90)

    # Only keep horizontal grid lines
    plt.grid(axis='y')

    # Show legend
    plt.legend()

    plt.tight_layout()  # Adjust layout to fit rotated labels
    plt.savefig(os.path.join(const.TEMP_FOLDER, path))

    plt.close()

def generate_lanes_chart(midi_path : str, spath : str, inst : const.Instrument, diff : const.Difficulty, song_name, song_artist):
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

    # Create the bar plot
    plt.bar(labels, notes, color=['green', 'red', 'yellow', 'blue', 'orange'])

    # Add the exact numbers above each bar
    for i, value in enumerate(notes):
        plt.text(i, value + 3, str(value), ha='center')

    # Add labels and title
    plt.xlabel('Lanes')
    plt.ylabel('Number of Notes')
    plt.title(f'{song_artist} - {song_name}: Notes per lane ({diff.english} {inst.english})')

    # Display the plot
    plt.savefig(os.path.join(const.TEMP_FOLDER, spath))

    plt.close()

def generate_no_notes_pdi_chart(midi_path : str, path : str, song_name, song_artist, lifts : bool = False):
    # Data for each instrument and difficulty level
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

    # Number of groups and positions of bars
    x = np.arange(len(labels))  # Label locations
    width = 0.2  # Width of bars

    # Create subplots
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot bars for each difficulty level
    rects1 = ax.bar(x - 1.5*width, easy, width, label='Easy', color='orange')
    rects2 = ax.bar(x - 0.5*width, medium, width, label='Medium', color='blue')
    rects3 = ax.bar(x + 0.5*width, hard, width, label='Hard', color='green')
    rects4 = ax.bar(x + 1.5*width, expert, width, label='Expert', color='purple')

    # Add labels, title, and legend
    ax.set_xlabel('Instrument')
    ax.set_ylabel('Notes')
    ax.set_title(f'{song_artist} - {song_name}: ' + ('Note counts' if not lifts else 'Lift counts'))
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    # Function to add numbers on top of each bar
    def add_bar_labels(rects):
        for rect in rects:
            height = rect.get_height()
            ax.text(
                rect.get_x() + rect.get_width() / 2, height + 10,
                f'{height}',  # Label text (height of the bar)
                ha='center', va='bottom', color='black', rotation=90  # Position and color of text
            )

    # Add labels on top of each bar
    add_bar_labels(rects1)
    add_bar_labels(rects2)
    add_bar_labels(rects3)
    add_bar_labels(rects4)

    # Display the graph
    # plt.tight_layout()
    plt.tight_layout()
    plt.savefig(os.path.join(const.TEMP_FOLDER, path))

    plt.close()