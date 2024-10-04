from datetime import datetime
import json
import subprocess
import discord
import requests

from bot import constants

class DailyCommandEmbedHandler():
    def __init__(self) -> None:
        pass

    def create_daily_embeds(self, daily_tracks, chunk_size=10):
        embeds = []
        
        for i in range(0, len(daily_tracks), chunk_size):
            embed = discord.Embed(title="Daily Rotation Tracks", color=0x8927A1)
            chunk = daily_tracks[i:i + chunk_size]
            
            for entry in chunk:
                active_since_display = f"<t:{entry['activeSince']}:R>" if entry['activeSince'] else "Unknown"
                active_until_display = f"<t:{entry['activeUntil']}:R>" if entry['activeUntil'] else "Unknown"
                
                embed.add_field(
                    name="",
                    value=f"**\\• {entry['title']}** - *{entry['artist']}*\n"
                        f"`Added:` {active_since_display} - `Leaving:` {active_until_display}\n"
                        f"```{entry['difficulty']}```\n",
                    inline=False
                )
            embeds.append(embed)

        return embeds

class LeaderboardEmbedHandler():
    def __init__(self) -> None:
        pass

    def format_stars(self, stars:int = 6):
        if stars > 5:
            stars = 5
            return '✪' * stars
        else:
            return '' + ('★' * stars) + ('☆' * (5-stars))

    def generate_leaderboard_entry_embeds(self, entries, title, chunk_size=5):
        embeds = []

        for i in range(0, len(entries), chunk_size):
            embed = discord.Embed(title=title, color=0x8927A1)
            chunk = entries[i:i + chunk_size]
            field_text = '```'
            for entry in chunk:
                try:
                    # Prepare leaderboard entry details
                    rank = f"#{entry['rank']}"
                    username = entry.get('userName', '[Unknown]')
                    difficulty = ['E', 'M', 'H', 'X'][entry['best_run']['difficulty']]
                    accuracy = f"{entry['best_run']['accuracy']}%"
                    stars = self.format_stars(entry['best_run']['stars'])
                    score = f"{entry['best_run']['score']}"
                    fc_status = "FC" if entry['best_run']['fullcombo'] else ""

                    # Add the formatted line for this entry
                    field_text += f"{rank:<5}{username:<18}{difficulty:<2}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}"

                except Exception as e:
                    print(f"Error in leaderboard entry formatting: {e}")
                field_text += '\n'
            field_text += '```'

            embed.add_field(name="", value=field_text, inline=False)
            embeds.append(embed)

        return embeds

    def generate_leaderboard_embed(self, track_data, entry_data, instrument):
        track = track_data['track']
        title = track['tt']
        embed = discord.Embed(title="", description=f"**{title}** - *{track['an']}*", color=0x8927A1)

        # Best Run information
        difficulty = ['Easy', 'Medium', 'Hard', 'Expert'][entry_data['best_run']['difficulty']]
        accuracy = f"{entry_data['best_run']['accuracy']}%"
        stars = self.format_stars(entry_data['best_run']['stars'])
        score = f"{entry_data['best_run']['score']}"
        fc_status = "FC" if entry_data['best_run']['fullcombo'] else ""

        # Add player info
        embed.add_field(name="Player", value=entry_data.get('userName', '[Unknown]'), inline=True)
        embed.add_field(name="Rank", value=f"#{entry_data['rank']}", inline=True)
        embed.add_field(name="Instrument", value=instrument, inline=True)

        # Add Best run info
        difficulty = f'[{difficulty}]'
        field_text = f"{difficulty:<18}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}"
        embed.add_field(name="Best Run", value=f"```{field_text}```", inline=False)

        # Session data (if present)
        for session in entry_data.get('sessions', []):
            session_field_text = '```'
            is_solo = len(session['stats']['players']) == 1
            for player in session['stats']['players']:
                try:
                    username = entry_data['userName'] if player['is_valid_entry'] else f"[Band Member] {['L', 'B', 'V', 'D', 'PL', 'PB'][player['instrument']]}"
                    difficulty = ['E', 'M', 'H', 'X'][player['difficulty']]
                    accuracy = f"{player['accuracy']}%"
                    stars = self.format_stars(player['stars'])
                    score = f"{player['score']}"
                    fc_status = "FC" if player['fullcombo'] else ""

                    session_field_text += f"{username:<18}{difficulty:<2}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}\n"
                except Exception as e:
                    print(f"Error in session formatting: {e}")

            # Band data
            if not is_solo:
                band = session['stats']['band']
                name =     '[Band Score]'
                accuracy = f'{band['accuracy']}%'
                stars = self.format_stars(band['stars'])
                base_score = band['scores']['base_score']
                od_bonus = band['scores']['overdrive_bonus']
                show_od_bonus = od_bonus > 0
                total = band['scores']['total']
                fc_status = "FC" if band['fullcombo'] else ""
                session_field_text += f"{name:<20}{accuracy:<5}{fc_status:<3}{stars:<7}{base_score:>8}\n"
                if show_od_bonus:
                    name = '[OD Bonus]'
                    od_bonus = f'+{od_bonus}'
                    session_field_text += f"{name:<36}{od_bonus:>9}\n"

                    name = '[Total Score]'
                    session_field_text += f"{name:<35}{total:>10}\n"

            session_field_text += '```'
            embed.add_field(name=f"<t:{int(session['time'])}:R>", value=session_field_text, inline=False)

        return embed
    
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
            return int(dt.timestamp())
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
        print(f'[GET] {repo_url}')
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
            print(f"Error getting local commit hash: {e}")
            return "Unknown", "Unknown", "Unknown"
        
