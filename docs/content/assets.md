# Assets

All assets are served under a single configurable prefix. The default
prefix is `/_stage/`. The leading underscore signals framework-internal,
avoids collision with app routes, and keeps app-owned routes clean.

## Route map

| Path | Source | Content |
|------|--------|---------|
| `/_stage/vendor/*` | `llming_stage/vendor/` | Vue, Quasar, Tailwind browser bundle, Three, Plotly, KaTeX, DOMPurify |
| `/_stage/fonts/*` | `llming_stage/fonts/` | All bundled fonts — Roboto, Material Icons, Material Symbols, KaTeX (`fonts/katex/`) — and `fonts.css` |
| `/_stage/lang/*` | `llming_stage/lang/` | 71 Quasar locale packs |
| `/_stage/icons/*` | `llming_stage/assets/phosphor-icons.zip` | Phosphor Icons, 6 weights |
| `/_stage/tabler/*` | `llming_stage/assets/tabler-icons.zip` | Tabler Icons (outline + filled, ~6000 SVGs) |
| `/_stage/emoji/*` | `llming_stage/assets/noto-emoji.zip` | Noto Emoji SVG set |
| `/_stage/llming-com/*` | `llming_com/static/` (from the installed `llming-com` wheel) | `LlmingWebSocket` client JS |
| `/_stage/loader.js` | `llming_stage/static/loader.js` | Lazy-load orchestrator |
| `/_stage/router.js` | `llming_stage/static/router.js` | SPA router |

## Vendor libraries

Each vendor file is referenced from `loader.js` (see
[Lazy loading](lazy-loading.md)). The intent is that app code never
hardcodes a `/_stage/vendor/foo.js` URL directly — instead, it calls
`window.__stage.load('foo')` and lets the loader resolve the path.

Vue, Quasar, and Tailwind are shell-level assets and load once on first
visit. Tailwind is served locally as
`/_stage/vendor/tailwindcss.browser.global.js` and the shell imports
`tailwindcss/theme` + `tailwindcss/utilities`, not preflight, so it does
not globally reset Quasar or host-app styles.

The shell also defines Tailwind's `dark:` variant against Quasar's
`body--dark` class. This keeps all theme behavior under one switch:
`Quasar.Dark.set(...)` updates Quasar components and Tailwind dark
utilities together.

## Fonts

Every font ships from a single tree under **`/_stage/fonts/`** so app
code never has to remember which family lives where. The shell loads
`fonts.css` for you on every page; KaTeX's CSS reaches into the same
tree when math is rendered.

```
/_stage/fonts/                     ← single URL prefix, single dir
├── fonts.css                       Roboto + Material Icons + Material Symbols
├── *.woff2  (49 files)             Roboto subsets, Material variants
└── katex/
    └── KaTeX_*.woff2  (20 files)   KaTeX math fonts
```

Family inventory:

| Family | Variants | Files |
|---|---|---|
| **Roboto** | thin, light, regular, medium, bold, black — across Latin / Latin-ext / Cyrillic / Cyrillic-ext / Greek / Greek-ext / Vietnamese / symbols / math | 42 |
| **Material Icons** | regular, outlined, round, sharp | 4 |
| **Material Symbols** | outlined, rounded, sharp | 3 |
| **KaTeX** | AMS, Caligraphic, Fraktur, Main, Math, SansSerif, Script, Size 1–4, Typewriter | 20 |

Page authors only ever need:

```html
<link rel="stylesheet" href="/_stage/fonts/fonts.css">
```

The shell does this automatically. Browsers pick the appropriate
Roboto subset on demand via `unicode-range`, so a Latin-only page
fetches a few KB even though the directory has 42 Roboto files
sitting there for international users.

A page that doesn't render math never fetches KaTeX fonts — the
`@font-face` rules for them only ship inside `vendor/katex.min.css`,
which itself is lazy-loaded.

## Phosphor icons & Noto emoji

Thousands of small SVG files are served from zip archives so the wheel
file listing stays short. The archive is opened once at mount time as a
thread-safe, read-only `ZipFile`; requests read entry bytes directly
from memory via `ZipFile.read(name)`. No SVG is ever extracted to disk.

Entry names are validated at archive open time. Any entry whose name
would fail the same path-safety checks applied to filesystem routes is
silently dropped from the whitelist.

To request a single icon:

```
GET /_stage/icons/regular/house.svg
GET /_stage/icons/bold/house.svg
GET /_stage/emoji/emoji_u1f436.svg
```

## Quasar locale packs

Quasar ships its translations as 71 separate `.umd.prod.js` files. The
default locale is the English built-in bundled inside `quasar.umd.prod.js`.
Only load a locale pack when the user's preference is not English:

```js
await window.__stage.load('lang-de'); // not auto-registered — see below
```

`loader.js` does **not** pre-register every locale. Call
`window.__stage.register(name, entry)` for the locales your app actually
supports:

```js
window.__stage.register('lang-de', { js: 'lang/de.umd.prod.js' });
```

## Shared hosting & bundle versioning

