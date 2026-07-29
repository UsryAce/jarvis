const CACHE = "jarvis-core-v5";
const CACHE_PREFIX = "jarvis-";
const STABLE_SHELL = [
  "/",
  "/mobile",
  "/manifest.webmanifest",
  "/claude-design/JARVIS%20Core.dc.html",
  "/claude-design/JARVIS%20Mobile.dc.html",
  "/claude-design/support.js",
  "/claude-design/jarvis-adapter.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) =>
        Promise.allSettled(
          STABLE_SHELL.map(async (url) => {
            const response = await fetch(url, { cache: "no-store" });
            if (isCacheable(response)) await cache.put(url, response);
          }),
        ),
      )
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

const isCacheable = (response) => {
  if (!response || !response.ok || response.type !== "basic") return false;
  const policy = response.headers.get("cache-control") || "";
  return !/(?:^|,)\s*(?:no-store|private)(?:\s|,|$)/i.test(policy);
};

const cachedFallback = async (request) => {
  const cached = await caches.match(request);
  if (cached) return cached;
  if (request.mode === "navigate") {
    const mobileShell = await caches.match("/mobile");
    if (mobileShell) return mobileShell;
  }
  return Response.error();
};

const networkFirst = async (request, event) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(request, { signal: controller.signal });
    if (isCacheable(response)) {
      event.waitUntil(
        caches.open(CACHE).then((cache) => cache.put(request, response.clone())),
      );
    }
    return response;
  } catch {
    return cachedFallback(request);
  } finally {
    clearTimeout(timeout);
  }
};

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/ws/")
  ) {
    return;
  }

  event.respondWith(networkFirst(request, event));
});
