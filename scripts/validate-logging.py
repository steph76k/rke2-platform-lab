#!/usr/bin/env python3
"""Validate staged cluster-1 logging offline; never deploy or read credentials."""
import argparse
import json
from pathlib import Path
import subprocess
import yaml
import jsonschema
from validate import strict, kubernetes_types, omit_null_fields

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--charts-dir', required=True, type=Path)
    p.add_argument('--schemas-dir', required=True, type=Path)
    a = p.parse_args()
    schemas = {}
    for f in a.schemas_dir.glob('*.json'):
        obj = json.loads(f.read_text())
        if obj.get('kind') == 'CustomResourceDefinition':
            for v in obj['spec']['versions']:
                if v['served']:
                    schemas[(obj['spec']['group'] + '/' + v['name'], obj['spec']['names']['kind'])] = strict(v['schema']['openAPIV3Schema'])
    openapi = kubernetes_types(json.loads((a.schemas_dir / 'kubernetes-openapi.json').read_text()))
    for definition in openapi['definitions'].values():
        for g in definition.get('x-kubernetes-group-version-kind', []):
            schemas[((g['group'] + '/' if g['group'] else '') + g['version'], g['kind'])] = dict(definition, definitions=openapi['definitions'])
    configs, resources = {}, []
    paths = sorted((ROOT / 'bundles/application/logging').glob('*/fleet.yaml'))
    for path in paths:
        f = yaml.safe_load(path.read_text()); configs[f['name']] = f
        assert f['name'].startswith('lab-app-')
        assert f['overrideTargets'] == [{'name': 'lab-applications', 'clusterSelector': {'matchLabels': {'environment': 'lab', 'role': 'applications'}}}]
        spec = {k: v for k, v in f.items() if k not in ['name', 'overrideTargets']}
        spec['targets'] = f['overrideTargets']
        jsonschema.Draft4Validator(schemas[('fleet.cattle.io/v1alpha1', 'Bundle')]).validate({'apiVersion': 'fleet.cattle.io/v1alpha1', 'kind': 'Bundle', 'metadata': {'name': f['name']}, 'spec': spec})
        h = f['helm']
        assert not h.get('force') and not h.get('takeOwnership')
        if 'chart' in h:
            chart = a.charts_dir / h['chart']; meta = yaml.safe_load((chart / 'Chart.yaml').read_text())
            assert meta['version'] == h['version'] == '109.0.1+up4.10.0-rancher.24'
            values = path.parent / 'values.yaml'
            lint = subprocess.run(['helm', 'lint', str(chart), '-f', str(values), '--strict', '--kube-version=1.33.7'], capture_output=True, text=True)
            if lint.returncode:
                errors = [line for line in lint.stdout.splitlines() if '[ERROR]' in line or '[WARNING]' in line]
                known = "[ERROR] Chart.yaml: chart type is not valid in apiVersion 'v1'. It is valid in apiVersion 'v2'"
                assert h['chart'] == 'rancher-logging-crd' and errors == [known], lint.stdout + lint.stderr
                assert meta.get('apiVersion') == 'v1' and meta.get('type') == 'application'
                print('KNOWN UPSTREAM LINT FAILURE: rancher-logging-crd Chart.yaml uses apiVersion v1 with type application; render/schema checks remain mandatory.')
            command = ['helm', 'template', h['releaseName'], str(chart), '-n', f['defaultNamespace'], '-f', str(values), '--include-crds', '--kube-version=1.33.7']
            rendered = subprocess.run(command, check=True, capture_output=True, text=True).stdout
            docs = [x for x in yaml.safe_load_all(rendered) if x]
        else:
            docs = [x for file in path.parent.glob('*.yaml') if file.name != 'fleet.yaml' for x in yaml.safe_load_all(file.read_text()) if x]
        resources.extend(docs)
    for obj in resources:
        if obj['kind'] == 'CustomResourceDefinition':
            for v in obj['spec']['versions']:
                if v['served']:
                    schemas[(obj['spec']['group'] + '/' + v['name'], obj['spec']['names']['kind'])] = strict(v['schema']['openAPIV3Schema'])
    identities = set()
    for obj in resources:
        identity = (obj['apiVersion'], obj['kind'], obj['metadata'].get('namespace'), obj['metadata']['name'])
        assert identity not in identities, identity
        identities.add(identity)
        jsonschema.Draft4Validator(schemas[(obj['apiVersion'], obj['kind'])]).validate(omit_null_fields(obj))
    resolved = {'lab-app-external-secrets'}
    pending = set(configs)
    while pending:
        ready = {n for n in pending if all(d['name'] in resolved for d in configs[n].get('dependsOn', []))}
        assert ready, 'Missing dependency or cycle'
        resolved |= ready; pending -= ready
    loggings = [x for x in resources if x['kind'] == 'Logging']
    agents = [x for x in resources if x['kind'] == 'FluentbitAgent']
    assert len(loggings) == len(agents) == 1
    assert loggings[0]['metadata']['name'] == agents[0]['metadata']['name'] == 'rancher-logging-root'
    output = next(x['spec']['opensearch'] for x in resources if x['kind'] == 'ClusterOutput')
    assert output['scheme'] == 'https' and output['ssl_verify'] is True
    assert output['logstash_prefix'] == 'kubernetes-rke2-cluster1'
    es = next(x for x in resources if x['kind'] == 'ExternalSecret')
    keys = {x['secretKey'] for x in es['spec']['data']}
    assert {'username', 'password', 'ca.crt'} <= keys
    assert output['password']['valueFrom']['secretKeyRef']['name'] == es['spec']['target']['name']
    assert output['ca_file']['mountFrom']['secretKeyRef']['key'] in keys
    assert not any(x['kind'] == 'Secret' for x in resources), 'Do not commit credential-bearing Secrets'
    print(f'PASS: {len(configs)} application logging bundles, two pinned charts, {len(resources)} resources, API schemas, DAG, single root pipeline, TLS/ESO references.')

if __name__ == '__main__':
    main()
