import requests
import os
from datetime import datetime

# Constants
REPO_OWNER = "FNLookup"
REPO_NAME = "data"
FILE_PATH = "festival/spark-tracks.json"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
COMMITS_URL = f"{API_URL}/commits"
DOWNLOAD_DIR = "./json"

# GitHub token (if needed for authentication or API rate limits)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # optional, or replace with your token

def get_commit_history():
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    params = {"path": FILE_PATH, "per_page": 100}  # Get up to 100 commits per page (max allowed)
    all_commits = []
    page = 1

    while True:
        params["page"] = page
        response = requests.get(COMMITS_URL, headers=headers, params=params)
        response.raise_for_status()
        commits = response.json()
        
        if not commits:  # No more commits left
            break

        all_commits.extend(commits)
        page += 1

    return all_commits

def format_commit_timestamp(commit_timestamp):
    try:
        # Try with fractional seconds
        formatted_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%dT%H.%M.%S.%f")[:-3]
    except ValueError:
        # If it fails, try without fractional seconds
        formatted_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%dT%H.%M.%S")
    
    return formatted_timestamp

def download_file_at_commit(commit_sha, commit_timestamp):
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{commit_sha}/{FILE_PATH}"
    response = requests.get(raw_url, headers=headers)
    response.raise_for_status()

    # Create the directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    # Format the filename using the commit timestamp
    formatted_timestamp = format_commit_timestamp(commit_timestamp)
    file_name = f"spark-tracks_{formatted_timestamp}.json"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Save the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(response.text)

    print(f"Downloaded: {file_name}")

def already_downloaded(commit_timestamp):
    # Format the timestamp to match the filenames we have saved
    formatted_timestamp = format_commit_timestamp(commit_timestamp)
    file_name = f"spark-tracks_{formatted_timestamp}.json"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Check if this file already exists
    return os.path.exists(file_path)

def main():
    commit_history = get_commit_history()
    print(f"Updating local repo of spark-tracks jsons")
    
    for commit in commit_history:
        commit_sha = commit["sha"]
        commit_timestamp = commit["commit"]["committer"]["date"]

        # Skip if the file has already been downloaded
        if already_downloaded(commit_timestamp):
            #print(f"Skipping: File from commit {commit_sha} at {commit_timestamp} already exists")
            continue

        #print(f"Downloading file from commit {commit_sha} at {commit_timestamp}")
        download_file_at_commit(commit_sha, commit_timestamp)

if __name__ == "__main__":
    main()
