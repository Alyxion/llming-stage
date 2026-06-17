# Data bundles

A **data bundle** is a whole file — usually a `.zip` — that the browser
downloads **once**, caches by content hash, and then reads from locally. It is
the foundation for complex apps that load their data (images, video, audio,
JSON, model files, locale packs, an entire mini-site) up front and then run
**offline**, with no further per-asset server round-trips.

This is distinct from the icon/emoji archives (see [Assets](assets.md)): those
are unzipped *on the server*, one entry per request, and need the server to
stay reachable. A data bundle is downloaded whole and unzipped *in the
browser*, so it keeps working with no network.

```
reactive / server-push?        → WSRouter over the WebSocket
large file, downloaded once?   → data bundle (this page)
many tiny files, server-side?  → zip-backed asset route (Assets)
```

## Serving a bundle

There are two server-side helpers, both of which serve the file with its
**content hash as the HTTP `ETag`** and `Cache-Control: no-cache`, so a cached
client revalidates with `If-None-Match` and gets a `304` until the bytes
change. There is **no manifest** — every file answers for itself.

### A directory of ready-made files

`Stage.mount_bundles(directory)` serves every `.zip` / `.json` / `.bin` under
*directory* at `/bundles/*`:

```python
from llming_stage import Stage

stage = Stage(app)
stage.mount_bundles("data")          # data/foo.zip → /bundles/foo.zip
```

Re-prepare a file in place and the client picks up the new bytes automatically
(the ETag is keyed by `(path, mtime, size)`, so overwriting it yields a new
hash with no bookkeeping).

### A self-building bundle from a source directory

`Stage.serve_bundle(name, source)` zips *source* **on demand** and re-zips it
**only when its contents change** — no build step, no watcher:

```python
stage.serve_bundle("media", "media_src")   # zips media_src/ → /bundles/media.zip
```

Edit, add, or remove any file under `media_src/` and the next request gets a
freshly built zip with a new ETag; an unchanged tree returns the cached bytes.
Under the hood this is a [`BundleBuilder`][builder] that takes a per-file
mtime/size *signature* of the tree and rebuilds when it differs.

For non-`Stage` apps the same primitives are free functions:

```python
from llming_stage import mount_bundles, mount_bundle_builder

mount_bundles(app, "data")                                  # static dir
mount_bundle_builder(app, "media_src", url="/bundles/media.zip")  # self-building
```

[builder]: api.md

## Loading a bundle in the browser

The client API is `window.__stageBundles`, lazily loaded the first time a view
calls `window.__stage.load('bundles')`. It downloads the bundle, unzips it with
the bundled [`fflate`](assets.md) library, and caches the entries in IndexedDB.

```js
await window.__stage.load('bundles');                 // ensures __stageBundles
window.__stageBundles.define('media', { url: '/bundles/media.zip' });

const media = await window.__stageBundles.load('media');   // gate: ready before use
```

