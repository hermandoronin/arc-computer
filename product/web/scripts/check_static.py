"""Verify shipped static assets and local links without controlling a browser."""
from html.parser import HTMLParser
from pathlib import Path
import re

root=Path(__file__).resolve().parents[1]/'dist'
class Check(HTMLParser):
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        for attr in ['src','href']:
            url=attrs.get(attr,'')
            if url and not url.startswith(('https:','http:','#','data:')):
                assert (root/url).is_file(),url
parser=Check();parser.feed((root/'index.html').read_text())
for url in re.findall(r'url\(([^)]+)\)',(root/'style.css').read_text()):
    assert (root/url.strip("\"'")).is_file(),url
for path in ['app.js','catalog.js','solver.js','sw.js','data/projects.json','data/devices.json','data/components.json']:
    assert (root/path).is_file(),path
assert not any(p.suffix in ['.key','.pem'] for p in root.rglob('*'))
print('Static asset and local-link checks passed.')
