#!/bin/sh
set -eu

userdata="$HOME/.kodi/userdata"
mkdir -p "$userdata"
# Seed only once, never overwrite local changes.
if [ ! -e "$userdata/advancedsettings.xml" ]; then
    cp /usr/local/share/kodi-box/advancedsettings.xml "$userdata/advancedsettings.xml"
fi

# Use the mounted PulseAudio socket (PipeWire-Pulse on the host); Kodi would otherwise probe PipeWire,
# which has no config in the container. Kodi 21+ takes a CLI flag, older versions read KODI_AE_SINK.
if [ "$KODI_MAJOR" -ge 21 ]; then
    set -- --audio-backend=pulseaudio "$@"
else
    export KODI_AE_SINK=PULSE
fi

exec kodi "$@"
