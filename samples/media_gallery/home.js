// Vanilla-JS view: load ONE bundle (media.zip) and render every kind of media
// out of it — images (png/jpg/webp/gif/svg), video (mp4/webm) and audio
// (mp3/ogg/wav) — using BOTH access mechanisms:
//
//   * blob URLs        handle.url(path)   — typed object URLs, set src yourself
//   * service worker   handle.src(path)   — literal /__stage_bundle__/… paths,
//                                            with HTTP Range so <video> seeks
//
// Each card is tagged with the mechanism that produced its src.
(function () {
  const BUNDLE = 'media';
  const BUNDLE_URL = '/bundles/media.zip';

  const ITEMS = [
    { path: 'logo.png',   kind: 'img',   access: 'blob' },
    { path: 'logo.jpg',   kind: 'img',   access: 'sw'   },
    { path: 'logo.webp',  kind: 'img',   access: 'blob' },
    { path: 'motion.gif', kind: 'img',   access: 'blob' },
    { path: 'vector.svg', kind: 'img',   access: 'blob' },
    { path: 'clip.mp4',   kind: 'video', access: 'sw'   },
    { path: 'clip.webm',  kind: 'video', access: 'blob' },
    { path: 'voice.mp3',  kind: 'audio', access: 'sw'   },
    { path: 'voice.ogg',  kind: 'audio', access: 'blob' },
    { path: 'voice.wav',  kind: 'audio', access: 'sw'   },
  ];

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const k in (attrs || {})) {
      if (k === 'class') node.className = attrs[k];
      else if (k === 'html') node.innerHTML = attrs[k];
      else node[k] = attrs[k];
    }
    for (const c of children || []) {
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return node;
  }
  const idFor = (p) => 'm-' + p.replace(/[^a-z0-9]+/gi, '-');
  const ICON = {
    img:   '<path d="M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
    video: '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="m17 9 4-2v10l-4-2"/>',
    audio: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  };
  function glyph(kind, cls) {
    // SVG must be created in its namespace (createElement would make an inert
    // HTML element); innerHTML then parses the path markup as SVG.
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const attrs = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
      'stroke-width': '1.6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      class: cls };
    for (const k in attrs) svg.setAttribute(k, attrs[k]);
    svg.innerHTML = ICON[kind];
    return svg;
  }

  window.__stageViews = window.__stageViews || {};
  window.__stageViews['home'] = {
    mount(target) {
      const grid = el('div', { id: 'gallery-grid',
        class: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6' });
      const meta = el('span', { id: 'gallery-meta',
        class: 'text-sm text-slate-400 dark:text-slate-500' }, ['loading…']);

      function pill(access) {
        const sw = access === 'sw';
        return el('span', {
          class: 'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ' +
            (sw ? 'bg-teal-50 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300'
                : 'bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300'),
        }, [
          el('span', { class: 'h-1.5 w-1.5 rounded-full ' + (sw ? 'bg-teal-500' : 'bg-violet-500') }),
          sw ? 'service worker' : 'blob url',
        ]);
      }

      function frame(item, srcUrl) {
        if (item.kind === 'img') {
          return el('div', { class: 'aspect-video bg-slate-50 dark:bg-slate-900/60 flex items-center justify-center overflow-hidden' }, [
            el('img', { id: idFor(item.path), src: srcUrl, alt: item.path, loading: 'lazy',
              class: 'max-h-full max-w-full object-contain transition-transform duration-300 group-hover:scale-[1.03]' }),
          ]);
        }
        if (item.kind === 'video') {
          return el('div', { class: 'aspect-video bg-black' }, [
            el('video', { id: idFor(item.path), src: srcUrl, controls: true, muted: true,
              playsInline: true, preload: 'metadata', class: 'h-full w-full object-cover' }),
          ]);
        }
        // audio — a tinted banner with a glyph, control sits in the body
        return el('div', { class: 'aspect-video bg-gradient-to-br from-violet-500/10 to-teal-500/10 flex items-center justify-center' },
          [ glyph('audio', 'h-12 w-12 text-slate-400 dark:text-slate-500') ]);
      }

      function card(item, srcUrl) {
        const ext = item.path.split('.').pop().toUpperCase();
        const body = [
          el('div', { class: 'flex items-center justify-between' }, [
            el('div', { class: 'flex items-center gap-2 min-w-0' }, [
              glyph(item.kind, 'h-4 w-4 text-slate-400 shrink-0'),
              el('span', { class: 'font-semibold text-sm text-slate-700 dark:text-slate-200' }, [ext]),
              el('span', { class: 'text-xs text-slate-400 truncate', title: item.path }, [item.path]),
            ]),
            pill(item.access),
          ]),
        ];
        if (item.kind === 'audio') {
          body.push(el('audio', { id: idFor(item.path), src: srcUrl, controls: true,
            preload: 'metadata', class: 'w-full' }));
        }
        return el('div', { class:
          'group rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-700/70 ' +
          'bg-white dark:bg-slate-800/50 shadow-sm hover:shadow-xl hover:-translate-y-0.5 ' +
          'transition duration-200' }, [
          frame(item, srcUrl),
          el('div', { class: 'p-4 space-y-3' }, body),
        ]);
      }

      async function boot() {
        try {
          await window.__stage.load('bundles');
          const b = window.__stageBundles;
          b.define(BUNDLE, { url: BUNDLE_URL });
          await b.serve();                       // SW first → handle.src() resolves
          const handle = await b.load(BUNDLE);
          for (const item of ITEMS) {
            const url = item.access === 'sw' ? handle.src(item.path) : handle.url(item.path);
            grid.appendChild(card(item, url));
          }
          meta.textContent = handle.list().length + ' items · unzipped & decoded locally';
          window.__galleryReady = true;          // signal for the e2e probe
        } catch (e) {
          meta.textContent = 'failed: ' + (e && e.message || e);
        }
      }

      const header = el('header', { class: 'mb-8' }, [
        el('div', { class: 'flex items-center gap-3' }, [
          el('span', { class: 'inline-flex h-10 w-10 items-center justify-center rounded-xl ' +
            'bg-gradient-to-br from-violet-600 to-teal-500 text-white shadow-md' },
            [ glyph('img', 'h-5 w-5') ]),
          el('h1', { class: 'text-3xl font-bold tracking-tight text-slate-900 dark:text-white' },
            ['Media gallery']),
        ]),
        el('p', { class: 'mt-2 text-slate-500 dark:text-slate-400 max-w-2xl' }, [
          'Images, video and audio — all delivered in a single ',
          el('span', { class: 'font-medium text-slate-700 dark:text-slate-200' }, ['media.zip']),
          ', downloaded once and decoded in your browser.',
        ]),
        el('div', { class: 'mt-3 inline-flex items-center gap-2 rounded-full bg-emerald-50 ' +
          'dark:bg-emerald-500/10 px-3 py-1' }, [
          el('span', { class: 'h-2 w-2 rounded-full bg-emerald-500' }),
          el('span', { class: 'text-xs font-medium text-emerald-700 dark:text-emerald-300' }, ['served locally · offline-ready']),
          el('span', { class: 'text-emerald-300 dark:text-emerald-700' }, ['·']),
          meta,
        ]),
      ]);

      const root = el('div', { class: 'max-w-5xl mx-auto px-6 py-10' }, [header, grid]);
      target.appendChild(root);
      boot();
      return { unmount() {
        const h = window.__stageBundles && window.__stageBundles.get(BUNDLE);
        if (h) h.revoke();
        target.innerHTML = '';
      } };
    },
  };
})();
