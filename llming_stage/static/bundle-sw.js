// llming-stage bundle service worker.
//
// Serves entries out of downloaded data bundles at stable, literal URLs:
//
//     /__stage_bundle__/<bundle-name>/<entry/path>
//
// so `<img src>`, `<video src>`, `<audio src>`, CSS `url(...)`, and RELATIVE
// references inside bundled HTML/SVG documents all resolve without minting
// blob URLs. Bytes come from the same IndexedDB store `bundles.js` fills
// (keyed by bundle name → { url, etag, files }); the worker reads, never
// writes. Requests outside the mount prefix pass straight through.
//
// HTTP Range is honoured so `<video>`/`<audio>` can seek and stream.

const MOUNT = '/__stage_bundle__/';
const DB_NAME = 'llming-stage-bundles';
const DB_STORE = 'bundles';

const MIME = {
  svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  gif: 'image/gif', webp: 'image/webp', avif: 'image/avif', ico: 'image/x-icon',
  bmp: 'image/bmp',
  mp4: 'video/mp4', m4v: 'video/mp4', webm: 'video/webm', ogv: 'video/ogg',
  mov: 'video/quicktime',
  mp3: 'audio/mpeg', m4a: 'audio/mp4', oga: 'audio/ogg', ogg: 'audio/ogg',
  wav: 'audio/wav', flac: 'audio/flac', aac: 'audio/aac',
  pdf: 'application/pdf', json: 'application/json', txt: 'text/plain',
  csv: 'text/csv', html: 'text/html', css: 'text/css', js: 'text/javascript',
  woff2: 'font/woff2', woff: 'font/woff', ttf: 'font/ttf', wasm: 'application/wasm',
};
function mimeFor(path) {
  return MIME[path.split('.').pop().toLowerCase()] || 'application/octet-stream';
}

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(DB_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
function dbGet(key) {
  return openDb().then((db) => new Promise((resolve) => {
    const tx = db.transaction(DB_STORE, 'readonly');
    const req = tx.objectStore(DB_STORE).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => resolve(null);
    tx.oncomplete = () => db.close();
  })).catch(() => null);
}

function notFound() {
  return new Response('bundle entry not found', { status: 404 });
}

function fullResponse(u8, type) {
  return new Response(u8, {
    status: 200,
    headers: {
      'Content-Type': type,
      'Content-Length': String(u8.byteLength),
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'no-cache',
    },
  });
}

// Parse a single `bytes=start-end` range against a known length.
function parseRange(header, len) {
  const m = /^bytes=(\d*)-(\d*)$/.exec((header || '').trim());
  if (!m) return null;
  let start = m[1] === '' ? null : parseInt(m[1], 10);
  let end = m[2] === '' ? null : parseInt(m[2], 10);
  if (start === null && end === null) return null;
  if (start === null) { start = len - end; end = len - 1; }       // suffix range
  else if (end === null || end >= len) { end = len - 1; }
  if (start > end || start < 0) return null;
  return { start, end };
}

function rangeResponse(u8, type, range) {
  const slice = u8.subarray(range.start, range.end + 1);
  return new Response(slice, {
    status: 206,
    headers: {
      'Content-Type': type,
      'Content-Length': String(slice.byteLength),
      'Content-Range': 'bytes ' + range.start + '-' + range.end + '/' + u8.byteLength,
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'no-cache',
    },
  });
}

async function handle(request, url) {
  const rest = decodeURIComponent(url.pathname.slice(MOUNT.length));
  const slash = rest.indexOf('/');
  if (slash < 0) return notFound();
  const name = rest.slice(0, slash);
  const entry = rest.slice(slash + 1);
  const record = await dbGet(name);
  if (!record || !record.files) return notFound();
  const bytes = record.files[entry];
  if (!bytes) return notFound();
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const type = mimeFor(entry);
  const range = parseRange(request.headers.get('Range'), u8.byteLength);
  return range ? rangeResponse(u8, type, range) : fullResponse(u8, type);
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith(MOUNT)) return;   // not ours → default network
  event.respondWith(handle(event.request, url));
});
