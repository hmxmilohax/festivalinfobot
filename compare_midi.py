import mido
import sys
from collections import defaultdict
import os
import matplotlib.pyplot as plt
import numpy as np
import re

# Define the note name maps for different tracks
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
        59: "Left Hand Highest",
        40: "Left Hand Lowest"
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
        59: "Left Hand Highest",
        40: "Left Hand Lowest"
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
        13: "Up Beats",
        12: "Downbeat"
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
        59: "Left Hand Highest",
        40: "Left Hand Lowest"
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
        52: "DRUM ANIMATION",
        51: "FLOOR TOM RH",
        50: "FLOOR TOM LH",
        49: "TOM2 RH",
        48: "TOM2 LH",
        47: "TOM1 RH",
        46: "TOM1 LH",
        45: "SOFT CRASH 2 LH",
        44: "CRASH 2 LH",
        43: "RIDE LH",
        42: "RIDE CYM RH",
        41: "CRASH2 CHOKE",
        40: "CRASH1 CHOKE",
        39: "CRASH2 SOFT RH",
        38: "CRASH2 HARD RH",
        37: "CRASH1 SOFT RH",
        36: "CRASH1 HARD RH",
        35: "CRASH1 SOFT LH",
        34: "CRASH1 HARD LH",
        32: "PERCUSSION RH",
        31: "HI-HAT RH",
        30: "HI-HAT LH",
        29: "SOFT SNARE RH",
        28: "SOFT SNARE LH",
        27: "SNARE RH",
        26: "SNARE LH",
        25: "HI-HAT OPEN",
        24: "KICK RF"
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
        59: "Left Hand Highest",
        40: "Left Hand Lowest"
    },
}

# Time window for grouping events
TIME_WINDOW = 10  # 60 ms window for grouping events
# Threshold for considering minor timing differences as insignificant
TIME_THRESHOLD = 10

# Define the notes to ignore for specific tracks
IGNORED_NOTES = {
    'PART POOP': {102},  # Ignore note 95 (2x kick) in PART DRUMS
}

# Define the tracks to compare
TRACKS_TO_COMPARE = [
    'PART BASS', 'PART GUITAR', 'PART DRUMS', 'PART VOCALS', "PLASTIC GUITAR", "PLASTIC DRUMS", "PLASTIC BASS", 'BEAT', 'EVENTS', 'SECTION'
]

def load_midi_tracks(file_path):
    try:
        mid = mido.MidiFile(file_path)
    except OSError as e:
        print(f"Error loading MIDI file {file_path}: {e}")
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
        if msg.type == 'text':
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

def visualize_midi_changes(differences, text_differences, note_name_map, track_name, output_folder, session_id):
    """Visualize MIDI changes between two tracks, including note and text event changes, and save as an image."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    times = []
    notes = []
    actions = []

    # Plot note changes
    for time, removed, added in differences:
        for note in removed:
            times.append(time)
            notes.append(note[0])  # Use the raw MIDI note number for plotting
            actions.append('removed')
        for note in added:
            times.append(time)
            notes.append(note[0])  # Use the raw MIDI note number for plotting
            actions.append('added')

    # Plot text event changes
    text_times = []
    text_events = []
    text_changes = []
    
    for time, text1, text2 in text_differences:
        text_times.append(time)
        text_events.append(f"Text changed: {text1} -> {text2}")
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
        ax.scatter(text_times, [-1] * len(text_times), c='blue', marker='^', s=100, edgecolor='black', label='Text Event')
        for i, txt in enumerate(text_events):
            ax.annotate(txt, (text_times[i], -1), textcoords="offset points", xytext=(0, 5), ha='center', fontsize=8)

    ax.set_xlabel('Time (ms)')
    ax.set_ylabel('MIDI Note/Text')
    ax.set_title(f'MIDI Changes for {track_name}')
    
    # Set y-ticks based on the sorted MIDI note numbers (highest to lowest)
    ax.set_yticks(np.arange(len(unique_notes) + 1))  # Include extra space for text events

    # Apply note names instead of raw MIDI numbers, using the note_name_map
    ax.set_yticklabels([note_name_map.get(note, f"Note {note}") for note in unique_notes] + ['Text Events'])
    
    ax.invert_yaxis()  # This inverts the y-axis to ensure highest notes are at the top

    ax.grid(True, linestyle='--', alpha=0.7)

    track_name = track_name.replace(' ', '_')

    plt.tight_layout()
    
    # Save the plot to the output folder with session ID in the file name
    image_path = os.path.join(output_folder, f"{track_name}_changes_{session_id}.png")
    plt.savefig(image_path)
    plt.close()
    
    #print(f"Saved MIDI comparison visualization for {track_name} to {image_path}")

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
        text1 = text1_dict.get(time, "[no event]")
        text2 = text2_dict.get(time, "[no event]")
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
        print(f"Filtered output only contains a single track that is not in the list to compare.")
    else:
        new_mid.save(output_file)
        print(f"Filtered update MIDI saved to '{output_file}'")

def main(midi_file1, midi_file2, session_id, note_range=range(60, 128)):
    base_name1, ext1 = os.path.splitext(midi_file1)
    base_name2, ext2 = os.path.splitext(midi_file2)
    session_id, ext3 = os.path.splitext(session_id)

    if not session_id:
        print("Error: Could not extract session ID from the arg.")
        return False

    output_folder = os.path.join(os.path.dirname(__file__), 'out')
    os.makedirs(output_folder, exist_ok=True)

    if not os.path.exists(midi_file2):
        print(f"Update file '{midi_file2}' is missing.")
        return False

    tracks1, tempo_events1 = load_midi_tracks(midi_file1)
    if tracks1 is None:
        print(f"Error loading base MIDI file '{midi_file1}'.")
        return False

    tracks2, tempo_events2 = load_midi_tracks(midi_file2)
    if tracks2 is None:
        print(f"Error loading update MIDI file '{midi_file2}'.")
        return False

    # Compare tempo events
    tempo_differences = compare_tempo_events(tempo_events1, tempo_events2)
    if tempo_differences:
        print("Tempo differences found:")
        for time, tempo1, tempo2 in tempo_differences:
            print(f"At time {time}: Tempo changed from {tempo1} to {tempo2}")
    else:
        print("Tempo Map unchanged")

    # Compare existing tracks
    common_tracks = sorted(set(tracks1) & set(tracks2))
    for track_name in common_tracks:
        if track_name not in TRACKS_TO_COMPARE:
            continue
        
        # Compare note events
        track1_events = extract_note_events(tracks1[track_name], note_range)
        track2_events = extract_note_events(tracks2[track_name], note_range)
        
        differences = compare_tracks(track1_events, track2_events, TIME_WINDOW, TIME_THRESHOLD)
        note_name_map = note_name_maps.get(track_name, {})
        
        # Compare text events (track events)
        track1_text_events = extract_text_events(tracks1[track_name])
        track2_text_events = extract_text_events(tracks2[track_name])
        
        text_differences = compare_text_events(track1_text_events, track2_text_events)
        
        if differences or text_differences:
            #print(f"Differences found in track '{track_name}':")
            visualize_midi_changes(differences, text_differences, note_name_map, track_name, output_folder, session_id)
        else:
            print(f"'{track_name}' unchanged")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python compare_midi.py <midi_file1> <midi_file2> <session_id>")
    else:
        midi_file1 = sys.argv[1]
        midi_file2 = sys.argv[2]
        session_id = sys.argv[3]
        
        result = main(midi_file1, midi_file2, session_id)
        if result:
            print("MIDI comparison completed successfully.")
        else:
            print("MIDI comparison failed.")