#!/usr/bin/env python3
"""Replace the oldest clips in audio_clips/ with new streams from surfacecollider.net.

Every stream generated on the Python Glossolalia page is archived by the website
and listed in archive.json. Each new stream is cut into pieces close to the
lengths of the oldest clips in audio_clips/, and each piece replaces one of
those clips, so the number of clips and their mix of lengths stay the same.
Cuts are made at natural pauses in the speech, within 25% of the target length;
if there is no pause in that range, the cut is made at the exact length.
Clips are replaced oldest first: the original clip_###.flac files in number
order, then website clips by date.

Runs hourly as a GitHub Action (.github/workflows/sync-clips.yml), which then
commits the changes. Needs ffmpeg and ffprobe.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

BASE_URL = "https://surfacecollider.net/wp-content/uploads/glossolalia/"
INDEX_URL = BASE_URL + "archive.json"
REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CLIPS_DIR = os.path.join(REPO_DIR, "audio_clips")
# Streams already used, so each is only cut up once
SYNCED_FILE = os.path.join(REPO_DIR, "synced_streams.json")
# Only accept names the website itself generates
VALID_NAME = re.compile(r"^glossolalia_\d{4}-\d{2}-\d{2}_\d{6}\.mp3$")
AUDIO_EXTENSIONS = (".flac", ".mp3")
FADE = 0.015  # seconds of fade at each cut, to avoid clicks
# A pause is at least PAUSE_MIN seconds quieter than PAUSE_DB. Tuned on real
# website streams, which have a pause every few seconds at these settings.
PAUSE_DB = -40
PAUSE_MIN = 0.25
# How far a cut may move from the target length to reach a pause
TOLERANCE = 0.25   # fraction of the target length...
MIN_TOLERANCE = 2  # ...but at least this many seconds, for short clips

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "python-glossolalia-local"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()

def duration(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "csv=p=0", path],
                            stdout=subprocess.PIPE, text=True, check=True)
    return float(result.stdout.strip())

def clips_oldest_first():
    """Original clip_###.flac files first, then website clips (named by date)."""
    names = [f for f in os.listdir(CLIPS_DIR) if f.lower().endswith(AUDIO_EXTENSIONS)]
    return sorted(names, key=lambda n: (not n.startswith("clip_"), n))

def cut_piece(stream_path, start, length, out_path):
    """Cut [start, start+length) from the stream as 16-bit 48 kHz mono FLAC."""
    fades = f"afade=t=in:d={FADE},afade=t=out:st={length - FADE:.3f}:d={FADE}"
    # -v fatal: website streams are many short MP3s joined together, and ffmpeg
    # reports a harmless "Header missing" at every join
    subprocess.run(["ffmpeg", "-nostdin", "-v", "fatal", "-y",
                    "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", stream_path,
                    "-af", fades, "-ar", "48000", "-ac", "1", "-sample_fmt", "s16",
                    "-c:a", "flac", "-compression_level", "8", out_path], check=True)

def find_pauses(stream_path):
    """Return the midpoint (in seconds) of every pause in the stream."""
    result = subprocess.run(["ffmpeg", "-nostdin", "-i", stream_path, "-af",
                             f"silencedetect=noise={PAUSE_DB}dB:d={PAUSE_MIN}", "-f", "null", "-"],
                            stderr=subprocess.PIPE, text=True, check=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", result.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", result.stderr)]
    return [(s + e) / 2 for s, e in zip(starts, ends)]

def choose_cut(offset, length, pauses, stream_length):
    """Pick where a piece starting at `offset` should end, aiming for `length` seconds.

    Returns the pause nearest the target within tolerance, else the exact target,
    or None if the rest of the stream is too short for this piece.
    """
    target = offset + length
    tolerance = max(length * TOLERANCE, MIN_TOLERANCE)
    candidates = [p for p in pauses if abs(p - target) <= tolerance and p > offset + 1]
    if candidates:
        return min(candidates, key=lambda p: abs(p - target))
    if target <= stream_length:
        return target
    if stream_length - offset >= length - tolerance:
        return stream_length  # the stream's own ending is close enough
    return None

def use_stream(stream_path, stream_name):
    """Cut the stream into pieces replacing the oldest clips. Returns the number replaced."""
    stream_length = duration(stream_path)
    pauses = find_pauses(stream_path)
    prefix = stream_name[:-len(".mp3")]
    offset = 0.0
    replaced = 0
    for old in clips_oldest_first():
        if old.startswith(prefix):
            break  # only newer clips remain, including this stream's own pieces
        length = duration(os.path.join(CLIPS_DIR, old))
        end = choose_cut(offset, length, pauses, stream_length)
        if end is None:
            break  # the rest of the stream is too short for the next clip; it goes unused
        new = f"{prefix}_{replaced + 1:02d}.flac"
        cut_piece(stream_path, offset, end - offset, os.path.join(CLIPS_DIR, new))
        os.remove(os.path.join(CLIPS_DIR, old))
        how = "at a pause" if end in pauses else "exact cut"
        print(f"  {old} ({length:.1f}s) -> {new} ({end - offset:.1f}s, {how})")
        offset = end
        replaced += 1
    return replaced

def main():
    try:
        index = json.loads(fetch(INDEX_URL))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("No archive.json yet - nothing to sync")
            return
        raise

    synced = []
    if os.path.exists(SYNCED_FILE):
        with open(SYNCED_FILE) as f:
            synced = json.load(f)

    total = 0
    for entry in index:
        name = entry.get("file", "")
        if not VALID_NAME.match(name):
            print(f"Skipping unexpected file name: {name!r}")
            continue
        if name in synced:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            stream_path = os.path.join(tmp, name)
            with open(stream_path, "wb") as f:
                f.write(fetch(BASE_URL + "archive/" + name))
            print(f"{name}:")
            count = use_stream(stream_path, name)
        print(f"  replaced {count} clip(s)")
        total += count
        synced.append(name)
        with open(SYNCED_FILE, "w") as f:
            json.dump(synced, f, indent=1)

    print(f"{total} clip(s) replaced")

if __name__ == "__main__":
    sys.exit(main())
