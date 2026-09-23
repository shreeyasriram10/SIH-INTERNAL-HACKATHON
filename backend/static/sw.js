/* LOHA DRISHTI service worker - offline mode for low-coverage sites.

   Pages and data are NETWORK-FIRST: a connected browser always gets the
   current build and live figures, and the cache is only read when the network
   fails. That matters here - a cache-first shell would reintroduce exactly the
   stale-page problem the server's no-store headers were added to prevent.

   Fingerprinted assets (/static/...?v=<hash>) are immutable, so they are
   served from cache first.

   Only an allowlist of read-only reference data is cached. Priced decisions
   (POST) are never cached here; the page keeps the last plan itself. */
const CACHE = 'ld-offline-v1';
const SHELL = ['/app', '/ml-training', '/verification', '/login'];
const API_ALLOW = [/^\/api\/ports\/?$/, /^\/api\/vessels\/?$/, /^\/api\/ops\/emergency$/,
                   /^\/api\/market\//, /^\/api\/auth\/access$/, /^\/api\/waterways/];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(() => {}).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function networkFirst(request){
  const cache = await caches.open(CACHE);
  try{
    const response = await fetch(request);
    if(response.ok) cache.put(request, response.clone());
    return response;
  }catch(err){
    const hit = await cache.match(request, {ignoreSearch: request.mode === 'navigate'});
    if(hit) return hit;
    throw err;
  }
}

async function cacheFirst(request){
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if(hit) return hit;
  const response = await fetch(request);
  if(response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if(request.method !== 'GET') return;
  const url = new URL(request.url);
  if(url.origin !== self.location.origin) return;

  if(url.pathname.startsWith('/static/')){
    event.respondWith(url.searchParams.has('v') ? cacheFirst(request) : networkFirst(request));
    return;
  }
  if(request.mode === 'navigate' || SHELL.includes(url.pathname)){
    event.respondWith(networkFirst(request));
    return;
  }
  if(API_ALLOW.some(re => re.test(url.pathname))){
    event.respondWith(networkFirst(request));
  }
});

/* Signing out clears everything this worker saved. */
self.addEventListener('message', event => {
  if(event.data === 'ld-clear') event.waitUntil(caches.delete(CACHE));
});
