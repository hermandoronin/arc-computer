"""Validate scoped, source-backed evidence packs and build the public catalogue.

This importer does not turn forum replies into verified facts. Editorial review is
required before a pack enters research/evidence. Unknowns stay explicit.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def validate(data):
    assert data['schema_version'] == 1, 'Unsupported schema'
    indexes = {}
    for group in ('sources', 'assets', 'devices', 'routes'):
        records = data[group]
        ids = [r['id'] for r in records]
        assert all(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,90}', id) for id in ids), f'Unsafe {group} ID'
        assert len(ids) == len(set(ids)), f'Duplicate {group} ID'
        indexes[group] = set(ids)
    for source in data['sources']:
        assert urlparse(source['url']).scheme == 'https', source['id']
        assert source['title'] and source['retrieved_at'], source['id']
    def refs(record):
        assert record.get('source_ids'), f'Missing provenance: {record}'
        assert set(record['source_ids']) <= indexes['sources'], record
    for asset in data['assets']:
        refs(asset)
        assert asset.get('credit'), asset['id']
        assert asset.get('license') or asset.get('license_note'), asset['id']
        src = asset['src']
        assert src.startswith(('https://', 'assets/evidence/')) and '..' not in src.split('/'), src
        if not src.startswith('https://'):
            assert (ROOT / 'dist' / src).is_file(), src
    claims = set()
    for device in data['devices']:
        refs(device)
        assert device['identity'] and device['unknown'] is not None
        for claim in device['claims']:
            assert claim['id'] not in claims, claim['id']
            claims.add(claim['id'])
            assert claim['text'] and claim['scope'], claim
            assert claim['status'] in ('documented', 'unknown', 'photo_observed', 'author_observed', 'author_reported_outcome'), claim
            refs(claim)
        for chip in device['chips']:
            assert chip['scope'] and chip['role'], chip
            refs(chip)
        assert set(device['routes']) <= indexes['routes'], device['id']
    for record in data['devices'] + data['routes']:
        asset_ids = record.get('gallery', []) + record.get('diagrams', [])
        if record.get('image'):
            asset_ids.append(record['image'])
        assert set(asset_ids) <= indexes['assets'], record['id']
        if record.get('bench_tested'):
            assert record.get('test_report_url') and record.get('tested_revision'), 'Physical test requires a report and revision'
    for route in data['routes']:
        refs(route)
        assert route['device_id'] in indexes['devices'], route['id']
        assert route['steps'] and route['tests'] and route['wiring'], route['id']
        assert route['requirements'], route['id']
        req_ids = [r['id'] for r in route['requirements']]
        assert len(req_ids) == len(set(req_ids)), route['id']
        for req in route['requirements']:
            assert isinstance(req['qty'], int) and req['qty'] > 0 and req['check'], req
    return data


def merge(packs):
    result = dict(schema_version=1, updated_at=max(p['updated_at'] for p in packs))
    for group in ('sources', 'assets', 'devices', 'routes'):
        combined = {}
        for pack in packs:
            for record in pack[group]:
                key = record['id']
                if key in combined and combined[key] != record:
                    raise ValueError(f'Conflicting {group}/{key}: review instead of overwriting')
                combined[key] = record
        result[group] = list(combined.values())
    return validate(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packs', nargs='*', type=Path, default=[ROOT / 'research/evidence/seed.json'])
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/data/evidence.json')
    args = parser.parse_args()
    result = merge([json.loads(path.read_text()) for path in args.packs])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f"Validated: {len(result['devices'])} devices, {len(result['routes'])} routes, {len(result['sources'])} sources")
