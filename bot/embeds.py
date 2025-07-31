from datetime import datetime
import json
import logging
import subprocess
import discord
import numpy
import requests
from bot.midi import MidiArchiveTools

from bot import constants
    
class StatsCommandEmbedHandler():
    def __init__(self) -> None:
        pass

    def compare_commit_hashes(self, local_hash, remote_hash):
        if local_hash == remote_hash:
            return "Up-to-date"
        else:
            return "Out of sync"

    def iso_to_unix_timestamp(self, iso_time_str):
        try:
            dt = datetime.fromisoformat(iso_time_str.replace('Z', '+00:00'))
            return dt
        except ValueError:
            return None
        
    def get_remote_url(self):
        return subprocess.check_output(['git', 'config', '--get', 'remote.origin.url']).strip().decode('utf-8')

    # Convert uptime to a more human-readable format
    def format_uptime(self, seconds):
        uptime_str = []
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            uptime_str.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            uptime_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 or not uptime_str:
            uptime_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        return ', '.join(uptime_str)

    def fetch_latest_github_commit_hash(self):
        repo_url = "https://api.github.com/repos/hmxmilohax/festivalinfobot/commits"
        logging.debug(f'[GET] {repo_url}')
        response = requests.get(repo_url)
        if response.status_code == 200:
            latest_commit = response.json()[0]
            commit_hash = latest_commit['sha']
            commit_time = latest_commit['commit']['author']['date']
            return commit_hash, commit_time
        return "Unknown", "Unknown"
    
    def get_local_commit_hash(self):
        try:
            # Run git command to get the latest commit hash
            branch_name = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode('utf-8')
            commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode('utf-8')
            dirtyness = subprocess.check_output(['git', 'status', '--porcelain']).strip().decode('utf-8')
            return dirtyness, branch_name, commit_hash
        except Exception as e:
            logging.error(f"Error getting local commit info", exc_info=e)
            return "Unknown", "Unknown", "Unknown"
        
