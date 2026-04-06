import io
import os
from typing import Literal

import discord
import requests
from bot import constants
import mido
from mido.midifiles.tracks import _to_abstime
import PIL
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from collections import Counter
import random

import textwrap

from bot.tools import midi
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

    async def handle_interaction(self, interaction: discord.Interaction, query: str, pt: Literal['No', 'Yes', 'Yes (Include Overdrive)'], should_be_ephemeral: bool = False):
        await interaction.response.defer(thinking=True, ephemeral=should_be_ephemeral)

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
            if pt == 'No':
                fname = await self.load_lyrics(track)
                await interaction.edit_original_response(attachments=[discord.File(fname)])
            else:
                content = await self.load_lyrics(track, plain_text=True)
                str_list = content.split('\n')
                final_list = []
                for line in str_list:
                    if line.startswith('[[OD]]'):
                        if pt == 'Yes (Include Overdrive)':
                            line = '**' + line.replace('[[OD]]', '') + '**'
                        else:
                            line = line.replace('[[OD]]', '')
                    if '[[' in line and ']]' in line:
                        section_name = line.replace('[[', '').replace(']]', '')
                        # remove symbols
                        section_name = ''.join(filter(str.isalnum, section_name))
                        real_name = event_map.get(section_name.lower(), section_name)
                        line = f"\n[{real_name}]"
                    final_list.append(line)

                final_list.append("\n- Made by Festival Tracker")
                content = '\n'.join(final_list)

                # remove any new lines at the start of the content
                content = content.lstrip('\n')

                await interaction.edit_original_response(content=f"**{track['track']['tt']}** - *{track['track']['an']}*", attachments=[
                    discord.File(io.StringIO(content), filename=f"{track['track']['sn']}_lyrics_festival_tracker.txt")
                ])
        except LyricsError as e:
            await interaction.edit_original_response(embed=constants.common_error_embed(str(e)))

    async def load_lyrics(self, track, plain_text: bool = False) -> str:
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
                if cur_sung.get(s.note): 
                    # this note is already active
                    # cause: midi errors on festival midis
                    # note off (0x80) events in midis are saved as note on (0x90)
                    # notes:
                    # - this will probably never be fixed server side
                    # accounting for it is neccessary
                    cur_sung[s.note]['end'] = s.time
                    sung.append(cur_sung[s.note])
                    cur_sung[s.note] = None

                    # do not bother creating a new note
                    # I SPENT ONE HOUR DEBUGGING THIS
                    continue

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
                # hi = ['h', 'i']
                # hi.insert(0, '[[OD]]')
                # print(hi)
            

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

        if not plain_text:
            image = self.draw_lyrics(
                sentences=sentences, 
                font_path="bot/data/Fonts/InterTight-Bold.ttf",
                album_art_path=album_art_path,
                line_spacing=10,
                text_colour=(255, 255, 255),
                song_name=song_name, artist_name=artist_name
            )
        else:
            return '\n'.join(sentences)
            
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
        song_name: str = 'Por El Asterisco',
        artist_name: str = 'Faraon Love Shady'):
        column_width = 720
        text_area_width = column_width - (2 * margin)
        fixed_height = 1920
        footer_height = 50
        
        try:
            font = ImageFont.truetype(font_path, font_size)
            font_sections = ImageFont.truetype(font_path, int(font_size / 1.5))
            header_height = max(0, 256 - margin)
            font_title = ImageFont.truetype(font_path, 35)
            font_artist = ImageFont.truetype(font_path, 30)
        except IOError:
            print(f"Error: The font file '{font_path}' was not found.")
            return None

        # Text Wrapping
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

        # calculate the rendered height of a sentence
        def calc_sentence_height(sentence_data, is_first=False):
            h = 0
            for i, line in enumerate(sentence_data['lines']):
                font_to_use = font
                is_section = False
                text = line
                text = text.replace('[[OD]]', '')

                if text.startswith('[') and text.endswith(']'):
                    font_to_use = font_sections
                    text = text[2:-2]
                    text = event_map.get(text.lower(), text)
                    is_section = True

                text_bbox = font_to_use.getbbox(text)
                text_height = text_bbox[3] - text_bbox[1]
                h += text_height
                if i < len(sentence_data['lines']) - 1:
                    h += line_spacing
                if is_section and not is_first:
                    h -= 20
            return h

        def is_section_sentence(sentence_data):
            """Check if this sentence is a section marker (e.g. [[Chorus]])"""
            if len(sentence_data['lines']) == 0:
                return False
            clean = sentence_data['lines'][0].replace('[[OD]]', '')
            return clean.startswith('[') and clean.endswith(']')

        # --- Column Pagination ---
        # Header spans full width at top; footer spans full width at bottom.
        # All columns share the same vertical lyrics zone.
        column_lyrics_start = 265  # after header area
        column_lyrics_bottom = fixed_height - (margin / 2) - footer_height  # 1280 - 45 - 100 = 1135

        # Each column is a list of indices into wrapped_sentences_data
        columns = [[]]
        current_y = column_lyrics_start
        current_col = 0
        just_moved_section = False

        for idx, sentence_data in enumerate(wrapped_sentences_data):
            is_first_in_col = len(columns[current_col]) == 0
            sentence_h = calc_sentence_height(sentence_data, is_first=is_first_in_col)
            total_needed = sentence_h
            if not is_first_in_col:
                total_needed += separation

            # Would this sentence overflow the column?
            if current_y + total_needed > column_lyrics_bottom and not is_first_in_col:
                # Check if the last sentence in current column is a section marker
                # and we haven't just moved one (prevent infinite loops)
                if (not just_moved_section and columns[current_col] and
                        is_section_sentence(wrapped_sentences_data[columns[current_col][-1]])):
                    # Move section marker to the new column so it stays with following content
                    moved_idx = columns[current_col].pop()
                    current_col += 1
                    columns.append([moved_idx])
                    moved_h = calc_sentence_height(wrapped_sentences_data[moved_idx], is_first=True)
                    current_y = column_lyrics_start + moved_h
                    just_moved_section = True
                else:
                    current_col += 1
                    columns.append([])
                    current_y = column_lyrics_start
                    just_moved_section = False

                # Recalculate for the (possibly non-empty) new column
                is_first_in_col = len(columns[current_col]) == 0
                sentence_h = calc_sentence_height(sentence_data, is_first=is_first_in_col)
                total_needed = sentence_h
                if not is_first_in_col:
                    total_needed += separation
            else:
                just_moved_section = False

            columns[current_col].append(idx)
            current_y += total_needed

        num_columns = len(columns)
        total_width = num_columns * column_width

        # Background Generation
        try:
            album_art = Image.open(album_art_path).convert("RGB")
        except FileNotFoundError:
            print(f"Error: Album art file not found at '{album_art_path}'")
            return None
        except Exception as e:
            print(f"Error opening album art: {e}")
            return None

        # Extract dominant colours from 8 sections of the album art
        small_album_art = album_art.resize((256, 256))
        
        dominant_colours = []
        section_width = small_album_art.width // 4
        section_height_img = small_album_art.height // 2

        for j in range(2):
            for i in range(4):
                left = i * section_width
                top = j * section_height_img
                right = left + section_width
                bottom = top + section_height_img
                
                section = small_album_art.crop((left, top, right, bottom))
                section_colours = list(section.getdata())
                
                if not section_colours:
                    continue

                total_r = sum(c[0] for c in section_colours)
                total_g = sum(c[1] for c in section_colours)
                total_b = sum(c[2] for c in section_colours)
                num_pixels = len(section_colours)
                avg_r = total_r / num_pixels
                avg_g = total_g / num_pixels
                avg_b = total_b / num_pixels

                if avg_r < 5 and avg_g < 5 and avg_b < 5:
                    brightest_colour = max(section_colours, key=lambda c: sum(c))
                    dominant_colours.append(brightest_colour)
                    continue

                colour_counts = Counter(section_colours)
                sorted_colours = sorted(colour_counts.keys(), key=lambda c: colour_counts[c], reverse=True)
                
                clusters = []
                processed_colours = set()

                for colour in sorted_colours:
                    if colour in processed_colours:
                        continue
                    
                    current_cluster = {'colours': [colour], 'count': colour_counts[colour]}
                    processed_colours.add(colour)

                    for other_colour in sorted_colours:
                        if other_colour in processed_colours:
                            continue
                        
                        if all(abs(c1 - c2) <= 10 for c1, c2 in zip(colour, other_colour)):
                            current_cluster['colours'].append(other_colour)
                            current_cluster['count'] += colour_counts[other_colour]
                            processed_colours.add(other_colour)
                    
                    clusters.append(current_cluster)

                if clusters:
                    largest_cluster = max(clusters, key=lambda c: c['count'])
                    
                    avg_r = sum(c[0] for c in largest_cluster['colours']) // len(largest_cluster['colours'])
                    avg_g = sum(c[1] for c in largest_cluster['colours']) // len(largest_cluster['colours'])
                    avg_b = sum(c[2] for c in largest_cluster['colours']) // len(largest_cluster['colours'])
                    
                    dominant_colours.append((avg_r, avg_g, avg_b))

        if not dominant_colours:
            print("Could not extract any dominant colours. Using default colours for background.")
            dominant_colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), 
                                (0, 255, 255), (255, 0, 255), (128, 128, 128), (0, 0, 0)]
            
        dominant_colours = [self.darken_colour(colour, 45) for colour in dominant_colours]

        # Generate grid at full image dimensions
        grid_w = total_width
        blocks_across = grid_w // block_size + (1 if grid_w % block_size > 0 else 0)
        blocks_down = fixed_height // block_size + (1 if fixed_height % block_size > 0 else 0)
        blocks_down = max(blocks_down, 2)
        
        grid_pixel_w = blocks_across * block_size
        grid_pixel_h = blocks_down * block_size

        grid_image = Image.new('RGB', (grid_pixel_w, grid_pixel_h), 'white')
        draw_grid = ImageDraw.Draw(grid_image)

        for y_chunk_start in range(0, blocks_down, 2):
            for x_chunk_start in range(0, blocks_across, 4):
                current_chunk_colours = random.sample(dominant_colours, min(len(dominant_colours), 8))
                colour_index = 0

                for y_off in range(2):
                    for x_off in range(4):
                        current_block_x = (x_chunk_start + x_off) * block_size
                        current_block_y = (y_chunk_start + y_off) * block_size

                        if current_block_x < grid_pixel_w and current_block_y < grid_pixel_h:
                            colour_to_use = current_chunk_colours[colour_index % len(current_chunk_colours)]
                            draw_grid.rectangle(
                                [current_block_x, current_block_y, 
                                current_block_x + block_size, current_block_y + block_size],
                                fill=colour_to_use
                            )
                            colour_index += 1

        blurred_grid = grid_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        final_background = blurred_grid.crop((0, 0, total_width, fixed_height))
        
        # Draw on the image
        img = final_background.copy()
        draw_text = ImageDraw.Draw(img)
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        # Draw Header
        art_x, art_y = 45, 30
        art_size = 175
        try:
            album_art_thumb = album_art.resize((art_size, art_size)).convert("RGBA")
        except Exception:
            album_art_thumb = album_art.copy().resize((art_size, art_size)).convert("RGBA")

        mask = Image.new('L', (art_size, art_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        radius = 20
        mask_draw.rounded_rectangle([0, 0, art_size, art_size], radius=radius, fill=255)

        rounded_art = Image.new('RGBA', (art_size, art_size))
        rounded_art.paste(album_art_thumb, (0, 0), mask=mask)

        img.paste(rounded_art, (art_x, art_y), mask)

        text_x_header = art_x + art_size + 25
        right_margin = 45
        header_avail_width = total_width - right_margin - text_x_header

        def ellipsize(text, font_obj, max_w):
            if not text:
                return ''
            if font_obj.getlength(text) <= max_w:
                return text
            ell = '...'
            low, high = 0, len(text)
            while low < high:
                mid = (low + high) // 2
                candidate = text[:mid].rstrip() + ell
                if font_obj.getlength(candidate) <= max_w:
                    low = mid + 1
                else:
                    high = mid
            candidate = text[:max(0, low-1)].rstrip() + ell
            if font_obj.getlength(candidate) <= max_w:
                return candidate
            for i in range(len(text), 0, -1):
                t = text[:i].rstrip() + ell
                if font_obj.getlength(t) <= max_w:
                    return t
            return ell

        title = ellipsize(song_name or '', font_title, header_avail_width)
        artist = ellipsize(artist_name or '', font_artist, header_avail_width)

        title_bbox = font_title.getbbox(title)
        artist_bbox = font_artist.getbbox(artist)
        title_h = title_bbox[3] - title_bbox[1] if title else 0
        artist_h = artist_bbox[3] - artist_bbox[1] if artist else 0
        spacing = 12
        y_center = art_y + art_size / 2
        total_h = title_h + artist_h + (spacing if title and artist else 0)
        y_start = int(y_center - total_h / 2)

        if title:
            draw_text.text((text_x_header, y_start), title, font=font_title, fill=text_colour)
        if artist:
            artist_rgba = (text_colour[0], text_colour[1], text_colour[2], int(0.8 * 255))
            draw_overlay.text((text_x_header, y_start + title_h + (spacing if title and artist else 0)), artist, font=font_artist, fill=artist_rgba)
        
        # Horizontal separator
        sep_y = 235
        sep_colour = (255, 255, 255, int(0.5 * 255))
        draw_overlay.rectangle([(margin, sep_y), (total_width - margin, sep_y)], fill=sep_colour)

        # Draw separators between columns
        col_sep_colour = (255, 255, 255, int(0.15 * 255))
        for col_idx in range(1, num_columns):
            sep_x = col_idx * column_width
            draw_overlay.rectangle([(sep_x, header_height + margin), (sep_x, fixed_height - margin)], fill=col_sep_colour)

        # Draw Lyrics per Column
        def draw_gradient_text(base_img, pos, text, font_obj, colour_start, colour_end):
            bbox = font_obj.getbbox(text)
            x0, y0, x1, y1 = bbox
            w = max(1, x1 - x0)
            h = max(1, y1 - y0)

            txt_mask = Image.new('L', (w, h), 0)
            md = ImageDraw.Draw(txt_mask)
            md.text((-x0, -y0), text, font=font_obj, fill=255)

            grad = Image.new('RGBA', (w, h))
            gd = ImageDraw.Draw(grad)
            for ix in range(w):
                t = ix / (w - 1) if w > 1 else 0
                r = int(colour_start[0] + (colour_end[0] - colour_start[0]) * t)
                g = int(colour_start[1] + (colour_end[1] - colour_start[1]) * t)
                b = int(colour_start[2] + (colour_end[2] - colour_start[2]) * t)
                gd.line([(ix, 0), (ix, h)], fill=(r, g, b, 255))

            px = pos[0] + x0
            py = pos[1] + y0
            try:
                base_img.paste(grad, (px, py), txt_mask)
            except Exception:
                base_img.paste(grad, (px, py), txt_mask)

        for col_idx, col_sentence_indices in enumerate(columns):
            col_x_offset = col_idx * column_width
            y_position = column_lyrics_start
            is_first_in_col = True

            for sent_idx in col_sentence_indices:
                sentence_data = wrapped_sentences_data[sent_idx]

                if not is_first_in_col:
                    y_position += separation

                for i, line in enumerate(sentence_data['lines']):
                    x_position = col_x_offset + margin

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
                        section_rgba = (255, 255, 255, int(0.75 * 255))
                        draw_overlay.text((x_position, y_position), text, font=font_to_use, fill=section_rgba)
                    elif is_overdrive:
                        draw_gradient_text(img, (x_position, y_position), text, font_to_use, (255, 227, 153), (255, 215, 0))
                    else:
                        draw_text.text((x_position, y_position), text, font=font_to_use, fill=cur_colour)

                    text_height = font_to_use.getbbox(text)[3] - font_to_use.getbbox(text)[1]
                    y_position += text_height
                    if is_section:
                        if not is_first_in_col:
                            y_position -= 20

                    if i < len(sentence_data['lines']) - 1:
                        y_position += line_spacing

                is_first_in_col = False
        
        # Composite overlay onto main image
        try:
            composed = Image.alpha_composite(img.convert('RGBA'), overlay)
        except Exception:
            composed = img.convert('RGBA')

        # Draw Footer
        try:
            footer_top = fixed_height - footer_height
            draw_footer = ImageDraw.Draw(composed)
            footer_text = 'festivaltracker.org'
            font_wmark = ImageFont.truetype(font_path, 25)
            ft_bbox = font_wmark.getbbox(footer_text)
            ft_w = ft_bbox[2] - ft_bbox[0]
            ft_h = ft_bbox[3] - ft_bbox[1]

            # Text at far right with margin
            ftxt_x = total_width - margin - ft_w
            ftxt_y = int(footer_top)
            draw_footer.text((ftxt_x, ftxt_y), footer_text, font=font_wmark, fill=(255, 255, 255, int(0.75 * 255)))

            # Logo to the left of the text
            # logo_path = os.path.join('bot', 'data', 'Logo', 'Title.png')
            # if os.path.exists(logo_path):
            #     logo = Image.open(logo_path).convert('RGBA')
            #     logo_h = 50
            #     logo_w = max(1, int(logo.width * (logo_h / logo.height)))
            #     logo_thumb = logo.resize((logo_w, logo_h))
            #     logo_x = ftxt_x - logo_w - 15
            #     logo_y = int(footer_top + (footer_height - logo_h) / 2)
            #     composed.paste(logo_thumb, (logo_x, logo_y), logo_thumb)
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