// llming-stage lazy-load orchestrator.
//
// Exposes `window.__stage` with a single `load(name)` method that loads a
// registered asset and resolves once it has been parsed by the browser. The
// same name can be requested concurrently; only one network request is issued.
(function () {
  if (window.__stage && window.__stage.load) return;

  const base = (window.__stageBase || '/_stage').replace(/\/$/, '');

  // Registry of loadable components. Each entry is either:
  //   - { js: 'path/to/file.js' }                    single script
  //   - { css: 'path/to/file.css' }                  single stylesheet
  //   - { js: '...', css: '...' }                    script + stylesheet
  //   - { module: 'path/to/file.mjs' }               ES module
  //   - { bundle: [entry, entry, ...] }              multiple assets, loaded in order
  const registry = {
    katex:        { js: 'vendor/katex.min.js',       css: 'vendor/katex.min.css' },
    mermaid:      { js: 'vendor/mermaid.min.js' },
    marked:       { js: 'vendor/marked.umd.js' },
    dompurify:    { js: 'vendor/dompurify.min.js' },
    three:        { module: 'vendor/three.module.min.js' },
    'three/controls': { module: 'vendor/three-orbit-controls.module.js' },
    plotly:       { js: 'vendor/plotly-basic.min.js' },
    'plotly/full': { js: 'vendor/plotly-full.min.js' },
    echarts:      { js: 'vendor/echarts.min.js' },
    drawflow:     { js: 'vendor/drawflow.min.js', css: 'vendor/drawflow.min.css' },
    xterm:        { js: 'vendor/xterm.js',        css: 'vendor/xterm.css' },
    'xterm/fit':       { js: 'vendor/xterm-addon-fit.js' },
    'xterm/web-links': { js: 'vendor/xterm-addon-web-links.js' },
    'xterm/webgl':     { js: 'vendor/xterm-addon-webgl.js' },
    codemirror: {
      // CodeMirror needs core+css first, then mode/addons, in order.
      bundle: [
        { js: 'vendor/codemirror.js', css: 'vendor/codemirror.css' },
        { js: 'vendor/codemirror-mode-javascript.js' },
        { js: 'vendor/codemirror-addon-matchbrackets.js' },
        { js: 'vendor/codemirror-addon-closebrackets.js' },
      ],
    },
  };

  // Cache holds the load Promise per name — the SAME instance is
  // returned on every subsequent call once the lib is loaded, so
  // `await __stage.load('plotly')` before every use is effectively
  // free after the first time (single Map lookup, no allocation).
  const cache = new Map();   // name -> Promise<void>
  const loaded = new Set();  // public introspection: which names are ready
  const components = new Map(); // target -> component stack
  let sessionPromise = null;
  let socketPromise = null;
  let socket = null;

  function resolveUrl(rel) {
    // Absolute URLs and paths rooted at '/' are passed through untouched.
    // Only relative paths are resolved against the stage base — so that
    // app code can register view modules served from arbitrary mounts
    // (e.g. '/app-static/home.js') without fighting the prefix.
    if (/^(https?:)?\/\//.test(rel) || rel.startsWith('/')) return rel;
    return base + '/' + rel;
  }

  function loadScript(rel) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = resolveUrl(rel);
      s.async = false;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('failed to load script ' + rel));
      document.head.appendChild(s);
    });
  }

  function loadModule(rel) {
    return import(resolveUrl(rel));
  }

  function loadStylesheet(rel) {
    return new Promise((resolve, reject) => {
      const l = document.createElement('link');
      l.rel = 'stylesheet';
      l.href = resolveUrl(rel);
      l.onload = () => resolve();
      l.onerror = () => reject(new Error('failed to load stylesheet ' + rel));
      document.head.appendChild(l);
    });
  }

  async function loadEntry(entry) {
    const jobs = [];
    if (entry.css) jobs.push(loadStylesheet(entry.css));
    if (entry.js) jobs.push(loadScript(entry.js));
    if (entry.module) jobs.push(loadModule(entry.module));
    await Promise.all(jobs);
    if (entry.bundle) {
      for (const sub of entry.bundle) {
        await loadEntry(sub);
      }
    }
  }

  function load(name) {
    // Fast path: single Map lookup. No async wrapper, no new Promise.
    // The cached Promise is reused for every call after the first —
    // both while still in flight (deduping concurrent loads) and
    // forever after it resolves (turning load() into a near-free
    // idempotent guard you can put in front of every use).
    const cached = cache.get(name);
    if (cached) return cached;

    const entry = registry[name];
    if (!entry) {
      return Promise.reject(
        new Error('llming-stage: unknown component "' + name + '"'));
    }
    const p = loadEntry(entry).then(
      () => { loaded.add(name); },
      (err) => { cache.delete(name); throw err; },
    );
    cache.set(name, p);
    return p;
  }

  function isLoaded(name) {
    return loaded.has(name);
  }

  function register(name, entry) {
    registry[name] = entry;
  }

  async function session(url = '/api/session') {
    if (sessionPromise) return sessionPromise;
    // Per-tab session continuity:
    //   - sessionStorage IS scoped per-tab+origin, BUT some openings
    //     (`window.open(url, '_blank')`, target=_blank links without
    //     noopener) clone it from the opener. If we naively trust the
    //     stored value on a fresh document we'd reuse another tab's
    //     session and both WSes would fight for one controller slot.
    //   - Trust the stored hint ONLY when this is a true reload of the
    //     same document. Anything else — paste URL, link click, popout,
    //     Cmd+T — mints a fresh hint so the server creates a fresh
    //     session. Reload-in-tab is exactly the case where we WANT to
    //     keep the same session_id (tab still holds its in-flight state).
    let trustStored = false;
    try {
      const nav = performance && performance.getEntriesByType
        && performance.getEntriesByType('navigation')[0];
      // `reload` is an explicit user reload of this document.
      // `back_forward` is a BFCache restore — the page is the same
      // document the user left, so the stored hint is still ours.
      if (nav && (nav.type === 'reload' || nav.type === 'back_forward')) {
        trustStored = true;
      }
    } catch (_) {}
    let hint = null;
    if (trustStored) {
      try { hint = sessionStorage.getItem('__llming_session'); } catch (_) {}
    }
    if (!hint) {
      hint = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : 'tab-' + Date.now() + '-' + Math.random().toString(36).slice(2);
    }
    const finalUrl = url + (url.indexOf('?') >= 0 ? '&' : '?') +
                     'session=' + encodeURIComponent(hint);
    sessionPromise = fetch(finalUrl, { credentials: 'include' }).then(async (r) => {
      if (!r.ok) throw new Error('llming-stage: session request failed');
      const data = await r.json();
      try {
        if (data && data.sessionId) {
          sessionStorage.setItem('__llming_session', data.sessionId);
        }
      } catch (_) {}
      return data;
    });
    return sessionPromise;
  }

  function registerComponent(target, component) {
    if (!target || !component) return () => {};
    const stack = components.get(target) || [];
    if (stack.length) {
      console.warn('[llming-stage] duplicate component target', target);
    }
    stack.push(component);
    components.set(target, stack);
    return () => {
      const current = components.get(target) || [];
      const next = current.filter((item) => item !== component);
      if (next.length) components.set(target, next);
      else components.delete(target);
    };
  }

  function call(target, method, args = [], kwargs = {}) {
    const stack = components.get(target);
    if (!stack || !stack.length) {
      console.warn('[llming-stage] no mounted target for', target);
      return false;
    }
    let handled = false;
    for (const component of stack.slice().reverse()) {
      const fn = component && component[method];
      if (typeof fn !== 'function') continue;
      fn.apply(component, [...args, kwargs]);
      handled = true;
      break;
    }
    if (!handled) {
      console.warn('[llming-stage] no mounted method for', target + '.' + method);
    }
    return handled;
  }

  function dispatch(msg) {
    if (msg && msg.type === 'llming.call') {
      let target = msg.target || '';
      let method = msg.method || '';
      if (!target && method.includes('.')) {
        const parts = method.split('.');
        method = parts.pop();
        target = parts.join('.');
      }
      call(target, method, msg.args || [], msg.kwargs || {});
      return;
    }
  }

  const reconnectListeners = [];
  function onReconnect(handler) {
    if (typeof handler === 'function') reconnectListeners.push(handler);
    return () => {
      const i = reconnectListeners.indexOf(handler);
      if (i >= 0) reconnectListeners.splice(i, 1);
    };
  }
  function fireReconnect() {
    for (const h of reconnectListeners.slice()) {
      try { h(); } catch (e) { console.error('[llming-stage] onReconnect handler', e); }
    }
  }

  async function connect(options = {}) {
    if (socketPromise) return socketPromise;
    socketPromise = session(options.sessionUrl).then(({ wsUrl }) => {
      const onOpen = options.onOpen || null;
      const onMessage = options.onMessage || null;
      const onReconnected = options.onReconnected || null;
      return new Promise((resolve) => {
        socket = new window.LlmingWebSocket(wsUrl, {
          ...options,
          onOpen() {
            if (onOpen) onOpen();
            resolve(socket);
          },
          onMessage(message) {
            dispatch(message);
            if (onMessage) onMessage(message);
          },
          onReconnected() {
            // LlmingWebSocket fires this after a successful reconnect
            // (network blip, server restart). Server-pushed state is
            // lost across the gap — give views a chance to re-sync.
            if (onReconnected) onReconnected();
            fireReconnect();
          },
        });
        socket.connect();
      });
    });
    return socketPromise;
  }

  async function send(type, payload = {}) {
    const ws = socket || await connect();
    ws.send({ type, ...payload });
    return true;
  }

  window.__stage = Object.freeze({
    base,
    load,
    isLoaded,
    register,
    registerComponent,
    session,
    connect,
    send,
    call,
    dispatch,
    onReconnect,
    loaded,
    registry,
    get socket() { return socket; },
  });
})();
