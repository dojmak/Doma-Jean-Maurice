// Service worker — met l'app en cache pour un usage hors-ligne après le premier chargement.
// Incrémenter CACHE à chaque mise à jour d'un fichier ci-dessous (moteur inclus).
const CACHE = "provision-rc-v1";
const FILES = [
  "./", "index.html", "manifest.webmanifest", "icons/icon.svg", "icons/apple-touch-icon.png",
  "engine/provision_engine.py", "engine/bridge.py",
  "vendor/pyodide/pyodide.js", "vendor/pyodide/pyodide.asm.js", "vendor/pyodide/pyodide.asm.wasm",
  "vendor/pyodide/python_stdlib.zip", "vendor/pyodide/pyodide-lock.json",
  "vendor/wheels/et_xmlfile-2.0.0-py3-none-any.whl", "vendor/wheels/openpyxl-3.1.5-py2.py3-none-any.whl",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(hit => hit || fetch(e.request)));
});
