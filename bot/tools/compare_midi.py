import mido
import sys
from collections import defaultdict
import os
import matplotlib

from bot import constants
matplotlib.use('Agg')

from matplotlib import pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.image as mpimg
import numpy as np
import re

import logging

font_path = os.path.abspath('bot/data/Fonts/InterTight-Regular.ttf')
prop = fm.FontProperties(fname=font_path)
font_name = prop.get_name()

fm.fontManager.addfont(font_path)

plt.rcParams['font.family'] = font_name

note_name_maps = {
    # Pro Charts
    'PLASTIC GUITAR': {
        127: "Trill Marker",
        126: "Tremolo Marker",
        116: "Overdrive",
        103: "Solo Marker",
        102: "EXPERT Force HOPO Off",
        101: "EXPERT Force HOPO On",
        100: "EXPERT Orange",
        99: "EXPERT Blue",
        98: "EXPERT Yellow",
        97: "EXPERT Red",
        96: "EXPERT Green",
        90: "HARD Force HOPO Off",
        89: "HARD Force HOPO On",
        88: "HARD Orange",
        87: "HARD Blue",
        86: "HARD Yellow",
        85: "HARD Red",
        84: "HARD Green",
        76: "MEDIUM Orange",
        75: "MEDIUM Blue",
        74: "MEDIUM Yellow",
        73: "MEDIUM Red",
        72: "MEDIUM Green",
        64: "EASY Orange",
        63: "EASY Blue",
        62: "EASY Yellow",
        61: "EASY Red",
        60: "EASY Green",
    },
    'PLASTIC BASS': {
        127: "Trill Marker",
        126: "Tremolo Marker",
        116: "Overdrive",
        103: "Solo Marker",
        102: "EXPERT Force HOPO Off",
        101: "EXPERT Force HOPO On",
        100: "EXPERT Orange",
        99: "EXPERT Blue",
        98: "EXPERT Yellow",
        97: "EXPERT Red",
        96: "EXPERT Green",
        90: "HARD Force HOPO Off",
        89: "HARD Force HOPO On",
        88: "HARD Orange",
        87: "HARD Blue",
        86: "HARD Yellow",
        85: "HARD Red",
        84: "HARD Green",
        76: "MEDIUM Orange",
        75: "MEDIUM Blue",
        74: "MEDIUM Yellow",
        73: "MEDIUM Red",
        72: "MEDIUM Green",
        64: "EASY Orange",
        63: "EASY Blue",
        62: "EASY Yellow",
        61: "EASY Red",
        60: "EASY Green",
    },
    'PLASTIC DRUMS': {
        127: "Cymbal Swells",
        126: "Drum Roll",
        124: "Drum Fill",
        123: "Drum Fill",
        122: "Drum Fill",
        121: "Drum Fill",
        120: "Drum Fill (use all 5)",
        116: "Overdrive",
        112: "Tom Marker 4",
        111: "Tom Marker 3",
        110: "Tom Marker 2",
        103: "Solo Marker",
        100: "EXPERT Green",
        99: "EXPERT Blue",
        98: "EXPERT Yellow",
        97: "EXPERT Red",
        96: "EXPERT Kick",
        88: "HARD Green",
        87: "HARD Blue",
        86: "HARD Yellow",
        85: "HARD Red",
        84: "HARD Kick",
        76: "MEDIUM Green",
        75: "MEDIUM Blue",
        74: "MEDIUM Yellow",
        73: "MEDIUM Red",
        72: "MEDIUM Kick",
        64: "EASY Green",
        63: "EASY Blue",
        62: "EASY Yellow",
        61: "EASY Red",
        60: "EASY Kick",
    },
    # Beat
    'BEAT': {
        13: "Measure",
        12: "Beat"
    },
    'SECTION': {
        10: "Practice Sections (?)"
    },
    'PRO VOCALS': {
        116: "Overdrive",
        105: "Phrase Marker",
        84: "Pro Vocals 48",
        83: "Pro Vocals 47",
        82: "Pro Vocals 46",
        81: "Pro Vocals 45",
        80: "Pro Vocals 44",
        79: "Pro Vocals 43",
        78: "Pro Vocals 42",
        77: "Pro Vocals 41",
        76: "Pro Vocals 40",
        75: "Pro Vocals 39",
        74: "Pro Vocals 38",
        73: "Pro Vocals 37",
        72: "Pro Vocals 36",
        71: "Pro Vocals 35",
        70: "Pro Vocals 34",
        69: "Pro Vocals 33",
        68: "Pro Vocals 32",
        67: "Pro Vocals 31",
        66: "Pro Vocals 30",
        65: "Pro Vocals 29",
        64: "Pro Vocals 28",
        63: "Pro Vocals 27",
        62: "Pro Vocals 26",
        61: "Pro Vocals 25",
        60: "Pro Vocals 24",
        59: "Pro Vocals 23",
        58: "Pro Vocals 22",
        57: "Pro Vocals 21",
        56: "Pro Vocals 20",
        55: "Pro Vocals 19",
        54: "Pro Vocals 18",
        53: "Pro Vocals 17",
        52: "Pro Vocals 16",
        51: "Pro Vocals 15",
        50: "Pro Vocals 14",
        49: "Pro Vocals 13",
        48: "Pro Vocals 12",
        47: "Pro Vocals 11",
        46: "Pro Vocals 10",
        45: "Pro Vocals 9",
        44: "Pro Vocals 8",
        43: "Pro Vocals 7",
        42: "Pro Vocals 6",
        41: "Pro Vocals 5",
        40: "Pro Vocals 4",
        39: "Pro Vocals 3",
        38: "Pro Vocals 2",
        37: "Pro Vocals 1"
    },
    # Normal Charts
    'PART VOCALS': {
        116: "Overdrive",
        106: "EXPERT 5 Lift",
        105: "EXPERT 4 Lift",
        104: "EXPERT 3 Lift",
        103: "EXPERT 2 Lift",
        102: "EXPERT 1 Lift",
        100: "EXPERT 5",
        99: "EXPERT 4",
        98: "EXPERT 3",
        97: "EXPERT 2",
        96: "EXPERT 1",
        93: "HARD 4 Lift",
        92: "HARD 3 Lift",
        91: "HARD 2 Lift",
        90: "HARD 1 Lift",
        87: "HARD 4",
        86: "HARD 3",
        85: "HARD 2",
        84: "HARD 1",
        81: "MEDIUM 4 Lift",
        80: "MEDIUM 3 Lift",
        79: "MEDIUM 2 Lift",
        78: "MEDIUM 1 Lift",
        75: "MEDIUM 4",
        74: "MEDIUM 3",
        73: "MEDIUM 2",
        72: "MEDIUM 1",
        69: "EASY 4 Lift",
        68: "EASY 3 Lift",
        67: "EASY 2 Lift",
        66: "EASY 1 Lift",
        63: "EASY 4",
        62: "EASY 3",
        61: "EASY 2",
        60: "EASY 1"
    },
    'PART BASS': {
        116: "Overdrive",
        106: "EXPERT 5 Lift",
        105: "EXPERT 4 Lift",
        104: "EXPERT 3 Lift",
        103: "EXPERT 2 Lift",
        102: "EXPERT 1 Lift",
        100: "EXPERT 5",
        99: "EXPERT 4",
        98: "EXPERT 3",
        97: "EXPERT 2",
        96: "EXPERT 1",
        93: "HARD 4 Lift",
        92: "HARD 3 Lift",
        91: "HARD 2 Lift",
        90: "HARD 1 Lift",
        87: "HARD 4",
        86: "HARD 3",
        85: "HARD 2",
        84: "HARD 1",
        81: "MEDIUM 4 Lift",
        80: "MEDIUM 3 Lift",
        79: "MEDIUM 2 Lift",
        78: "MEDIUM 1 Lift",
        75: "MEDIUM 4",
        74: "MEDIUM 3",
        73: "MEDIUM 2",
        72: "MEDIUM 1",
        69: "EASY 4 Lift",
        68: "EASY 3 Lift",
        67: "EASY 2 Lift",
        66: "EASY 1 Lift",
        63: "EASY 4",
        62: "EASY 3",
        61: "EASY 2",
        60: "EASY 1",
        59: "Fret 12",
        57: "Fret 11",
        56: "Fret 10",
        55: "Fret 9",
        53: "Fret 8",
        52: "Fret 7",
        50: "Fret 6",
        49: "Fret 5",
        47: "Fret 4",
        45: "Fret 3",
        43: "Fret 2",
        40: "Fret 1"
    },
    'PART DRUMS': {
        116: "Overdrive",
        106: "EXPERT 5 Lift",
        105: "EXPERT 4 Lift",
        104: "EXPERT 3 Lift",
        103: "EXPERT 2 Lift",
        102: "EXPERT 1 Lift",
        100: "EXPERT 5",
        99: "EXPERT 4",
        98: "EXPERT 3",
        97: "EXPERT 2",
        96: "EXPERT 1",
        93: "HARD 4 Lift",
        92: "HARD 3 Lift",
        91: "HARD 2 Lift",
        90: "HARD 1 Lift",
        87: "HARD 4",
        86: "HARD 3",
        85: "HARD 2",
        84: "HARD 1",
        81: "MEDIUM 4 Lift",
        80: "MEDIUM 3 Lift",
        79: "MEDIUM 2 Lift",
        78: "MEDIUM 1 Lift",
        75: "MEDIUM 4",
        74: "MEDIUM 3",
        73: "MEDIUM 2",
        72: "MEDIUM 1",
        69: "EASY 4 Lift",
        68: "EASY 3 Lift",
        67: "EASY 2 Lift",
        66: "EASY 1 Lift",
        63: "EASY 4",
        62: "EASY 3",
        61: "EASY 2",
        60: "EASY 1",
        51: "Floor Tom hit w/RH",
        50: "Floor Tom hit w/LH",
        49: "Tom2 hit w/RH",
        48: "Tom2 hit w/LH",
        47: "Tom1 hit w/RH",
        46: "Tom1 hit w/LH",
        45: "A soft hit on crash 2 with the left hand",
        44: "A hit on crash 2 with the left hand",
        43: "A ride hit with the left hand",
        42: "Ride Cym hit w/RH",
        41: "Crash2 Choke (hit w/RH, choke w/LH)",
        40: "Crash1 Choke (hit w/RH, choke w/LH)",
        39: "Crash2 (near Ride Cym) soft hit w/RH",
        38: "Crash2 hard hit w/RH",
        37: "Crash1 (near Hi-Hat) soft hit w/RH",
        36: "Crash1 hard hit w/RH",
        35: "Crash1 soft hit w/LH",
        34: "Crash1 hard hit w/LH",
        32: "Percussion w/ RH",
        31: "Hi-Hat hit w/RH",
        30: "Hi-Hat hit w/LH",
        29: "A soft snare hit with the right hand",
        28: "A soft snare hit with the left hand",
        27: "Snare hit w/RH",
        26: "Snare hit w/LH",
        25: "Hi-Hat pedal up (hat open) w/LF",
        24: "Kick hit w/RF",
    },
    'PART GUITAR': {
        116: "Overdrive",
        106: "EXPERT 5 Lift",
        105: "EXPERT 4 Lift",
        104: "EXPERT 3 Lift",
        103: "EXPERT 2 Lift",
        102: "EXPERT 1 Lift",
        100: "EXPERT 5",
        99: "EXPERT 4",
        98: "EXPERT 3",
        97: "EXPERT 2",
        96: "EXPERT 1",
        93: "HARD 4 Lift",
        92: "HARD 3 Lift",
        91: "HARD 2 Lift",
        90: "HARD 1 Lift",
        87: "HARD 4",
        86: "HARD 3",
        85: "HARD 2",
        84: "HARD 1",
        81: "MEDIUM 4 Lift",
        80: "MEDIUM 3 Lift",
        79: "MEDIUM 2 Lift",
        78: "MEDIUM 1 Lift",
        75: "MEDIUM 4",
        74: "MEDIUM 3",
        73: "MEDIUM 2",
        72: "MEDIUM 1",
        69: "EASY 4 Lift",
        68: "EASY 3 Lift",
        67: "EASY 2 Lift",
        66: "EASY 1 Lift",
        63: "EASY 4",
        62: "EASY 3",
        61: "EASY 2",
        60: "EASY 1",
        59: "Fret 12",
        57: "Fret 11",
        56: "Fret 10",
        55: "Fret 9",
        53: "Fret 8",
        52: "Fret 7",
        50: "Fret 6",
        49: "Fret 5",
        47: "Fret 4",
        45: "Fret 3",
        43: "Fret 2",
        40: "Fret 1"
    },
}

