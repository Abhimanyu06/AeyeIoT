import requests
from git import Repo
import os

def get_latest_release_version(owner, repo_name, token=None):
    """Fetch the latest release version from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo_name}/releases/latest"
    headers = {}
    
    if token:
        headers["Authorization"] = f"token {token}"

    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        latest_release = response.json()
        return latest_release['tag_name'], latest_release['tarball_url']
    else:
        print(f"Failed to fetch release info: {response.status_code}")
        return None, None

def compare_and_pull(repo_path, latest_version):
    """Check if the local version matches the latest release version and pull if necessary."""
    try:
        repo = Repo(repo_path)
        # Fetch latest tags from remote
        origin = repo.remotes.origin
        origin.fetch(tags=True)

        # Get the latest tag from the local repo
        local_tags = repo.tags
        local_version = str(local_tags[-1]) if local_tags else None

        print(f"Latest local version: {local_version}")
        print(f"Latest remote release version: {latest_version}")

        if local_version != latest_version:
            print(f"Local version {local_version} is outdated. Pulling changes for release {latest_version}...")
            os.system(f"git fetch --tags")
            os.system(f"git checkout {latest_version}")
        else:
            print("Your local repository is up to date.")
    except Exception as e:
        print(f"An error occurred: {e}")

# GitHub repository details
owner = "Abhimanyu06"
repo_name = "AeyeIoT"
repo_path = "."  # Path to your local git repository
token = os.getenv('token', "")

# Fetch the latest release version from GitHub
latest_version, tarball_url = get_latest_release_version(owner, repo_name, token)

# Compare local version with the latest release version
if latest_version:
    compare_and_pull(repo_path, latest_version)
