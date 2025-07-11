"""
The MIT License (MIT)

Copyright (c) 2024-present Festival Tracker

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from hashlib import md5
import json
import math
import concurrent
import os
from pathlib import Path
import subprocess
import discord
from discord.ext import commands

import requests
import xmltodict
import base64

import logging

from pydub import AudioSegment
from pydub import utils as pdutils
import numpy as np
import base64

from bot import constants

class PreviewAudioMgr:
    def __init__(self, bot: discord.Client, track: any, interaction: discord.Interaction):
        self.bot = bot
        self.interaction = interaction
        self.track = track
        self.hash = md5(bytes(f"{interaction.user.id}-{interaction.id}-{interaction.message.id}", "utf-8")).digest().hex()
        self.audio_duration = 0

        qi = self.track['track']['qi']
        quicksilver_data = json.loads(qi)
        self.pid = quicksilver_data['pid']

        output_path = f'{constants.PREVIEW_FOLDER}{self.pid}/preview.ogg'
        if not os.path.exists(output_path):
            mpd = self.acquire_mpegdash_playlist(quicksilver_data)
            master_audio_path = self.download_mpd_playlist(mpd)
            output_path = self.convert_to_ogg(master_audio_path)

        self.output_path = output_path

    def _get_ffmpeg_path(self) -> str:
        ffmpeg_path = Path('ffmpeg.exe')

        if Path.exists(ffmpeg_path):
            return str(ffmpeg_path.resolve()).replace('\\', '/')
        
    def _get_ffprobe_path(self) -> str:
        ffprobe_path = Path('ffprobe.exe')

        if Path.exists(ffprobe_path):
            return str(ffprobe_path.resolve()).replace('\\', '/')

    def acquire_mpegdash_playlist(self, quicksilver_data: any) -> str:
        endpoint = 'https://cdn.qstv.on.epicgames.com/'
        url = endpoint + quicksilver_data['pid']

        logging.info(f'[GET] {url}')
        vod_data = requests.get(url)
        vod_data.raise_for_status()

        data = vod_data.json()
        playlist = base64.b64decode(data['playlist'])
        return playlist
    
    def download_mpd_playlist(self, mpd: str) -> str:
        data = xmltodict.parse(mpd)
        mpd_node = data['MPD']

        base_url = mpd_node['BaseURL']
        audio_duration = float(mpd_node['@mediaPresentationDuration'].replace('PT', '').replace('S', ''))

        self.audio_duration = audio_duration

        segment_duration = float(mpd_node['@maxSegmentDuration'].replace('PT', '').replace('S', ''))

        num_segments = math.ceil(audio_duration / segment_duration)

        representation = mpd_node['Period']['AdaptationSet']['Representation']
        repr_id = int(representation['@id'])
        sample_rate = int(representation['@audioSamplingRate'])

        init_template = representation['SegmentTemplate']['@initialization']
        segment_template = representation['SegmentTemplate']['@media']
        segment_start = int(representation['SegmentTemplate']['@startNumber'])

        output = f'temp/streaming_{self.hash}_'
        init_file = init_template.replace('$RepresentationID$', str(repr_id))
        init_path = output + init_file
        init_url = base_url + init_file
        logging.info(f'[GET] {init_url}')

        init_data = requests.get(init_url)
        with open(init_path, 'wb') as init_file_io:
            init_file_io.write(init_data.content)

        segments = []
            
        def download_segment(segment_id):
            segment_file = segment_template.replace('$RepresentationID$', str(repr_id)).replace('$Number$', str(segment_id))
            segment_path = output + segment_file
            segment_url = base_url + segment_file

            logging.info(f'[GET] {segment_url}')

            segment_data = requests.get(segment_url)
            with open(segment_path, 'wb') as segment_file_io:
                segment_file_io.write(segment_data.content)
                segments.append(segment_path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(download_segment, idx) for idx in range(segment_start, num_segments + 1)]
            concurrent.futures.wait(futures)

        segments.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))

        master_file = output + 'master_audio.mp4'
        with open(master_file, 'wb') as master:
            master.write(open(init_path, 'rb').read())
            os.remove(init_path)

            for segment in segments:
                master.write(open(segment, 'rb').read())
                os.remove(segment)

        return master_file
    
    def convert_to_ogg(self, master_audio_path):
        output_path = f'{constants.PREVIEW_FOLDER}{self.pid}'
        os.makedirs(output_path)
        output_path += '/preview.ogg'

        ffmpeg_path = self._get_ffmpeg_path()
        ffmpeg_command = [
            ffmpeg_path,
            '-i',
            master_audio_path,
            '-acodec', 
            'libopus',
            '-ar',
            '48000',
            output_path
        ]
        subprocess.run(ffmpeg_command)
        return output_path

    def get_waveform_bytearray(self) -> np.uint8:
        AudioSegment.converter = self._get_ffmpeg_path()

        def override_prober() -> str:
            return self._get_ffprobe_path()
        
        pdutils.get_prober_name = override_prober

        if os.path.exists(self.output_path.replace('preview.ogg', 'waveform.dat')):
            with open(self.output_path.replace('preview.ogg', 'waveform.dat'), 'rb') as f:
                return np.frombuffer(f.read(), dtype=np.uint8)

        audio = AudioSegment.from_file(self.output_path, format="ogg")
        audio.converter = self._get_ffmpeg_path()

        samples = np.array(audio.get_array_of_samples())
        sample_rate = audio.frame_rate

        # Normalize to range [-1.0, 1.0]
        samples = samples / np.max(np.abs(samples))

        # Downsample to 256 points
        total_samples = len(samples)
        stride = max(1, total_samples // 256)
        downsampled = samples[::stride][:256]

        # Scale to 0-255
        byte_array = np.uint8((downsampled + 1.0) * 127.5)

        # Cache the waveform bytearray
        with open(self.output_path.replace('preview.ogg', 'waveform.dat'), 'wb') as f:
            f.write(byte_array.tobytes())

        return byte_array

    async def reply_to_interaction_message(self):
        msg = self.interaction.message

        # url = f'https://discord.com/api/v10/channels/{msg.channel.id}/messages'

        # for responding to an ephmeral button interaction:
        url = f'https://discord.com/api/v10/webhooks/{self.bot.application.id}/{self.interaction.token}/messages/@original'
        # + remove message_reference from the payload
        # + change the method to PATCH

        flags = discord.MessageFlags()
        flags.voice = True

        wvform_bytearray = self.get_waveform_bytearray()
        wvform_b64 = base64.b64encode(wvform_bytearray.tobytes()).decode('utf-8')

        payload = {
            "tts": False,
            "flags": flags.value,
            "attachments": [
                {
                    "id": "0",
                    "filename": f"{self.hash}_voice-message.ogg",
                    "duration_secs": self.audio_duration,
                    "waveform": wvform_b64
                }
            ] # ,
            # "message_reference": {
            #     "message_id": msg.id,
            #     "channel_id": msg.channel.id,
            #     "guild_id": msg.guild.id
            # }
        }
        
        data = bytearray()
        data.extend(b"--boundary\r\n")
        data.extend(b"Content-Disposition: form-data; name=\"payload_json\"\r\n")
        data.extend(b"Content-Type: application/json\r\n\r\n")
        data.extend(json.dumps(payload, indent=4).encode('utf-8'))
        data.extend(b"\r\n--boundary\r\n")
        data.extend(f"Content-Disposition: form-data; name=\"files[0]\"; filename=\"{self.hash}_voice-message.ogg\"\r\n".encode('utf-8'))
        data.extend(b"Content-Type: audio/ogg\r\n\r\n")
        data.extend(open(self.output_path, 'rb').read())
        data.extend(b"\r\n--boundary--")

        logging.info(f'[POST] {url}')
        resp = requests.patch(url, data=data, headers={
            "Content-Type": "multipart/form-data; boundary=\"boundary\"",
            "Authorization": "Bot " + self.bot.http.token
        })

        logging.info(f'[Interaction {self.interaction.id}] Voice Message Received: {resp.status_code} {resp.reason}')

        if not resp.ok:
            logging.error(resp.text)

        await self.bot.get_channel(constants.LOG_CHANNEL).send(content=f"{constants.tz()} Voice Message for {self.track['track']['sn']} sent to {self.interaction.user.id}")