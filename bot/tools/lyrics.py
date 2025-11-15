import os

import discord
import requests
from bot import constants, midi
import mido
from mido.midifiles.tracks import _to_abstime
import PIL
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from collections import Counter
import random

import textwrap

from bot.tracks import JamTrackHandler

class LyricsError(Exception):
    pass

event_map = {
    'intro': 'Intro',
    'verse': 'Verse',
    'build': 'Build',
    'chorus': 'Chorus',
    'prechorus': 'Pre-Chorus',
    'breakdown': 'Breakdown',
    'bridge': 'Bridge',
    'drop': 'Drop',
    'solo_guitar': 'Guitar Solo',
    'solo_bass': 'Bass Solo',
    'solo_drums': 'Drum Solo',
    'solo_vocals': 'Vocal Solo',
    'solo_keys': 'Keyboard Solo',
    'outro': 'Outro',
}

class LyricsHandler():
    def __init__(self):
        self.midi_tool = midi.MidiArchiveTools()
        self.jam_track_handler = JamTrackHandler()

    async def handle_interaction(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        track_list = constants.get_jam_tracks(use_cache=True)
        if not track_list:
            await interaction.edit_original_response(embed=constants.common_error_embed('Could not get Jam Tracks.'))
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(track_list, query)
        if not matched_tracks:
            await interaction.edit_original_response(embed=constants.common_error_embed(f'No tracks were found matching \"{query}\"'))
            return
        
        track = matched_tracks[0]

        try:
            fname = await self.load_lyrics(track)
            await interaction.edit_original_response(attachments=[discord.File(fname)])
        except LyricsError as e:
            await interaction.edit_original_response(embed=constants.common_error_embed(str(e)))

    async def load_lyrics(self, track):
        midi = track['track']['mu']
        midi_path = await self.midi_tool.save_chart(midi)
        
        midi_slug = midi_path.split('/')[-1].replace('.mid', '')
        print(midi_slug)

        os.makedirs('cache/lyrics', exist_ok=True)
        os.makedirs('cache/lyrics/img', exist_ok=True)

        fname = f"cache/lyrics/img/lyrics_{track['track']['sn']}_{midi_slug}.png"
        # if os.path.exists(fname):
        #     return fname

        mid = mido.MidiFile(midi_path, charset='utf-8')
        tracks: list[mido.MidiTrack] = mid.tracks
        pro_vocals_track = discord.utils.find(lambda t: t.name == 'PRO VOCALS', tracks)

        if not pro_vocals_track:
            raise LyricsError('Pro Vocals not supported')

        messages = list(_to_abstime(pro_vocals_track))
        messages_only_notes = list(filter(lambda m: m.type == 'note_on' or m.type == 'note_off', messages))
        messages_only_phrases = list(filter(lambda m: m.note == 105, messages_only_notes))
        messages_only_phrases.sort(key=lambda msg: msg.note) # ascending notes
        messages_only_phrases.sort(key=lambda msg: msg.time) # ascending time

        phrases = []
        cur_phrase = None
        for phrase in messages_only_phrases:
            #                            I hope this doesnt
            #                              break anything!
            if phrase.type == 'note_on' and not cur_phrase:
                cur_phrase = {
                    'start': phrase.time,
                    'note': phrase.note,
                    'end': None,
                    'notes': []
                }
                #                                   DUMBASS FIX BRO 
                #                                    HARMONIX FIX
                #                                    UR GAME PLS
            elif (phrase.type == 'note_off' or phrase.type == 'note_on') and cur_phrase and phrase.note == cur_phrase['note']:
                cur_phrase['end'] = phrase.time
                phrases.append(cur_phrase)
                cur_phrase = None

        # print(phrases)

        messages_only_meta = list(filter(lambda m: isinstance(m, mido.MetaMessage), messages))
        messages_only_lyrics = list(filter(lambda m: m.type == 'lyrics', messages_only_meta))
        messages_only_lyrics.sort(key=lambda msg: msg.time) # ascending time

        messages_only_sung = list(filter(lambda m: m.note < 85 and m.note > 35, messages_only_notes))
        messages_only_sung.sort(key=lambda msg: msg.time) # ascending time

        sung = []
        cur_sung = {}
        for s in messages_only_sung:
            if s.type == 'note_on':
                cur_sung[s.note] = {
                    'start': s.time,
                    'end': None,
                    'note': s.note,
                    'text': None
                }
            elif s.type == 'note_off' and cur_sung[s.note]:
                cur_sung[s.note]['end'] = s.time
                sung.append(cur_sung[s.note])
                cur_sung[s.note] = None

        sung.sort(key=lambda s: s['start']) # ascending time

        messages_only_overdrive = list(filter(lambda m: m.note == 116, messages_only_notes))
        overdrive_phrases = []
        cur_overdrive_phrase = None
        for phrase in messages_only_overdrive:
            if phrase.type == 'note_on':
                cur_overdrive_phrase = {
                    'start': phrase.time,
                    'note': phrase.note,
                    'end': None,
                    'notes': []
                }
            elif phrase.type == 'note_off' and cur_overdrive_phrase and phrase.note == cur_overdrive_phrase['note']:
                cur_overdrive_phrase['end'] = phrase.time
                overdrive_phrases.append(cur_overdrive_phrase)
                cur_overdrive_phrase = None

        for lyric in messages_only_lyrics:
            # Find the sung note that matches this lyric
            matching_sung = discord.utils.find(lambda s: s['start'] == lyric.time, sung)
            if matching_sung:
                # find if this sung note is within an overdrive phrase
                # by checking if its start time is between the start and end of any overdrive phrase
                matching_sung['text'] = lyric.text
                # # Find the phrase that contains this sung note
                # matching_phrase = discord.utils.find(lambda p: p['start'] <= matching_sung['start'] <= p['end'], phrases)
                # if matching_phrase:
                #     matching_phrase['lyrics'].append(lyric.text)

        for phrase in phrases:
            phrase['notes'] = []
            for s in sung:
                # if it starts after or when the phrase starts
                a = s['start'] >= phrase['start']
                # if it ends before or when the phrase ends
                b = s['end'] <= phrase['end']
                # if it has valid text
                c = s['text'] and len(s['text'].strip()) > 0

                # if it ends before the next phrase starts (if there is a next phrase)
                next_phrase = discord.utils.find(lambda p: p['start'] > phrase['start'], phrases)
                if next_phrase:
                    d = s['end'] < next_phrase['start']
                else:
                    d = True

                if a and b and c and d:
                    phrase['notes'].append(s)

        sentences = []

        section_track = discord.utils.find(lambda t: t.name == 'SECTION', tracks)
        messages = list(_to_abstime(section_track))
        messages_only_meta = list(filter(lambda m: isinstance(m, mido.MetaMessage), messages))
        
        for m in messages_only_meta:
            print(m)
            if hasattr(m, 'text') and m.text and len(m.text.strip()) > 0:
                # insert a new phrase between existing phrases
                # at the time of this section message
                phrases.append({
                    'start': m.time,
                    'note': None,
                    'end': m.time,
                    'notes': [{
                        'start': m.time,
                        'end': m.time,
                        'note': None,
                        'text': f"SPECIAL-{m.text}"
                    }]
                })

        for phrase in phrases:
            is_overdrive_active = discord.utils.find(lambda od: od['start'] <= phrase['start'] < od['end'], overdrive_phrases)

            if is_overdrive_active:
                print(phrase['notes'])
                phrase['notes'].insert(0, {
                    'start': phrase['start'],
                    'end': phrase['start'],
                    'note': 116,
                    'text': '[[OD]]'
                })
                # [].insert()
                hi = ['h', 'i']
                hi.insert(0, '[[OD]]')
                print(hi)
            

        # phrases.sort(key=lambda p: p['start'])
        # Sort phrases: if two phrases have the same start time, the one with any SPECIAL note goes first
        def phrase_sort_key(phrase):
            has_special = any(note['text'] and note['text'].startswith('SPECIAL-') for note in phrase['notes'])
            # SPECIAL phrases should come first if start times are equal
            return (phrase['start'], 0 if has_special else 1)

        phrases.sort(key=phrase_sort_key)

        for phrase in phrases:
            sentence_text = ''
            for note in phrase['notes']:
                note_text = note['text'].strip()

                if note_text.startswith('SPECIAL-'):
                    sentence_text += f"[{note_text.replace('SPECIAL-', '')}]"
                    continue
                if note_text == '[[OD]]':
                    sentence_text += note_text
                    continue
                
                # vocals processing
                should_not_space = '-' in note_text or '=' in note_text or '+' in note_text
                is_last_syllable = note == phrase['notes'][-1]

                # hyphen treatment
                note_text = note_text.replace('-', '')

                # plus treatment
                note_text = note_text.replace('+', '')

                # equals treatment
                note_text = note_text.replace('=', '-')

                # pound treatment
                note_text = note_text.replace('#', '')

                # caret treatment
                note_text = note_text.replace('^', '')

                # asterisk treatment
                note_text = note_text.replace('*', '')

                # percent treatment
                note_text = note_text.replace('%', '')

                # section treatment
                note_text = note_text.replace('§', ' ')

                # dollar sign treatment
                note_text = note_text.replace('$', '')

                # underscore treatment
                note_text = note_text.replace('_', '')

                sentence_text += note_text
                if not should_not_space and not is_last_syllable:
                    sentence_text += ' '

            sentences.append(sentence_text.strip())

        aa = track['track'].get('au')
        rq = requests.get(aa)
        album_art_path = f"cache/lyrics/album_art_{track['track']['sn']}_{midi_slug}.jpg"
        with open(album_art_path, 'wb') as f:
            f.write(rq.content)

        # attempt to get song and artist from track metadata (safe fallbacks)
        song_name = track['track'].get('tt')
        artist_name = track['track'].get('an')

        image = self.draw_lyrics(
            sentences=sentences, 
            font_path="bot/data/Fonts/InterTight-Bold.ttf",
            album_art_path=album_art_path,
            line_spacing=10,
            text_colour=(255, 255, 255),
            song_name=song_name, artist_name=artist_name
        )
            
        # Save the image
        image.save(fname)

        return fname

    def draw_lyrics(self, sentences, 
        album_art_path, 
        font_path, 
        font_size=40, 
        separation=50, 
        line_spacing=5, 
        margin=45,
        num_dominant_colours=8, 
        block_size=180, 
        blur_radius=200,
        text_colour=(0, 0, 0),
        song_name: str = 'Llorarás',
        artist_name: str = 'Oscar D\'León'):
        max_width = 720
        text_area_width = max_width - (2 * margin)
        
        try:
            font = ImageFont.truetype(font_path, font_size)
            font_sections = ImageFont.truetype(font_path, int(font_size / 1.5))
            # Header area settings: reserve space so everything below starts at y=256
            # margin + header_height == 256 -> header_height = 256 - margin
            header_height = max(0, 256 - margin)
            # Larger title/artist fonts for header
            font_title = ImageFont.truetype(font_path, 35)
            font_artist = ImageFont.truetype(font_path, 30)
        except IOError:
            print(f"Error: The font file '{font_path}' was not found.")
            return None

        # --- Text Wrapping and Height Calculation (from draw_lyrics) ---
        wrapped_sentences_data = []
        for sentence in sentences:
            if not sentence.strip():
                continue

            sentence_overdrive = sentence.startswith('[[OD]]')
            sentence = sentence.replace('[[OD]]', '')
            prefix = '' if not sentence_overdrive else '[[OD]]'
            
            wrapped_lines = []
            words = sentence.split(' ')
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                if font.getlength(test_line) <= text_area_width:
                    current_line = test_line
                else:
                    wrapped_lines.append(f'{prefix}{current_line}')
                    current_line = word
            wrapped_lines.append(f'{prefix}{current_line}')
            
            wrapped_sentences_data.append({
                'type': 'sentence',
                'lines': wrapped_lines
            })
        
        # Calculate the total height required for the image based on wrapped text
        y_offset = margin + header_height
        for sentence_data in wrapped_sentences_data:
            if y_offset > margin + header_height: # Add separation before each new sentence (except the very first)
                y_offset += separation
            
            for i, line in enumerate(sentence_data['lines']):
                font_to_use = font
                is_section = False

                if line.startswith('[') and line.endswith(']'):
                    font_to_use = font_sections
                    is_section = True

                line = line.replace('[[OD]]', '')
                line = line.replace('SPECIAL-', '')
                text_bbox = font_to_use.getbbox(line)
                text_height = text_bbox[3] - text_bbox[1]
                y_offset += text_height
                if i < len(sentence_data['lines']) - 1: # Add line_spacing between wrapped lines
                    y_offset += line_spacing

                if is_section:
                    y_offset -= 20
        
        final_image_height = y_offset + margin + 100 # Add bottom margin

        # --- Background Generation (from create_blurred_colour_grid_background) ---
        try:
            album_art = Image.open(album_art_path).convert("RGB")
        except FileNotFoundError:
            print(f"Error: Album art file not found at '{album_art_path}'")
            return None
        except Exception as e:
            print(f"Error opening album art: {e}")
            return None

        # Step 1: Extract Dominant colours from 8 sections of the album art
        small_album_art = album_art.resize((256, 256))
        
        dominant_colours = []
        section_width = small_album_art.width // 4
        section_height = small_album_art.height // 2

        for j in range(2): # 2 rows
            for i in range(4): # 4 columns
                left = i * section_width
                top = j * section_height
                right = left + section_width
                bottom = top + section_height
                
                section = small_album_art.crop((left, top, right, bottom))
                section_colours = list(section.getdata())
                
                if not section_colours:
                    continue

                # Check if the section is mostly dark
                total_r = sum(c[0] for c in section_colours)
                total_g = sum(c[1] for c in section_colours)
                total_b = sum(c[2] for c in section_colours)
                num_pixels = len(section_colours)
                avg_r = total_r / num_pixels
                avg_g = total_g / num_pixels
                avg_b = total_b / num_pixels

                if avg_r < 5 and avg_g < 5 and avg_b < 5:
                    # If section is dark, find the brightest colour
                    brightest_colour = max(section_colours, key=lambda c: sum(c))
                    dominant_colours.append(brightest_colour)
                    continue

                # Group similar colours
                colour_counts = Counter(section_colours)
                sorted_colours = sorted(colour_counts.keys(), key=lambda c: colour_counts[c], reverse=True)
                
                clusters = []
                processed_colours = set()

                for colour in sorted_colours:
                    if colour in processed_colours:
                        continue
                    
                    current_cluster = {'colours': [colour], 'count': colour_counts[colour]}
                    processed_colours.add(colour)

                    # Find similar colours to add to the current cluster
                    for other_colour in sorted_colours:
                        if other_colour in processed_colours:
                            continue
                        
                        # Check if colours are similar (e.g., within a threshold of 10 for each channel)
                        if all(abs(c1 - c2) <= 10 for c1, c2 in zip(colour, other_colour)):
                            current_cluster['colours'].append(other_colour)
                            current_cluster['count'] += colour_counts[other_colour]
                            processed_colours.add(other_colour)
                    
                    clusters.append(current_cluster)

                if clusters:
                    # Find the largest cluster
                    largest_cluster = max(clusters, key=lambda c: c['count'])
                    
                    # Calculate the average colour of the largest cluster
                    avg_r = sum(c[0] for c in largest_cluster['colours']) // len(largest_cluster['colours'])
                    avg_g = sum(c[1] for c in largest_cluster['colours']) // len(largest_cluster['colours'])
                    avg_b = sum(c[2] for c in largest_cluster['colours']) // len(largest_cluster['colours'])
                    
                    dominant_colours.append((avg_r, avg_g, avg_b))

        if not dominant_colours:
            print("Could not extract any dominant colours. Using default colours for background.")
            dominant_colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), 
                                (0, 255, 255), (255, 0, 255), (128, 128, 128), (0, 0, 0)]
            
        dominant_colours = [self.darken_colour(colour, 45) for colour in dominant_colours]
        # print(dominant_colours)

        # Step 2: Generate Grid Pattern (dynamically adjust height)
        grid_width = max_width
        blocks_across = grid_width // block_size
        
        # Calculate blocks_down dynamically to ensure grid_height is at least final_image_height
        blocks_down = (final_image_height // block_size) + (1 if final_image_height % block_size > 0 else 0)
        # Ensure there's at least one 4x2 chunk vertically for randomness if the height is small
        blocks_down = max(blocks_down, 2)
        
        grid_height = blocks_down * block_size

        grid_image = Image.new('RGB', (grid_width, grid_height), 'white')
        draw_grid = ImageDraw.Draw(grid_image) # Use a separate Draw object for the grid

        for y_chunk_start in range(0, blocks_down, 2):
            for x_chunk_start in range(0, blocks_across, 4):
                current_chunk_colours = random.sample(dominant_colours, min(len(dominant_colours), 8))
                colour_index = 0

                for y_offset in range(2):
                    for x_offset in range(4):
                        current_block_x = (x_chunk_start + x_offset) * block_size
                        current_block_y = (y_chunk_start + y_offset) * block_size

                        if current_block_x < grid_width and current_block_y < grid_height:
                            colour_to_use = current_chunk_colours[colour_index % len(current_chunk_colours)]
                            draw_grid.rectangle(
                                [current_block_x, current_block_y, 
                                current_block_x + block_size, current_block_y + block_size],
                                fill=colour_to_use
                            )
                            colour_index += 1

        # Step 3: Apply Gaussian Blur
        blurred_grid = grid_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Crop the blurred grid to the exact dimensions of the final image
        final_background = blurred_grid.crop((0, 0, max_width, final_image_height))
        
        # --- Draw Text on Background ---
        # Use the prepared background as the base image for drawing
        img = final_background.copy() # Make a copy to draw on
        draw_text = ImageDraw.Draw(img) # Use a separate Draw object for text
        # Overlay for semi-transparent text (artist and section headers)
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        # Draw header: album art at (45,30) sized 175x175, then title and artist to the right
        art_x, art_y = 45, 30
        art_size = 175
        try:
            album_art_thumb = album_art.resize((art_size, art_size)).convert("RGBA")
        except Exception:
            album_art_thumb = album_art.copy().resize((art_size, art_size)).convert("RGBA")

        # Create rounded corner mask and apply it
        mask = Image.new('L', (art_size, art_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        radius = 20
        mask_draw.rounded_rectangle([0, 0, art_size, art_size], radius=radius, fill=255)

        rounded_art = Image.new('RGBA', (art_size, art_size))
        rounded_art.paste(album_art_thumb, (0, 0), mask=mask)

        # Paste rounded album art onto the main image using the mask for transparency
        img.paste(rounded_art, (art_x, art_y), mask)

        # text should start 25px right of the album art and must not pass x=675 (right margin 45)
        text_x = art_x + art_size + 25
        right_margin = 45
        header_avail_width = max_width - right_margin - text_x  # enforces max x = 675

        def ellipsize(text, font_obj, max_w):
            if not text:
                return ''
            if font_obj.getlength(text) <= max_w:
                return text
            ell = '...'
            # binary-search like shrink
            low, high = 0, len(text)
            while low < high:
                mid = (low + high) // 2
                candidate = text[:mid].rstrip() + ell
                if font_obj.getlength(candidate) <= max_w:
                    low = mid + 1
                else:
                    high = mid
            candidate = text[:max(0, low-1)].rstrip() + ell
            # final fallback brute force
            if font_obj.getlength(candidate) <= max_w:
                return candidate
            for i in range(len(text), 0, -1):
                t = text[:i].rstrip() + ell
                if font_obj.getlength(t) <= max_w:
                    return t
            return ell

        title = ellipsize(song_name or '', font_title, header_avail_width)
        artist = ellipsize(artist_name or '', font_artist, header_avail_width)

        # Center the two lines vertically relative to the album art's area
        title_bbox = font_title.getbbox(title)
        artist_bbox = font_artist.getbbox(artist)
        title_h = title_bbox[3] - title_bbox[1] if title else 0
        artist_h = artist_bbox[3] - artist_bbox[1] if artist else 0
        spacing = 12
        y_center = art_y + art_size / 2
        total_h = title_h + artist_h + (spacing if title and artist else 0)
        y_start = int(y_center - total_h / 2)

        if title:
            draw_text.text((text_x, y_start), title, font=font_title, fill=text_colour)
        if artist:
            # draw artist semi-transparent (0.8 alpha)
            artist_rgba = (text_colour[0], text_colour[1], text_colour[2], int(0.8 * 255))
            draw_overlay.text((text_x, y_start + title_h + (spacing if title and artist else 0)), artist, font=font_artist, fill=artist_rgba)
        
        # Draw a 1px tall semi-transparent white separator at (45,225) width 675
        sep_x = 45
        sep_y = 235
        sep_w = 675
        sep_colour = (255, 255, 255, int(0.5 * 255))
        draw_overlay.rectangle([(sep_x, sep_y), (sep_w, sep_y)], fill=sep_colour)

        # Start drawing lyrics at absolute y=256 (ensured by header_height calculation)
        y_position = 265
        is_first = True
        for sentence_data in wrapped_sentences_data:
            if y_position > 265:  # Add separation before each new sentence (except the very first)
                y_position += separation

            print(sentence_data['lines'])
                
            for i, line in enumerate(sentence_data['lines']):
                x_position = margin

                font_to_use = font
                is_section = False
                text = line

                is_overdrive = text.startswith('[[OD]]')
                text = text.replace('[[OD]]', '')

                if text.startswith('[') and text.endswith(']'):
                    font_to_use = font_sections
                    text = text[2:-2]
                    text = event_map.get(text.lower(), text)
                    is_section = True

                cur_colour = text_colour
                if is_section:
                    # draw section header semi-transparent via overlay
                    section_rgba = (255, 255, 255, int(0.75 * 255))
                    draw_overlay.text((x_position, y_position), text, font=font_to_use, fill=section_rgba)
                elif is_overdrive:
                    # We'll render gradient text instead of solid colour
                    def draw_gradient_text(base_img, pos, text, font_obj, colour_start, colour_end):
                        # compute bbox and size
                        bbox = font_obj.getbbox(text)
                        x0, y0, x1, y1 = bbox
                        w = max(1, x1 - x0)
                        h = max(1, y1 - y0)

                        # create mask for text
                        mask = Image.new('L', (w, h), 0)
                        md = ImageDraw.Draw(mask)
                        md.text((-x0, -y0), text, font=font_obj, fill=255)

                        # create horizontal gradient
                        grad = Image.new('RGBA', (w, h))
                        gd = ImageDraw.Draw(grad)
                        for ix in range(w):
                            t = ix / (w - 1) if w > 1 else 0
                            r = int(colour_start[0] + (colour_end[0] - colour_start[0]) * t)
                            g = int(colour_start[1] + (colour_end[1] - colour_start[1]) * t)
                            b = int(colour_start[2] + (colour_end[2] - colour_start[2]) * t)
                            gd.line([(ix, 0), (ix, h)], fill=(r, g, b, 255))

                        # paste gradient using text mask
                        px = pos[0] + x0
                        py = pos[1] + y0
                        try:
                            base_img.paste(grad, (px, py), mask)
                        except Exception:
                            base_img.paste(grad, (px, py), mask)
                    # draw gradient from (255,227,153) to (255,215,0)
                    draw_gradient_text(img, (x_position, y_position), text, font_to_use, (255, 227, 153), (255, 215, 0))

                # print(f"Drawing text: '{text}' at position ({x_position}, {y_position})")
                else:
                    if not is_overdrive:
                        draw_text.text((x_position, y_position), text, font=font_to_use, fill=cur_colour)
                text_height = font_to_use.getbbox(text)[3] - font_to_use.getbbox(text)[1]
                # print('Adding line spacing by ' + str(text_height) + ' to ' + str(y_position))
                y_position += text_height
                if is_section:
                    # print('reducing line spacing by 20 to ' + str(y_position))
                    if not is_first:
                        y_position -= 20

                if i < len(sentence_data['lines']) - 1:
                    # print('FFFFFFFFFFFFFFFFF Adding line spacing by ' + str(line_spacing) + ' to ' + str(y_position))
                    y_position += line_spacing

            is_first = False
        
        # Composite overlay onto main image to apply semi-transparent texts
        try:
            composed = Image.alpha_composite(img.convert('RGBA'), overlay)
        except Exception:
            composed = img.convert('RGBA')

        # Draw footer: paste logo at left and right-align festivaltracker.org at right margin
        try:
            footer_top = final_image_height - 100
            logo_path = os.path.join('bot', 'data', 'Logo', 'index.png')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path).convert('RGBA')
                # resize to height 50 keeping aspect ratio
                logo_h = 50
                logo_w = max(1, int(logo.width * (logo_h / logo.height)))
                logo_thumb = logo.resize((logo_w, logo_h))
                logo_x = 45
                logo_y = int(footer_top + (100 - logo_h) / 2)
                composed.paste(logo_thumb, (logo_x, logo_y), logo_thumb)

            # Draw footer text right-aligned with 45px right margin
            draw_footer = ImageDraw.Draw(composed)
            footer_text = 'festivaltracker.org'
            font_wmark = ImageFont.truetype(font_path, 25)
            text_bbox = font_wmark.getbbox(footer_text)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            text_x = max_width - 45 - text_w
            text_y = int(footer_top + (100 - text_h) / 2)
            draw_footer.text((text_x, text_y), footer_text, font=font_wmark, fill=text_colour)
        except Exception:
            pass

        return composed
    
    def darken_colour(self, rgb_tuple, percentage):
        if not (0 <= percentage <= 100):
            raise ValueError("Percentage must be between 0 and 100.")

        darken_factor = 1 - (percentage / 100.0)
        r = int(rgb_tuple[0] * darken_factor)
        g = int(rgb_tuple[1] * darken_factor)
        b = int(rgb_tuple[2] * darken_factor)
        
        # Ensure colour components stay within the valid 0-255 range
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))