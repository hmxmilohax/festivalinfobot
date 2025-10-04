# this still works so im not touching it
# it still works dont touch it

import logging
import requests
import os
from datetime import datetime

from bot import constants

# Constants
REPO_OWNER = "FNLookup"
REPO_NAME = "data"
FILE_PATH = "festival/spark-tracks.json"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
COMMITS_URL = f"{API_URL}/commits"
DOWNLOAD_DIR = "./json"

GITHUB_TOKEN = constants.GITHUB_PAT

def get_commit_history():
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    params = {"path": FILE_PATH, "per_page": 100}
    all_commits = []
    page = 1

    while True:
        params["page"] = page
        url = f'{COMMITS_URL}?' + '&'.join([f'{k}={v}' for k, v in params.items()])
        logging.debug(f'[GET] {url}')
        response = requests.get(url, headers=headers)
        # print(response.headers)
        response.raise_for_status()
        commits = response.json()
        
        if not commits:
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
    logging.debug(f'[GET] {raw_url}')
    response = requests.get(raw_url, headers=headers)
    response.raise_for_status()

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    formatted_timestamp = format_commit_timestamp(commit_timestamp)
    file_name = f"spark-tracks_{formatted_timestamp}.json"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Save the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(response.text)

    logging.debug(f"Downloaded: {file_name}")

def already_downloaded(commit_timestamp):
    formatted_timestamp = format_commit_timestamp(commit_timestamp)
    file_name = f"spark-tracks_{formatted_timestamp}.json"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Check if this file already exists
    return os.path.exists(file_path)

def main():
    commit_history = get_commit_history()
    
    
    for commit in commit_history:
        commit_sha = commit["sha"]
        commit_timestamp = commit["commit"]["committer"]["date"]

        if already_downloaded(commit_timestamp):
            continue

        download_file_at_commit(commit_sha, commit_timestamp)

if __name__ == "__main__":
    main()
