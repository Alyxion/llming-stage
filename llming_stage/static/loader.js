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

  window.__stage = Object.freeze({
    base,
    load,
    isLoaded,
    register,
    loaded,
    registry,
  });
})();
