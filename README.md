# Python Glossolalia: Gallery Player

An offline way to present [Python Glossolalia](https://github.com/jamesairwin/python-glossolalia) in a gallery.

The main Python Glossolalia project creates glossolalia (streams of nonsense speech) live. It sends random strings of letters and sounds to the ElevenLabs text-to-speech API, which needs an internet connection and an API key. Galleries often have neither. This repo holds a set of 200 pre-rendered clips from the generator, plus a small player that runs on a Raspberry Pi with no network.

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

## Contents

| Path | Purpose |
|---|---|
| `gallery_player.py` | The player |
| `audio_clips/` | 200 glossolalia clips (FLAC, 16-bit, 48 kHz, mono; about 235 MB) |
| `glossolalia-gallery.service` | systemd service that starts the player automatically on boot |

The clips are FLAC, a lossless format: the audio is identical to the original WAVs at a third of the size.

## Setup on the Raspberry Pi

1. Install the tools the player needs: `flac` decodes the clips and `aplay` plays them.
   ```bash
   sudo apt update
   sudo apt install git flac alsa-utils
   ```

2. Clone this repository.
   ```bash
   cd ~
   git clone https://github.com/jamesairwin/python-glossolalia-gallery.git
   cd python-glossolalia-gallery
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

## Settings

You can pass options on the command line (add them to the `ExecStart` line in the service file to make them permanent):

```bash
python3 gallery_player.py --audio-dir /path/to/clips   # use a different folder of .flac clips
python3 gallery_player.py --device "USB Audio"         # use another interface (any text from its `aplay -l` line)
```

The gap between clips is set by `MIN_INTERVAL` and `MAX_INTERVAL`, in seconds, at the top of `gallery_player.py`.

To start the cycle again from scratch, stop the player and delete `gallery_audio_state.json`.

## Using your own clips

Put `.flac` files in `audio_clips/` (or point `--audio-dir` somewhere else). You can convert other formats with FFmpeg:

```bash
ffmpeg -i clip.wav -c:a flac clip.flac
```

To create new glossolalia audio, use the main [Python Glossolalia](https://github.com/jamesairwin/python-glossolalia) project.
