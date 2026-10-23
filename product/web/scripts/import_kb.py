"""Create a browser-sized, read-only catalogue from the recovered ARC corpus.

Usage: python3 scripts/import_kb.py --root /path/to/ark
Never executes code or copies assembly instructions from unreviewed records.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import subprocess
import tarfile

HERE = pathlib.Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = args.root
    dest = HERE / 'dist' / 'data'
    dest.mkdir(exist_ok=True)
    archive = root / 'final/ark-kb-v0.1.tar.zst'
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected = archive.with_suffix('.zst.sha256').read_text().split()[0]
    if digest != expected:
        raise SystemExit('Archive checksum mismatch')
    counts = collections.Counter()
    components = []
    with subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE) as proc:
        with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
            for member in tar:
                if not member.isfile():
                    continue
                category = member.name.split('/')[1] if '/' in member.name else member.name
                counts[category] += 1
                if category == 'components':
                    d = json.load(tar.extractfile(member))
                    components.append({'id': d['id'], 'name': d.get('name', d['id']),
                                       'category': d.get('category', ''),
                                       'specifications': d.get('specifications', ''),
                                       'provenance': d.get('provenance', {})})
        if proc.wait():
            raise SystemExit('zstd failed')
    raw_projects = {}
    for folder in ['instructables', 'hackaday']:
        for path in (root / 'raw' / folder).glob('*.json'):
            try:
                d = read(path)
                if isinstance(d, dict):
                    raw_projects[path.stem.lower()] = d
            except (ValueError, OSError):
                pass
    projects, devices, errors = [], [], []
    for path in sorted((root / 'extracted-bulk/projects').glob('*.json')):
        try:
            d = read(path)
            raw = raw_projects.get(path.stem.removeprefix('prj:').lower(), {})
            url = raw.get('url') or raw.get('project_url')
            if not isinstance(url, str) or not url.startswith('https://'):
                url = None
            bom = [{'id': x['component_id'], 'quantity': x.get('quantity', 1),
                    'notes': x.get('notes', '')} for x in d.get('required_components', []) if x.get('component_id')]
            projects.append({'id': d['id'], 'name': d.get('name', d['id']),
                             'summary': d.get('summary', ''), 'goals': d.get('goals', []),
                             'difficulty': d.get('difficulty'), 'bom': bom,
                             'source': url, 'author': raw.get('author'),
                             'origin': path.name, 'status': 'unreviewed'})
        except (ValueError, KeyError, TypeError) as error:
            errors.append({'file': path.name, 'error': str(error)})
    for path in sorted((root / 'extracted-bulk/devices').glob('*.json')):
        try:
            d = read(path); dev = d.get('device', d)
            devices.append({'id': dev['id'], 'name': dev.get('name', dev['id']),
                            'category': dev.get('category', ''),
                            'hazards': dev.get('safety_hazards', []),
                            'parts': [{'id': c['component_id'], 'quantity': c.get('quantity', 1)}
                                      for c in d.get('components_inside', []) if c.get('component_id')],
                            'origin': path.name, 'status': 'unreviewed'})
        except (ValueError, KeyError, TypeError) as error:
            errors.append({'file': path.name, 'error': str(error)})
    report = {'imported_at': '2026-10-23', 'archive_sha256': digest,
              'archive_counts': dict(counts), 'projects': len(projects), 'devices': len(devices),
              'components': len(components), 'unique_device_ids': len({d['id'] for d in devices}), 'recovered_project_sources': sum(bool(x['source']) for x in projects),
              'errors': errors, 'warning': 'Machine-extracted records. Not validated hardware instructions. Archive component identifiers and extracted BOM identifiers are separate namespaces; no inferred equivalence.'}
    for name, data in [('projects', projects), ('devices', devices), ('components', components), ('manifest', report)]:
        (dest / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    (HERE / 'research/data-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
