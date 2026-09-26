#!/usr/bin/env python3
"""Download new glossolalia streams from surfacecollider.net into audio_clips/.

Every stream generated on the Python Glossolalia page is archived by the website
and listed in archive.json. This fetches any listed stream not already in
audio_clips/. It runs hourly as a GitHub Action (.github/workflows/sync-clips.yml),
which then commits the new clips to the repo.
"""
import json
import os
import re
import sys
import urllib.request

BASE_URL = "https://surfacecollider.net/wp-content/uploads/glossolalia/"
INDEX_URL = BASE_URL + "archive.json"
CLIPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio_clips")
# Only accept names the website itself generates, so nothing can be written outside audio_clips/
VALID_NAME = re.compile(r"^glossolalia_\d{4}-\d{2}-\d{2}_\d{6}\.mp3$")

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "python-glossolalia-local"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()

def main():
    try:
        index = json.loads(fetch(INDEX_URL))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("No archive.json yet - nothing to sync")
            return
        raise

    added = 0
    for entry in index:
        name = entry.get("file", "")
        if not VALID_NAME.match(name):
            print(f"Skipping unexpected file name: {name!r}")
            continue
        path = os.path.join(CLIPS_DIR, name)
        if os.path.exists(path):
            continue
        data = fetch(BASE_URL + "archive/" + name)
        with open(path, "wb") as f:
            f.write(data)
        print(f"Added {name} ({len(data) / 1e6:.1f} MB)")
        added += 1

    print(f"{added} new clip(s)")

if __name__ == "__main__":
    sys.exit(main())
