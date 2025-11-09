import base64
import logging
import os
import subprocess

import aiohttp
import mido
import requests

from bot import constants

import Crypto.Cipher.AES as AES


class MidiArchiveTools:
    def __init__(self) -> None:
        pass
    
    def decrypt_bytes(self, dat_bytes) -> bytes:
        midi_key = base64.b64decode(constants.SPARKS_MIDI_KEY)
        cipher = AES.new(midi_key, AES.MODE_ECB)
        decrypted_data = cipher.decrypt(dat_bytes)
        return decrypted_data

    async def save_chart(self, chart_url:str, decrypt:bool = True, log: bool = True) -> str:
        fname = chart_url.split('/')[-1].split('.')[0]
        midiname = f"{fname}.mid"
        encname = f"{fname}.dat"
        local_path = os.path.join(constants.MIDI_FOLDER, midiname)
        local_enc_path = os.path.join(constants.MIDI_FOLDER, encname)

        if os.path.exists(local_path):
            
            if log:
                logging.info(f"File {chart_url} already exists, using local copy.")

            return local_path
        
        elif os.path.exists(local_enc_path):

            if log:
                logging.info(f"File [encrypted] {chart_url} already exists, using local copy.")

            open(local_path, 'wb').write(self.decrypt_bytes(open(local_enc_path, 'rb').read()))
            return local_path
        else:
            logging.debug(f'[GET] {chart_url}')
            session = aiohttp.ClientSession()
            response = await session.get(chart_url)
            response.raise_for_status()

            midi_data = await response.content.read() # why??


            with open(local_enc_path, 'wb') as f:
                f.write(midi_data)

            
            if decrypt:
                decrypted_data = self.decrypt_bytes(midi_data)
                with open(local_path, 'wb') as f:
                    f.write(decrypted_data)

                await session.close()
                return local_path
            
            await session.close()
            return local_enc_path
        
    def modify_midi_file(self, midi_file: str, instrument: constants.Instrument, session_hash: str, shortname: str) -> str:
        mid = mido.MidiFile(midi_file)
        track_names_to_delete = []
        track_names_to_rename = {}

        track_names_to_delete.append(instrument.replace)
        track_names_to_rename[instrument.midi] = instrument.replace

        new_tracks = []
        for track in mid.tracks:
            modified_track = mido.MidiTrack() 
            for msg in track:
                if msg.type == 'track_name':
                    if msg.name in track_names_to_delete:
                        continue 
                    elif msg.name in track_names_to_rename:
                        msg.name = track_names_to_rename[msg.name] 
                modified_track.append(msg)
            new_tracks.append(modified_track)

        mid.tracks = new_tracks

        output_folder = 'out'
        midi_file_name = os.path.basename(midi_file)
        modified_midi_file_name = f"{shortname}_{session_hash}.mid"
        modified_midi_file = os.path.join(output_folder, modified_midi_file_name)

        mid.save(modified_midi_file)
        return modified_midi_file
