#!/usr/bin/env python3
"""Offline gallery player for Python Glossolalia.

Plays glossolalia clips (FLAC and MP3) at random intervals through a USB
audio interface on a Raspberry Pi. Every clip plays once before any repeats,
and progress is saved so a restart or power cut resumes the same cycle.
Clips added to the folder while it runs join the current cycle.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FOLDER = os.path.join(BASE_DIR, "audio_clips")
STATE_FILE = os.path.join(BASE_DIR, "gallery_audio_state.json")
DEVICE_NAMES = ["MGXU", "H4"]   # USB interfaces to look for, in order of preference
AUDIO_EXTENSIONS = (".flac", ".mp3")
MIN_INTERVAL = 30               # seconds between clips
MAX_INTERVAL = 300

# --- FUNCTIONS ---
def find_usb_interface(names):
    """Return the ALSA device string for the first matching USB interface."""
    result = subprocess.run(["aplay", "-l"], stdout=subprocess.PIPE, text=True)
    for name in names:
        for line in result.stdout.splitlines():
            match = re.match(r"card (\d+):.*device (\d+):", line)
            if match and name.lower() in line.lower():
                print(f"Using device: {line.strip()}", flush=True)
                return f"plughw:{match.group(1)},{match.group(2)}"
    return None

def list_clips(audio_dir):
    return sorted(f for f in os.listdir(audio_dir) if f.lower().endswith(AUDIO_EXTENSIONS))

def play_audio(file_path, alsa_device):
    """Play a FLAC (decoded by `flac` into aplay) or MP3 (via mpg123) clip."""
    if file_path.lower().endswith(".mp3"):
        subprocess.run(["mpg123", "-q", "-o", "alsa", "-a", alsa_device, file_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    decoder = subprocess.Popen(["flac", "-d", "-c", "-s", file_path],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    player = subprocess.Popen(["aplay", "-q", "-D", alsa_device],
                              stdin=decoder.stdout, stderr=subprocess.DEVNULL)
    decoder.stdout.close()  # let flac see a broken pipe if aplay exits early
    player.wait()
    decoder.wait()

def load_state(files):
    """Load saved progress, keeping only clips that still exist."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            unplayed = [f for f in state.get("unplayed_files", []) if f in files]
            # Clips that arrived while the player was off join the current cycle
            known = state.get("known_files")
            if known is not None:
                unplayed += [f for f in files if f not in known and f not in unplayed]
            last_file = state.get("last_file")
            if last_file not in files:
                last_file = None
            return unplayed, last_file
        except Exception:
            pass
    return [], None

def save_state(unplayed_files, last_file, known_files):
    state = {"unplayed_files": unplayed_files, "last_file": last_file,
             "known_files": sorted(known_files)}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# --- MAIN LOOP ---
def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--audio-dir", default=AUDIO_FOLDER,
                        help="folder of .flac/.mp3 clips (default: ./audio_clips)")
    parser.add_argument("--device", action="append",
                        help="name of the USB interface to use, as shown by `aplay -l` "
                             "(default: MGXU, then H4)")
    args = parser.parse_args()

    for tool in ("flac", "aplay", "mpg123"):
        if not shutil.which(tool):
            sys.exit(f"Error: `{tool}` not found. Install it with: sudo apt install flac alsa-utils mpg123")

    device_names = args.device or DEVICE_NAMES
    alsa_device = find_usb_interface(device_names)
    if not alsa_device:
        sys.exit(f"Error: no {' or '.join(device_names)} device found!")

    # State stores file names only, so the repo can live anywhere
    files = list_clips(args.audio_dir)
    if not files:
        sys.exit(f"Error: no audio files found in {args.audio_dir}")
    print(f"Found {len(files)} clips", flush=True)

    unplayed_files, last_file = load_state(files)
    if not unplayed_files:
        unplayed_files = files.copy()
        last_file = None
    known_files = set(files)

    while True:
        # Rescan so clips added by `git pull` join the cycle without a restart
        files = list_clips(args.audio_dir) or files
        new_files = [f for f in files if f not in known_files]
        if new_files:
            print(f"Added {len(new_files)} new clip(s)", flush=True)
            unplayed_files += new_files
            known_files.update(new_files)
        # Clips replaced by newer audio drop out of the cycle
        known_files.intersection_update(files)
        unplayed_files = [f for f in unplayed_files if f in files]

        if not unplayed_files:
            unplayed_files = files.copy()

        file_to_play = random.choice(unplayed_files)
        if last_file and len(unplayed_files) > 1:
            while file_to_play == last_file:
                file_to_play = random.choice(unplayed_files)

        play_audio(os.path.join(args.audio_dir, file_to_play), alsa_device)

        last_file = file_to_play
        unplayed_files.remove(file_to_play)
        save_state(unplayed_files, last_file, known_files)

        time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

if __name__ == "__main__":
    main()
