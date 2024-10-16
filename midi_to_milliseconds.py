import logging
import time
import mido
import json

def get_length_in_beats(_bpm, ticks_since_last, ppqn):
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

def get_length_in_beats_tempo(tempo, ticks_since_last, ppqn):
    try:
        bpm = mido.tempo2bpm(tempo)
    except Exception as e:
        logging.error(f'Failed to make bpm, tempo is {tempo}', exc_info=e)
        bpm = mido.tempo2bpm(500000)
    return get_length_in_beats(bpm, ticks_since_last, ppqn)

def get_tempo(time, tempo_times):
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

def midi_to_object(midi_file_path):
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
                tempo_change_times += get_length_in_beats(previous_tempo_change_bpm, ticks_since_last_tempo, mid.ticks_per_beat)

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
                tempo_event = get_tempo(absolute_time, tempo_times)
                event_bpm = tempo_event[1]
                absolute_time_of_event = tempo_event[0]
                time_event_began = tempo_event[2]
                ticks_for_recalc = absolute_time - absolute_time_of_event

                current_event_time_s = time_event_began + get_length_in_beats(event_bpm, ticks_for_recalc, mid.ticks_per_beat)
                track_data['events'].append({
                    'time': current_event_time_s * 1000,
                    'text': event_text
                })

            # If a note starts playing, write it down
            if msg.type == 'note_on':
                # Get the time in beats and increment the value

                # Tempo of note
                tempo_event = get_tempo(absolute_time, tempo_times)
                event_bpm = tempo_event[1]

                absolute_time_of_event = tempo_event[0]

                time_event_began = tempo_event[2]
                
                ticks_for_recalc = absolute_time - absolute_time_of_event

                # if ticks_for_recalc < 0: the note uses the previous bpm
                #ticks_for_recalc = 0

                current_note_time_s = time_event_began + get_length_in_beats(event_bpm, ticks_for_recalc, mid.ticks_per_beat)

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

                    tempo_event = get_tempo(absolute_time, tempo_times)
                    bpm_note = tempo_event[1]
                    #print(f'Tempo at note_on: {bpm_note}')

                    note_duration = get_length_in_beats(bpm_note, note_duration_ticks, mid.ticks_per_beat)

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

if __name__ == '__main__':
    thing = midi_to_object('notes.mid')
    open('notes_test.json', 'w').write(json.dumps(thing, indent=4))