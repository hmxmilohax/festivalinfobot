import json
import discord
import re
import mido
from mido.midifiles.tracks import _to_abstime

class LyricsError(Exception):
    pass

class LyricParser:
    def __init__(self, ):
        pass

    def parse(self, midi_path: str, ):
        mid = mido.MidiFile(midi_path, charset='utf-8')
        tracks: list[mido.MidiTrack] = mid.tracks
        pro_vocals_track = discord.utils.find(lambda t: t.name == 'PRO VOCALS', tracks)

        if not pro_vocals_track:
            raise LyricsError('Karaoke not supported')

        messages = list(_to_abstime(pro_vocals_track))
        messages_only_notes = list(filter(lambda m: m.type == 'note_on' or m.type == 'note_off', messages))
        messages_only_phrases = list(filter(lambda m: m.note == 105, messages_only_notes))
        messages_only_phrases.sort(key=lambda msg: msg.note) # ascending notes
        messages_only_phrases.sort(key=lambda msg: msg.time) # ascending time

        sections = []
        phrases = []
        cur_phrase = None
        for phrase in messages_only_phrases:
            if phrase.type == 'note_on' and (not cur_phrase) and phrase.velocity > 0:
                cur_phrase = {
                    'start': phrase.time,
                    'note': phrase.note,
                    'end': None,
                    'notes': [],
                    'is_overdrive': False
                }
            elif (
                phrase.type == 'note_off' or
                # alternative note off in midi 
                (phrase.type == 'note_on' and phrase.velocity == 0)
            ) and cur_phrase and phrase.note == cur_phrase['note']:
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
            if s.type == 'note_on' and s.velocity > 0:
                cur_sung[s.note] = {
                    'start': s.time,
                    'end': None,
                    'note': s.note,
                    'text': None
                    # can't do unpitched here because words are the ones that are; not phrases!
                }
            elif (
                s.type == 'note_off' or
                # alternative note off in midi 
                (s.type == 'note_on' and s.velocity == 0)
            ) and cur_sung.get(s.note):
                cur_sung[s.note]['end'] = s.time
                sung.append(cur_sung[s.note])
                cur_sung[s.note] = None

        sung.sort(key=lambda s: s['start']) # ascending time

        messages_only_overdrive = list(filter(lambda m: m.note == 116, messages_only_notes))
        overdrive_phrases = []

        cur_overdrive_phrase = None
        for phrase in messages_only_overdrive:
            if phrase.type == 'note_on' and phrase.velocity > 0:
                cur_overdrive_phrase = {
                    'start': phrase.time,
                    'note': phrase.note,
                    'end': None
                }
            elif (
                phrase.type == 'note_off' or
                # alternative note off in midi 
                (phrase.type == 'note_on' and phrase.velocity == 0)
            ) and cur_overdrive_phrase and phrase.note == cur_overdrive_phrase['note']:
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


        for phrase in phrases:
            is_overdrive_active = discord.utils.find(lambda od: od['start'] <= phrase['start'] < od['end'], overdrive_phrases)
            if is_overdrive_active:
                phrase['is_overdrive'] = True

        # sort them again just in case
        phrases.sort(key=lambda p: p['start'])

        section_track = discord.utils.find(lambda t: t.name == 'SECTION', tracks)
        messages = list(_to_abstime(section_track))
        messages_only_sub_section_separators = list(filter(lambda m: m.type == 'note_on' and m.velocity > 0 and m.note == 10, messages))
        messages_only_meta = list(filter(lambda m: isinstance(m, mido.MetaMessage), messages))
        
        # section markers
        for m in messages_only_meta:
            if hasattr(m, 'text') and m.text and len(m.text.strip()) > 0:
                # we're gonna find all the sub-section separators within this section
                # DO NOT USE adjusted times here!
                related_sub_sections = []
                next_section = discord.utils.find(lambda s: s.time > m.time, messages_only_meta)
                if next_section:
                    related_sub_sections = list(filter(
                        lambda sep: sep.time >= m.time and sep.time < next_section.time, 
                        messages_only_sub_section_separators))
                else:
                    related_sub_sections = list(filter(
                        lambda sep: sep.time >= m.time, 
                        messages_only_sub_section_separators))

                print(related_sub_sections)

                sub_sections = []

                for ssep in related_sub_sections:
                    related_phrases = []

                    # find all the phrases WITHIN this sub section marker and the next (if there is)
                    adjusted_start = ssep.time - (mid.ticks_per_beat * 1.5)
                    next_ssep = discord.utils.find(lambda s: s.time > ssep.time, related_sub_sections)
                    if next_ssep:
                        adjusted_end = next_ssep.time - (mid.ticks_per_beat * 1.5)
                        related_phrases = list(filter(lambda p: p['start'] >= adjusted_start and p['start'] <= adjusted_end, phrases))
                    else:
                        # if we can't find the next separator we will use the next section instead
                        # find the next section
                        next_section = discord.utils.find(lambda s: s.time > m.time, messages_only_meta)
                        if next_section:
                            adjusted_end = next_section.time - (mid.ticks_per_beat * 1.5)
                            related_phrases = list(filter(lambda p: p['start'] >= adjusted_start and p['start'] <= adjusted_end, phrases))
                        else:
                            # this code should NEVER be ran
                            print('ALERT!!!!!!!')
                            print('ALERT!!!!!!!')
                            print('ALERT!!!!!!!')
                            print('ALERT!!!!!!!')
                            print('ALERT!!!!!!!')
                            related_phrases = list(filter(lambda p: p['start'] >= adjusted_start, phrases))

                    sub_sections.append({
                        'phrases': related_phrases,
                        'index': related_sub_sections.index(ssep)
                    })

                sections.append({
                    'marker': m.text,
                    'sub_sections': sub_sections
                })

        with open('lyricstest.json', 'w', encoding='utf-8') as f:
            json.dump(sections, f, indent=4)

        sentences = []
        for section in sections:
            marker_name = re.search(r"\[(.*?)\]", section['marker']).group(1)

            for sub_section in section['sub_sections']:
                letter = ['A', 'B', 'C', 'D', 'E', 'F']
                sentences.append(f"\n\n{marker_name} {letter[sub_section['index']]}\n")

                for phrase in sub_section['phrases']:
                    sentence_text = ''
                    if phrase['is_overdrive']:
                        sentence_text += '\n\nOverdrive Phrase\n'

                    for note in phrase['notes']:
                        note_text = note['text'].strip()
                
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
                        note_text = note_text.replace('#', '<unpitched>')

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

        with open('lyricsout.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(sentences))