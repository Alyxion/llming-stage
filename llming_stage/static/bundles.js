// llming-stage data-bundle manager.
//
// Exposes `window.__stageBundles` — a small client for downloading whole
// data files (`.zip`, `.json`, `.bin`) ONCE, caching them by content hash,
// and reading their contents locally so an app can run offline.
//
// It is the client half of `bundle_server.py`: the server tags each bundle
// with its SHA-256 as an `ETag`; this client stores that ETag (with the
// unzipped entries) in IndexedDB and revalidates with `If-None-Match`, so a
// re-prepared bundle is picked up automatically and an unchanged one costs a
// single 304 — or nothing at all, when already in memory.
//
// Public API (all keyed by a logical bundle `name`):
//   __stageBundles.define(name, { url })       register a source
//   __stageBundles.load(name[, opts])  -> Promise<BundleHandle>   (gates render)
//   __stageBundles.prefetch(name[, opts])      fire-and-forget warm-up
//   __stageBundles.check(name)         -> Promise<bool>   newer available?
//   __stageBundles.get(name)           -> BundleHandle | null
//   __stageBundles.isReady(name)       -> bool
//
// A BundleHandle reads entries out of the (unzipped) bundle:
//   handle.list()        -> string[]            entry paths
//   handle.has(path)     -> bool
//   handle.bytes(path)   -> Uint8Array | null
//   handle.text(path)    -> string | null
//   handle.json(path)    -> any | null
//   handle.url(path)     -> string | null       cached object URL (img src, …)
//   handle.etag          -> string              the server version tag
(function () {
  if (window.__stageBundles) return;

  const stage = window.__stage;
  const DB_NAME = 'llming-stage-bundles';
  const DB_STORE = 'bundles';

  const registry = new Map();   // name -> { url }
  const cache = new Map();      // name -> Promise<BundleHandle>  (dedup + memo)
  const ready = new Map();      // name -> BundleHandle           (introspection)

  // ---- IndexedDB persistence (download-once across reloads) -------------
  function openDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) { reject(new Error('IndexedDB unavailable')); return; }
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(DB_STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
    });
  }
  function idbGet(key) {
    return openDb().then((db) => new Promise((resolve) => {
      const tx = db.transaction(DB_STORE, 'readonly');
      const req = tx.objectStore(DB_STORE).get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => resolve(null);
      tx.oncomplete = () => db.close();
    })).catch(() => null);
  }
  function idbPut(key, value) {
    return openDb().then((db) => new Promise((resolve) => {
      const tx = db.transaction(DB_STORE, 'readwrite');
      tx.objectStore(DB_STORE).put(value, key);
      tx.oncomplete = () => { db.close(); resolve(); };
      tx.onerror = () => { db.close(); resolve(); };
    })).catch(() => {});
  }

  // ---- Source resolution -----------------------------------------------
  function resolve(name, opts) {
    const url = (opts && opts.url) || (registry.get(name) || {}).url;
    if (!url) throw new Error('llming-stage: unknown bundle "' + name + '" (call define() or pass {url})');
    return url;
  }
  function define(name, source) {
    registry.set(name, { url: (source && source.url) || source });
    return name;
  }

  // ---- Unzip (lazy fflate) ---------------------------------------------
  async function explode(url, bytes) {
    // A .zip is exploded into { path: Uint8Array }; anything else is a
    // single-entry bundle keyed by its own filename.
    if (/\.zip(?:[?#]|$)/.test(url)) {
      await stage.load('fflate');
      return window.fflate.unzipSync(bytes);
    }
    const name = url.split('/').pop().split('?')[0] || 'data';
    const map = {};
    map[name] = bytes;
    return map;
  }

  // Content type for an entry, so an object URL renders as an image / plays as
  // a <video>/<audio> / parses as JSON instead of an undisplayable octet-stream.
  const MIME = {
    // images
    svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
    gif: 'image/gif', webp: 'image/webp', avif: 'image/avif', ico: 'image/x-icon',
    bmp: 'image/bmp',
    // video
    mp4: 'video/mp4', m4v: 'video/mp4', webm: 'video/webm', ogv: 'video/ogg',
    mov: 'video/quicktime',
    // audio
    mp3: 'audio/mpeg', m4a: 'audio/mp4', oga: 'audio/ogg', ogg: 'audio/ogg',
    wav: 'audio/wav', flac: 'audio/flac', aac: 'audio/aac',
    // documents / fonts / data
    pdf: 'application/pdf', json: 'application/json', txt: 'text/plain',
    csv: 'text/csv', html: 'text/html', css: 'text/css', js: 'text/javascript',
    woff2: 'font/woff2', woff: 'font/woff', ttf: 'font/ttf', wasm: 'application/wasm',
  };
  function mimeFor(path) {
    const ext = path.split('.').pop().toLowerCase();
    return MIME[ext] || 'application/octet-stream';
  }

  // ---- Bundle handle ----------------------------------------------------
  function makeHandle(name, etag, files) {
    const objectUrls = new Map();
    const decoder = new TextDecoder();
    function bytes(path) {
      const v = files[path];
      return v ? v : null;
    }
    return Object.freeze({
      name,
      etag,
      list() { return Object.keys(files); },
      has(path) { return Object.prototype.hasOwnProperty.call(files, path); },
      bytes,
      text(path) { const b = bytes(path); return b ? decoder.decode(b) : null; },
      json(path) { const t = this.text(path); return t == null ? null : JSON.parse(t); },
      url(path) {
        if (objectUrls.has(path)) return objectUrls.get(path);
        const b = bytes(path);
        if (!b) return null;
        // Copy into a fresh ArrayBuffer so the Blob owns contiguous bytes,
        // and tag it with a content type so <img>/<video>/<audio> render it.
        // The same URL is reused for repeated url(path) calls (cheap to bind
        // in a template), so revoke() can tear them all down on unmount.
        const u = URL.createObjectURL(new Blob([b.slice()], { type: mimeFor(path) }));
        objectUrls.set(path, u);
        return u;
      },
      revoke() {
        for (const u of objectUrls.values()) URL.revokeObjectURL(u);
        objectUrls.clear();
      },
      // Stable literal URL for this entry, served by the bundle service
      // worker once serve() has resolved. Drop straight into src=/href=.
      src(path) { return '/__stage_bundle__/' + name + '/' + String(path).replace(/^\/+/, ''); },
    });
  }

  // ---- Core fetch + revalidate -----------------------------------------
  async function fetchBundle(name, url, onProgress) {
    // Keyed by logical NAME (not url) so the service worker can resolve a
    // virtual `/__stage_bundle__/<name>/<path>` request straight from here.
    const stored = await idbGet(name);
    const headers = {};
    if (stored && stored.etag) headers['If-None-Match'] = stored.etag;

    let resp;
    try {
      resp = await fetch(url, {
        headers,
        credentials: 'include',
        // We do the conditional GET ourselves (header + IndexedDB), so keep
        // the browser HTTP cache out of it for deterministic 304/200.
        cache: 'no-store',
      });
    } catch (err) {
      // Offline: fall back to the last good copy if we have one.
      if (stored) return makeHandle(name, stored.etag, stored.files);
      throw err;
    }

    if (resp.status === 304 && stored) {
      return makeHandle(name, stored.etag, stored.files);
    }
    if (!resp.ok) {
      if (stored) return makeHandle(name, stored.etag, stored.files);
      throw new Error('llming-stage: bundle "' + name + '" failed (' + resp.status + ')');
    }

    const etag = resp.headers.get('ETag') || '';
    const bytes = await readWithProgress(resp, onProgress);
    const files = await explode(url, bytes);
    await idbPut(name, { url, etag, files });
    return makeHandle(name, etag, files);
  }

  async function readWithProgress(resp, onProgress) {
    const total = Number(resp.headers.get('Content-Length') || 0);
    if (!onProgress || !resp.body || !total) {
      return new Uint8Array(await resp.arrayBuffer());
    }
    const reader = resp.body.getReader();
    const chunks = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.length;
      try { onProgress(received, total); } catch (_) {}
    }
    const out = new Uint8Array(received);
    let off = 0;
    for (const c of chunks) { out.set(c, off); off += c.length; }
    return out;
  }

  // ---- Public load / prefetch / check ----------------------------------
  function load(name, opts) {
    opts = opts || {};
    // `refresh` drops the memo so the next load re-validates against the
    // server (conditional GET → 304 keeps the cache, 200 swaps in new bytes).
    // Without it load() is a permanent idempotent gate — instant after first
    // use — which is what you want for gating a render, but it can never pick
    // up a re-prepared bundle on its own.
    if (opts.refresh) cache.delete(name);
    const cached = cache.get(name);
    if (cached) return cached;
    const url = resolve(name, opts);
    const p = fetchBundle(name, url, opts.onProgress).then(
      (handle) => { ready.set(name, handle); return handle; },
      (err) => { cache.delete(name); throw err; },
    );
    cache.set(name, p);
    return p;
  }

  function refresh(name, opts) {
    return load(name, Object.assign({}, opts, { refresh: true }));
  }

  function prefetch(name, opts) {
    opts = opts || {};
    const start = () => load(name, opts).catch((e) =>
      console.warn('[llming-stage] prefetch "' + name + '" failed', e));
    if (opts.idle && window.requestIdleCallback) window.requestIdleCallback(start);
    else start();
    return undefined;   // fire-and-forget by design
  }

  async function check(name, opts) {
    const url = resolve(name, opts || {});
    const stored = await idbGet(name);
    if (!stored || !stored.etag) return true;   // nothing cached → "newer" exists
    const resp = await fetch(url, {
      method: 'HEAD', credentials: 'include', cache: 'no-store',
    });
    if (!resp.ok) return false;
    return (resp.headers.get('ETag') || '') !== stored.etag;
  }

  // ---- Service-worker virtual mount ------------------------------------
  // After serve() resolves, bundle entries are reachable at stable, literal
  // URLs — `/__stage_bundle__/<name>/<path>` — so `<img src>`, `<video src>`,
  // CSS `url(...)`, and RELATIVE references inside bundled HTML/SVG all just
  // work, with HTTP Range support for video seeking. No blob bookkeeping.
  const MOUNT = '/__stage_bundle__';
  let servePromise = null;

  function serve(opts) {
    opts = opts || {};
    if (servePromise) return servePromise;
    if (!('serviceWorker' in navigator)) {
      return Promise.reject(new Error('llming-stage: service workers unavailable'));
    }
    // The worker script is a sibling of bundles.js under the asset base.
    const base = (window.__stageBase || '').replace(/\/+$/, '');
    const swUrl = opts.swUrl || (base + '/bundle-sw.js');
    servePromise = navigator.serviceWorker
      .register(swUrl, { scope: '/' })
      .then((reg) => navigator.serviceWorker.ready.then(() => {
        // Claimed pages are controlled immediately (the SW calls
        // clients.claim()); if not yet controlling, wait one controllerchange.
        if (navigator.serviceWorker.controller) return reg;
        return new Promise((res) => {
          navigator.serviceWorker.addEventListener(
            'controllerchange', () => res(reg), { once: true });
        });
      }))
      .then(() => MOUNT);
    return servePromise;
  }

  function src(name, path) {
    return MOUNT + '/' + name + '/' + String(path).replace(/^\/+/, '');
  }

  window.__stageBundles = Object.freeze({
    define,
    load,
    refresh,
    prefetch,
    check,
    serve,
    src,
    mount: MOUNT,
    get(name) { return ready.get(name) || null; },
    isReady(name) { return ready.has(name); },
    registry,
  });
})();
