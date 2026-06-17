#!/usr/bin/env bash
# Regenerate the media bundled by the media_gallery sample.
#
# Sources (override via env):
#   SRC_LOGO   a logo image          (default: ~/Downloads/logo.png)
#   SRC_VIDEO  a high-res video clip (default: ~/Downloads/12499611_3840_2160_60fps.mp4)
#   ELEVENLABS_API_KEY   used to (re)generate the spoken audio; if unset, the
#                        existing voice.* files are kept.
#   VOICE_ID   ElevenLabs voice      (default: yoZ06aMxZJJ28mfd3POQ — Sam, narrator)
#
# Requires ffmpeg (and curl for the speech). Run: ./regenerate.sh
set -euo pipefail
cd "$(dirname "$0")/media_src"

SRC_LOGO="${SRC_LOGO:-$HOME/Downloads/logo.png}"
SRC_VIDEO="${SRC_VIDEO:-$HOME/Downloads/12499611_3840_2160_60fps.mp4}"
VOICE_ID="${VOICE_ID:-yoZ06aMxZJJ28mfd3POQ}"
SPEECH="Welcome to the Lemming Stage media gallery. This voice was generated with Eleven Labs and streamed straight from a zip bundle, decoded right here in your browser."

# images from the logo
ffmpeg -y -loglevel error -i "$SRC_LOGO" -vf "scale=480:-1" logo.png
ffmpeg -y -loglevel error -i "$SRC_LOGO" -vf "scale=480:-1" -q:v 3 logo.jpg
ffmpeg -y -loglevel error -i "$SRC_LOGO" -vf "scale=480:-1" -quality 90 logo.webp

# animated gif + video clips from the source video
ffmpeg -y -loglevel error -ss 5 -t 2 -i "$SRC_VIDEO" \
  -vf "fps=10,scale=240:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse" motion.gif
ffmpeg -y -loglevel error -ss 5 -t 4 -i "$SRC_VIDEO" -vf "scale=640:-2" -r 30 -c:v libx264 -pix_fmt yuv420p -crf 26 -an clip.mp4
ffmpeg -y -loglevel error -ss 5 -t 4 -i "$SRC_VIDEO" -vf "scale=640:-2" -r 30 -c:v libvpx-vp9 -b:v 600k -an clip.webm

# a clean vector mark
printf '%s' "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#6d28d9'/><stop offset='1' stop-color='#0d9488'/></linearGradient></defs><rect width='320' height='180' rx='16' fill='url(#g)'/><circle cx='160' cy='78' r='34' fill='none' stroke='white' stroke-width='6'/><text x='160' y='150' font-family='sans-serif' font-size='20' fill='white' text-anchor='middle' font-weight='600'>vector · svg</text></svg>" > vector.svg

# spoken audio via ElevenLabs (kept as-is if no API key)
if [ -n "${ELEVENLABS_API_KEY:-}" ]; then
  curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"text\":\"${SPEECH}\",\"model_id\":\"eleven_multilingual_v2\",\"output_format\":\"mp3_44100_128\"}" \
    -o voice.mp3
fi
ffmpeg -y -loglevel error -i voice.mp3 -c:a libvorbis -q:a 4 voice.ogg
ffmpeg -y -loglevel error -i voice.mp3 voice.wav

echo "regenerated media in $(pwd)"
