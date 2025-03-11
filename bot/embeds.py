from datetime import datetime
import json
import logging
import subprocess
import discord
import numpy
import requests

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
            title = f"New Track Added:\n{track['tt']}"
        elif is_removed:
            title = f"Track Removed:\n{track['tt']}"
        elif is_random:
            title = f"Your Random Jam Track:\n{track['tt']}"
        else:
            title = f"{track['tt']}"
        placeholder_id = track.get('ti', 'sid_placeholder_00').split('_')[-1].zfill(2) 
        embed = discord.Embed(title="", description=f"**{title}** - *{track['an']}*", color=0x8927A1)

        embed.add_field(name="\n", value="", inline=False)
        embed.add_field(name="Release Year", value=track.get('ry', 'Unknown'), inline=True)

        key = track.get('mk', 'Unknown') 
        mode = track.get('mm', 'Unknown')

        key = f"{key} {mode}"

        embed.add_field(name="Key", value=key, inline=True)
        embed.add_field(name="BPM", value=str(track.get('mt', 'Unknown')), inline=True)


        embed.add_field(name="Album", value=track.get('ab', 'N/A'), inline=True)
        embed.add_field(name="Genre", value=", ".join(track.get('ge', ['N/A'])), inline=True)    

        duration = track.get('dn', 0)
        embed.add_field(name="Duration", value=f"{duration // 60}m {duration % 60}s", inline=True)
        embed.add_field(name="Shortname", value=track['sn'], inline=True)
        embed.add_field(name="Song ID", value=f"{placeholder_id}", inline=True)

        # Add Last Modified field if it exists and format it to be more human-readable
        if 'lastModified' in track_data:
            human_readable_date = constants.format_date(track_data['lastModified'])
            embed.add_field(name="Last Modified", value=human_readable_date, inline=True)
        
        # Add Song Rating
        rating = track.get('ar', 'N/A')
        if rating == 'T':
            rating_description = 'Teen'
        elif rating == 'E':
            rating_description = 'Everyone'
        else:
            rating_description = rating
        
        embed.set_footer(text="Festival Tracker", icon_url=f"https://www.globalratings.com/images/ESRB_{rating}_68.png")

        embed.add_field(name="Rating", value=rating_description, inline=True)
        
        # Difficulty bars
        vocals_diff = track['in'].get('vl', 0)
        guitar_diff = track['in'].get('gr', 0)
        bass_diff = track['in'].get('ba', 0)
        drums_diff = track['in'].get('ds', 0)
        # pro_vocals_diff = track['in'].get('pv', 0)
        pro_guitar_diff = track['in'].get('pg', 0)
        pro_bass_diff = track['in'].get('pb', 0)
        pro_drums_diff = track['in'].get('pd', 0)

        # average diff
        avg_diff = numpy.average([
            vocals_diff, guitar_diff,
            bass_diff, drums_diff,
            pro_guitar_diff, pro_bass_diff, 
            pro_drums_diff
        ])+1

        embed.add_field(name="Creative Code", value=track.get('jc', 'N/A'))
        embed.add_field(name="Avg. Difficulty", value=f'{round(avg_diff, 1)}/7')
        embed.add_field(name="Released", value=constants.format_date(track_data.get('_activeDate')))
        embed.add_field(name="ISRC", value=track.get('isrc', 'N/A'))

        difficulties = (
            f"Lead:      {constants.generate_difficulty_bar(guitar_diff)}\n"
            f"Bass:      {constants.generate_difficulty_bar(bass_diff)}\n"
            f"Drums:     {constants.generate_difficulty_bar(drums_diff)}\n"
            f"Vocals:    {constants.generate_difficulty_bar(vocals_diff)}\n"
            f"Pro Lead:  {constants.generate_difficulty_bar(pro_guitar_diff)}\n"
            f"Pro Bass:  {constants.generate_difficulty_bar(pro_bass_diff)}\n"
            f"Pro Drums: {constants.generate_difficulty_bar(pro_drums_diff)}"
        )

        embed.add_field(name="Difficulties", value=f"```{difficulties}```", inline=False)
        
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
        title = f"Track Modified:\n{new_track_data['tt']}"
        embed = discord.Embed(title="", description=f"**{title}** - *{new_track_data['an']}*", color=0x8927A1)

        simple_comparisons = constants.SIMPLE_COMPARISONS

        difficulty_comparisons = constants.DIFFICULTY_COMPARISONS

        extra_comparisons = constants.EXTRA_COMPARISONS

        for value, name in simple_comparisons.items():
            if old_track_data.get(value, '[N/A]') != new_track_data.get(value, '[N/A]'):
                embed.add_field(
                    name=f"{name} changed", 
                    value=f"```Old: \"{old_track_data.get(value, '[N/A]')}\"\nNew: \"{new_track_data.get(value, '[N/A]')}\"```", 
                    inline=False
                )

        for value, name in difficulty_comparisons.items():
            if old_track_data['in'].get(value, 0) != new_track_data['in'].get(value, 0):
                embed.add_field(
                    name=f"{name} difficulty changed", 
                    value=f"```Old: \"{constants.generate_difficulty_bar(old_track_data['in'].get(value, 0))}\"\nNew: \"{constants.generate_difficulty_bar(new_track_data['in'].get(value, 0))}\"```", 
                    inline=False
                )


        for key in new_track_data['in'].keys():
            if key not in difficulty_comparisons.keys() and key != '_type':
                embed.add_field(
                    name=f"{key} (*Mismatched Difficulty*)", 
                    value=f"```Found: {constants.generate_difficulty_bar(new_track_data['in'][key])}```", 
                    inline=False
                )

        if old.get('lastModified') != new.get('lastModified'):
            embed.add_field(
                name="Last Modified Date changed", 
                value=f"```Old: {old.get('lastModified', '[N/A]')}\nNew: {new.get('lastModified', '[N/A]')} ```", 
                inline=False
            )

        qi_comparisons = self.compare_qi_fields(old_track_data.get('qi', ''), new_track_data.get('qi', ''))
        if qi_comparisons:
            for field in qi_comparisons:
                embed.add_field(name="QI Field Update", value=field, inline=False)

        for value, name in extra_comparisons.items():
            if old.get(value) != new.get(value):
                embed.add_field(
                    name=f"{name} changed", 
                    value=f"```Old: \"{old.get(value, '[N/A]')}\"\nNew: \"{new.get(value, '[N/A]')}\"```", 
                    inline=False
                )

        return embed