# Time window for grouping events
TIME_WINDOW = 10  # 60 ms window for grouping events
# Threshold for considering minor timing differences as insignificant
TIME_THRESHOLD = 10

# Define the notes to ignore for specific tracks

# Define the tracks to compare
TRACKS_TO_COMPARE = [
    'PART BASS', 'PART GUITAR', 'PART DRUMS', 'PART VOCALS', "PRO VOCALS", "PLASTIC GUITAR", "PLASTIC DRUMS", "PLASTIC BASS", 'BEAT', 'EVENTS', 'SECTION'
]

def load_midi_tracks(file_path):
    try:
        mid = mido.MidiFile(file_path)
    except OSError as e:
        logging.debug(f"Error loading MIDI file {file_path}: {e}")
        return None, None

    tracks = {}
    tempo_events = []
    for track in mid.tracks:
        track_name = None
        for msg in track:
            if msg.type == 'track_name':
                track_name = msg.name
                tracks[track_name] = track
                break
        if track_name is None:
            for msg in track:
                if msg.type == 'set_tempo':
                    tempo_events.append((msg.time, msg.tempo))
    return tracks, tempo_events

def compare_tempo_events(tempo_events1, tempo_events2):
    differences = []
    
    # Combine both sets of tempo events
    all_times = sorted(set([t[0] for t in tempo_events1] + [t[0] for t in tempo_events2]))
    
    # Create dictionaries to map time -> tempo
    tempo_map1 = {time: tempo for time, tempo in tempo_events1}
    tempo_map2 = {time: tempo for time, tempo in tempo_events2}
    
    # Compare tempo changes at each time
    for time in all_times:
        tempo1 = tempo_map1.get(time, None)
        tempo2 = tempo_map2.get(time, None)
        
        if tempo1 != tempo2:
            differences.append((time, tempo1, tempo2))
    
    return differences


