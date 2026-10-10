#!/usr/bin/env python3
"""Offline validation; needs unpacked pinned charts and read-only schema exports.

No Kubernetes or OpenBao writes. Rendered manifests stay in memory.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PATHS = ['bundles/00-bootstrap-test', 'bundles/application/operators/external-secrets']


def strict(schema):
    schema = copy.deepcopy(schema)
    if isinstance(schema, dict):
        if schema.get('nullable') and isinstance(schema.get('type'), str):
            schema['type'] = [schema['type'], 'null']
        if schema.get('properties') and not schema.get('x-kubernetes-preserve-unknown-fields'):
            schema.setdefault('additionalProperties', False)
        for key, value in list(schema.items()):
            if isinstance(value, dict):
                schema[key] = {k: strict(v) for k, v in value.items()} if key in ('properties', 'definitions') else strict(value)
            elif isinstance(value, list):
                schema[key] = [strict(v) for v in value]
    return schema


def omit_null_fields(value):
    # Kubernetes decodes null optional map fields as absent (e.g. Harbor's
    # empty, chart-owned Secret.data). Preserve array entries and all values.
    if isinstance(value, dict):
        return {k: omit_null_fields(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [omit_null_fields(v) for v in value]
    return value


def kubernetes_types(value):
    if isinstance(value, dict):
        out = {k: kubernetes_types(v) for k, v in value.items()}
        if out.get('format') == 'int-or-string' or out.get('x-kubernetes-int-or-string') is True:
            out.pop('type', None)
            out['anyOf'] = [{'type': 'string'}, {'type': 'integer'}]
        return out
    if isinstance(value, list):
        return [kubernetes_types(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--charts-dir', type=Path, required=True)
    parser.add_argument('--schemas-dir', type=Path, required=True)
    parser.add_argument('--staged-only', action='store_true', help='Require infrastructure paths to remain inactive')
    args = parser.parse_args()
    for p in ROOT.rglob('*.yaml'):
        list(yaml.safe_load_all(p.read_text()))
    for p in (ROOT / 'config').rglob('*.yml'):
        list(yaml.safe_load_all(p.read_text()))
    gitrepo = yaml.safe_load((ROOT / 'fleet/gitrepo.yaml').read_text())
    active_paths = gitrepo['spec']['paths']
    assert active_paths[:2] == EXPECTED_PATHS, 'Existing active paths changed'
    allowed_paths = {str(p.parent.relative_to(ROOT)) for p in (ROOT / 'bundles/infrastructure').rglob('fleet.yaml')}
    assert len(active_paths) == len(set(active_paths))
    assert set(active_paths[2:]) <= allowed_paths, 'Unknown or overly broad active path'
    if args.staged_only:
        assert active_paths == EXPECTED_PATHS, 'Infrastructure already activated'
    schemas = {}
    for path in args.schemas_dir.glob('*.json'):
        crd = json.loads(path.read_text())
        if crd.get('kind') != 'CustomResourceDefinition':
            continue
        for version in crd['spec']['versions']:
            if version['served']:
                schemas[(crd['spec']['group'] + '/' + version['name'], crd['spec']['names']['kind'])] = strict(version['schema']['openAPIV3Schema'])
    # Built-in API schemas from the actual Kubernetes 1.33 server.
    openapi = kubernetes_types(json.loads((args.schemas_dir / 'kubernetes-openapi.json').read_text()))
    for definition in openapi['definitions'].values():
        for gvk in definition.get('x-kubernetes-group-version-kind', []):
            api = (gvk['group'] + '/' if gvk['group'] else '') + gvk['version']
            schemas[(api, gvk['kind'])] = dict(definition, definitions=openapi['definitions'])
    configs, objects, graph = {}, [], {}
    rendered_secret_names = set()
    for p in sorted((ROOT / 'bundles/infrastructure').rglob('fleet.yaml')):
        f = yaml.safe_load(p.read_text())
        name = f['name']
        assert name.startswith('lab-infra-') and len(name) <= 53 and name not in configs
        assert f['overrideTargets'] == [{'name': 'lab-infrastructure', 'clusterSelector': {'matchLabels': {'environment': 'lab', 'role': 'infrastructure'}}}]
        assert not any(str(p.parent.relative_to(ROOT)).startswith(active + '/') or str(p.parent.relative_to(ROOT)) == active for active in EXPECTED_PATHS)
        spec = {k: v for k, v in f.items() if k not in ('name', 'overrideTargets')}
        spec['targets'] = f['overrideTargets']
        jsonschema.Draft4Validator(schemas[('fleet.cattle.io/v1alpha1', 'Bundle')]).validate({'apiVersion': 'fleet.cattle.io/v1alpha1', 'kind': 'Bundle', 'metadata': {'name': name}, 'spec': spec})
        assert not f['helm'].get('takeOwnership') and not f['helm'].get('force')
        configs[name] = f
        graph[name] = [dep['name'] for dep in f.get('dependsOn', [])]
        if 'chart' in f['helm']:
            h = f['helm']
            chart = args.charts_dir / h['chart']
            meta = yaml.safe_load((chart / 'Chart.yaml').read_text())
            assert str(meta['version']) == str(h['version'])
            values = p.parent / 'values.yaml'
            lint = subprocess.run(['helm', 'lint', str(chart), '-f', str(values), '--strict', '--kube-version=1.33.13'], capture_output=True, text=True)
            assert lint.returncode == 0, f'Helm lint failed: {name}: {lint.stderr or lint.stdout}'
            command = ['helm', 'template', h['releaseName'], str(chart), '-n', f['defaultNamespace'], '-f', str(values), '--include-crds', '--kube-version=1.33.13']
            result = subprocess.run(command, capture_output=True, text=True)
            assert result.returncode == 0, f'Helm render failed: {name}: {result.stderr}'
            docs = [o for o in yaml.safe_load_all(result.stdout) if o]
        else:
            docs = [o for file in sorted(p.parent.glob('*.yaml')) if file.name != 'fleet.yaml' for o in yaml.safe_load_all(file.read_text()) if o]
        for o in docs:
            o.setdefault('metadata', {})
            if o['kind'] not in ('CustomResourceDefinition', 'ClusterRole', 'ClusterRoleBinding', 'ClusterSecretStore', 'Namespace', 'StorageClass', 'ValidatingWebhookConfiguration', 'MutatingWebhookConfiguration'):
                o['metadata'].setdefault('namespace', f['defaultNamespace'])
            objects.append((name, o))
            if o['kind'] == 'Secret':
                rendered_secret_names.add((o['metadata']['namespace'], o['metadata']['name']))
    remaining = set(graph)
    order = []
    while remaining:
        ready = sorted(n for n in remaining if all(d in order for d in graph[n]))
        assert ready, 'Cycle or missing dependency: ' + str(remaining)
        order += ready
        remaining.difference_update(ready)
    # CRDs shipped by charts also validate newly rendered custom resources.
    for _, o in objects:
        if o['kind'] == 'CustomResourceDefinition':
            for v in o['spec']['versions']:
                if v['served']:
                    schemas[(o['spec']['group'] + '/' + v['name'], o['spec']['names']['kind'])] = strict(v['schema']['openAPIV3Schema'])
    identities = set()
    external_keys = {}
    for name, o in objects:
        identity = (o['apiVersion'], o['kind'], o['metadata'].get('namespace'), o['metadata']['name'])
        assert identity not in identities, 'Duplicate resource: ' + str(identity)
        identities.add(identity)
        schema = schemas.get((o['apiVersion'], o['kind']))
        assert schema is not None, 'Missing API schema: ' + str(identity)
        try:
            jsonschema.Draft4Validator(schema).validate(omit_null_fields(o))
        except jsonschema.ValidationError as exc:
            raise AssertionError(f'{identity}: {list(exc.path)}: {exc.message}') from None
        if o['kind'] == 'ExternalSecret':
            key = (o['metadata']['namespace'], o['spec']['target']['name'])
            assert key not in rendered_secret_names, 'Helm and ESO both own secret: ' + str(key)
            external_keys[key] = {d['secretKey'] for d in o['spec']['data']}
    refs = []
    volume_refs = []
    def walk(x, ns):
        if isinstance(x, dict):
            if 'secretKeyRef' in x:
                ref = x['secretKeyRef']
                refs.append((ns, ref['name'], ref['key']))
            if isinstance(x.get('secret'), dict) and 'secretName' in x['secret']:
                volume_refs.append((ns, x['secret']['secretName']))
            for v in x.values():
                walk(v, ns)
        elif isinstance(x, list):
            for v in x:
                walk(v, ns)
    for _, o in objects:
        if o['kind'] != 'CustomResourceDefinition':
            walk(o, o['metadata'].get('namespace'))
        if o['kind'] == 'Cluster' and o['apiVersion'] == 'postgresql.cnpg.io/v1':
            volume_refs.append((o['metadata']['namespace'], o['spec']['bootstrap']['initdb']['secret']['name']))
        if o['kind'] == 'RedisReplication':
            for conf in [o['spec']['kubernetesConfig'], o['spec']['sentinel']]:
                refs.append((o['metadata']['namespace'], conf['redisSecret']['name'], conf['redisSecret']['key']))
    for ns, name, key in refs:
        if name.startswith('platform-'):
            assert key in external_keys.get((ns, name), set()), f'Missing ESO target/key: {ns}/{name}:{key}'
    for ns, name in volume_refs:
        if name.startswith('platform-'):
            assert (ns, name) in external_keys, f'Missing ESO volume/bootstrap secret: {ns}/{name}'
    stores = {o['metadata']['name']: o for _, o in objects if o['kind'] == 'ClusterSecretStore'}
    for _, o in objects:
        if o['kind'] != 'ExternalSecret':
            continue
        store = stores[o['spec']['secretStoreRef']['name']]
        assert o['metadata']['namespace'] in store['spec']['conditions'][0]['namespaces']
        auth = store['spec']['provider']['vault']['auth']['kubernetes']
        role = json.loads((ROOT / 'config/openbao/roles' / (auth['role'] + '.json')).read_text())
        assert auth['serviceAccountRef']['name'] in role['bound_service_account_names']
        assert auth['serviceAccountRef']['namespace'] in role['bound_service_account_namespaces']
        assert auth['serviceAccountRef']['audiences'] == [role['audience']]
        policy = (ROOT / 'config/openbao/policies' / (role['token_policies'][0] + '.hcl')).read_text()
        for item in o['spec']['data']:
            assert 'path "secret/data/' + item['remoteRef']['key'] + '"' in policy
    print(f'PASS: YAML, {len(configs)} Fleet bundles, 7 pinned Helm charts (lint + render), {len(objects)} resources/API schemas, dependency DAG, targets, ESO/Helm ownership and secretKeyRefs.')
    print('Order: ' + ' -> '.join(order))


if __name__ == '__main__':
    main()
