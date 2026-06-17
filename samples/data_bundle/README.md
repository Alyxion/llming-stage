# Offline data bundle

Download a `.zip` **once**, cache it by content hash, and read its contents
in the browser — the foundation for complex apps that load their data up
front and then run offline.

## What it shows

- **`stage.mount_bundles("data")`** serves every file under `data/` at
  `/bundles/*`, each tagged with its content hash as an HTTP `ETag`.
- **`stage.serve_bundle("live", "live_src")`** zips `live_src/` **on demand**
  and serves it at `/bundles/live.zip`, re-zipping automatically whenever the
  directory's contents change — no build step, no watcher.
- **`__stageBundles.load("demo")`** downloads `demo.zip` with a progress bar,
  unzips it in the browser (via the bundled `fflate` library), and caches the
  entries in IndexedDB. A second load is served from cache.
- **`__stageBundles.prefetch(...)`** warms a bundle in the background so the
  view it belongs to renders instantly when reached.
- **`__stageBundles.check("demo")`** asks the server — with a conditional
  request — whether a newer version exists, then `refresh()`es to the new
  bytes. Re-prepare the zip and the client picks it up; leave it and the
  server answers `304`.
- **`__stageBundles.serve()`** registers a service worker so bundle entries
  are reachable at stable literal URLs — `/__stage_bundle__/<name>/<path>` —
  for `<img src>`, `<video src>` (with Range/seek), and relative references
  inside bundled documents, with no blob URLs.

## Accessing media

```js
const media = await window.__stageBundles.load('media');

// Blob URLs — works anywhere you set src yourself:
img.src   = media.url('photos/hero.webp');
video.src = media.url('clips/intro.webm');   // mp4 / webm / ogv, seekable
audio.src = media.url('music/theme.ogg');

// Or literal URLs via the service worker (await __stageBundles.serve() once):
img.src   = media.src('photos/hero.webp');   // /__stage_bundle__/media/photos/hero.webp
```

The view (`home.js`) is plain vanilla JavaScript.

## Run

```bash
python main.py
# open http://127.0.0.1:8765
```
