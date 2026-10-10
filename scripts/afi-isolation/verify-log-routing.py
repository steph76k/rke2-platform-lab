#!/usr/bin/env python3
"""Test real namespace routing with forged labels/log fields and blocked Forward access.

Creates two temporary pods, temporarily adds tenant labels to the dev namespaces,
then restores labels and removes its pods. Requires existing platform admin access.
Only synthetic marker documents are inspected; no application log content is printed.
"""
import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from afi_platform import CONFIG, kv, sessions

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--identities', type=Path, help='Protected JSON file containing temporary OIDC identities')
a = p.parse_args()
os.umask(0o077)
k = ['kubectl', '--context=rke2-cluster1', '--request-timeout=30s']

def kubectl(args, data=None):
    r = subprocess.run(k + args, input=json.dumps(data) if data is not None else None,
                       text=True, capture_output=True)
    if r.returncode:
        raise RuntimeError('Kubernetes operation failed: ' + ' '.join(args[:3]))
    return r.stdout

run_id = str(int(time.time()))
created = []
labels = {}
results = {}
with tempfile.TemporaryDirectory(prefix='afi-routing-') as directory:
    ca = Path(directory) / 'ca.crt'
    ca.write_text(kv('pki/lab-ca')['ca.crt'])
    _, admin = sessions(ca)
    base = CONFIG['opensearch_tunnel']
    try:
        for tenant in ['mandant-a', 'mandant-b']:
            namespace = tenant + '-dev'
            other = 'mandant-b' if tenant == 'mandant-a' else 'mandant-a'
            original = json.loads(kubectl(['get', 'namespace', namespace, '-o', 'json']))
            labels[namespace] = {key: original['metadata'].get('labels', {}).get(key)
                                 for key in ['tenant', 'tenant_id']}
            kubectl(['patch', 'namespace', namespace, '--type=merge', '-p', json.dumps({
                'metadata': {'labels': {'tenant': other, 'tenant_id': other}}})])
            name = 'afi-route-' + tenant + '-' + run_id
            marker = {'afi_probe': run_id, 'tenant_id': other, 'cluster_name': 'forged-cluster',
                      'kubernetes': {'namespace_name': other + '-prod'}}
            shell = '''printf '%s\n' "$AFI_MARKER"
nslookup rancher-logging-root-fluentd.cattle-logging-system.svc.cluster.local >/dev/null || exit 43
if nc -z -w 3 rancher-logging-root-fluentd.cattle-logging-system.svc.cluster.local 24240; then
  echo AFI_FORWARD_UNEXPECTEDLY_ALLOWED
  exit 42
else
  echo AFI_FORWARD_BLOCKED
fi
sleep 15
'''
            pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {
                'name': name, 'namespace': namespace,
                'labels': {'tenant': other, 'tenant_id': other, 'app': 'afi-routing-probe'}},
                'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                    'containers': [{'name': 'probe', 'image': 'docker.io/library/busybox:1.36',
                        'command': ['sh', '-c', shell],
                        'env': [{'name': 'AFI_MARKER', 'value': json.dumps(marker)}],
                        'resources': {'requests': {'cpu': '10m', 'memory': '8Mi'},
                                      'limits': {'cpu': '100m', 'memory': '32Mi'}}}]}}
            kubectl(['create', '-f', '-'], pod)
            created.append((namespace, name, tenant))

        deadline = time.monotonic() + 240
        pending = list(created)
        while pending and time.monotonic() < deadline:
            for namespace, name, tenant in list(pending):
                pod = json.loads(kubectl(['get', 'pod', name, '-n', namespace, '-o', 'json']))
                statuses = pod.get('status', {}).get('containerStatuses', [])
                if not statuses or not statuses[0].get('state', {}).get('terminated'):
                    continue
                assert statuses[0]['state']['terminated']['exitCode'] == 0, 'Forward endpoint accessible'
                query = {'query': {'term': {'kubernetes.pod_name': name}}, 'size': 100}
                r = admin.post(base + '/logs-rke2-cluster1-*/_search', json=query, timeout=30)
                r.raise_for_status()
                hits = [hit for hit in r.json()['hits']['hits']
                        if run_id in str(hit['_source'].get('log', hit['_source'].get('message', '')))]
                if not hits:
                    continue
                for hit in hits:
                    source = hit['_source']
                    assert hit['_index'].startswith('logs-rke2-cluster1-' + tenant + '-')
                    assert source['tenant_id'] == tenant
                    assert source['cluster_name'] == 'rke2-cluster1'
                    assert source['kubernetes']['namespace_name'] == namespace
                    assert json.loads(source.get('log', source.get('message', '')))['tenant_id'] != tenant
                results[tenant] = {'forgedNamespaceAndPodLabelsIgnored': True,
                    'forgedLogMetadataContainedInMessage': True, 'realNamespaceUsed': True,
                    'onlyOwnTenantIndex': True, 'directForwardConnectionBlocked': True,
                    'markerHits': len(hits)}
                print(tenant + ': routing and Forward isolation passed', flush=True)
                pending.remove((namespace, name, tenant))
            if pending:
                time.sleep(5)
        assert not pending, 'Timed out waiting for routed synthetic logs'
        if a.identities:
            from validation_oidc import access_token
            identities = json.loads(a.identities.read_text())
            for namespace, name, tenant in created:
                identity = next(user for user in identities.values() if user['tenant'] == tenant)
                _, session = sessions(ca)
                session.auth = None
                session.headers['Authorization'] = 'Bearer ' + access_token(identity)
                own = 'logs-rke2-cluster1-' + tenant + '-*'
                other = 'mandant-b' if tenant == 'mandant-a' else 'mandant-a'
                query = {'query': {'term': {'kubernetes.pod_name': name}}}
                r = session.post(base + '/' + own + '/_search', json=query, timeout=30)
                assert r.status_code == 200 and r.json()['hits']['hits']
                foreign = session.get(base + '/logs-rke2-cluster1-' + other + '-*/_search', timeout=30)
                assert foreign.status_code == 403
                results[tenant]['oidcOwnRealPodLogs'] = 200
                results[tenant]['oidcForeignRealPodLogsDenied'] = 403
    finally:
        for namespace, name, tenant in created:
            kubectl(['delete', 'pod', name, '-n', namespace, '--ignore-not-found', '--wait=false'])
        for namespace, previous in labels.items():
            kubectl(['patch', 'namespace', namespace, '--type=merge', '-p',
                     json.dumps({'metadata': {'labels': previous}})])
        # Only documents from the exact, unique probe pod names are removed.
        time.sleep(15)
        for namespace, name, tenant in created:
            r = admin.post(base + '/logs-rke2-cluster1-' + tenant + '-*/_delete_by_query',
                           json={'query': {'term': {'kubernetes.pod_name': name}}}, timeout=30)
            r.raise_for_status()
            assert not r.json().get('failures')
    results['cleanup'] = {'probePodsRemoved': True, 'namespaceLabelsRestored': True,
                          'onlyOwnProbeDocumentsDeleted': True}
    a.output.write_text(json.dumps(results, indent=2) + '\n')
