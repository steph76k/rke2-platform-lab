#!/usr/bin/env python3
"""Approved live test: block only a synthetic output, replace Fluentd pod, recover.

This intentionally restarts the cluster's real Fluentd collector. Run only in an
approved maintenance window after the persistent PVC rollout is complete.
"""
import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
import yaml
from afi_platform import CONFIG, ROOT, kv, sessions

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--cluster', type=int, choices=[1, 2], required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--kubeconfig', type=Path, help='Optional direct cluster kubeconfig instead of Rancher proxy')
p.add_argument('--approved-restart', action='store_true', required=True)
a = p.parse_args()
os.umask(0o077)
k = ['kubectl', '--request-timeout=30s'] + (['--context=rke2-cluster1'] if a.cluster == 1 else
    ['--context=rancher', '--server=https://rancher.berger.ph/k8s/clusters/c-44q9v'])
if a.kubeconfig:
    k = ['kubectl', '--kubeconfig=' + str(a.kubeconfig), '--request-timeout=30s']
ns = 'cattle-logging-system'
pod_name = 'rancher-logging-root-fluentd-0'
run_id = str(int(time.time()))
name = 'afi-buffer-' + run_id
test_ns = name
prefix = 'logs-rke2-cluster' + str(a.cluster) + '-validation-' + run_id

def run(args, data=None, optional=False):
    r = subprocess.run(k + args, input=json.dumps(data) if data is not None else None,
                       text=True, capture_output=True)
    if r.returncode and not optional:
        raise RuntimeError('Kubernetes command failed: ' + ' '.join(args[:3]))
    return r

def get(args):
    return json.loads(run(['get', *args, '-o', 'json']).stdout)

def metrics():
    r = run(['exec', '-n', ns, pod_name, '-c', 'fluentd', '--', 'curl',
             '--max-time', '5', '-s', 'http://localhost:24231/metrics'], optional=True)
    return [line for line in r.stdout.splitlines() if line.startswith(
        'fluentd_output_status_buffer_total_bytes{') and name in line]

def wait_until(condition, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(3)
    raise RuntimeError('Timed out waiting for collector test condition')

before = get(['pod', pod_name, '-n', ns])
buffer_mount = next(m for c in before['spec']['containers'] if c['name'] == 'fluentd'
                    for m in c['volumeMounts'] if m['mountPath'] == '/buffers')
buffer_volume = next(v for v in before['spec']['volumes'] if v['name'] == buffer_mount['name'])
claim_name = buffer_volume['persistentVolumeClaim']['claimName']
assert claim_name.startswith('rancher-logging-root-afi-fluentd-buffer-'), 'Unexpected buffer claim'
pvc = get(['pvc', claim_name, '-n', ns])
assert pvc['status']['phase'] == 'Bound'
assert run(['get', 'namespace', test_ns], optional=True).returncode != 0
docs = list(yaml.safe_load_all((ROOT / ('config/afi-isolation/rollout/cluster' +
    str(a.cluster) + '-logging-output.yaml')).read_text()))
output = next(d for d in docs if d['kind'] == 'ClusterOutput')
output['metadata'] = {'name': name, 'namespace': ns}
settings = output['spec']['opensearch']
settings['port'] = 9201
settings['logstash_prefix'] = prefix
settings['buffer']['total_limit_size'] = '256m'
flow = {'apiVersion': 'logging.banzaicloud.io/v1beta1', 'kind': 'ClusterFlow',
    'metadata': {'name': name, 'namespace': ns}, 'spec': {
        'match': [{'select': {'namespaces': [test_ns]}}], 'globalOutputRefs': [name]}}
resources = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': test_ns}}, output, flow]
run(['create', '-f', '-'], {'apiVersion': 'v1', 'kind': 'List', 'items': resources})
restored = False
with tempfile.TemporaryDirectory(prefix='afi-durability-') as directory:
    ca = Path(directory) / 'ca.crt'
    ca.write_text(kv('pki/lab-ca')['ca.crt'])
    _, admin = sessions(ca)
    try:
        wait_until(lambda: bool(metrics()))
        script = 'i=0; while [ "$i" -lt 50 ]; do echo AFI_BUFFER_' + run_id + '_$i; i=$((i+1)); done; sleep 10'
        probe = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': test_ns},
            'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                'containers': [{'name': 'probe', 'image': 'docker.io/library/busybox:1.36',
                    'command': ['sh', '-c', script], 'resources': {
                        'requests': {'cpu': '10m', 'memory': '8Mi'},
                        'limits': {'cpu': '100m', 'memory': '32Mi'}}}]}}
        run(['create', '-f', '-'], probe)
        wait_until(lambda: any(float(line.rsplit(' ', 1)[1]) > 0 for line in metrics()))
        print('Synthetic records buffered; replacing the approved real collector pod', flush=True)
        run(['delete', 'pod', pod_name, '-n', ns, '--wait=false'])

        def ready_replacement():
            r = run(['get', 'pod', pod_name, '-n', ns, '-o', 'json'], optional=True)
            if r.returncode:
                return False
            d = json.loads(r.stdout)
            statuses = d.get('status', {}).get('containerStatuses', [])
            return d['metadata']['uid'] != before['metadata']['uid'] and statuses and all(
                c['ready'] for c in statuses)

        wait_until(ready_replacement)
        wait_until(lambda: any(float(line.rsplit(' ', 1)[1]) > 0 for line in metrics()))
        assert get(['pvc', claim_name, '-n', ns])['metadata']['uid'] == pvc['metadata']['uid']
        settings['port'] = 9200
        run(['apply', '-f', '-'], output)
        restored = True
        found = []

        def delivered():
            global found
            r = admin.post(CONFIG['opensearch_tunnel'] + '/' + prefix + '-*/_search',
                           json={'size': 200, 'query': {'match_all': {}}}, timeout=30)
            if r.status_code == 404:
                return False
            r.raise_for_status()
            found = [h['_source'].get('log', h['_source'].get('message', '')).strip() for h in r.json()['hits']['hits']
                     if h['_source'].get('log', h['_source'].get('message', '')).startswith('AFI_BUFFER_' + run_id + '_')]
            return len(set(found)) == 50

        wait_until(delivered)
        result = {'cluster': 'rke2-cluster' + str(a.cluster), 'realCollectorPodReplaced': True,
            'samePersistentPVC': True, 'queuePresentAfterReplacement': True,
            'uniqueRecordsDelivered': len(set(found)), 'duplicates': len(found) - len(set(found)),
            'onlySyntheticOutputUnavailable': True}
        a.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        if not restored:
            settings['port'] = 9200
            run(['apply', '-f', '-'], output, optional=True)
        run(['delete', 'namespace', test_ns, '--wait=false'], optional=True)
        run(['delete', 'clusterflow', name, '-n', ns], optional=True)
        run(['delete', 'clusteroutput', name, '-n', ns], optional=True)
        # These indices belong exclusively to this invocation's synthetic output.
        r = admin.delete(CONFIG['opensearch_tunnel'] + '/' + prefix + '-*', timeout=30)
        assert r.status_code in [200, 404]