class SearchEmbedHandler:
    def __init__(self) -> None:
        pass

    def format_date(self, date_string):
        if date_string:
            date_ts = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return date_ts.strftime("%B %d, %Y")
        return "Currently in the shop!"
    
    def create_track_embeds(self, track_list, title, chunk_size=10, shop=False, jam_tracks=None):
        embeds = []

        for i in range(0, len(track_list), chunk_size):
            embed = discord.Embed(title=title, color=0x8927A1)
            chunk = track_list[i:i + chunk_size]

            for track in chunk:
                if shop:
                    # Shop-specific fields
                    in_date_display = self.format_date(track['inDate'])
                    out_date_display = self.format_date(track['outDate'])
                    
                    # Cross-reference with jam tracks for difficulty data
                    shortname = track['devName']
                    jam_track = [jt for jt in jam_tracks if jt['track']['sn'] == shortname][0] if jam_tracks else None

                    if jam_track:
                        difficulty_data = jam_track['track'].get('in', {})
                        difficulty_str = constants.generate_difficulty_string(difficulty_data)
                    else:
                        difficulty_str = "No difficulty data available"

                    embed.add_field(
                        name="",
                        value=f"**\\• {track['title']}** - *{track['artist']}*\n"
                            f"`Added:` {in_date_display} - `Leaving:` {out_date_display}\n"
                            f"```{difficulty_str}```",
                        inline=False
                    )
                else:
                    # Daily rotation or full list tracks
                    shortname = track['track']['sn']
                    embed.add_field(
                        name="",
                        value=f"**\\• {track['track']['tt']}** - *{track['track']['an']}*",
                        inline=False
                    )

            embeds.append(embed)

        return embeds
    
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
        placeholder_id = track.get('ti', 'sid_placeholder_00').split('_')[-1].zfill(2)  # Extract the placeholder ID
        embed = discord.Embed(title="", description=f"**{title}** - *{track['an']}*", color=0x8927A1)
        embed.set_footer(text="Festival Tracker")

        # Add various fields to the embed
        embed.add_field(name="\n", value="", inline=False)
        embed.add_field(name="Release Year", value=track.get('ry', 'Unknown'), inline=True)

        # Add Key and BPM to the embed
        key = track.get('mk', 'Unknown')  # Get the key
        mode = track.get('mm', 'Unknown')  # Get the mode

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
            last_modified = datetime.fromisoformat(track_data['lastModified'].replace('Z', '+00:00'))
            human_readable_date = last_modified.strftime("%B %d, %Y")
            embed.add_field(name="Last Modified", value=human_readable_date, inline=True)
        
        # Add Song Rating
        rating = track.get('ar', 'N/A')
        if rating == 'T':
            rating_description = 'Teen'
        elif rating == 'E':
            rating_description = 'Everyone'
        else:
            rating_description = rating
        
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

        # Construct the vertical difficulty bars
        difficulties = (
            f"Lead:      {constants.generate_difficulty_bar(guitar_diff)}\n"
            f"Bass:      {constants.generate_difficulty_bar(bass_diff)}\n"
            f"Drums:     {constants.generate_difficulty_bar(drums_diff)}\n"
            f"Vocals:    {constants.generate_difficulty_bar(vocals_diff)}\n"
            f"Pro Lead:  {constants.generate_difficulty_bar(pro_guitar_diff)}\n"
            f"Pro Bass:  {constants.generate_difficulty_bar(pro_bass_diff)}\n"
            f"Pro Drums: {constants.generate_difficulty_bar(pro_drums_diff)}"
        )

        # Add difficulties to embed
        embed.add_field(name="Difficulties", value=f"```{difficulties}```", inline=False)
        
        # Add the album art
        embed.set_thumbnail(url=track['au'])
        
        return embed
    
    def compare_qi_fields(self, old_qi, new_qi):
        # Parse the qi fields if they are valid JSON strings
        try:
            old_qi_data = json.loads(old_qi)
            new_qi_data = json.loads(new_qi)
        except json.JSONDecodeError:
            return None  # Return None if parsing fails

        embed_fields = []

        # Compare the direct fields like 'sid', 'pid', 'title'
        for field in ['sid', 'pid', 'stereoId', 'instrumentalId', 'title']:
            if old_qi_data.get(field) != new_qi_data.get(field):
                embed_fields.append(
                    f"**{field}** changed\n"
                    f"```Old: {old_qi_data.get(field, '[N/A]')}\nNew: {new_qi_data.get(field, '[N/A]')}```"
                )

        # Compare the tracks part
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

        # Compare the preview part if exists
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

        # Report changes in the simple fields
        for value, name in simple_comparisons.items():
            if old_track_data.get(value, '[N/A]') != new_track_data.get(value, '[N/A]'):
                embed.add_field(
                    name=f"{name} changed", 
                    value=f"```Old: \"{old_track_data.get(value, '[N/A]')}\"\nNew: \"{new_track_data.get(value, '[N/A]')}\"```", 
                    inline=False
                )

        # Report changes in difficulty fields
        for value, name in difficulty_comparisons.items():
            if old_track_data['in'].get(value, 0) != new_track_data['in'].get(value, 0):
                embed.add_field(
                    name=f"{name} difficulty changed", 
                    value=f"```Old: \"{constants.generate_difficulty_bar(old_track_data['in'].get(value, 0))}\"\nNew: \"{constants.generate_difficulty_bar(new_track_data['in'].get(value, 0))}\"```", 
                    inline=False
                )

        # Check for mismatched difficulty properties
        for key in new_track_data['in'].keys():
            if key not in difficulty_comparisons.keys() and key != '_type':
                embed.add_field(
                    name=f"{key} (*Mismatched Difficulty*)", 
                    value=f"```Found: {constants.generate_difficulty_bar(new_track_data['in'][key])}```", 
                    inline=False
                )

        # Report `lastModified` change
        if old.get('lastModified') != new.get('lastModified'):
            embed.add_field(
                name="Last Modified Date changed", 
                value=f"```Old: {old.get('lastModified', '[N/A]')}\nNew: {new.get('lastModified', '[N/A]')} ```", 
                inline=False
            )

        # Report `qi` change (JSON string difference)
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