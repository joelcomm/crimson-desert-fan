#!/usr/bin/env python3
"""Build the public website version of the voyage companion as one Cloudflare Worker.

index.html in this folder is the source of truth (it is also what the Claude artifact
publishes). This wraps it in a full HTML document, adds the web-app manifest, icons and
an offline service worker, and bundles everything into site/worker.js for upload.
"""
import base64, json, pathlib, time

HERE = pathlib.Path(__file__).parent
SITE = HERE / "site"
SITE.mkdir(exist_ok=True)

page = (HERE / "index.html").read_text()
version = time.strftime("%Y%m%d%H%M%S")

head = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0B3D91">
<meta name="description" content="Pathway to Sunshine: an independent guest companion for the Barcelona to Miami voyage, Nov 17 to Dec 2, 2026.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Sunshine">
<style>:root{{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}html{{scroll-padding-top:env(safe-area-inset-top,0px)}}body{{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}}img{{max-width:100%}}[hidden]:not([hidden=until-found i]){{display:none!important}}</style>
</head><body>
"""
index_html = head + page + "\n</body></html>\n"

manifest = {
    "name": "Pathway to Sunshine",
    "short_name": "Sunshine",
    "description": "Guest companion for the Barcelona to Miami voyage, Nov 17 to Dec 2, 2026.",
    "start_url": "./#today",
    "scope": "./",
    "display": "standalone",
    "background_color": "#FFFFFF",
    "theme_color": "#0B3D91",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
}

# Network first so new programs show up as soon as there is a connection;
# fall back to the saved copy after a few seconds on slow or missing ship Wi-Fi.
sw = """const CACHE='sunshine-%s';
const CORE=['./','./manifest.webmanifest','./icon-192.png','./icon-512.png','./icon-180.png'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE)))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  const r=e.request;if(r.method!=='GET')return;
  const nav=r.mode==='navigate';
  const key=nav?'./':r;
  const net=fetch(r).then(res=>{if(res&&(res.ok||res.type==='opaque')){const copy=res.clone();caches.open(CACHE).then(c=>c.put(key,copy))}return res});
  const cached=()=>caches.match(key);
  const timeout=new Promise(ok=>setTimeout(ok,nav?4000:8000));
  e.respondWith(Promise.race([net.catch(()=>null),timeout.then(()=>null)]).then(res=>res||cached().then(m=>m||net)));
});
""" % version

files = {
    "/": ("text/html; charset=utf-8", index_html, False, "no-cache"),
    "/sw.js": ("text/javascript; charset=utf-8", sw, False, "no-cache"),
    "/manifest.webmanifest": ("application/manifest+json", json.dumps(manifest, indent=1), False, "public, max-age=3600"),
}
for n in (180, 192, 512):
    data = (SITE / f"icon-{n}.png").read_bytes()
    files[f"/icon-{n}.png"] = ("image/png", base64.b64encode(data).decode(), True, "public, max-age=604800")

(SITE / "index.html").write_text(index_html)
(SITE / "sw.js").write_text(sw)
(SITE / "manifest.webmanifest").write_text(json.dumps(manifest, indent=1))

table = {k: {"type": t, "body": b, "b64": b64, "cache": c} for k, (t, b, b64, c) in files.items()}
worker = """const FILES=%s;
const HEADERS={'x-content-type-options':'nosniff','referrer-policy':'no-referrer'};
export default{async fetch(req){
  const url=new URL(req.url);let p=url.pathname;if(p==='/index.html')p='/';
  const f=FILES[p];
  if(!f)return new Response('Not found',{status:404,headers:{'content-type':'text/plain'}});
  const body=f.b64?Uint8Array.from(atob(f.body),c=>c.charCodeAt(0)):f.body;
  return new Response(req.method==='HEAD'?null:body,{headers:{...HEADERS,'content-type':f.type,'cache-control':f.cache}});
}};
""" % json.dumps(table, ensure_ascii=False)
(SITE / "worker.js").write_text(worker)
print(f"built site/worker.js ({len(worker)//1024} KB), version {version}")