The whole asset tree under `/_stage/...` is identical for every app
built against the same `llming-stage` release. When you run many apps
behind one server, you can host the bytes **once** at a shared mount and
point every app's shell at it.

### The two version stamps

Two version strings live in `llming_stage`, on purpose distinct:

- **`__version__`** — the Python package version (from `pyproject.toml`).
  Bumps many times per month for Python-side fixes. **Apps do not pin
  against this.**
- **`LIB_VERSION`** — the **vendor-bundle version** (calendar format
  `YYYY-MM`, e.g. `"2026-05"`). Bumps **only** when a file under
  `llming_stage/{vendor, fonts, lang, assets}/` is swapped — typically a
  few times per year. The same string is stamped at the top of
  `THIRD_PARTY.md`; a test (`tests/test_lib_version_sync.py`) enforces
  they cannot drift.

An app written against today's Plotly may break under a future Plotly
3.x. `LIB_VERSION` is what an app pins against to keep its old vendor
surface alive on a shared host that has been updated.

### Resolution rule

```python
Stage(app, lib_version="2026-05")
```

Decision happens at shell-render time, by comparing the pinned string to
the currently-installed `LIB_VERSION`:

| App pin | Installed `LIB_VERSION` | Shell emits |
|---------|-------------------------|-------------|
| `None` (no pin) | any | `/_stage/vendor/…` (latest, current path) |
| same as installed | matches | `/_stage/vendor/…` (no rewrite) |
| older than installed | newer | `/_stage/v2026-05/vendor/…` (versioned) |

The latest bundle therefore **always** sits at the current path. Old
apps only get the `/v<YYYY-MM>/` segment if they pinned an older
version *and* you chose to keep that bundle published on the shared
host. Pinning the bundle currently in use is a no-op — encouraged for
new apps, since the pin only "activates" once that bundle stops being
the latest.

### Shared-host workflow

The `llming-stage export-assets` CLI dumps the *currently-installed*
package's vendor bundle as a complete static tree:

```bash
# 1. Install the current llming-stage and dump it into the unversioned mount
pip install llming-stage==0.1.5
llming-stage export-assets --out /var/www/_stage

# 2. When LIB_VERSION later changes, archive the OLD bundle at /v<YYYY-MM>/
#    BEFORE upgrading the unversioned mount. In a separate venv:
pip install llming-stage==0.1.5     # the release that ships LIB_VERSION='2026-05'
llming-stage export-assets --out /var/www/_stage/v2026-05

# 3. Now refresh the unversioned mount with the new bundle
pip install llming-stage==0.2.0     # ships LIB_VERSION='2026-11'
llming-stage export-assets --out /var/www/_stage
```

The dump tree contains `vendor/`, `fonts/`, `lang/`, `llming-com/`,
`icons/`, `emoji/`, `tabler/`, `loader.js`, `router.js`, and a
`manifest.json` with `lib_version` and `pkg_version`. Partial dumps are
not supported — replace the destination whole or not at all. Use
`--no-manifest` to skip the audit file if you don't want it served.

### Pointing apps at the shared mount

Every app uses the standard `asset_prefix` knob, optionally combined
with a `lib_version` pin:

```python
# Same-origin shared subpath, no pin: app always rides the latest bundle.
Stage(app, asset_prefix="/shared/_stage")

# Pinned to 2026-05: shell emits unversioned URLs while that's still the
# current bundle; the day 2026-11 ships, this app's shell starts emitting
# /shared/_stage/v2026-05/... and keeps working.
Stage(app, asset_prefix="/shared/_stage", lib_version="2026-05")
```

For self-reporting in the browser, the shell sets
`window.__stageLibVersion` to the bundle the page is actually loading
(`LIB_VERSION` when there's no rewrite, the pinned string when there
is). This is a debug surface — nothing in the runtime reads it.

### What gets pinned

Bundle version pinning is **whole-snapshot**: one `lib_version=` covers
JS/CSS libraries (Plotly, Three, Mermaid, …), fonts, icon archives,
locale packs, and the llming-com client JS together. There is no
per-library or per-category dial today; that's a deliberate
simplification matched to a real-world cadence (a few refreshes per
year). Per-category versioning can layer on later without breaking the
current API.

### Operator caveats

- `Stage.build(out_dir)` refuses when the Stage is pinned to a bundle
  different from the installed one — the static build can only snapshot
  the bytes the package actually owns. To archive an older bundle,
  install that older `llming-stage` into a separate venv and run
  `llming-stage export-assets`.
- `Stage(...)` does **not** mount the currently-installed files under an
  older `/v<YYYY-MM>/` prefix. If the shell rewrites to an archived
  bundle, the shared host must actually serve that archive; otherwise
  the browser gets a clear 404 instead of silently loading incompatible
  current bytes.
- Pinning a bundle the shared host has **not** published (newer or
  older) is silent at build time but produces 404s in the browser.
  Inspect `manifest.json` on each archived directory to audit what's
  actually live.
- The `lib_version` string is regex-validated (`\d{4}-\d{2}(-\d+)?`) at
  `Stage.__init__`. Anything else — semver, slashes, traversal —
  raises `ValueError` before any URL is built.