def extract_note_events(track, note_range, ignore_notes=None):
    note_events = defaultdict(list)
    current_time = 0
    for msg in track:
        current_time += msg.time
        if msg.type in {'note_on', 'note_off'}:
            if msg.note in note_range and (ignore_notes is None or msg.note not in ignore_notes):
                note_type = 'note_off' if msg.type == 'note_off' or msg.type == 'note_on' else 'note_on'
                note_events[current_time].append((msg.note, note_type, msg.velocity))
    return note_events

def extract_text_events(track):
    text_events = []
    current_time = 0
    for msg in track:
        current_time += msg.time
        if msg.type == 'text' or msg.type == 'lyrics':
            text_events.append((current_time, msg.text))
    return text_events

def group_events_by_time_window(events, time_window):
    grouped_events = defaultdict(list)
    for time, notes in events.items():
        grouped_time = min(grouped_events.keys(), key=lambda t: abs(t - time) if abs(t - time) <= time_window else float('inf'), default=time)
        if abs(grouped_time - time) <= time_window:
            grouped_events[grouped_time].extend(notes)
        else:
            grouped_events[time].extend(notes)
    return grouped_events

def events_equal(event1, event2):
    return event1[0] == event2[0] and event1[1] == event2[1]

def extract_session_id(file_name):
    # Use regex to capture the hash part of the file name
    match = re.search(r'version_([a-f0-9]+)_', file_name)
    if match:
        return match.group(1)  # Return the hash
    return None

