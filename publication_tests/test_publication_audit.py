"""Synthetic regression tests; no private identifiers or real credentials."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.publication_audit import audit, detect


class PublicationAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture Author')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.commit('readme.txt', 'Synthetic fixture\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, timeout=10).stdout

    def commit(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')
        self.git('add', '--', name)
        self.git('commit', '-qm', 'Synthetic fixture change')

    def test_clean_scan_does_not_authorize_release(self):
        result = audit(self.root)
        self.assertEqual(result['automated_text_scan'], 'NO_PATTERN_MATCHES')
        self.assertFalse(result['ready_for_public_release'])

    def test_deleted_history_is_scanned_without_echoing_value(self):
        value = 'gh' + 'p_' + 'A' * 36
        self.commit('removed.txt', value)
        self.git('rm', '-q', 'removed.txt')
        self.git('commit', '-qm', 'Remove synthetic fixture')
        result = audit(self.root)
        self.assertGreater(result['object_rule_counts']['github_token_shape'], 0)
        self.assertNotIn(value, json.dumps(result))
        self.assertNotIn('removed.txt', json.dumps(result))

    def test_other_branch_is_scanned(self):
        original = self.git('branch', '--show-current').decode().strip()
        self.git('checkout', '-qb', 'fixture-other')
        self.commit('other.txt', 'AK' + 'IA' + 'B' * 16)
        self.git('checkout', '-q', original)
        self.assertIn('aws_access_key_shape', audit(self.root)['object_rule_counts'])

    def test_metadata_is_scanned(self):
        self.git('config', 'user.email', 'fixture@host' + '.local')
        self.commit('metadata.txt', 'fixture\n')
        self.assertIn('local_domain_email', audit(self.root)['object_rule_counts'])

    def test_size_limit_is_incomplete_not_clean(self):
        result = audit(self.root, max_object_bytes=30)
        self.assertEqual(result['automated_text_scan'], 'INCOMPLETE')
        self.assertGreater(result['objects_skipped'], 0)

    def test_shallow_clone_is_rejected(self):
        shallow = self.root / 'shallow'
        subprocess.run(['git', 'clone', '-q', '--depth', '1', self.root.as_uri(), str(shallow)],
                       check=True, capture_output=True, timeout=10)
        with self.assertRaisesRegex(RuntimeError, 'FULL_HISTORY_REQUIRED'):
            audit(shallow)

    def test_no_real_values_in_detection_labels(self):
        self.assertEqual(detect(b'Ordinary synthetic example'), [])
        payload = ('-----BEGIN ' + 'PRIVATE KEY-----').encode()
        self.assertEqual(detect(payload), ['private_key_header'])


if __name__ == '__main__':
    unittest.main()
