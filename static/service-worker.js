const CACHE_NAME = 'power-safety-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Basic fetch handler to satisfy PWA installation criteria without caching issues
    event.respondWith(fetch(event.request));
});
