const CACHE_NAME = 'mediapass-v1';
const urlsToCache = [
    '/',
    '/static/assets/vendor/fonts/boxicons.css',
    '/static/assets/vendor/css/core.css',
    '/static/assets/vendor/css/theme-default.css',
    '/static/assets/css/demo.css',
    '/static/assets/vendor/libs/jquery/jquery.js',
    '/static/assets/vendor/libs/popper/popper.js',
    '/static/assets/vendor/js/bootstrap.js',
    '/static/assets/vendor/libs/perfect-scrollbar/perfect-scrollbar.js',
    '/static/assets/vendor/js/menu.js',
    '/static/assets/js/main.js',
    'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.4/index.global.min.js'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request)
                    .then(response => {
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });
                        return response;
                    });
            })
    );
});