class SearchEmbedHandler:
    def __init__(self) -> None:
        pass
    
    def generate_track_embed(self, track_data, is_new=False, is_removed=False, is_random=False):
        track = track_data['track']
        if is_new:
            title = f"New Track Added:"
        elif is_removed:
            title = f"Track Removed:"
        elif is_random:
            title = f"Your Random Jam Track:"
        else:
            title = ""

        embed = discord.Embed(title=title, description=f"**{track['tt']}** - *{track['an']}*", color=0x8927A1)
        embed.add_field(name="\n", value="", inline=False)

        # ----------

        embed.add_field(name="Release Year", value=track.get('ry', 'Unknown'), inline=True)

        album = track.get('ab', 'N/A')
        embed.add_field(name="Album", value=album, inline=True)
        
        genre = track.get('ge', ['N/A'])
        embed.add_field(name="Genre", value=", ".join(genre), inline=True)

        # ----------

        _key = track.get('mk', 'Unknown') 
        mode = track.get('mm', 'Unknown')

        key = discord.utils.find(lambda v: v.value.code == _key, constants.KeyTypes.__members__.values()).value.english
        key = f"{key} {mode}"

        duration = track.get('dn', 0)
        embed.add_field(name="Duration", value=f"{duration // 60}m {duration % 60}s", inline=True)
        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="BPM", value=str(track.get('mt', 'Unknown')), inline=True)

        # ----------

        embed.add_field(name="Shortname & ID", value=track['sn'] + ' [' + track.get('ti').replace('SparksSong:sid_placeholder_', '') + ']', inline=True)
        embed.add_field(name="Jam Loop Code", value=track.get('jc', 'N/A'), inline=True)
        embed.add_field(name="ISRC", value=track.get('isrc', 'N/A'))
        
        # ----------
        
        # Difficulty bars
        vocals_diff = track['in'].get('vl', -1)
        guitar_diff = track['in'].get('gr', -1)
        bass_diff = track['in'].get('ba', -1)
        drums_diff = track['in'].get('ds', -1)
        # pro_vocals_diff = track['in'].get('pv', 0)
        pro_guitar_diff = track['in'].get('pg', -1)
        pro_bass_diff = track['in'].get('pb', -1)
        pro_drums_diff = track['in'].get('pd', -1)
        band_diff = track['in'].get('bd', -1) # apparently bd is placeholder for pro vocals

        midi_tool = MidiArchiveTools()
        user_id = track.get('ry', 2025)
        session_hash = constants.generate_session_hash(user_id, track['sn'])
        midi_file = midi_tool.save_chart(track['mu'])
        has_pro_vocals = b'PRO VOCALS' in open(midi_file, 'rb').read()

        # ----------

        last_modified = constants.format_date(track_data['lastModified'])
        embed.add_field(name="Last Modified", value=last_modified, inline=True)
        embed.add_field(name="Active Date", value=constants.format_date(track_data.get('_activeDate')), inline=True)
        
        new_until = track.get('nu')
        if new_until == None:
            new_until = 'N/A'
        else:
            new_until = constants.format_date(new_until)
            
        embed.add_field(name="New Until", value=new_until, inline=True)

        # ----------

        gameplay_tags = track.get('gt')
        if gameplay_tags != None:
            embed.add_field(name="Gameplay Tags", value=', '.join(gameplay_tags), inline=True)

        pro_vocals_supported_indicator = '✓' if has_pro_vocals else '✗'

        # average diff
        difficulties_array = [
            vocals_diff, guitar_diff,
            bass_diff, drums_diff,
            pro_guitar_diff, pro_bass_diff, 
            pro_drums_diff
        ]
        if band_diff != -1:
            difficulties_array.append(band_diff)

        avg_diff = numpy.average(difficulties_array)+1
        med_diff = numpy.median(difficulties_array)+1

        # embed.add_field(name="Avg. Difficulty", value=f'{round(avg_diff, 2)}/7 (`{constants.generate_difficulty_bar(int(avg_diff - 1))}`)')
        # embed.add_field(name="Med. Difficulty", value=f'{med_diff}/7 (`{constants.generate_difficulty_bar(int(med_diff - 1))}`)')

        m = round(med_diff, 1)
        a = round(avg_diff, 1)

        cur_pad = -1
        for d in [vocals_diff, guitar_diff,
            bass_diff, drums_diff]:
            if d > cur_pad:
                cur_pad = d
        
        N = cur_pad + 1

        cur_pro = -1
        for d in difficulties_array[4:]:
            if d > cur_pro:
                cur_pro = d
        
        P = cur_pro + 1

        difficulties = (
            f"Lead:       {constants.generate_difficulty_bar(guitar_diff)}\n"
            f"Bass:       {constants.generate_difficulty_bar(bass_diff)}\n"
            f"Drums:      {constants.generate_difficulty_bar(drums_diff)}\n"
            f"Vocals:     {constants.generate_difficulty_bar(vocals_diff)}\n"
            f"Pro Lead:   {constants.generate_difficulty_bar(pro_guitar_diff)}\n"
            f"Pro Bass:   {constants.generate_difficulty_bar(pro_bass_diff)}\n"
            f"Pro Drums:  {constants.generate_difficulty_bar(pro_drums_diff)}\n"
            f"Pro Vocals: {constants.generate_difficulty_bar(band_diff)} {pro_vocals_supported_indicator}\n"
            f"    -----------    \n"
            f"Max Pad:  {N} {constants.generate_difficulty_bar(cur_pad)}\n"
            f"Max Pro:  {P} {constants.generate_difficulty_bar(cur_pro)}\n"
            f"Med.:   {m} {constants.generate_difficulty_bar(int(med_diff - 1))}\n"
            f"Avg.:   {a} {constants.generate_difficulty_bar(int(avg_diff - 1))}"
        )

        embed.add_field(name="Difficulties", value=f"```{difficulties}```", inline=False)

        # Add Song Rating
        rating = track.get('ar', 'N/A')
        if rating == 'T':
            rating_description = 'Teen'
        elif rating == 'E':
            rating_description = 'Everyone'
        else:
            rating_description = rating

        embed.set_footer(text=f"[ESRB] {rating_description} · Festival Tracker", icon_url=f"https://www.globalratings.com/images/ESRB_{rating}_68.png")
        
        embed.set_thumbnail(url=track['au'])
        
        return embed
    
    def compare_qi_fields(self, old_qi, new_qi):
        try:
            old_qi_data = json.loads(old_qi)
            new_qi_data = json.loads(new_qi)
        except json.JSONDecodeError:
            return None

        embed_fields = []

        for field in ['sid', 'pid', 'stereoId', 'instrumentalId', 'title']:
            if old_qi_data.get(field) != new_qi_data.get(field):
                embed_fields.append(
                    f"**{field}** changed\n"
                    f"```Old: {old_qi_data.get(field, '[N/A]')}\nNew: {new_qi_data.get(field, '[N/A]')}```"
                )

        if 'tracks' in old_qi_data and 'tracks' in new_qi_data:
            old_tracks = old_qi_data['tracks']
            new_tracks = new_qi_data['tracks']
            if len(old_tracks) == len(new_tracks):
                for i, track in enumerate(old_tracks):
                    for track_field in ['part', 'channels', 'vols']:
                        if track.get(track_field) != new_tracks[i].get(track_field):
                            embed_fields.append(
                                f"Track {i+1} **{track_field}** changed\n"
                                f"```Old: {track.get(track_field, '[N/A]')}\nNew: {new_tracks[i].get(track_field, '[N/A]')}```"
                            )
            else:
                embed_fields.append("Track length changed in 'tracks' field")

        if 'preview' in old_qi_data and 'preview' in new_qi_data:
            if old_qi_data['preview'].get('starttime') != new_qi_data['preview'].get('starttime'):
                embed_fields.append(
                    "**preview.starttime** changed\n"
                    f"```Old: {old_qi_data['preview'].get('starttime', '[N/A]')}\nNew: {new_qi_data['preview'].get('starttime', '[N/A]')}```"
                )

        return embed_fields
    
    def generate_modified_track_embed(self, old, new):
        old_track_data = old['track']
        new_track_data = new['track']
        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"Track Modified:\n**{new_track_data['tt']}** - *{new_track_data['an']}*")
                , accessory=discord.ui.Thumbnail(new_track_data['au'])
            ), accent_colour=0x8927A1
        )
        container._view = discord.ui.LayoutView() # STUPID HACK TO MAKE IT WORK

        simple_comparisons = constants.SIMPLE_COMPARISONS

        difficulty_comparisons = constants.DIFFICULTY_COMPARISONS

        extra_comparisons = constants.EXTRA_COMPARISONS

        for value, name in simple_comparisons.items():
            if old_track_data.get(value, '[N/A]') != new_track_data.get(value, '[N/A]'):
                container.add_item(
                    discord.ui.TextDisplay(f"{name} changed"),
                )
                container.add_item(
                    discord.ui.TextDisplay(
                        f"```Old: \"{old_track_data.get(value, '[N/A]')}\"\nNew: \"{new_track_data.get(value, '[N/A]')}\"```"
                    )
                )

        for value, name in difficulty_comparisons.items():
            if old_track_data['in'].get(value, 0) != new_track_data['in'].get(value, 0):
                container.add_item(
                    discord.ui.TextDisplay(f"{name} difficulty changed"),
                )
                container.add_item(
                    discord.ui.TextDisplay(f"```Old: \"{constants.generate_difficulty_bar(old_track_data['in'].get(value, 0))}\"\nNew: \"{constants.generate_difficulty_bar(new_track_data['in'].get(value, 0))}\"```")
                )


        for key in new_track_data['in'].keys():
            if key not in difficulty_comparisons.keys() and key != '_type':
                container.add_item(
                    discord.ui.TextDisplay(f"{key} (*Mismatched Difficulty*)")
                )
                container.add_item(
                    discord.ui.TextDisplay(f"```Found: {constants.generate_difficulty_bar(new_track_data['in'][key])}```")
                )

        if old.get('lastModified') != new.get('lastModified'):
            old_date = 'N/A'
            if old.get('lastModified', None) != None:
                date = old.get('lastModified')
                print(date)
                old_date = constants.format_date(date)

            new_date = 'N/A'
            if new.get('lastModified', None) != None:
                date = new.get('lastModified')
                print(date)
                new_date = constants.format_date(date)

            container.add_item(
                discord.ui.TextDisplay("Last Modified Date changed")
            )
            container.add_item(
                discord.ui.TextDisplay(f"{old_date} > {new_date}")
            )

        qi_comparisons = self.compare_qi_fields(old_track_data.get('qi', ''), new_track_data.get('qi', ''))
        if qi_comparisons:
            for field in qi_comparisons:
                container.add_item(
                    discord.ui.TextDisplay("QI Field Update")
                )
                container.add_item(
                    discord.ui.TextDisplay(field)
                )

        for value, name in extra_comparisons.items():
            if old.get(value) != new.get(value):
                container.add_item(
                    discord.ui.TextDisplay(f"{name} changed")
                )
                container.add_item(
                    discord.ui.TextDisplay(f"```Old: \"{old.get(value, '[N/A]')}\"\nNew: \"{new.get(value, '[N/A]')}\"```")
                )

        return container