def visualize_midi_changes(differences, text_differences, note_name_map, track_name, output_folder, session_id, song_name, midi_file2):
    """Visualize MIDI changes between two tracks, including note and text event changes, and save as an image."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # dark mode (prototype)
    dark_mode = False

    if dark_mode:
        gray = (0.1, 0.1, 0.1)
        fig.patch.set_facecolor(gray)
        ax.set_facecolor(gray)

        ax.tick_params(colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')

    img = mpimg.imread('bot/data/Logo/Festival_Tracker_Fuser_sat.png')
    fig.figimage(img, xo=0, yo=0, alpha=0.15, zorder=-1)
    
    times = []
    notes = []
    actions = []

    mid = mido.MidiFile(midi_file2)
    ppqn = mid.ticks_per_beat

    # Plot note changes
    for time, removed, added in differences:
        for note in removed:
            times.append(time/ppqn)
            notes.append(note[0])  # Use the raw MIDI note number for plotting
            actions.append('removed')
        for note in added:
            times.append(time/ppqn)
            notes.append(note[0])  # Use the raw MIDI note number for plotting
            actions.append('added')

    # Plot text event changes
    text_times = []
    text_events = []
    text_changes = []
    
    for time, text1, text2 in text_differences:
        text_times.append(time/ppqn)
        text_events.append(f"{text1} >\n{text2}")
        text_changes.append('changed')

    # Convert note and text times to numpy arrays for plotting
    times = np.array(times)
    colors = np.array(['red' if action == 'removed' else 'green' for action in actions])

    # Sort the MIDI notes in descending order and map them to note names
    unique_notes = sorted(np.unique(notes), reverse=True)
    note_to_index = {note: i for i, note in enumerate(unique_notes)}
    
    # Plot note changes (use note indices for y-axis)
    note_indices = [note_to_index[note] for note in notes]
    ax.scatter(times, note_indices, c=colors, marker='s', s=100, edgecolor='black', label=f'{track_name}')

    

    # Add text event markers
    if text_times:
        # Plot text event changes with blue triangles
        ax.scatter(text_times, [-1] * len(text_times), c='blue', marker='^', s=25, edgecolor='black', label='Text Event')
        for i, txt in enumerate(text_events):
            ax.annotate(txt, (text_times[i], -1), textcoords="offset points", xytext=(0, 5), ha='center', fontsize=6)

    ax.set_xlabel('Beat (Time)')
    ax.set_ylabel('MIDI Note/Text')
    ax.set_title(f'{track_name} Track Diff. ({song_name})')
    
    # Set y-ticks based on the sorted MIDI note numbers (highest to lowest)
    ax.set_yticks(np.arange(len(unique_notes) + 1))  # Include extra space for text events

    # Apply note names instead of raw MIDI numbers, using the note_name_map
    ax.set_yticklabels([note_name_map.get(note, f"Note {note}") for note in unique_notes] + ['MIDI Notes'])
    
    ax.invert_yaxis()  # This inverts the y-axis to ensure highest notes are at the top

    ax.grid(True, linestyle='--', alpha=0.7)

    track_name = track_name.replace(' ', '_')
    fig.text(0.99, 0.01, "festivaltracker.org", fontsize=12, color='black', ha='right', va='bottom', alpha=1)

    plt.tight_layout()
    
    # Save the plot to the output folder with session ID in the file name
    image_path = os.path.join(output_folder, f"{track_name}_changes_{session_id}.png")
    logging.debug(f"Saving {image_path}")

    plt.savefig(image_path)

    plt.close()
    
    #logging.debug(f"Saved MIDI comparison visualization for {track_name} to {image_path}")

def compare_tracks(track1_events, track2_events, time_window, time_threshold, velocity_threshold=5):
    differences = []

    grouped_track1 = group_events_by_time_window(track1_events, time_window)
    grouped_track2 = group_events_by_time_window(track2_events, time_window)

    all_times = sorted(set(grouped_track1.keys()).union(grouped_track2.keys()))

    for time in all_times:
        base_events = grouped_track1.get(time, [])
        update_events = grouped_track2.get(time, [])

        base_events_set = {(e[0], e[1], e[2]) for e in base_events}  # Include velocity
        update_events_set = {(e[0], e[1], e[2]) for e in update_events}  # Include velocity

        if base_events_set != update_events_set:
            added = update_events_set - base_events_set
            removed = base_events_set - update_events_set

            close_matches = False
            for other_time in all_times:
                if time != other_time and abs(time - other_time) <= time_threshold:
                    other_base_events = grouped_track1.get(other_time, [])
                    other_update_events = grouped_track2.get(other_time, [])
                    other_base_events_set = {(e[0], e[1], e[2]) for e in other_base_events}
                    other_update_events_set = {(e[0], e[1], e[2]) for e in other_update_events}

                    if (removed & other_update_events_set) or (added & other_base_events_set):
                        close_matches = True
                        break

            if not close_matches:
                filtered_added = {note for note in added if abs(note[2]) > velocity_threshold}
                filtered_removed = {note for note in removed if abs(note[2]) > velocity_threshold}

                if filtered_added or filtered_removed:
                    differences.append((time, list(filtered_removed), list(filtered_added)))

    return differences

def compare_text_events(track1_text_events, track2_text_events):
    differences = []

    times1 = {time for time, _ in track1_text_events}
    times2 = {time for time, _ in track2_text_events}
    all_times = sorted(times1 | times2)

    text1_dict = dict(track1_text_events)
    text2_dict = dict(track2_text_events)

    for time in all_times:
        text1 = text1_dict.get(time, "X")
        text2 = text2_dict.get(time, "X")
        if text1 != text2:
            differences.append((time, text1, text2))

    return differences

def format_comparison(removed, added, note_name_map):
    messages = []
    if removed:
        removed_str = ', '.join(note_name_map.get(note[0], f"Unknown Note ({note[0]})") for note in removed)
        messages.append(f"removed: {removed_str}")
    if added:
        added_str = ', '.join(note_name_map.get(note[0], f"Unknown Note ({note[0]})") for note in added)
        messages.append(f"added: {added_str}")
    return ', '.join(messages)

def format_text_comparison(time, text1, text2):
    return f"Time: {time}, Text event changed from '{text1}' to '{text2}'"

def save_filtered_midi(input_file, output_file, tracks_to_remove, tempo_events):
    mid = mido.MidiFile(input_file)
    new_mid = mido.MidiFile()
    
    # Create a new tempo track if there are tempo events
    if tempo_events:
        tempo_track = mido.MidiTrack()
        new_mid.tracks.append(tempo_track)
        current_time = 0
        for time, tempo in tempo_events:
            current_time += time
            tempo_track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=current_time))
            current_time = 0
    
    for track in mid.tracks:
        track_name = None
        for msg in track:
            if msg.type == 'track_name':
                track_name = msg.name
                break
        
        if track_name not in tracks_to_remove:
            new_mid.tracks.append(track)
    
    if len(new_mid.tracks) == 1:
        # Create an emptyupdate.txt file if conditions are met
        #empty_output_file = os.path.join(os.path.dirname(output_file), f"{os.path.splitext(os.path.basename(output_file))[0]}_emptyupdate.txt")
        #with open(empty_output_file, 'w', encoding='utf-8') as f:
        #    f.write("EMPTY")
        logging.debug(f"Filtered output only contains a single track that is not in the list to compare.")
    else:
        new_mid.save(output_file)
        logging.debug(f"Filtered update MIDI saved to '{output_file}'")

def main(midi_file1, midi_file2, session_id, song_name, note_range=range(1, 128)):
    base_name1, ext1 = os.path.splitext(midi_file1)
    base_name2, ext2 = os.path.splitext(midi_file2)
    session_id, ext3 = os.path.splitext(session_id)

    if not session_id:
        logging.debug("Error: Could not extract session ID from the arg.")
        return False

    output_folder = constants.TEMP_FOLDER
    os.makedirs(output_folder, exist_ok=True)

    if not os.path.exists(midi_file2):
        logging.debug(f"Update file '{midi_file2}' is missing.")
        return False

    tracks1, tempo_events1 = load_midi_tracks(midi_file1)
    if tracks1 is None:
        logging.debug(f"Error loading base MIDI file '{midi_file1}'.")
        return False

    tracks2, tempo_events2 = load_midi_tracks(midi_file2)
    if tracks2 is None:
        logging.debug(f"Error loading update MIDI file '{midi_file2}'.")
        return False

    # Compare tempo events
    tempo_differences = compare_tempo_events(tempo_events1, tempo_events2)
    if tempo_differences:
        logging.debug("Tempo differences found:")
        for time, tempo1, tempo2 in tempo_differences:
            logging.debug(f"At time {time}: Tempo changed from {tempo1} to {tempo2}")
    else:
        logging.debug("Tempo Map unchanged")

    # Compare existing tracks
    common_tracks = sorted(set(tracks1) & set(tracks2))
    if 'PRO VOCALS' not in common_tracks:
        common_tracks.append('PRO VOCALS')

    for track_name in common_tracks:
        if track_name not in TRACKS_TO_COMPARE:
            continue
        
        # Compare note events
        track1_events = extract_note_events(tracks1.get(track_name, []), note_range)
        track2_events = extract_note_events(tracks2.get(track_name, []), note_range)
        
        differences = compare_tracks(track1_events, track2_events, TIME_WINDOW, TIME_THRESHOLD)
        note_name_map = note_name_maps.get(track_name, {})
        
        # Compare text events (track events)
        track1_text_events = extract_text_events(tracks1.get(track_name, []))
        track2_text_events = extract_text_events(tracks2.get(track_name, []))
        
        text_differences = compare_text_events(track1_text_events, track2_text_events)
        
        if differences or text_differences:
            #logging.debug(f"Differences found in track '{track_name}':")
            visualize_midi_changes(differences, text_differences, note_name_map, track_name, output_folder, session_id, song_name, midi_file2)
        else:
            logging.debug(f"'{track_name}' unchanged")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 5:
        logging.debug("Usage: python compare_midi.py <midi_file1> <midi_file2> <session_id> <song_name>")
    else:
        midi_file1 = sys.argv[1]
        midi_file2 = sys.argv[2]
        session_id = sys.argv[3]
        song_name = sys.argv[4] if len(sys.argv) > 4 else "Unknown Track"
        
        result = main(midi_file1, midi_file2, session_id, song_name)
        if result:
            logging.debug("MIDI comparison completed successfully.")
        else:
            logging.debug("MIDI comparison failed.")

def run_comparison(midi_file1, midi_file2, session_id, song_name = 'unknown'):
    result = main(midi_file1, midi_file2, session_id, song_name)
    if result:
        logging.debug("MIDI comparison completed successfully.")
    else:
        logging.debug("MIDI comparison failed.")
    return result