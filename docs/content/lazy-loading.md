# Lazy loading

Only the critical shell ships on first paint. Every other vendor library
loads the first time it is needed, and every subsequent request is a
no-op.

## The orchestrator

`loader.js` exposes `window.__stage`:

```js
await window.__stage.load('mermaid'); // fetches + parses mermaid, once
await window.__stage.load('mermaid'); // returns the SAME cached Promise
```

The cache holds the load Promise per name, so:

- **Concurrent calls** during the first load all share one in-flight
  Promise — only one network fetch, only one `<script>` tag.
- **Repeated calls** after resolution return the same Promise instance
  with zero allocation. `await __stage.load('plotly')` before every
  chart render is the intended idiom — the cost after the first call
  is a single `Map.get()`.
- **Failures** evict the cache entry so the next call retries.

A synchronous helper `__stage.isLoaded(name)` returns `true` once the
lib is ready, for code that wants to branch without awaiting.

## Built-in registrations

The loader ships with these components pre-registered:

| Name | Triggered by (suggested) |
|------|--------------------------|
| `katex` | First `$…$` or `$$…$$` rendered |
| `mermaid` | First ```mermaid fenced block rendered |
| `dompurify` | First untrusted HTML sanitized |
| `three` | First 3D scene created |
| `plotly` | First chart drawn |

The library does not trigger these itself; app code decides *when* to
call `load()`.

## Registering custom components

Any app may add its own registrations:

```js
window.__stage.register('xlsx', { js: 'vendor/xlsx.full.min.js' });
window.__stage.register('my-view', { js: 'views/my-view.js' });
```

`register()` accepts:

| Key | Meaning |
|-----|---------|
| `js` | Classic script (loaded via a `<script>` tag) |
| `module` | ES module (loaded via dynamic `import()`) |
| `css` | Stylesheet (loaded via a `<link>` tag) |
| `bundle` | Array of nested entries — loaded sequentially |

A single name may combine `js` + `css` (both load in parallel):

```js
window.__stage.register('katex', {
  js: 'vendor/katex.min.js',
  css: 'vendor/katex.min.css',
});
```

## View modules

View modules are just another lazy-loaded component. The SPA router
calls `__stage.load(viewName)` before invoking `mount()`, so your view
only needs to be registered:

```js
window.__stage.register('home', { js: '/my-app/home.js' });
window.__stage.register('chat', { js: '/my-app/chat.js' });
```

## Fonts

Fonts are *not* lazy-loaded — they ship in the shell. Loading fonts on
demand usually causes a visible FOUT (flash of unstyled text) on the
first view. The combined Roboto + Material Icons cost is ~350 KB, which
is comparable to a single lazy library.
