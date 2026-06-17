// Vanilla-JS view: fetch / prefetch an offline data bundle (a .zip) and read
// its contents in the browser. No framework — just the DOM and the global
// `window.__stageBundles` client (loaded on demand via __stage.load).
//
// Demonstrates the whole offline-bundle story end to end:
//   * prefetch in the background (idle) before it is needed,
//   * load with a download-progress bar (gates the "real" render),
//   * read JSON, text and an image out of the unzipped bundle locally,
//   * show the server version tag (ETag) and re-check for a newer one.
(function () {
  const BUNDLE = 'demo';
  const BUNDLE_URL = '/bundles/demo.zip';

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.assign(node, attrs || {});
    for (const c of children || []) {
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return node;
  }

  window.__stageViews = window.__stageViews || {};
  window.__stageViews['home'] = {
    mount(target) {
      const status = el('div', {
        className: 'text-sm text-slate-500',
        id: 'bundle-status',
        textContent: 'Idle — nothing fetched yet.',
      });
      const bar = el('div', { className: 'h-2 rounded bg-violet-500', id: 'bundle-bar' });
      bar.style.width = '0%';
      const barWrap = el('div', { className: 'h-2 w-full rounded bg-slate-200 overflow-hidden' }, [bar]);
      const out = el('div', { className: 'space-y-3', id: 'bundle-output' });

      const loadBtn = el('button', {
        className: 'px-4 py-2 rounded bg-violet-600 text-white font-medium',
        id: 'bundle-load',
        textContent: 'Load & show data',
      });
      const prefetchBtn = el('button', {
        className: 'px-4 py-2 rounded bg-slate-200 text-slate-800 font-medium',
        id: 'bundle-prefetch',
        textContent: 'Prefetch (background)',
      });
      const checkBtn = el('button', {
        className: 'px-4 py-2 rounded bg-slate-200 text-slate-800 font-medium',
        id: 'bundle-check',
        textContent: 'Check for newer',
      });
      const swBtn = el('button', {
        className: 'px-4 py-2 rounded bg-slate-200 text-slate-800 font-medium',
        id: 'bundle-sw',
        textContent: 'Mount via service worker',
      });

      function setStatus(text) { status.textContent = text; }
      function setProgress(pct) { bar.style.width = pct + '%'; }

      async function bundles() {
        await window.__stage.load('bundles');
        window.__stageBundles.define(BUNDLE, { url: BUNDLE_URL });
        return window.__stageBundles;
      }

      async function doLoad() {
        loadBtn.disabled = true;
        try {
          setStatus('Loading ' + BUNDLE_URL + ' …');
          setProgress(0);
          const b = await bundles();
          const handle = await b.load(BUNDLE, {
            onProgress: (recv, total) => setProgress(Math.round((recv / total) * 100)),
          });
          setProgress(100);
          render(handle);
          setStatus('Ready — version (ETag) ' + (handle.etag || '∅') +
            ' · ' + handle.list().length + ' entries · served from cache after first load');
        } catch (e) {
          setStatus('Load failed: ' + (e && e.message || e));
        } finally {
          loadBtn.disabled = false;
        }
      }

      function render(handle) {
        out.textContent = '';
        const cfg = handle.json('config.json');
        const readme = handle.text('README.txt');
        const imgUrl = handle.url('logo.svg');

        out.appendChild(el('img', { src: imgUrl, alt: 'logo from zip', className: 'rounded shadow' }));
        out.appendChild(el('div', { className: 'font-semibold text-lg', textContent: cfg.title }));
        out.appendChild(el('div', { className: 'text-sm text-slate-600', textContent: readme }));
        out.appendChild(el('div', { className: 'text-sm' }, [
          el('span', { className: 'text-slate-500', textContent: 'items: ' }),
          el('span', { textContent: (cfg.items || []).join(', ') }),
        ]));
        const pre = el('pre', {
          className: 'text-xs bg-slate-900 text-slate-100 rounded p-3 overflow-auto',
          id: 'bundle-config',
          textContent: JSON.stringify(cfg, null, 2),
        });
        out.appendChild(pre);
      }

      async function doPrefetch() {
        const b = await bundles();
        b.prefetch(BUNDLE, { idle: true });
        setStatus('Prefetch scheduled in the background (idle). Click “Load & show” — it will be instant.');
      }

      async function doCheck() {
        checkBtn.disabled = true;
        try {
          const b = await bundles();
          const newer = await b.check(BUNDLE);
          if (!newer) {
            setStatus('Up to date — the server still hosts the cached version (304).');
            return;
          }
          // Detected a re-prepared bundle → pull the new bytes and re-render.
          setStatus('Newer version found — updating …');
          const handle = await b.refresh(BUNDLE, {
            onProgress: (recv, total) => setProgress(Math.round((recv / total) * 100)),
          });
          render(handle);
          setStatus('Updated — new version (ETag) ' + (handle.etag || '∅'));
        } catch (e) {
          setStatus('Check failed: ' + (e && e.message || e));
        } finally {
          checkBtn.disabled = false;
        }
      }

      async function doServe() {
        swBtn.disabled = true;
        try {
          setStatus('Registering bundle service worker …');
          const b = await bundles();
          await b.serve();              // worker now controls the page
          await b.load(BUNDLE);         // ensure entries are cached for it
          // A LITERAL path — no handle, no blob URL — resolved by the worker.
          const literal = b.src(BUNDLE, 'logo.svg');
          out.textContent = '';
          out.appendChild(el('div', { className: 'text-sm text-slate-500' }, [
            'served at literal path ', el('code', { textContent: literal }),
          ]));
          out.appendChild(el('img', { src: literal, alt: 'via service worker', className: 'rounded shadow' }));
          setStatus('Service worker mounted — <img src="' + literal + '"> renders with no blob URL.');
        } catch (e) {
          setStatus('Service worker failed: ' + (e && e.message || e));
        } finally {
          swBtn.disabled = false;
        }
      }

      loadBtn.addEventListener('click', doLoad);
      prefetchBtn.addEventListener('click', doPrefetch);
      checkBtn.addEventListener('click', doCheck);
      swBtn.addEventListener('click', doServe);

      const root = el('div', { className: 'max-w-xl mx-auto p-6 space-y-4' }, [
        el('h1', { className: 'text-2xl font-bold', textContent: 'Offline data bundle' }),
        el('p', { className: 'text-slate-600 text-sm' }, [
          'Downloads ', el('code', { textContent: 'demo.zip' }),
          ' once, caches it by content hash, and reads its entries locally.',
        ]),
        el('div', { className: 'flex flex-wrap gap-2' }, [loadBtn, prefetchBtn, checkBtn, swBtn]),
        barWrap,
        status,
        out,
      ]);
      target.appendChild(root);
      return { unmount() { target.innerHTML = ''; } };
    },
  };
})();
