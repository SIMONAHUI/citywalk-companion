# CityWalk Companion

A macOS companion for street-walking videos. Prepare short scene commentary with the signed-in **ChatGPT website**, then play the video, captions, and cached natural narration on one timeline.

**No AI API key. No Codex required at runtime. Launching the app never starts AI work or narration.**

## What it does

- Creates timestamped commentary from previews spanning the video's full duration.
- Uses ChatGPT's visible web composer and Read Aloud controls. It does not call an AI backend directly.
- Caches video, commentary, and web narration locally for reuse after restarting.
- Plays commentary only after you explicitly select **Start companion** and start the video.
- Lowers the original soundtrack during narration and restores it afterward.
- Provides a transparent caption overlay, draggable header, resizable corner, and optional matching image.
- Cancels preparation and live sending through **Stop all tasks**. Stop closes the app-owned Chrome session and clears queued work; it also stops cached narration. Previously submitted requests cannot be unsent or refunded.
- Cancels old commentary when seeking. The app does not replay a backlog of old scenes.

The interface is currently Chinese. This is an experimental, locally installed prototype, not a signed/notarized App Store product.

## Install

Tested on Apple Silicon with macOS 26.5.2, Python 3.12, and Google Chrome. Other versions have not been verified. ScreenCaptureKit requires a recent macOS version; Xcode Command Line Tools are needed to build the Swift helpers.

1. Install Python 3.12 or newer, Google Chrome, and Apple's Command Line Tools.
2. Download the included [source archive](citywalk-companion-source.zip?raw=1), extract it, and keep the extracted folder in one location. This archive preserves the launcher executable permissions.
3. Run `install.command` to create a virtual environment, install dependencies, and compile the native helpers.
4. Open `CityWalk Companion.app` in that folder.
5. Use **Login / set up GPT** to sign in yourself in the app's dedicated Chrome profile. Authentication and any verification remain under your control.
6. For natural voice recording, grant Terminal screen and system-audio recording access when macOS asks. The recorder captures the app-owned Chrome process's audio, not microphone input.

The installer does not configure startup/login items. The service runs only while you open the app. Closing the app exits its local service and dedicated browser. `start.command` is a fallback launcher that also opens the native viewer.

## Use

### Already prepared video

Open the app, select **Start companion**, then press the video's Play button. Without Start companion, you can play the video without commentary. Restarting never restores a previous enabled state. Cached viewing does not need ChatGPT or Codex requests.

### New video

Paste a complete public Bilibili BV video URL and explicitly select **Prepare new video (uses GPT)**. This downloads public media to your computer, extracts a preview every 30 seconds, asks GPT for brief observations, and records its web Read Aloud output. Preparation may be audible and consumes ChatGPT usage and network traffic. It is separate from viewing and does not automatically enable companion playback.

For a roughly one-hour video, allow approximately **15–40 minutes** as a planning estimate; connection speed, GPT limits, and response/voice latency can change this substantially. Download and preview extraction can also take time. Cached videos do not need this preparation again. Complete cached entries are reused; an interrupted vision stage may need to restart its scene analysis.

Currently supported: public single Bilibili BV videos up to four hours. Multi-part videos, gated/premium media, and guaranteed 60 fps are not supported. The downloader does not read browser cookies or bypass login, paywalls, or verification.

### Stop

Select **Stop all tasks** at any time. This disables companion playback, pauses the local player, cancels preparation/live analysis, clears the sending queue, stops recording/narration, and closes only the app-owned Chrome process. Cached files remain. There is no automatic retry or restart. To continue, explicitly start companion playback or preparation again.

## Files and privacy

The application directory contains:

- `prepared/`: local video/audio, preview frames, scene timeline, and narration files. New videos use separate BV-ID subdirectories.
- `browser-profile/`: the dedicated browser's private login state.
- `config.json`: optional local settings and conversation binding.
- `control-url.txt`: a private session control link, recreated each launch.

None of these private/runtime files are included in this repository. Do not attach them to issues. Preview images are sent to your ChatGPT conversation only during explicitly started preparation/live analysis. Cached playback stays local. No model inference runs through Codex.

The local control service uses a random per-launch token. Audio recording endpoints additionally require loopback access. A legacy phone control link is available on the same LAN; keep its complete URL private. No cloud-hosted MCP server or public tunnel is created.

## Scope and limitations

- Full-duration coverage means **sampling every 30 seconds**, not analyzing every frame or continuously understanding video.
- Web selectors, login state, ChatGPT availability, and account limits can interrupt preparation. The app stops with an error instead of silently switching to an AI API or mechanical TTS.
- Vision-generated commentary can be wrong; unclear signs should be omitted. It is not an authoritative travel guide.
- Voice cache recording depends on system-audio permission. Keep other audio in the dedicated Chrome session paused during preparation.
- The included tests verify idle startup, task cancellation, explicit narration consent, token checks, and recording access boundaries. The current machine's prepared-media playback was opened and checked in the native viewer. A fresh arbitrary-video preparation workflow has not yet been independently tested end to end.

## Development checks

```sh
.venv/bin/python -m pip install httpx
.venv/bin/python -m unittest discover -s . -v
node test_player.js
```

## Feedback welcome

Please open an issue with the macOS version, the step that failed, and expected versus observed behavior. Useful suggestions include safer web automation, shorter preparation, better scene timing, and more accessible caption controls. Remove private URLs, tokens, chat contents, login details, and downloaded media before attaching anything.

## Related projects

Design mechanisms were compared with [nerdpudding](https://github.com/nerdpudding/nerdpudding) (buffered commentary), [avorythm](https://github.com/msmahdinejad/avorythm) (timeline and audio ducking), [bilibili-ai-summary](https://github.com/zanmeidalao/bilibili-ai-summary) (web composer automation), and [BiliScript](https://github.com/Edmund724/BiliScript) (playback-time synchronization). No code from these projects is included here, and their API-based inference stacks were not adopted.

MIT license applies to this project's source. Dependencies keep their own licenses; media remains owned by its creators. Only prepare media you are permitted to download and process.
