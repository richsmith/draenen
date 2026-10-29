// The page, offline: a service worker that keeps everything the page needs,
// so once it has been opened with a signal it works underground. Written by
// tools/model3d, which fills in VERSION and FILES; a new build is a new
// version, which replaces the saved copy the next time the page is opened.
const VERSION = '__VERSION__';
const FILES = __FILES__;
const APP = `draenen-${VERSION}`;
const TILES = 'draenen-tiles';      // satellite imagery, kept as it's seen

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(APP);
    await c.addAll(FILES);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith('draenen-') && ![APP, TILES].includes(k)) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // imagery: the saved tile if there is one, else fetch and save it
  if (url.hostname === 'server.arcgisonline.com') {
    e.respondWith((async () => {
      const c = await caches.open(TILES);
      const hit = await c.match(e.request);
      if (hit) return hit;
      const r = await fetch(e.request);
      if (r.ok) c.put(e.request, r.clone());
      return r;
    })());
    return;
  }
  if (url.origin !== location.origin) return;
  // everything else: the saved copy, ignoring ?query and #hash
  e.respondWith((async () => {
    const hit = await caches.match(e.request, { ignoreSearch: true });
    return hit || fetch(e.request);
  })());
});
