import logging
import os
import subprocess

import mido
import requests

from bot import constants


class MidiArchiveTools:
    def __init__(self) -> None:
        pass

    def download_and_archive_midi_file(self, midi_url, midi_shortname, local_filename=None):
        file_name_from_url = midi_url.split('/')[-1] 
        if local_filename is None:
            local_filename = f"dat_{midi_shortname}_{file_name_from_url}"

        local_path = os.path.join(constants.LOCAL_MIDI_FOLDER, local_filename)
        if os.path.exists(local_path):
            logging.info(f"File {local_path} already exists, using local copy.")
            return local_path

        # Attempt to download the MIDI file
        logging.debug(f'[GET] {midi_url}')
        response = requests.get(midi_url, timeout=10)  # Add timeout to avoid hanging
        response.status_code = 500 # TESTING PURPOSES ONLY
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"Downloaded and saved {local_filename}")
        return local_path
        
    def decrypt_dat_file(self, dat_url_or_path, output_file):
        if os.path.exists(dat_url_or_path):
            dat_file_path = dat_url_or_path
        else:
            logging.info(f"Downloading file from: {dat_url_or_path}")
            dat_file_path = os.path.join(constants.TEMP_FOLDER, output_file)
            # Download the .dat file
            logging.debug(f'[GET] {dat_url_or_path}')
            response = requests.get(dat_url_or_path)
            # response.status_code = 500
            # print(response.status_code)
            response.raise_for_status()

            with open(dat_file_path, "wb") as file:
                file.write(response.content)

        decrypted_midi_path = dat_file_path.replace('.dat', '.mid')
        
        if not os.path.exists(decrypted_midi_path):
            logging.info(f"Decrypting {dat_file_path} to {decrypted_midi_path}...")
            result = subprocess.run(['python', 'fnf-midcrypt.py', '-d', dat_file_path], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Decryption failed: {result.stderr}")
        else:
            #print(f"Decrypted MIDI file already exists: {decrypted_midi_path}")
            return decrypted_midi_path

        return decrypted_midi_path
        
    def modify_midi_file(self, midi_file: str, instrument: constants.Instrument, session_hash: str, shortname: str) -> str:
        logging.info(f"Loading MIDI file: {midi_file}")
        mid = mido.MidiFile(midi_file)
        track_names_to_delete = []
        track_names_to_rename = {}

        track_names_to_delete.append(instrument.replace)
        track_names_to_rename[instrument.midi] = instrument.replace

        logging.info(f"Track names to delete: {track_names_to_delete}")
        logging.info(f"Track names to rename: {track_names_to_rename}")

        new_tracks = []
        for track in mid.tracks:
            modified_track = mido.MidiTrack() 
            for msg in track:
                if msg.type == 'track_name':
                    logging.info(f"Processing track: {msg.name}")
                    if msg.name in track_names_to_delete:
                        logging.info(f"Deleting track: {msg.name}")
                        continue 
                    elif msg.name in track_names_to_rename:
                        logging.info(f"Renaming track {msg.name} to {track_names_to_rename[msg.name]}")
                        msg.name = track_names_to_rename[msg.name] 
                modified_track.append(msg)
            new_tracks.append(modified_track)

        mid.tracks = new_tracks

        output_folder = 'out'
        midi_file_name = os.path.basename(midi_file)
        modified_midi_file_name = f"{shortname}_{session_hash}.mid"
        modified_midi_file = os.path.join(output_folder, modified_midi_file_name)

        logging.info(f"Saving modified MIDI to: {modified_midi_file}")
        mid.save(modified_midi_file)
        logging.info(f"Modified MIDI saved successfully.")
        return modified_midi_file