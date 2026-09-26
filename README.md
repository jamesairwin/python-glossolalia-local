# Python Glossolalia Local

An offline way to present [Python Glossolalia](https://github.com/jamesairwin/python-glossolalia) in a gallery.

The main Python Glossolalia project creates glossolalia (streams of nonsense speech) live. It sends random strings of letters and sounds to the ElevenLabs text-to-speech API, which needs an internet connection and an API key. Galleries often have neither. This repo holds 200 pre-rendered clips from the generator, gradually refreshed with new audio, plus a small player that runs on a Raspberry Pi with no network.

This README describes the setup the work was shown with.

## Installation setup

```
Raspberry Pi  ──USB──▶  Yamaha MG-XU mixer  ──main out──▶  active speaker
```

- **Raspberry Pi** (any model with USB) running Raspberry Pi OS.
- **Yamaha MG-XU series mixer**, connected by USB. The Pi treats the mixer as its sound card, so the Pi's own headphone jack and HDMI audio are not used. The mixer controls the overall level.
- **Active (powered) speaker** connected to the mixer's main output.

The player also recognises a Zoom H4 recorder used as a USB audio interface, and you can name any other USB interface (see [Settings](#settings)).

## What it does

- It picks a random clip from `audio_clips/`, plays it in full, then waits a random 30 seconds to 5 minutes before the next one.
- Every clip plays once before any clip repeats, and the same clip never plays twice in a row.
- It saves its progress to `gallery_audio_state.json` after each clip. After a restart or power cut, it carries on with the same cycle.
- It plays continuously while the Pi is powered. Opening hours are controlled by switching the power on and off at the socket.
- New clips added to `audio_clips/` join the current cycle without a restart.

## A changing collection

The collection always holds 200 clips, but their contents change as people use the work online. Each time a visitor generates a stream (up to 2 minutes) on the [Python Glossolalia page on surfacecollider.net](https://surfacecollider.net), the website keeps a copy. Every hour, a GitHub Action ([`sync-clips.yml`](.github/workflows/sync-clips.yml)) collects any new streams, cuts them up, and uses them to replace the oldest clips:

- Each stream is cut into pieces that match the lengths of the oldest clips, and each piece replaces one clip. The number of clips and their mix of lengths (9 seconds to about 1.5 minutes) stay the same.
- The original clips (`clip_###.flac`) are replaced first, in number order. After that, the earliest clips from the website are replaced by date, so the collection becomes the most recent 200 clips.
- A stream usually replaces 3 to 6 clips. Any audio left at the end of a stream that is too short for the next clip goes unused.
- Each stream is only used once; `synced_streams.json` lists the streams already used.

A Pi that has internet access, even occasionally, pulls these new clips automatically (see [Automatic updates](#automatic-updates)). Without internet, it plays the clips it already has.

## Contents

| Path | Purpose |
|---|---|
| `gallery_player.py` | The player |
| `audio_clips/` | The 200 clips: originals (`clip_###.flac`) and pieces of website streams (`glossolalia_<date>_<time>_<piece>.flac`) |
| `glossolalia-gallery.service` | systemd service that starts the player automatically on boot |
| `glossolalia-update.service`, `glossolalia-update.timer` | systemd timer that pulls new clips from GitHub every hour |
| `scripts/sync_clips.py`, `.github/workflows/sync-clips.yml` | The hourly GitHub Action that replaces clips with new streams from the website |
| `synced_streams.json` | Website streams already used (created by the first sync) |

All clips are FLAC (16-bit, 48 kHz, mono), a lossless format.

## Setup on the Raspberry Pi

1. Install the tools the player needs: `flac` and `mpg123` decode the clips, and `aplay` plays them.
   ```bash
   sudo apt update
   sudo apt install git flac mpg123 alsa-utils
   ```

2. Clone this repository.
   ```bash
   cd ~
   git clone https://github.com/jamesairwin/python-glossolalia-local.git
   cd python-glossolalia-local
   ```

3. Connect the mixer by USB and switch it on. Check that the Pi can see it:
   ```bash
   aplay -l
   ```
   One of the lines should mention `MGXU`, for example:
   ```
   card 1: MGXU [MG-XU], device 0: USB Audio [USB Audio]
   ```

4. Do a test run. Turn the speaker and the mixer's USB channel up to a sensible level, then run:
   ```bash
   python3 gallery_player.py
   ```
   It should print the device it is using and the number of clips. The first clip plays straight away. Press `Ctrl+C` to stop.

## Start automatically on boot

Install the service. This command fills in your username and the repo's location:

```bash
sed "s|__USER__|$USER|g; s|__DIR__|$PWD|g" glossolalia-gallery.service \
  | sudo tee /etc/systemd/system/glossolalia-gallery.service
sudo systemctl daemon-reload
sudo systemctl enable --now glossolalia-gallery
```

The player now starts whenever the Pi boots. If the mixer is off or unplugged, the service tries again every 10 seconds until it appears, so the Pi and the mixer can be powered on in any order.

Useful commands:

```bash
systemctl status glossolalia-gallery       # is it running?
journalctl -u glossolalia-gallery -f       # follow its output
sudo systemctl stop glossolalia-gallery    # stop it
sudo systemctl disable glossolalia-gallery # don't start on boot
```

## Automatic updates

To have the Pi collect new clips from GitHub every hour, install the update timer from the repo folder:

```bash
sed "s|__USER__|$USER|g; s|__DIR__|$PWD|g" glossolalia-update.service \
  | sudo tee /etc/systemd/system/glossolalia-update.service
sudo cp glossolalia-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now glossolalia-update.timer
```

It checks two minutes after boot and then every hour. When there's no internet, the check fails quietly and the player carries on with the clips it has. To check for updates straight away, run `git pull` in the repo folder.

```bash
systemctl list-timers glossolalia-update   # when it last ran and runs next
journalctl -u glossolalia-update           # output from each check
```

## Settings

You can pass options on the command line (add them to the `ExecStart` line in the service file to make them permanent):

```bash
python3 gallery_player.py --audio-dir /path/to/clips   # use a different folder of .flac/.mp3 clips
python3 gallery_player.py --device "USB Audio"         # use another interface (any text from its `aplay -l` line)
```

The gap between clips is set by `MIN_INTERVAL` and `MAX_INTERVAL`, in seconds, at the top of `gallery_player.py`.

To start the cycle again from scratch, stop the player and delete `gallery_audio_state.json`.

## Using your own clips

Put `.flac` or `.mp3` files in `audio_clips/`, or point `--audio-dir` somewhere else. You can convert other formats with FFmpeg:

```bash
ffmpeg -i clip.wav -c:a flac clip.flac
```

To create new glossolalia audio, use the main [Python Glossolalia](https://github.com/jamesairwin/python-glossolalia) project.
