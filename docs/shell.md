# App shell

The shell is a single HTML document that boots Vue + Quasar once, then
hosts whatever view the SPA router navigates to. Navigating between
routes does **not** reload the page; the router calls the previous
view's `unmount()` and the next view's `mount()`.

## What the shell loads on first visit

Only the critical path — everything else is lazy:

| Asset | Size (approx) | Loaded at |
|-------|---------------|-----------|
| `vue.global.prod.js` | 150 KB | shell boot |
| `quasar.umd.prod.js` | 500 KB | shell boot |
| `quasar.prod.css` | 200 KB | shell boot |
| `fonts.css` + Roboto/Material Icons | ~350 KB | shell boot |
| `llming-com/llming-ws.js` | <10 KB | shell boot |
| `loader.js` | <2 KB | shell boot |
| `router.js` | <3 KB | shell boot |
| Everything else | see [Lazy loading](lazy-loading.md) | on demand |

After the shell boots, `window.LlmingWebSocket` is available to every
view module. See [llming-com integration](llming-com.md) for how to
open a session.

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

## Writing a view module

A view module is any JavaScript file that registers itself with
`window.__stageViews`:

```js
// home.js — served from wherever your app hosts it
window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  mount(target, params) {
    target.innerHTML = '<h1>Home</h1>';
    return {
      unmount() { target.innerHTML = ''; }
    };
  },
};
```

Then teach the loader where to find it. In your host app, inline a small
registration snippet in `extra_head` or serve your view file under a
path your shell knows about:

```js
window.__stage.register('home', { js: '/my-app/home.js' });
```

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

Because the shell is one HTML document, any `LlmingWebSocket` opened
by an earlier view stays connected while the user moves between views.
Views that need view-specific context should send a "context" message
over the same socket rather than opening a new one.

For the full integration story — opening sessions, auth cookies, the
AI debug API — see [llming-com integration](llming-com.md).
