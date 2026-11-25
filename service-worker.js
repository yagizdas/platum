'use strict';

const CACHE_NAME = 'plato-shell-v1';
const SHELL = [
  './',
  './index.html',
  './menu.html',
  './landing.css',
  './landing.js',
  './menu.css',
  './menu-days.js',
  './dish-icons.js',
  './campus-config.js',
  './report-config.js',
  './report-client.js',
  './pwa-install.css',
  './pwa-install.js',
  './manifest.webmanifest',
  './icons/ui/app-192.png',
  './icons/ui/app-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) caches.open(CACHE_NAME).then(cache => cache.put(event.request, response.clone()));
        return response;
      })
      .catch(() => caches.match(event.request).then(response => {
        if (response) return response;
        if (event.request.mode === 'navigate') return caches.match('./');
        return Response.error();
      }))
  );
});
