# Media bundle gallery

One downloaded `.zip` → **images, video and audio**, all decoded in the
browser. Shows both ways to point a media element at bundle data.

## What it shows

- **`stage.serve_bundle("media", "media_src")`** zips `media_src/` on demand
  (re-built automatically when the folder changes) and serves it at
  `/bundles/media.zip`.
- The view downloads that bundle **once**, unzips it in the browser, and
  renders every entry:
  - **images** — `logo.{png,jpg,webp}`, an animated `motion.gif`, a `vector.svg`
  - **video** — `clip.{mp4,webm}` (with `controls`, seekable)
  - **audio** — `voice.{mp3,ogg,wav}` — a spoken intro (with `controls`)
- Each card is tagged with the access mechanism it uses:
  - **blob url** — `handle.url(path)` returns a typed object URL.
  - **service worker** — `handle.src(path)` returns a literal
    `/__stage_bundle__/media/<path>` URL served by the bundle service worker,
    with HTTP Range support so `<video>`/`<audio>` can seek.

```js
img.src   = media.url('logo.webp');    // blob URL
video.src = media.src('clip.mp4');     // /__stage_bundle__/media/clip.mp4 (Range/seek)
```

The image is a logo, the video is a clip scaled down from a high-resolution
source, and the audio is a short spoken intro generated with ElevenLabs.
Regenerate with `./regenerate.sh` (see the script header for the source
assets and the optional `ELEVENLABS_API_KEY`).

## Run

```bash
python main.py
# open http://127.0.0.1:8765
```
