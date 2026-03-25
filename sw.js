self.addEventListener('install', (e) => {
  console.log('[Service Worker] Install');
});

self.addEventListener('fetch', (e) => {
  // Required for PWA installability, though Streamlit requires active internet
  e.respondWith(fetch(e.request));
});