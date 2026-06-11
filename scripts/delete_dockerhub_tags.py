import os
import re
import sys
import requests
from dotenv import load_dotenv

# Load .env from project root or current directory
_env_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    os.path.join(os.getcwd(), ".env"),
]
for _env_path in _env_candidates:
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        break

username = os.getenv("DOCKER_HUB_USERNAME", "webyhomelab")
password = os.getenv("DOCKER_HUB_PASSWORD")
repo = "power-safety-ua"

if not password:
    print("Error: DOCKER_HUB_PASSWORD not found in environment.")
    sys.exit(1)

print(f"Logging in to Docker Hub as {username}...")
login_url = "https://hub.docker.com/v2/users/login/"
r = requests.post(login_url, json={"username": username, "password": password})
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text}")
    sys.exit(1)

token = r.json().get("token")
headers = {"Authorization": f"JWT {token}"}

print(f"Fetching tags for {username}/{repo}...")
tags_url = f"https://hub.docker.com/v2/repositories/{username}/{repo}/tags/?page_size=100"
r = requests.get(tags_url, headers=headers)
if r.status_code != 200:
    print(f"Failed to fetch tags: {r.status_code} {r.text}")
    sys.exit(1)

tags_data = r.json().get("results", [])

# Hardcoded whitelists as per security guidelines
WHITELIST = {"latest", "main", "master", "stable"}

# Parse tags into version numbers
version_pattern = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")

version_tags = []
for t in tags_data:
    name = t.get("name")
    digest = t.get("digest")
    if name in WHITELIST:
        continue
    match = version_pattern.match(name)
    if match:
        # Extract major, minor, patch (default 0 if missing)
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) is not None else 0
        version_tags.append((major, minor, patch, name, digest))

if not version_tags:
    print("No version tags found to clean up.")
    sys.exit(0)

# Sort version tags descending to find the newest one
version_tags.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
newest_version = version_tags[0]
newest_tag_name = newest_version[3]
newest_tag_digest = newest_version[4]

print(f"\nNewest stable version identified: {newest_tag_name} (digest: {newest_tag_digest})")

# Determine which tags to protect
protected_tags = set(WHITELIST)
protected_digests = {newest_tag_digest} if newest_tag_digest else set()

# Also protect any tag that matches the newest version tag name
protected_tags.add(newest_tag_name)

# Identify tags to delete
to_delete = []
for t in tags_data:
    name = t.get("name")
    digest = t.get("digest")
    
    # Check if protected by name or digest
    if name in protected_tags:
        print(f"Protecting tag (by name whitelist): {name}")
        continue
    if digest and digest in protected_digests:
        print(f"Protecting tag (by digest match): {name}")
        continue
        
    # Extra safety: Make sure it's a version tag before deleting
    if version_pattern.match(name):
        to_delete.append(name)
    else:
        print(f"Skipping unknown tag (not version pattern, not whitelisted): {name}")

if not to_delete:
    print("\nNo outdated tags to delete. Repository is clean!")
    sys.exit(0)

print(f"\nTags marked for DELETION: {to_delete}")

for tag_name in to_delete:
    print(f"Deleting tag {tag_name}...")
    delete_url = f"https://hub.docker.com/v2/repositories/{username}/{repo}/tags/{tag_name}/"
    r = requests.delete(delete_url, headers=headers)
    if r.status_code == 204:
        print(f"Successfully deleted tag {tag_name}")
    else:
        print(f"Failed to delete tag {tag_name}: {r.status_code} {r.text}")

print("\nDocker Hub tags cleanup finished!")
