const CACHE='arc-field-v2';
const CORE=['./','index.html','field.css','field.js','evidence-logic.js','data/evidence.json','archive.html','style.css','app.js','catalog.js','solver.js','assets/workbench.webp','assets/mono.woff2','assets/display.woff2','assets/favicon.svg','assets/door-alarm.ino','assets/evidence/esp32-cam.jpg','assets/evidence/esp32-cam_parts.jpg','assets/evidence/esp32-cam-schematic.png','assets/evidence/pinout.png','assets/evidence/cam_versions.jpg','assets/evidence/rpi-csi-connector.png','assets/firmware/esp32-camera-3.3.12.zip'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('arc-field-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
 event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request).then(response=>{
   if(response.ok&&response.type==='basic'){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}
   return response;
 }).catch(()=>event.request.mode==='navigate'?caches.match('./'):Response.error())));
});
