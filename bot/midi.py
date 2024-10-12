import logging
import os
import subprocess

import mido
import requests

from bot import constants


class MidiArchiveTools:
    def __init__(self) -> None:
        pass

    # Function to download and archive MIDI files locally
    def download_and_archive_midi_file(self, midi_url, midi_shortname, local_filename=None):
        # Use the file name from the URL if no local_filename is provided
        file_name_from_url = midi_url.split('/')[-1]  # Extract the file name from the URL
        if local_filename is None:
            local_filename = f"dat_{midi_shortname}_{file_name_from_url}"

        local_path = os.path.join(constants.LOCAL_MIDI_FOLDER, local_filename)
        if os.path.exists(local_path):
            logging.info(f"File {local_path} already exists, using local copy.")
            return local_path

        try:
            # Attempt to download the MIDI file
            logging.debug(f'[GET] {midi_url}')
            response = requests.get(midi_url, timeout=10)  # Add timeout to avoid hanging
            response.raise_for_status()

            # Write the file to the local path
            with open(local_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Downloaded and saved {local_filename}")
            return local_path
        except requests.exceptions.RequestException as e:
            # Catch network-related issues and print a helpful error message
            logging.error(f"Failed to download {midi_url}", exc_info=e)
            return None
        except Exception as e:
            # Catch any other exceptions that could occur and log them
            logging.error(f"Unexpected error occurred while downloading {midi_url}", exc_info=e)
            return None
        
    def decrypt_dat_file(self, dat_url_or_path, output_file):
        try:
            # Determine if we are dealing with a local file or URL
            if os.path.exists(dat_url_or_path):
                #print(f"Using local file: {dat_url_or_path}")
                dat_file_path = dat_url_or_path
            else:
                logging.info(f"Downloading file from: {dat_url_or_path}")
                dat_file_path = os.path.join(constants.TEMP_FOLDER, output_file)
                # Download the .dat file
                logging.debug(f'[GET] {dat_url_or_path}')
                response = requests.get(dat_url_or_path)
                if response.status_code == 200:
                    with open(dat_file_path, "wb") as file:
                        file.write(response.content)
                else:
                    logging.error(f"Failed to download .dat file from {dat_url_or_path}, response code was {response.status_code}")
                    return None

            # Decrypt the .dat file to .mid
            decrypted_midi_path = dat_file_path.replace('.dat', '.mid')
            
            # Check if the decrypted file already exists
            if not os.path.exists(decrypted_midi_path):
                logging.info(f"Decrypting {dat_file_path} to {decrypted_midi_path}...")
                result = subprocess.run(['python', 'fnf-midcrypt.py', '-d', dat_file_path], capture_output=True, text=True)
                if result.returncode != 0:
                    logging.error(f"Decryption failed: {result.stderr}")
                    return decrypted_midi_path
            else:
                #print(f"Decrypted MIDI file already exists: {decrypted_midi_path}")
                return decrypted_midi_path

            return decrypted_midi_path

        except Exception as e:
            logging.error(f"Error decrypting .dat file", exc_info=e)
            return None
        
    # Helper function to modify the MIDI file for Pro Lead and Pro Bass and Pro Drum
    def modify_midi_file(self, midi_file: str, instrument: constants.Instrument, session_hash: str, shortname: str) -> str:
        try:
            logging.info(f"Loading MIDI file: {midi_file}")
            mid = mido.MidiFile(midi_file)
            track_names_to_delete = []
            track_names_to_rename = {}

            # Check for Pro Lead, Pro Bass, or Pro Drums
            track_names_to_delete.append(instrument.replace)
            track_names_to_rename[instrument.midi] = instrument.replace

            # Logging track modification intent
            logging.info(f"Track names to delete: {track_names_to_delete}")
            logging.info(f"Track names to rename: {track_names_to_rename}")

            # Modify the tracks
            new_tracks = []
            for track in mid.tracks:
                modified_track = mido.MidiTrack()  # Create a new track object
                for msg in track:
                    if msg.type == 'track_name':
                        logging.info(f"Processing track: {msg.name}")
                        if msg.name in track_names_to_delete:
                            logging.info(f"Deleting track: {msg.name}")
                            continue  # Skip tracks we want to delete
                        elif msg.name in track_names_to_rename:
                            logging.info(f"Renaming track {msg.name} to {track_names_to_rename[msg.name]}")
                            msg.name = track_names_to_rename[msg.name]  # Rename the track
                    modified_track.append(msg)  # Append the message to the new track
                new_tracks.append(modified_track)

            # Assign modified tracks back to the MIDI file
            mid.tracks = new_tracks

            # Create the new file path in the 'out' folder with the session hash in the filename
            output_folder = 'out'  # Ensure this folder exists in your setup
            midi_file_name = os.path.basename(midi_file)  # Get the original file name
            modified_midi_file_name = f"{shortname}_{session_hash}.mid"  # Add session hash to the file name
            modified_midi_file = os.path.join(output_folder, modified_midi_file_name)  # Save in 'out' folder

            logging.info(f"Saving modified MIDI to: {modified_midi_file}")
            mid.save(modified_midi_file)
            logging.info(f"Modified MIDI saved successfully.")
            return modified_midi_file

        except Exception as e:
            logging.error(f"Error modifying MIDI for {instrument}", exc_info=e)
            return None