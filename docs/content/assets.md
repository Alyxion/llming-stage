# Assets

All assets are served under a single configurable prefix. The default
prefix is `/_stage/`. The leading underscore signals framework-internal,
avoids collision with app routes, and mirrors the convention from
NiceGUI (`/_nicegui/`).

## Route map

| Path | Source | Content |
|------|--------|---------|
| `/_stage/vendor/*` | `llming_stage/vendor/` | Vue, Quasar, Three, Plotly, KaTeX, DOMPurify |
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
