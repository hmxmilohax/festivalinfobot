import mido
import sys
from collections import defaultdict
import os
import matplotlib.pyplot as plt
import numpy as np


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
TIME_WINDOW = 240  # 60 ms window for grouping events
# Threshold for considering minor timing differences as insignificant
TIME_THRESHOLD = 240

# Define the notes to ignore for specific tracks
IGNORED_NOTES = {
    'PART POOP': {102},  # Ignore note 95 (2x kick) in PART DRUMS
}

# Define the tracks to compare
TRACKS_TO_COMPARE = [
    'PART BASS', 'PART GUITAR', 'PART DRUMS', 'PART VOCALS', "PLASTIC GUITAR", "PLASTIC DRUMS", "PLASTIC BASS", 'BEAT', 'EVENTS'
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

def visualize_midi_changes(differences, note_name_map, track_name, output_folder):
    """Visualize MIDI changes between two tracks and save as an image, using note name maps."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    times = []
    notes = []
    actions = []
    
    for time, removed, added in differences:
        for note in removed:
            times.append(time)
            # Get note name or fallback to note number
            notes.append(note_name_map.get(note[0], f"Note {note[0]}"))
            actions.append('removed')
        for note in added:
            times.append(time)
            notes.append(note_name_map.get(note[0], f"Note {note[0]}"))
            actions.append('added')
    
    times = np.array(times)
    note_labels = np.array(notes)
    colors = np.array(['red' if action == 'removed' else 'green' for action in actions])

    # Get unique note labels for y-axis
    unique_notes = np.unique(note_labels)
    note_to_index = {note: i for i, note in enumerate(unique_notes)}

    # Plot using the index of the note names for y-axis
    note_indices = [note_to_index[note] for note in note_labels]
    
    ax.scatter(times, note_indices, c=colors, marker='s', s=100, edgecolor='black', label=f'{track_name}')
    
    ax.set_xlabel('Time (ms)')
    ax.set_ylabel('Note')
    ax.set_title(f'MIDI Changes for {track_name}')
    ax.set_yticks(np.arange(len(unique_notes)))
    ax.set_yticklabels(unique_notes)  # Set the note names as labels
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Save the plot to the output folder
    image_path = os.path.join(output_folder, f"{track_name}_changes.png")
    plt.savefig(image_path)
    plt.close()
    
    print(f"Saved MIDI comparison visualization for {track_name} to {image_path}")

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


def main(midi_file1, midi_file2, note_range=range(60, 128)):
    base_name, ext = os.path.splitext(midi_file1)
    file_base_name = os.path.basename(base_name)
    output_folder = os.path.join(os.path.dirname(__file__), 'out')
    os.makedirs(output_folder, exist_ok=True)

    if not os.path.exists(midi_file2):
        print(f"Update file '{midi_file2}' is missing.")
        return

    tracks1, tempo_events1 = load_midi_tracks(midi_file1)
    if tracks1 is None:
        print(f"Error loading base MIDI file '{midi_file1}'.")
        return

    tracks2, tempo_events2 = load_midi_tracks(midi_file2)
    if tracks2 is None:
        print(f"Error loading update MIDI file '{midi_file2}'.")
        return
    
    # Compare existing tracks
    common_tracks = sorted(set(tracks1) & set(tracks2))
    for track_name in common_tracks:
        if track_name not in TRACKS_TO_COMPARE:
            continue
        
        track1_events = extract_note_events(tracks1[track_name], note_range)
        track2_events = extract_note_events(tracks2[track_name], note_range)
        
        differences = compare_tracks(track1_events, track2_events, TIME_WINDOW, TIME_THRESHOLD)
        note_name_map = note_name_maps.get(track_name, {})
        
        if differences:
            print(f"Differences found in track '{track_name}':")
            visualize_midi_changes(differences, note_name_map, track_name, output_folder)
        else:
            print(f"Track '{track_name}' matches old track")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_midi.py <midi_file1>")
    else:
        midi_file1 = sys.argv[1]
        midi_file2 = sys.argv[2]
        main(midi_file1, midi_file2)