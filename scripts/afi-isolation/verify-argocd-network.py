#!/usr/bin/env python3
"""Read-only demo HTTP and direct cross-tenant Pod connectivity checks."""
import argparse
import concurrent.futures
import hashlib
import json
import socket
import subprocess
from pathlib import Path
import requests

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kubeconfig', required=True)
parser.add_argument('--ingress-ip', default='192.168.1.195')
parser.add_argument('--output', type=Path, required=True)
a = parser.parse_args()
kube = ['kubectl', '--kubeconfig=' + a.kubeconfig, '--request-timeout=20s']
pods, pages = [], []
for tenant in ['mandant-a', 'mandant-b']:
    ns = tenant + '-dev'
    r = subprocess.run(kube + ['get', 'pods', '-n', ns, '-l', 'app.kubernetes.io/name=tenant-demo', '-o', 'json'], capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError('Cannot read demo Pods')
    items = json.loads(r.stdout)['items']
    assert len(items) == 2 and len({p['spec']['nodeName'] for p in items}) == 2
    for p in items:
        assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status']['conditions'])
        pods.append({'tenant': tenant, 'namespace': ns, 'name': p['metadata']['name'], 'ip': p['status']['podIP'], 'node': p['spec']['nodeName']})
    host = tenant + '-demo.berger.ph'
    r = requests.get('http://' + a.ingress_ip + '/', headers={'Host': host}, timeout=20)
    assert r.status_code == 200 and tenant.replace('-', ' ') in r.text.lower(), (host, r.status_code)
    try:
        dns = socket.gethostbyname(host)
    except socket.gaierror:
        dns = None
    pages.append({'host': host, 'httpStatus': r.status_code, 'dnsAddress': dns, 'sha256': hashlib.sha256(r.content).hexdigest()})

def check(pair):
    source, target = pair
    r = subprocess.run(kube + ['exec', '-n', source['namespace'], source['name'], '-c', 'web', '--', 'wget', '-T', '3', '-qO-', 'http://' + target['ip'] + ':8080/'], capture_output=True, text=True, timeout=20)
    allowed = source['tenant'] == target['tenant']
    if allowed:
        assert r.returncode == 0 and target['tenant'].replace('-', ' ') in r.stdout.lower(), (source['name'], target['name'], 'same-tenant access failed')
    else:
        assert r.returncode != 0 and ('timed out' in r.stderr.lower() or 'timeout' in r.stderr.lower()), (source['name'], target['name'], 'expected network timeout, not an exec/tool error')
    return {'sourceTenant': source['tenant'], 'sourceNode': source['node'], 'targetTenant': target['tenant'], 'targetNode': target['node'], 'expectedAllowed': allowed, 'passed': True}

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(check, [(s,t) for s in pods for t in pods]))
assert pages[0]['sha256'] != pages[1]['sha256']
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps({'pages': pages, 'podConnectivity': results, 'temporaryResourcesCreated': False}, indent=2) + '\n')
print(json.dumps({'httpPagesPassed': len(pages), 'networkChecksPassed': len(results), 'dnsPending': [p['host'] for p in pages if p['dnsAddress'] != a.ingress_ip]}))
