# App shell

For new apps, prefer the OOP [Stage apps](stage.md) API:

```python
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app).view("/", "home.vue")
```

This page documents the lower-level shell primitives that `Stage` uses
internally.

The shell is a single HTML document that boots Vue + Quasar once, then
hosts whatever view the SPA router navigates to. Navigating between
routes does **not** reload the page; the router calls the previous
view's `unmount()` and the next view's `mount()`.

Tailwind utilities are bundled and loaded once by the shell. App views
can use utility classes directly in `.vue` templates without shipping a
local CSS file.

## Tailwind

Tailwind is a first-class shell asset, not an app dependency. The shell
loads `/_stage/vendor/tailwindcss.browser.global.js` once, next to Vue
and Quasar, and provides this built-in Tailwind entrypoint:

```css
@import "tailwindcss/theme";
@import "tailwindcss/utilities";
@custom-variant dark (&:where(.body--dark, .body--dark *));
```

What that means for app authors:

- Use Tailwind classes directly in `.vue` templates:
  `class="min-h-screen grid place-items-center p-8"`.
- Use `dark:` variants normally. They follow Quasar dark mode because
  the shell maps Tailwind's `dark:` variant to Quasar's `body--dark`
  class.
- Do not add Tailwind, Vue, Quasar, fonts, or icons in every app. The
  shell owns those assets once under `/_stage`.
- Do not use sample-local CSS for ordinary layout or decoration. Prefer
  Tailwind utilities and Quasar components.
- Tailwind preflight is intentionally not loaded. Preflight would reset
  Quasar and host-app styles globally.
- The bundled browser build supports Tailwind theme + utilities, but
  not Node-side Tailwind config files or plugins. If an app needs a
  custom production build pipeline, use the lower-level shell module path
  and serve that built output yourself.

## What the shell loads on first visit

Only the critical path — everything else is lazy:

| Asset | Size (approx) | Loaded at |
|-------|---------------|-----------|
| `vue.global.prod.js` | 150 KB | shell boot |
| `quasar.umd.prod.js` | 500 KB | shell boot |
| `quasar.prod.css` | 200 KB | shell boot |
| `tailwindcss.browser.global.js` | 270 KB | shell boot |
| `fonts.css` + Roboto/Material Icons | ~350 KB | shell boot |
| `llming-com/llming-ws.js` | <10 KB | shell boot |
| `loader.js` | <2 KB | shell boot |
| `router.js` | <3 KB | shell boot |
| Everything else | see [Lazy loading](lazy-loading.md) | on demand |

After the shell boots, Vue views use `this.$stage.connect()` and
`this.$stage.send(...)`. Direct `window.LlmingWebSocket` access remains
available for lower-level integrations. See
[llming-com integration](llming-com.md).

## `ShellConfig`

```python
from llming_stage import ShellConfig

config = ShellConfig(
    title="My App",                      # <title>
    asset_prefix="/_stage",              # URL prefix for assets
    routes=[
        ("/", "home"),                   # pattern → view module name
        ("/chat", "chat"),
        ("/chat/:id", "chat"),
    ],
    preload_views=["home"],              # loaded right after shell boot
    extra_head="<link rel='icon' ...>",  # raw HTML inserted into <head>
    extra_body="",                       # raw HTML inserted at end of <body>
)
```

## View modules

For application code, prefer `Stage(app).view("/", "home.vue")`.
`Stage` transforms the Vue file and registers the generated module with
the shell. The lower-level `ShellConfig(view_modules=...)` path remains
available for framework integrations that already own their module
pipeline.

Once registered, navigating to the route triggers:

1. `window.__stage.load('home')` — fetches `home.js` (once).
2. The router calls `window.__stageViews.home.mount(target, params)`.
3. On the next navigation, `unmount()` runs, then the next view mounts.

## Client-side navigation

Any anchor with `data-stage-link` is intercepted by the router:

```html
<a data-stage-link href="/chat">Open chat</a>
```

Or navigate programmatically:

```js
window.__stageRouter.navigate('/chat');
window.__stageRouter.navigate('/chat', { replace: true });
```

## WebSocket sessions survive navigation

Because the shell is one HTML document, the `$stage` socket stays
connected while the user moves between views. Views that need
view-specific context should send a `SessionRouter` command over the
same socket rather than opening a new one.

For the full integration story — opening sessions, auth cookies, the
AI debug API — see [llming-com integration](llming-com.md).
