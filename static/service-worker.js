const CACHE_NAME = 'power-safety-v3.8.0';
const ASSETS = [
    '/',
    '/manifest.json',
    '/static/favicon.png',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/icon.svg',
    '/static/dashboard_preview.jpg'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS);
        }).then(() => {
            return self.skipWaiting();
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => {
            return self.clients.claim();
        })
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response.status === 200 && event.request.url.includes('/static/')) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    if (event.request.mode === 'navigate') {
                        return caches.match('/');
                    }
                });
            })
    );
});

// --- Web Push Notifications ---
self.addEventListener('push', (event) => {
    let data = { title: 'СВІТЛО⚡БЕЗПЕКА', body: 'Новий статус', icon: '/static/icon-192.png', url: '/' };

    if (event.data) {
        try {
            const payload = event.data.json();
            data = { ...data, ...payload };
        } catch (e) {
            data.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: data.icon || '/static/icon-192.png',
            badge: data.badge || '/static/favicon.png',
            vibrate: [200, 100, 200],
            data: { url: data.url || '/' },
            actions: [
                { action: 'open', title: 'Відкрити' },
                { action: 'dismiss', title: 'Закрити' }
            ],
            tag: 'power-status',
            renotify: true
        })
    );
});

self.addEventListener('notificationclose', () => {});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    if (event.action === 'dismiss') return;

    const urlToOpen = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            for (const client of windowClients) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    return client.focus();
                }
            }
            return clients.openWindow(urlToOpen);
        })
    );
});
