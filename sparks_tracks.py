# this still works so im not touching it
# it still works dont touch it

import json
import logging
import requests
import os
from datetime import datetime
import hashlib
import re
from urllib.parse import urlparse, parse_qs

from bot import constants

# Constants
REPO_OWNER = "FNLookup"
REPO_NAME = "data"
FILE_PATH = "festival/spark-tracks.json"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
COMMITS_URL = f"{API_URL}/commits"
DOWNLOAD_DIR = "./json/github"
ARCHIVE_DIR = "./json"

GITHUB_TOKEN = constants.GITHUB_PAT

def get_last_page(header) -> int:
    links = header.split(', ')
    for link in links:
        match = re.match(r'<(.+)>; rel="last"', link)
        if match:
            url = match.group(1)
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'page' in query_params:
                return int(query_params['page'][0])

def get_latest_iso():
    hashes_idx = os.path.join(ARCHIVE_DIR, 'hashes.dat')
    if os.path.exists(hashes_idx):
        with open(hashes_idx, 'r') as f:
            latest_date = None
            for line in f.read().split('\n'):
                parts = line.split(':')
                fname = parts[1]
                match = re.search(r'spark-tracks_(\d{4}-\d{2}-\d{2}T\d{2}\.\d{2}\.\d{2})', fname)
                if match:
                    date_str = match.group(1)
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H.%M.%S")
                    if latest_date is None or dt > latest_date:
                        latest_date = dt
            if latest_date:
                return latest_date.isoformat()
            
    return None

def get_commit_history():
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    since = get_latest_iso()
    since = None

    params = {"path": FILE_PATH, "per_page": 100, 'since': since}
    all_commits = []

    page = 1
    last_page = None

    while last_page is None or page <= last_page:
        params["page"] = page
        url = f'{COMMITS_URL}?' + '&'.join([f'{k}={v}' for k, v in params.items() if v is not None])
        print(f'[GET] {url}')
        response = requests.get(url, headers=headers)
        # print(response.headers)
        response.raise_for_status()
        commits = response.json()

        if last_page is None:
            if 'Link' in response.headers:
                last_page = get_last_page(response.headers['Link'])
            else:
                logging.error('No Link header')
                break

        all_commits.extend(commits)
        page += 1

    return all_commits

def format_commit_timestamp(commit_timestamp):
    try:
        formatted_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%dT%H.%M.%S.%f")[:-3]
    except ValueError:
        formatted_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%dT%H.%M.%S")
    
    return formatted_timestamp

def download_file_at_commit(commit_sha, commit_timestamp):
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{commit_sha}/{FILE_PATH}"
    logging.info(f'[GET] {raw_url}')
    response = requests.get(raw_url, headers=headers)
    response.raise_for_status()

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    formatted_timestamp = format_commit_timestamp(commit_timestamp)
    file_name = f"spark-tracks_{formatted_timestamp}_{commit_sha}.json"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Save the file
    with open(file_path, 'w') as f:
        f.write(response.text)

    logging.debug(f"Downloaded: {file_name}")

    return file_path

def already_downloaded(commit_sha, commit_timestamp):
    formatted_timestamp = format_commit_timestamp(commit_timestamp)
    file_name = f"spark-tracks_{formatted_timestamp}_{commit_sha}.json"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Check if this file already exists
    return os.path.exists(file_path)

def main():
    commit_history = get_commit_history()

    fhashes = {}

    hashes_idx = os.path.join(ARCHIVE_DIR, 'hashes.dat')
    if os.path.exists(hashes_idx):
        with open(hashes_idx, 'r') as f:
            for line in f.read().split('\n'):
                finfo = line.split(':')
                fhash = finfo[0]
                fname = finfo[1]
                fhashes[fhash] = fname.rstrip('\n')

    for file in os.listdir(ARCHIVE_DIR):
        if file.endswith('.json'):
            if file not in fhashes.values():
                # the file isnt hashed so we hash it
                with open(os.path.join(ARCHIVE_DIR, file), 'r') as f:
                    json_content = json.dumps(json.loads(f.read()))
                    _hash = hashlib.sha256(json_content.encode('utf-8')).hexdigest()
                    fhashes[_hash] = file
                    print(f'{file} hashed [{_hash}]')
    
    if not os.path.exists(hashes_idx):
        hashes_str = '\n'.join(f"{fhash}:{fname}" for fhash, fname in fhashes.items())
        with open(hashes_idx, 'w') as f:
            f.write(hashes_str)
    
    for commit in commit_history:
        commit_sha = commit["sha"]
        commit_timestamp = commit["commit"]["committer"]["date"]

        if already_downloaded(commit_sha, commit_timestamp):
            continue

        fname = download_file_at_commit(commit_sha, commit_timestamp)
        # the file didnt exist before
        # so now we have to compare it

        # for getting an accurate hash we have to exterminate all indentation
        fcontent = open(fname, 'r').read()
        json_noindent = json.dumps(json.loads(fcontent))
        fhash = hashlib.sha256(json_noindent.encode('utf-8')).hexdigest()

        if fhash not in fhashes:
            # this file is new, so we can archive it
            archive_path = os.path.join(ARCHIVE_DIR, f"spark-tracks_{commit_timestamp}.json")
            with open(archive_path, 'w') as f:
                f.write(json.dumps(json.loads(fcontent), indent=4))

            # print(f"Archived: {archive_path}")
        else:
            # print(f'file is equal to {fhashes[fhash]}')
            pass

if __name__ == "__main__":
    main()
