# Kodi boxes

Run Kodi Matrix (19), Nexus (20) or Omega (21) locally in Docker, with the addon source of this repository
mounted read-only and live. GUI on the host X11 display, GPU and audio (PulseAudio/PipeWire) from the host,
one data dir per version outside the repo.

| Box    | Kodi | Debian   |
|--------|------|----------|
| matrix | 19   | bullseye |
| nexus  | 20   | bookworm |
| omega  | 21   | sid      |

- **omega uses Debian sid:** trixie's `kodi-inputstream-adaptive` 21.5.9 crashes in the current Widevine CDM
  (Debian bug #1108891, fixed in 21.5.16, only in sid so far). Switch back to trixie once the fix lands there.
- **Version guard:** `versions.env` holds the expected Kodi major per box (`<box>=<release>:<major>`). The image
  build fails if the release ships another major, e.g. when sid moves on to Kodi 22.
- **matrix:** bullseye is end-of-life; the image installs from `archive.debian.org`.
- **Audio** goes through the host's PulseAudio socket (PipeWire-Pulse works); the entrypoint forces Kodi's
  PulseAudio backend.

Requirements: Linux with X11, Docker with the compose plugin, user in the groups `docker`, `video`, `render`.

## Quickstart

```bash
cp dev/kodi-boxes/.env.example dev/kodi-boxes/.env   # set KODI_BOXES_DATA
ln -s "$PWD/dev/kodi-boxes/bin/kodi-box" ~/.local/bin/kodi-box
kodi-box up nexus
kodi-box log --grep crunchyroll
```

`kodi-box help` lists all commands. Commands taking an optional `[<version>]` default to the single running box.

First start of a box (state persists in its data dir):

1. Enable the addon in Kodi (Add-ons > My add-ons > Video add-ons).
2. Run `kodi-box bootstrap` - it installs the addon's dependencies from the Kodi repository, one confirm
   dialog in Kodi per dependency. `kodi-box up` prints a hint while dependencies are missing.

Toggle fullscreen with `\`.

## Debug workflow

1. Edit the addon code in the repo.
2. Reopen the addon menu in Kodi - Python plugins run per call, no Kodi restart needed.
3. Watch `kodi-box log --grep crunchyroll` (debug log level is preset via `advancedsettings.xml`).

Kodi builtins can be sent from the host, e.g. `kodi-box send "RunAddon(plugin.video.crunchyroll)"`.
To run another branch, point `ADDON_SRC` in `.env` to a git worktree.

## Security

- The data dir contains login tokens and the Widevine CDM. Never commit it; keep it outside the repo.
- X11 access is granted to the local user only (`xhost +SI:localuser:<user>`) and revoked when the last box stops.
