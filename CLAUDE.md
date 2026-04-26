# CLAUDE.md

## Project
`llming-stage` is the **Vue + Quasar SPA foundation** that pairs with
[`llming-com`](https://github.com/Alyxion/llming-com) — a Python WebSocket session
framework with HMAC cookie auth, a per-session command dispatcher (`WSRouter` for
reactive WS commands, `@command` / `build_command_router` for HTTP commands), and an
AI-debug API. The purpose of `llming-stage` is to unite that session framework with a
Vue + Quasar single-page application, so that AI agents can drive and debug a live UI
through the session framework's existing APIs without any bespoke frontend wiring.

Concretely, `llming-stage` ships:
- A Vue + Quasar SPA shell with a client-side router (views swap without page reload).
- Vendored JS libs, CSS, fonts, and icon/emoji archives served via hardened Starlette routes.
- Automatic loading of the llming-com `LlmingWebSocket` JS client on every view — so every
  view starts already capable of speaking to llming-com's WebSocket endpoint.

## User-Facing Docs Stay User-Facing
Sample READMEs, the top-level README, and the MkDocs site must answer
one question for the reader: **"what does this do for me and how do I
run it?"** They must NOT drag readers into maintainer concerns.

Never put the following in user-facing docs:

- Supply-chain mechanics — upstream registries, tarball URLs, SHA
  sums, how vendored files got into the repo.
- `THIRD_PARTY.md` cross-references. That file is for the
  maintainer's license audit; users do not need to click it.
- "One-time maintainer actions" — bundling scripts, rebundling
  instructions, version-pinning workflow.
- Provenance prose about where a file came from, unless it is the
  **one** sentence needed to license-attribute it inline.

If a vendored detail leaks into a user-facing doc, move it here (or to
`THIRD_PARTY.md` for pure license provenance) and leave the user-facing
doc with only what the user cares about: *the thing works, here is how
to run it.*

## Documentation Wording — Describe, Don't Assume
Readers arriving at `llming-stage` cold do not know what `llming-com` is. In
every document (README, `docs/**`, sample READMEs, top-of-module docstrings),
the **first** mention of `llming-com` must describe its function in plain
terms before (or alongside) naming it. After the first mention, either the
name or a descriptive shorthand is fine.

Preferred descriptors (pick one that fits the context):

- "a Python WebSocket session framework with HMAC cookie auth and an AI-debug API"
- "the per-session WebSocket + command framework"
- "the transport + session layer"
- "the session framework" (shorthand, after a full introduction in the same doc)

Bad (assumes knowledge): *"Vue + Quasar wired to llming-com."*
Good: *"A Vue + Quasar shell wired to `llming-com`, a per-session WebSocket
framework with HMAC cookie auth and a built-in AI-debug API."*

Code (imports, type hints, API names) always uses the real name — this rule
only governs prose.

## llming-com is MANDATORY
`llming-com` is not an optional integration. It is the *reason* `llming-stage` exists —
the whole point is AI-driven UI development plus remote debugging through llming-com's
debug API. Rules:

- `pyproject.toml` lists `llming-com` as a required runtime dependency. Do not remove it.
- `mount_assets()` mounts the llming-com static directory under `<prefix>/llming-com/`
  and raises `RuntimeError` at call time if `llming-com` cannot be imported. Do not
  silence that error — a broken install should fail loudly.
- The shell HTML loads `<prefix>/llming-com/llming-ws.js` before `loader.js` and
  `router.js`, so `window.LlmingWebSocket` is globally available to every view module.
  Do not make this lazy — every view in the ecosystem assumes it.
- Tests must keep verifying that the llming-com client JS is both served and referenced
  from the shell (`tests/test_shell.py::test_llming_com_client_served` and
  `test_shell_includes_llming_com_client`).

If a future change would let `llming-stage` function without `llming-com`, stop — that
breaks the whole architectural premise. Push back and clarify with the user before
proceeding.

## Communication Model — NORMATIVE
Every interactive feature in an llming-stage app must fit exactly one of three channels.
The full rationale lives in `docs/content/communication-model.md`; the summary here is
non-negotiable:

1. **WebSocket is the primary channel.** *All major, reactive communication flows through
   one per-user WebSocket session from the session framework.* One session per user (not
   per tab, not per view). All reactive WS commands are `WSRouter` handlers mounted on the
   session's controller — never ad-hoc REST routes, never a second socket, never SSE,
   never long-polling. Server→client pushes use the same socket. This is what makes the
   app AI-debuggable; logic that routes around the session is invisible to the debug API.

2. **HTTP GET/POST is narrowly scoped.** Permitted only for (a) large file transfer and
   (b) hash-addressable caching. Every HTTP endpoint must authenticate through the same
   session-framework cookie (`AuthManager.get_auth_session_id`). Endpoints must stay
   idempotent or content-addressed — they must not model reactive state transitions. A
   POST that changes session state without telling the WebSocket will desync the AI's
   view of the world.

   **Prefer `@command` over plain `@app.post`.** The canonical mechanism for an HTTP
   endpoint in this stack is the session framework's `@command(...)` decorator combined
   with `build_command_router(registry, prefix="/cmd")`. One declaration gives you the
   REST route, parameter coercion, *and* automatic MCP-tool exposure so AI agents can
   invoke the endpoint they already introspect. Drop to a raw FastAPI route only when
   the endpoint is genuinely a blob mover with no command semantics.

3. **Static deploy must stay possible.** An llming-stage app that needs no server
   reactivity must be deployable as a purely static bundle (GitHub Pages, S3, any CDN).
   This is the major architectural differentiator from NiceGUI. `render_shell(config)`
   returns a fixed HTML string; vendor JS, fonts, icon zips, locale packs, and
   `llming-ws.js` are all snapshottable static files. Never add server-side rendering,
   per-request shell mutation, or any host-app dependency that would break a static
   bundle build.

When reviewing or writing code, apply the decision tree from
`docs/content/communication-model.md`:

```
reactive / server-push?        → WSRouter handler over the WebSocket
large file or cache-friendly?  → HTTP (cookie-authed, idempotent)
neither, no server state?      → pure client-side, no network call
```

Anti-patterns that are NOT acceptable, even as stopgaps:
- Second WebSocket "because the first one is busy."
- REST endpoint that wraps an existing `WSRouter` handler (reactive logic must live
  on the socket).
- `@command` used for reactive state transitions (use `WSRouter` for that;
  `@command` is for idempotent or content-addressed HTTP).
- Hidden out-of-band `fetch()` calls during navigation.
- HTTP polling loops pretending to be reactive.

If a proposed change violates any of these rules, stop and flag it rather than applying it.

## Scope — Out of Bounds

`llming-stage` ships **only general-purpose UI primitives**: SPA shell,
router, vendor libraries needed to render an app in the browser
(charting, 3D, code editing, terminal emulation, markdown, math,
diagrams, sanitisation). It does **not** ship document-format libraries.

The following are explicitly out of scope and live in a separate
**document-handling library** (the `llming-docs` / future doc package):

- Spreadsheet generation / parsing (`xlsx` / SheetJS, `exceljs`, …).
- Presentation generation (`pptxgenjs`, …).
- Word-processor formats (`docx`, …).
- PDF generation / parsing.
- DOM-to-image / DOM-to-canvas exporters used purely to *produce*
  document artefacts (e.g. `html2canvas` when used for export).

If a library's primary purpose is producing or consuming a document
file format, it does **not** belong in `llming_stage/vendor/`. Apps
that need document workflows must depend on the doc library
separately. Keep `llming-stage` focused on the UI surface itself.

## No External Network — STRICTLY ENFORCED (EU privacy)

`llming-stage` ships every asset its rendered pages need. The runtime
**must not** fetch from any external host — no Google Fonts, no
jsDelivr, no unpkg, no cdnjs, no analytics or tag-manager beacons.
This is a privacy / GDPR commitment: a user opening an `llming-stage`
app makes no requests beyond the app's own origin.

Concretely:

- No `<script src="https://…">`, no `<link href="https://…">`, no
  `@import url('https://…')` in any code we control (shell, samples,
  docs).
- No `fetch()`, `import()`, `new Image()`, or `navigator.sendBeacon()`
  pointing at a third-party host in our JS.
- All fonts, icons, charting libs, code-editor libs, etc. must be
  vendored locally — see `THIRD_PARTY.md` for the canonical list.
- License-attribution URLs as comments inside vendor files are fine
  (they're text, not network calls). Active runtime fetches are not.

Two tests guard this:

1. `tests/test_no_external_network.py` — static scan of every
   non-vendor file for known CDN/analytics hosts.
2. `tests/e2e/test_no_external_network.py` — runs the gallery + a
   few samples through Chromium and asserts every network request
   stayed on `127.0.0.1` / `localhost`.

If you need to add a new third-party library, vendor it (npm tarball
+ SHA, recorded in `THIRD_PARTY.md`). Never link to a CDN.

## License Policy — STRICTLY ENFORCED
This repository is MIT-licensed. The following rules are non-negotiable:

- **NEVER** add any dependency, vendored file, or asset licensed under AGPL, GPL, or LGPL.
  These licenses have copyleft provisions that would "infect" this repository and all
  downstream consumers.
- Only MIT, Apache 2.0, BSD (2/3-clause), ISC, CC0, CC-BY, and SIL OFL are acceptable.
- Before adding ANY third-party library, asset set, font, or resource:
  1. Verify its license explicitly. Read the LICENSE file in the
     upstream tarball — do not trust headers in minified files.
  2. Prefer **canonical npm registry tarballs** (`registry.npmjs.org`)
     over CDN-stripped distributions. Verify the SHA the registry
     advertises matches the downloaded tarball before extracting.
  3. Add an entry to `THIRD_PARTY.md` with: name, version, license,
     source URL **including the registry tarball URL and SHA-1**, and
     what it's used for.
  4. If the license is unclear or dual-licensed with a copyleft option,
     do NOT add it — ask first.
- The `llming_stage/vendor/` directory and all zip archives in `llming_stage/assets/` contain
  third-party code. Every file in these locations MUST be tracked in `THIRD_PARTY.md`.

## Third-Party Resource Tracking
`THIRD_PARTY.md` in the repo root is the single source of truth for all vendored/bundled
resources. It must be updated in the SAME commit that adds or updates any third-party
resource. Never commit a vendored file without updating this table.

## Loading Strategy
All components MUST be lazy-loaded on demand. Only the critical shell (Vue, Quasar core,
fonts) loads on initial page load. Everything else (KaTeX, Mermaid, Three.js, Plotly,
DOMPurify, icons, emoji, locale packs, view modules) loads when first needed.
Page load time must be near-instant.

## Security
All asset serving routes MUST enforce path traversal hardening: whitelist-only routing,
path canonicalization, dangerous pattern rejection, extension whitelist
(`.js`, `.css`, `.woff2`, `.svg`, `.json`, `.mjs` only), no directory listing, symlink
rejection. See `llming_stage/asset_server.py` and `llming_stage/zip_server.py`.

## No NiceGUI Dependency
`llming-stage` has ZERO NiceGUI dependencies. It mounts onto any Starlette/FastAPI app.

## No Customer-Specific Content
This is a generic open-source package. Do not hardcode customer names, internal URLs,
or any organization-specific identifiers. See the pre-commit guard below for the set
of terms that are blocked from ever being committed.

## Documentation
- Documentation lives in `docs/content/` and uses MkDocs (mkdocs-material).
- Every public API, configuration option, and asset group must be documented.
- Run `mkdocs serve -f docs/mkdocs.yml` from the repo root to preview locally.

## Build & Publish
- Build tool: Poetry.
- Run `python -m llming.publish_guard ../llming-stage` before any PyPI publish.
- After publishing, update `docs/pypi-packages.md` in the orchestrator repo to add the
  new `llming-stage` version.

## Forbidden Content — Pre-Commit Enforced
This repo has a pre-commit hook that blocks commits containing customer-specific or
domain-specific terms. The hook scans all staged files and rejects the commit if any
match is found. The patterns are defined as regex in `scripts/content_guard.py` and
must not be bypassed with `--no-verify`.

Do NOT add any content that would trigger the hook. If you are unsure, run the check
manually before committing:

```bash
python scripts/content_guard.py
```

Or via Poetry:

```bash
poetry run content-guard
```

## Pre-Commit Hook Setup
After cloning, install the content guard hook:

```bash
cp .pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

The hook runs automatically on every commit. Do NOT use `--no-verify` to bypass it.
