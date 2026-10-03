// Network first, falling back to the last copy: listings stay fresh online, and the
// installed app still opens (with the last listings) offline.
const CACHE = "whatson-v1";

// Save the page, its scripts and styles (hashed names, read from the page) and the
// listings straight away, so the app opens offline even after just one visit.
self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      try {
        const page = await fetch("./", { cache: "no-cache" });
        if (page.ok) {
          await cache.put("./", page.clone());
          const html = await page.text();
          const assets = [...html.matchAll(/(?:src|href)="(\.\/assets\/[^"]+)"/g)].map((m) => m[1]);
          await cache.addAll([...new Set(assets)]);
          await cache.addAll(["./data/events.json", "./data/venues.json", "./data/status.json"]);
        }
      } catch {
        // Offline or a partial deploy: the network-first handler fills the cache later.
      }
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key);
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  // Only this site's own files; venue images and booking sites go straight through.
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(
    (async () => {
      try {
        const response = await fetch(request);
        if (response.ok) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE).then((cache) => cache.put(request, copy)));
        }
        return response;
      } catch (error) {
        // Filtered views (?tags=…) share the one cached page. ignoreVary: the module
        // script is requested with an Origin header that the saved copy wasn't.
        const cached = await caches.match(request, { ignoreSearch: request.mode === "navigate", ignoreVary: true });
        if (cached) return cached;
        throw error;
      }
    })(),
  );
});