| Call | Purpose |
|------|---------|
| `load(name[, opts])` | Download + unzip + cache; resolves to a **handle**. Deduped and memoised — `await load(name)` after the first time is a near-free idempotent gate you can put in front of any render. |
| `prefetch(name[, {idle}])` | Fire-and-forget warm-up. `{idle: true}` schedules it via `requestIdleCallback` so it doesn't compete with the active view. |
| `refresh(name)` | Force a re-validation against the server in the current session (`load` is memoised and won't re-fetch on its own). |
| `check(name)` | `HEAD` probe → `true` if the server hosts a newer version than the cached one. |
| `serve()` | Register the bundle service worker (see [Accessing media](#accessing-images-video-and-audio)). |
| `define(name, {url})` | Register a source so later calls can use just the name. |

!!! note "First load always revalidates"
    `load()` issues **one conditional GET** the first time it runs on a page,
    so a fresh load automatically picks up a re-prepared bundle (`304` from
    cache, or `200` with new bytes). If the server is unreachable it falls
    back to the cached copy — that is what makes the app work offline.

### Reading entries — the handle

```js
media.list()          // → ['photo.webp', 'clip.mp4', 'config.json', …]
media.has('x.json')   // → boolean
media.bytes(path)     // → Uint8Array | null
media.text(path)      // → string | null
media.json(path)      // → parsed JSON | null
media.url(path)       // → blob: object URL (typed) for <img>/<video>/<audio>
media.src(path)       // → /__stage_bundle__/media/<path> (service worker)
media.revoke()        // free every blob URL this handle minted
media.etag            // the server version tag
```

## Accessing images, video and audio

There are two ways to point a media element at bundle data. Both set the right
content type so the browser decodes the file.

### Blob URLs — `handle.url(path)`

A typed `blob:` object URL. Use it wherever **you** assign `src`:

```js
img.src   = media.url('photo.webp');
video.src = media.url('clip.webm');   // seekable
audio.src = media.url('tone.ogg');
```

`url(path)` memoises, so binding the same path repeatedly in a template is
cheap; call `handle.revoke()` on unmount to release them. Recognised types
include `png · jpg · webp · gif · avif · bmp · svg`, `mp4 · webm · ogv · mov`,
`mp3 · ogg · wav · flac · aac · m4a`, plus `pdf`, fonts and `wasm`.

### Serving media via the service worker — `handle.src(path)`

Blob URLs are perfect when you control the `src`. They **cannot** resolve
*relative* references inside a bundled document (a `page.html` with
`<img src="img/a.png">`, or CSS `url(fonts/x.woff2)`), because a blob URL has
no folder context. For that — and for dropping a **literal path** straight into
`src` — register the bundle service worker once:

```js
await window.__stageBundles.serve();          // registers the worker at scope /
img.src   = media.src('photo.webp');          // /__stage_bundle__/media/photo.webp
video.src = media.src('clip.mp4');            // Range-enabled → <video> seeks
```

The worker intercepts `/__stage_bundle__/<name>/<path>`, serves the entry from
the cached bundle with the correct MIME type, and honours HTTP **Range**
requests (so `<video>`/`<audio>` stream and seek). Relative references inside
bundled HTML/CSS/SVG resolve naturally, and there are no blob URLs to revoke.

| | Blob URL `url()` | Service worker `src()` |
|---|---|---|
| Setup | none | `await serve()` once |
| `<img>` / `<video>` / `<audio>` | ✅ | ✅ |
| Relative refs in bundled HTML/CSS | ❌ | ✅ |
| HTTP Range / large-video seek | whole blob in memory | ✅ real Range |
| Literal path in `src=` | ❌ (needs the URL) | ✅ |
| Cleanup | `revoke()` | automatic |

## Versioning and change detection

The hash **is** the version. To ask whether the server has a newer bundle than
the one cached, the client sends a conditional request — no manifest, no global
state:

```js
if (await __stageBundles.check('media')) {
  const fresh = await __stageBundles.refresh('media');   // pull the new bytes
}
```

Server side, re-preparing a file (or editing a `serve_bundle` source) changes
its ETag automatically. So "is there a newer one?" is a `HEAD`/conditional
`GET` the server answers from the bytes on disk.

For **forward compatibility** on a shared host you can also pin a content-
addressed URL (`media-9f3a.zip`) and serve it `immutable`, mirroring the
[`LIB_VERSION` pinning](assets.md#shared-hosting-bundle-versioning) model — the
"latest, but check" path uses the stable URL plus the conditional request.

## Samples

- **`samples/data_bundle`** — load with progress, prefetch, check-for-newer →
  auto-update, and the service-worker `<img src>` form.
- **`samples/media_gallery`** — one self-built `media.zip` rendered as images
  (`png/jpg/webp/gif/svg`), video (`mp4/webm`) and audio (`mp3/ogg/wav`), using
  both blob URLs and the service worker.
