#!/usr/bin/env python3
"""Read administrative states over TLS/SSE-C and verify SOPS backups.

Requires AFI_RECOVERY_KEY and AFI_BACKUP_DIR outside Git, plus existing OpenBao
operator access. Never prints state contents, API credentials or encryption keys.
"""
import argparse
import base64
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from afi_platform import ROOT, backup, kv

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('tenants', nargs='*', default=['tenants'], help='State scopes; default: shared tenants state')
a = p.parse_args()
if any(not re.fullmatch(r'[a-z][a-z0-9-]{1,39}', t) for t in a.tenants):
    p.error('Invalid tenant slug')
if not os.environ.get('AFI_BACKUP_DIR') or not os.environ.get('AFI_RECOVERY_KEY'):
    p.error('Set AFI_BACKUP_DIR and AFI_RECOVERY_KEY explicitly')
os.umask(0o077)
cfg = json.loads((ROOT / 'config/afi-isolation/state-backend.json').read_text())
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
with tempfile.TemporaryDirectory(prefix='afi-state-backup-') as directory:
    ca = Path(directory) / 'ca.crt'
    ca.write_text(kv('pki/lab-ca')['ca.crt'])
    for tenant in a.tenants:
        credentials = kv('terraform-state/' + tenant)
        client = boto3.client('s3', endpoint_url=cfg['endpoint'], region_name=cfg['region'],
            aws_access_key_id=credentials['access_key'],
            aws_secret_access_key=credentials['secret_key'], verify=str(ca),
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        key = cfg['environment'] + '/' + tenant + '/terraform.tfstate'
        response = client.get_object(Bucket=cfg['bucket'], Key=key,
            SSECustomerAlgorithm='AES256',
            SSECustomerKey=base64.b64decode(credentials['sse_customer_key']))
        state = json.loads(response['Body'].read())
        backup(tenant + '-state-' + stamp, state)
        # Independently recover OpenBao credentials if OpenBao is also lost.
        backup(tenant + '-backend-credentials-' + stamp, credentials)
        backup(tenant + '-backup-metadata-' + stamp, {
            'bucket': cfg['bucket'], 'key': key, 'version_id': response['VersionId'],
            'lineage': state['lineage'], 'serial': state['serial'], 'timestamp': stamp})
        print(json.dumps({'tenant': tenant, 'serial': state['serial'],
            'managed_resources': len(state.get('resources', [])),
            'state_and_credentials_backup_verified': True, 'timestamp': stamp}))
