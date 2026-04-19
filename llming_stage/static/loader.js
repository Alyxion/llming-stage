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
    katex:     { js: 'vendor/katex.min.js',       css: 'vendor/katex.min.css' },
    mermaid:   { module: 'vendor/mermaid.esm.min.mjs' },
    dompurify: { js: 'vendor/dompurify.min.js' },
    three:     { module: 'vendor/three.module.min.js' },
    plotly:    { js: 'vendor/plotly-basic.min.js' },
  };

  const pending = new Map(); // name -> Promise<void>
  const loaded = new Set();

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

  async function load(name) {
    if (loaded.has(name)) return;
    if (pending.has(name)) return pending.get(name);
    const entry = registry[name];
    if (!entry) {
      throw new Error('llming-stage: unknown component "' + name + '"');
    }
    const p = loadEntry(entry).then(() => {
      loaded.add(name);
      pending.delete(name);
    }).catch((err) => {
      pending.delete(name);
      throw err;
    });
    pending.set(name, p);
    return p;
  }

  function register(name, entry) {
    registry[name] = entry;
  }

  window.__stage = Object.freeze({
    base,
    load,
    register,
    loaded,
    registry,
  });
})();
