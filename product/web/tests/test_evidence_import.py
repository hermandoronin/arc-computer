import copy
import importlib.util
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('import_evidence', ROOT / 'scripts/import_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EvidenceImportTests(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads((ROOT / 'research/evidence/seed.json').read_text())
    def test_valid_pack_and_idempotent_merge(self):
        self.assertEqual(module.merge([self.pack, copy.deepcopy(self.pack)]), self.pack)
    def test_conflicting_observations_not_silently_overwritten(self):
        other = copy.deepcopy(self.pack)
        other['devices'][0]['chips'][0]['name'] = 'GUESS'
        with self.assertRaises(ValueError): module.merge([self.pack, other])
    def test_missing_source_rejected(self):
        self.pack['devices'][0]['claims'][0]['source_ids'] = ['missing-source']
        with self.assertRaises(AssertionError): module.validate(self.pack)
    def test_missing_scope_rejected(self):
        self.pack['devices'][0]['claims'][0]['scope'] = ''
        with self.assertRaises(AssertionError): module.validate(self.pack)
    def test_hardware_claim_requires_test_report(self):
        self.pack['routes'][0]['bench_tested'] = True
        with self.assertRaises(AssertionError): module.validate(self.pack)

if __name__ == '__main__': unittest.main()
