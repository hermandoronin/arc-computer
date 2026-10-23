"""Check shipping files and links without running a browser."""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import zipfile

root = Path(__file__).resolve().parents[1] / 'dist'

def local_exists(url):
    if not url or url.startswith(('https:', 'http:', '#', 'data:')):
        return
    target = url.split('#', 1)[0].split('?', 1)[0]
    assert (root / target).is_file(), target

class Check(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for attr in ('src', 'href'):
            local_exists(attrs.get(attr, ''))

for page in ('index.html', 'archive.html'):
    parser = Check()
    parser.feed((root / page).read_text())
for stylesheet in ('style.css', 'field.css'):
    for url in re.findall(r'url\(([^)]+)\)', (root / stylesheet).read_text()):
        local_exists(url.strip("\"'"))
for path in ('app.js', 'field.js', 'catalog.js', 'solver.js', 'evidence-logic.js', 'sw.js', 'data/projects.json', 'data/devices.json', 'data/components.json', 'data/evidence.json'):
    assert (root / path).is_file(), path
sw = (root / 'sw.js').read_text()
for file in re.findall(r"'([^']+)'", sw.split('const CORE=')[1].split(';',1)[0]):
    if file != './': local_exists(file)
cache = re.search(r"const CACHE='([^']+)'", sw)[1]
for file in ('app.js', 'field.js'):
    assert f"caches.open('{cache}')" in (root / file).read_text(), file
assert not any(p.suffix in ('.key', '.pem') for p in root.rglob('*'))
with zipfile.ZipFile(root / 'assets/firmware/esp32-camera-3.3.12.zip') as z:
    config = z.read('CameraWebServer/board_config.h').decode()
    selected = re.findall(r'^#define (CAMERA_MODEL_\w+)', config, re.M)
    assert selected == ['CAMERA_MODEL_AI_THINKER'], selected
    ino = z.read('CameraWebServer/CameraWebServer.ino').decode()
    assert 'const char *ssid = "";' in ino and 'const char *password = "";' in ino
    assert z.read('CameraWebServer/UPSTREAM-LICENSE.md')
    manifest=json.loads((root.parent/'research/evidence/firmware-manifest.json').read_text())
    import hashlib
    for entry in manifest['files']:
        assert hashlib.sha256(z.read('CameraWebServer/'+entry['file'])).hexdigest()==entry['packaged_sha256']
print('Static links, service worker cache, firmware model selection, placeholders and SHA-256 checks passed.')
