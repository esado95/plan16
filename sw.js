/* Офлайн-режим: в зале и в магазине сети может не быть.
   При изменении index.html или списка файлов поднять VERSION —
   иначе телефон останется на старой версии. */
const VERSION = 'plan16-v11';

const ASSETS = [
  './',
  'index.html',
  'manifest.json',
  'icon-180.png',
  'icon-192.png',
  'icon-512.png',
  'icon-512-maskable.png',
  'photos/01-poulet-basquaise.webp',
  'photos/02-piperade.webp',
  'photos/03-omelette-fines-herbes.webp',
  'photos/04-ratatouille.webp',
  'photos/05-saumon-papillote.webp',
  'photos/06-crevettes-ail-persil.webp',
  'photos/07-salade-lentilles.webp',
  'photos/08-escalope-moutarde.webp',
  'photos/09-vinaigrette-maison.webp',
  'photos/10-poulet-roti.webp',
  'photos/11-pot-au-feu.webp',
  'photos/12-blanquette-dinde.webp',
  'photos/13-hachis-parmentier.webp',
  'photos/14-cabillaud-provencale.webp',
  'photos/15-poulet-citron-olives.webp',
  'photos/16-truite-amandes.webp',
  'photos/17-salade-nicoise.webp',
  'photos/18-soupe-oignon.webp',
  'photos/19-potage-parmentier.webp',
  'photos/20-soupe-pistou.webp',
  'photos/21-oeufs-cocotte.webp',
  'photos/22-quiche-poireaux.webp',
  'photos/23-gratin-chou-fleur.webp',
  'photos/24-tian-legumes.webp',
  'photos/25-omelette-champignons.webp'
];

self.addEventListener('install', function(e){
  e.waitUntil(caches.open(VERSION).then(function(c){ return c.addAll(ASSETS); }).then(function(){ return self.skipWaiting(); }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){ return k !== VERSION; }).map(function(k){ return caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});

self.addEventListener('fetch', function(e){
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    caches.match(e.request).then(function(hit){
      return hit || fetch(e.request).catch(function(){
        return e.request.mode === 'navigate' ? caches.match('index.html') : Response.error();
      });
    })
  );
});
