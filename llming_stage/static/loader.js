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

  function debugValueText(value) {
    if (typeof value === 'string') return value;
    try {
      const text = JSON.stringify(value);
      return text === undefined ? String(value) : text;
    }
    catch (_) { return String(value); }
  }

  function sendDebugMessage(type, payload = {}) {
    if (!socket) return false;
    try {
      socket.send({ type, ...payload });
      return true;
    } catch (_) {
      return false;
    }
  }

  function runDebugEval(id, code) {
    if (!(window.__stageDebug && window.__stageDebug.enabled)) return;
    const finish = (payload) => {
      sendDebugMessage('llming.debug.eval_result', { id, ...payload });
    };
    try {
      const result = window.eval(String(code || ''));
      if (result && typeof result.then === 'function') {
        result.then(
          (value) => finish({ ok: true, result: debugValueText(value) }),
          (err) => finish({ ok: false, error: String((err && err.message) || err) }),
        );
      } else {
        finish({ ok: true, result: debugValueText(result) });
      }
    } catch (err) {
      finish({ ok: false, error: String((err && err.message) || err) });
    }
  }

  function installDebugBridge() {
    const bootstrap = window.__stageDebug || {};
    if (!bootstrap.enabled || window.__llmingStageDebugBridge) return;
    window.__llmingStageDebugBridge = true;
    registerComponent('__stageDebug', {
      eval(id, code) {
        runDebugEval(id, code);
      },
    });
    const levels = ['log', 'info', 'warn', 'error', 'debug'];
    levels.forEach((level) => {
      const original = window.console && window.console[level];
      if (typeof original !== 'function') return;
      const bound = original.bind(window.console);
      window.console[level] = function () {
        bound.apply(null, arguments);
        const text = Array.from(arguments).map(debugValueText).join(' ');
        sendDebugMessage('llming.debug.console', { level, text });
      };
    });
  }

  function component(target) {
    const stack = components.get(target);
    return stack && stack.length ? stack[stack.length - 1] : null;
  }

  function dispatch(msg) {
    if (msg && msg.type === 'llming.debug.eval' && window.__stageDebug && window.__stageDebug.enabled) {
      runDebugEval(msg.id || '', msg.code || '');
      return;
    }
    if (msg && msg.type === 'llming.call') {
      let target = msg.target || '';
      let method = msg.method || '';
      if (!target && method.includes('.')) {
        const parts = method.split('.');
        method = parts.pop();
        target = parts.join('.');
      }
      if (
        target === '__stageDebug' &&
        method === 'eval' &&
        window.__stageDebug &&
        window.__stageDebug.enabled
      ) {
        const args = msg.args || [];
        runDebugEval(args[0] || '', args[1] || '');
        return;
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

  const debug = createDebugActions();
  installDebugBridge();

  window.__stage = Object.freeze({
    base,
    load,
    isLoaded,
    register,
    registerComponent,
    component,
    session,
    connect,
    send,
    call,
    dispatch,
    onReconnect,
    debug,
    loaded,
    registry,
    get socket() { return socket; },
  });

  function createDebugActions() {
    const bootstrap = window.__stageDebug || {};
    const enabled = !!bootstrap.enabled;
    const actions = new Map();
    const flows = new Map();
    const loadedDebugModules = new Set();
    const DB_NAME = 'llming-stage-debug-actions';
    const DB_STORE = 'state';
    let currentView = null;

    function noopPromise(value) {
      return Promise.resolve(value);
    }

    function clone(value) {
      if (value == null) return value;
      try { return JSON.parse(JSON.stringify(value)); }
      catch (_) { return value; }
    }

    function openDb() {
      return new Promise((resolve, reject) => {
        if (!window.indexedDB) {
          reject(new Error('IndexedDB unavailable'));
          return;
        }
        const req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = () => req.result.createObjectStore(DB_STORE);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
      });
    }

    function dbGet(key, fallback) {
      if (!enabled) return noopPromise(fallback);
      return openDb().then((db) => new Promise((resolve) => {
        const tx = db.transaction(DB_STORE, 'readonly');
        const req = tx.objectStore(DB_STORE).get(key);
        req.onsuccess = () => resolve(req.result === undefined ? fallback : req.result);
        req.onerror = () => resolve(fallback);
        tx.oncomplete = () => db.close();
        tx.onerror = () => db.close();
      })).catch(() => fallback);
    }

    function dbSet(key, value) {
      if (!enabled) return noopPromise();
      return openDb().then((db) => new Promise((resolve) => {
        const tx = db.transaction(DB_STORE, 'readwrite');
        tx.objectStore(DB_STORE).put(value, key);
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => { db.close(); resolve(); };
      })).catch(() => {});
    }

    function normalizeAction(id, options, run) {
      if (typeof options === 'function') {
        run = options;
        options = {};
      }
      options = options || {};
      return {
        id,
        label: options.label || id,
        description: options.description || '',
        scope: options.scope || currentView || 'app',
        view: options.view || currentView || null,
        group: options.group || 'General',
        tags: Array.isArray(options.tags) ? options.tags.slice() : [],
        params: options.params || {},
        presets: Array.isArray(options.presets) ? options.presets.map((p) => ({
          id: p.id || slug(p.label || 'preset'),
          label: p.label || p.id || 'Preset',
          params: p.params || {},
        })) : [],
        button: options.button !== false,
        url: options.url !== false,
        pin: !!options.pin,
        run,
      };
    }

    function slug(value) {
      return String(value || 'preset').toLowerCase().replace(/[^a-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '') || 'preset';
    }

    function action(id, options, run) {
      if (!enabled) return null;
      if (!id || typeof id !== 'string') throw new Error('debug action id must be a string');
      const record = normalizeAction(id, options, run);
      if (typeof record.run !== 'function') {
        throw new Error('debug action "' + id + '" needs a run function');
      }
      actions.set(id, record);
      return record;
    }

    function flow(id, options) {
      if (!enabled) return null;
      options = options || {};
      if (!id || typeof id !== 'string') throw new Error('debug flow id must be a string');
      const record = {
        id,
        label: options.label || id,
        description: options.description || '',
        scope: options.scope || currentView || 'app',
        view: options.view || currentView || null,
        group: options.group || 'Flows',
        tags: Array.isArray(options.tags) ? options.tags.slice() : [],
        steps: Array.isArray(options.steps) ? options.steps.slice() : [],
        button: options.button !== false,
        url: options.url !== false,
        pin: !!options.pin,
      };
      flows.set(id, record);
      return record;
    }

    function coerceParams(actionRecord, params) {
      const out = {};
      const schema = actionRecord.params || {};
      const source = params || {};
      for (const [key, spec] of Object.entries(schema)) {
        const cfg = spec || {};
        let value = Object.prototype.hasOwnProperty.call(source, key)
          ? source[key]
          : cfg.default;
        if (value == null || value === '') {
          if (cfg.required) throw new Error('missing debug param "' + key + '"');
          if (value == null) continue;
        }
        if (cfg.type === 'number') value = Number(value);
        else if (cfg.type === 'boolean') {
          value = value === true || value === 'true' || value === '1' || value === 1;
        } else if (cfg.type === 'json' && typeof value === 'string') {
          value = JSON.parse(value);
        } else if (value != null) value = String(value);
        if (cfg.options && cfg.options.length && !cfg.options.includes(value)) {
          throw new Error('invalid value for debug param "' + key + '"');
        }
        out[key] = value;
      }
      for (const [key, value] of Object.entries(source)) {
        if (!Object.prototype.hasOwnProperty.call(out, key) &&
            Object.prototype.hasOwnProperty.call(schema, key)) {
          out[key] = value;
        }
      }
      return out;
    }

    function ctx(viewName) {
      return {
        enabled,
        viewName,
        action,
        flow,
        router: window.__stageRouter,
        stage: window.__stage,
        command: send,
        component(target = viewName) { return component(target); },
        get view() { return component(viewName); },
      };
    }

    async function loadForView(viewName) {
      currentView = viewName || currentView;
      if (!enabled || !viewName) return false;
      if (loadedDebugModules.has(viewName)) {
        await runPendingForView(viewName);
        return true;
      }
      const modules = (window.__stageDebug && window.__stageDebug.modules) || {};
      const url = modules[viewName];
      if (!url) return false;
      try {
        const mod = await import(resolveUrl(url));
        const fn = mod.default || mod.registerDebugActions || mod.debug;
        if (typeof fn === 'function') await fn(ctx(viewName));
        loadedDebugModules.add(viewName);
      } catch (e) {
        loadedDebugModules.delete(viewName);
        throw e;
      }
      await runPendingForView(viewName);
      return true;
    }

    async function runAction(id, params = {}, meta = {}) {
      if (!enabled) throw new Error('debug actions are disabled');
      const record = actions.get(id);
      if (!record) throw new Error('unknown debug action "' + id + '"');
      const finalParams = coerceParams(record, params);
      const result = await record.run(finalParams, {
        ...ctx(record.view || currentView),
        action: record,
        meta,
      });
      await addRecent({ kind: 'action', id, params: finalParams });
      return result || { ok: true };
    }

    async function runPreset(actionId, presetId, meta = {}) {
      const record = actions.get(actionId);
      if (!record) throw new Error('unknown debug action "' + actionId + '"');
      const preset = (record.presets || []).find((p) => p.id === presetId);
      if (!preset) throw new Error('unknown debug preset "' + actionId + ':' + presetId + '"');
      const result = await runAction(actionId, preset.params || {}, {
        ...meta,
        preset: presetId,
      });
      await addRecent({ kind: 'preset', id: actionId + ':' + presetId });
      return result;
    }

    async function runFlow(id, meta = {}) {
      if (!enabled) throw new Error('debug actions are disabled');
      const record = flows.get(id);
      if (!record) throw new Error('unknown debug flow "' + id + '"');
      for (const step of record.steps) {
        if (Array.isArray(step)) {
          await runAction(step[0], step[1] || {}, { ...meta, flow: id });
        } else if (step && step.kind === 'preset') {
          const [actionId, presetId] = String(step.id || '').split(':');
          await runPreset(actionId, presetId, { ...meta, flow: id });
        } else if (step && step.kind === 'flow') {
          await runFlow(step.id, { ...meta, flow: id });
        } else if (step && step.id) {
          await runAction(step.id, step.params || {}, { ...meta, flow: id });
        }
      }
      await addRecent({ kind: 'flow', id });
      return { ok: true };
    }

    async function runRequest(request) {
      request = request || {};
      if (request.kind === 'preset') {
        const [actionId, presetId] = String(request.id || '').split(':');
        return runPreset(actionId, presetId, { source: request.source || 'bridge' });
      }
      if (request.kind === 'flow') {
        return runFlow(request.id, { source: request.source || 'bridge' });
      }
      return runAction(request.id, request.params || {}, { source: request.source || 'bridge' });
    }

    async function addRecent(item) {
      const recent = await dbGet('recent', []);
      const next = [item, ...recent.filter((r) => !(r.kind === item.kind && r.id === item.id))].slice(0, 20);
      await dbSet('recent', next);
    }

    async function configure(request) {
      request = request || {};
      const key = request.key;
      const value = request.value;
      if (!['pinned', 'runOnce', 'runAlways'].includes(key)) {
        throw new Error('unknown debug config key "' + key + '"');
      }
      await dbSet(key, Array.isArray(value) ? value : []);
      return snapshot();
    }

    function serialAction(record) {
      return {
        id: record.id,
        label: record.label,
        description: record.description,
        scope: record.scope,
        view: record.view,
        group: record.group,
        tags: record.tags,
        params: clone(record.params) || {},
        presets: clone(record.presets) || [],
        button: record.button,
        url: record.url,
        pin: record.pin,
      };
    }

    async function snapshot() {
      const [pinned, runOnce, runAlways, recent] = await Promise.all([
        dbGet('pinned', []),
        dbGet('runOnce', []),
        dbGet('runAlways', []),
        dbGet('recent', []),
      ]);
      let sessionId = null;
      try { sessionId = sessionStorage.getItem('__llming_session'); } catch (_) {}
      return {
        enabled,
        sessionId,
        currentView,
        actions: Array.from(actions.values()).map(serialAction),
        flows: Array.from(flows.values()).map((f) => ({
          id: f.id,
          label: f.label,
          description: f.description,
          scope: f.scope,
          view: f.view,
          group: f.group,
          tags: f.tags,
          button: f.button,
          url: f.url,
          pin: f.pin,
        })),
        pinned,
        runOnce,
        runAlways,
        recent,
      };
    }

    function decodeStageParams(raw) {
      if (!raw) return {};
      try {
        const padded = raw + '='.repeat((4 - raw.length % 4) % 4);
        return JSON.parse(atob(padded.replace(/-/g, '+').replace(/_/g, '/')));
      } catch (_) {
        try { return JSON.parse(raw); } catch (_) { return {}; }
      }
    }

    function queryRequest() {
      if (!enabled) return null;
      const p = new URLSearchParams(location.search);
      const flowId = p.get('stage_flow');
      if (flowId) return { kind: 'flow', id: flowId, source: 'url' };
      const presetId = p.get('stage_preset');
      if (presetId) return { kind: 'preset', id: presetId, source: 'url' };
      const actionId = p.get('stage_action');
      if (!actionId) return null;
      const params = decodeStageParams(p.get('stage_params'));
      for (const [key, value] of p.entries()) {
        if (!key.startsWith('stage_') && !key.startsWith('_')) params[key] = value;
      }
      return { kind: 'action', id: actionId, params, source: 'url' };
    }

    async function runPendingForView() {
      const pending = [];
      const q = queryRequest();
      if (q) pending.push(q);
      pending.push(...(await dbGet('runAlways', [])));
      const once = await dbGet('runOnce', []);
      if (once.length) await dbSet('runOnce', []);
      pending.push(...once);
      for (const item of pending) {
        try { await runRequest(item); }
        catch (e) { console.warn('[llming-stage] debug action skipped', e); }
      }
    }

    return Object.freeze({
      enabled,
      action,
      flow,
      loadForView,
      runAction,
      runPreset,
      runFlow,
      runRequest,
      configure,
      snapshot,
    });
  }
})();
