# Basic script to rewind the known_tracks.json file if there is an error with it

from datetime import datetime
import json
import requests

from datetime import datetime

def convert_to_unix(date_string):
    dt = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")
    unix_timestamp = int(dt.timestamp())
    return unix_timestamp

def time_ago(timestamp):
    now = datetime.now()
    diff = now - datetime.fromtimestamp(timestamp)
    
    seconds = diff.total_seconds()
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    months = days / 30
    years = days / 365

    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    elif minutes < 60:
        return f"{int(minutes)} minutes ago"
    elif hours < 24:
        return f"{int(hours)} hours ago"
    elif days < 30:
        return f"{int(days)} days ago"
    elif months < 12:
        return f"{int(months)} months ago"
    else:
        return f"{int(years)} years ago"

def get_track_array(url):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        available_tracks = []
        for k, v in data.items():
            if isinstance(v, dict) and 'track' in v:
                available_tracks.append(v)
        return available_tracks
    else:
        print(f'Unexpected data format: {type(data)}')
        return []

def main():

    def get_commits():
        all_commits = []
        page = 1

        while True:
            commit_url = f'https://api.github.com/repos/FNLookup/data/commits?path=festival/spark-tracks.json&per_page=100&page={page}'
            print(f'[GET] {commit_url}')
            response = requests.get(commit_url)
            response.raise_for_status()
            commits = response.json()
            
            if not commits:  # No more commits left
                break

            all_commits.extend(commits)
            page += 1

        return all_commits
    
    commits = get_commits()
    commits.reverse()
    for no, commit in enumerate(commits):
        print(f'#{len(commits) - no}', commit['sha'][:7], time_ago(convert_to_unix(commit['commit']['committer']['date'])))

    num = input('Enter commit to return to: ')
    if num.isdigit():
        index = (len(commits) - int(num))
        commit = commits[index]
        sha = commit['sha']

        file_url = f'https://raw.githubusercontent.com/FNLookup/data/{sha}/festival/spark-tracks.json'
        print(f'[GET] {file_url}')
        track_data = get_track_array(file_url)
        
        open('known_tracks.json', 'w').write(json.dumps(track_data))
        print('Wrote successfully!')

        rewind_choice = input('Rewind known_songs.json (shortnames) too? [y/anything] ')
        if rewind_choice.lower().strip() == 'y':
            current_songs_data = [song['track']['sn'] for song in track_data]

            open('known_songs.json', 'w').write(json.dumps(current_songs_data))
            print('Wrote successfully!')

        print('Done')
    else:
        print('Please insert a number')

if __name__ == '__main__':
    main()