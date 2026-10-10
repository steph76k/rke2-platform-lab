"""Credential generation contract tests. All OpenBao calls are mocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import bcrypt
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'scripts/bootstrap-new-lab-secrets.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_no_writes_without_explicit_flag(self):
        with patch('sys.argv', ['bootstrap']), patch.object(bootstrap.subprocess, 'run') as run:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bootstrap.main()
            run.assert_not_called()

    def test_existing_destination_blocks_bootstrap(self):
        with patch('sys.argv', ['bootstrap', '--execute-new-lab']), patch.object(bootstrap.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '{}', '')
            with self.assertRaisesRegex(RuntimeError, 'Destination exists'):
                bootstrap.main()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][2:4], ['metadata', 'get'])

    def test_generated_values_satisfy_bootstrap_owned_external_secrets(self):
        stored = {}

        def fake_run(argv, **kwargs):
            if argv[2] == 'metadata':
                return subprocess.CompletedProcess(argv, 2, '', 'No value found')
            self.assertEqual(argv[2], 'put')
            self.assertIn('-cas=0', argv)
            self.assertEqual(argv[-1], '-')
            payload = json.loads(kwargs['input'])
            path = argv[-2]
            self.assertNotIn(path, stored)
            stored[path] = payload
            return subprocess.CompletedProcess(argv, 0, '', '')

        with patch('sys.argv', ['bootstrap', '--execute-new-lab']), patch.object(bootstrap.subprocess, 'run', side_effect=fake_run):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                bootstrap.main()
        for path in (ROOT / 'bundles/infrastructure/secrets').rglob('*.yaml'):
            for obj in yaml.safe_load_all(path.read_text()):
                if not obj or obj.get('kind') != 'ExternalSecret':
                    continue
                for item in obj['spec']['data']:
                    remote = item['remoteRef']
                    # These additive paths are owned by the separate AFI OIDC /
                    # logging and bootstrap-minio.py bootstraps, not the destructive fresh-lab bootstrap.
                    if remote['key'].startswith(('platform/afi-logging/', 'platform/oidc/', 'platform/minio/')):
                        continue
                    self.assertIn(remote['property'], stored[remote['key']])
        creds = stored['platform/harbor/credentials']
        self.assertEqual(len(creds['secret-key']), 16)
        self.assertEqual(len(creds['csrf-key']), 32)
        self.assertTrue(stored['platform/harbor/token-tls']['tls.key'].startswith('-----BEGIN RSA PRIVATE KEY-----'))
        self.assertTrue(stored['platform/opensearch/tls']['tls.key'].startswith('-----BEGIN PRIVATE KEY-----'))
        self.assertTrue(bcrypt.checkpw(creds['registry-password'].encode(), creds['registry-htpasswd'].split(':', 1)[1].encode()))
        users = yaml.safe_load(stored['platform/opensearch/security']['internal_users.yml'])
        for user, path in [('admin', 'platform/opensearch/admin'), ('kibanaserver', 'platform/opensearch/dashboards'), ('platform-logging', 'platform/opensearch/logging')]:
            self.assertTrue(bcrypt.checkpw(stored[path]['password'].encode(), users[user]['hash'].encode()))
            self.assertNotIn(stored[path]['password'], output.getvalue())
        node = x509.load_pem_x509_certificate(stored['platform/opensearch/tls']['tls.crt'].encode())
        ca = x509.load_pem_x509_certificate(stored['platform/opensearch/tls']['ca.crt'].encode())
        ca.public_key().verify(node.signature, node.tbs_certificate_bytes, padding.PKCS1v15(), node.signature_hash_algorithm)
        self.assertIn('opensearch-cluster-master', node.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName))
        self.assertEqual(node.subject.rfc4514_string(), 'CN=opensearch-nodes')


if __name__ == '__main__':
    unittest.main()
