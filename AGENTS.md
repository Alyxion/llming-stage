# AGENTS.md — guide for AI coding agents

Cross-agent counterpart to `CLAUDE.md`. Read both — the overlap is intentional;
`CLAUDE.md` is the long form, this file is the high-signal checklist.

## What this project is

`llming-stage` is a Python package that mounts a Vue + Quasar SPA shell —
vendor JS/CSS, fonts, icon/emoji/tabler archives, locale packs, a client-side
router, lazy loader, and the `llming-com` WebSocket client — onto any
FastAPI/Starlette app. Pairs with [`llming-com`](https://github.com/Alyxion/llming-com)
for per-session WebSocket + AI-debug.

Built bundle ships under `/_stage/` URL prefix by default. Apps consume it by
calling `Stage(app)` once and writing `.vue` view files.

## Hard rules (must follow)

1. **Pin `lib_version` in new user apps.** When generating `Stage(...)` for a
   user's app (a new `main.py`, a template, a copy-pasteable snippet),
   **always** pass `lib_version="<current>"` as a **string literal**:

   ```python
   stage = Stage(app, lib_version="2026-05")  # ← bake current LIB_VERSION
   ```

   Look up the current value with
   `python -c "import llming_stage; print(llming_stage.LIB_VERSION)"`.

   The literal is what makes the user's app forward-compatible: when the
   shared host later refreshes its bundle, the app's shell auto-rewrites
   URLs to the archived `/v2026-05/` tree and keeps loading the libraries
   it was built against. Using `LIB_VERSION` as a *symbol* defeats the
   point — it always equals "current installed" and provides zero forward
   compatibility. Exception: this repo's own `samples/` and `tests/` do
   **not** pin — they upgrade with the package.

2. **No external network.** Never link to a CDN, Google Fonts, jsDelivr,
   unpkg, cdnjs, analytics beacons, tag managers, etc. All assets are
   vendored. Two tests guard this (`tests/test_no_external_network.py`).

3. **MIT-compatible licenses only.** No AGPL/GPL/LGPL anywhere. Acceptable:
   MIT, Apache 2.0, BSD-2/3, ISC, CC0, CC-BY, SIL OFL. Update `THIRD_PARTY.md`
   in the same commit when adding any vendored file.

4. **WebSocket is the primary channel.** Reactive logic goes on `WSRouter`
   handlers over the single per-user WebSocket session from `llming-com`.
   HTTP is allowed only for (a) large file transfers and (b) hash-addressable
   caches. Prefer `@command(...)` over raw `@app.post(...)` for HTTP — it
   gives REST + MCP-tool exposure in one declaration.

5. **`llming-com` is mandatory.** Every shell loads `llming-ws.js`. Don't
   try to make the package work without it.

6. **Quasar component classes go on Quasar components.** `<div class="q-card">`
   doesn't switch theme in dark mode (Quasar's dark-mode logic lives in the
   `<q-card>` *component*, not the CSS class). Use `<q-card>` directly.
   Same for `q-banner`, `q-chip`, `q-btn`. A test enforces this.

7. **Don't pair `bg-white`/`text-white`/`bg-black`/`text-black` with `dark:`
   variants.** Quasar's `!important` color utilities win. Use `bg-[#ffffff]`
   or `bg-white/100` for arbitrary-value white. A test enforces this.

8. **Don't bypass the pre-commit content guard.** `--no-verify` is not
   allowed. The guard blocks customer/domain-specific terms.

## Where to look

| Topic | File |
|---|---|
| `Stage` API + patterns | `docs/content/stage.md` |
| Asset routes, shared hosting, bundle versioning | `docs/content/assets.md` |
| Communication model decision tree | `docs/content/communication-model.md` |
| Full API reference | `docs/content/api.md` |
| Lazy-loading catalog | `docs/content/lazy-loading.md` |
| Security hardening | `docs/content/security.md` |
| Vendored files + licenses + bundle version stamp | `THIRD_PARTY.md` |
| Runnable examples (do **not** pin `lib_version`) | `samples/` |
| Cross-cutting rules + rationale (long form) | `CLAUDE.md` |

## Commands

```bash
# Install / refresh editable env
poetry install

# Run the unit test suite
poetry run pytest --ignore=tests/e2e

# Run a sample
poetry run python samples/<name>/main.py

# Run the gallery (port 8000, samples land on 8765)
poetry run python samples/gallery.py

# Build docs
poetry run mkdocs build -f docs/mkdocs.yml --strict

# Dump assets for a shared host
poetry run llming-stage export-assets --out /var/www/_stage
```

## Out of scope

- Document-format libraries (xlsx/SheetJS, pptxgenjs, docx, PDF, html2canvas
  *for export*). These belong in a separate doc-handling package.
- Customer-specific names, domains, or internal URLs anywhere in the repo.
- Server-side rendering or per-request shell mutation — must stay
  statically deployable.
