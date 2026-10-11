#!/usr/bin/env python3
"""Verify platform-group privileges and tenant denials through fresh OIDC logins.

Creates temporary identities, performs reads and a no-op Argo project update,
then removes the temporary Keycloak, Rancher, Harbor and OpenBao identities.
No credentials or session cookies are written to the report.
"""
import argparse
import json
import secrets
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from afi_platform import BAO, CONFIG, TLSHostAdapter, command, keycloak, sessions
from validation_oidc import LoginForm, access_token

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--ca-file', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
kc_base = CONFIG['keycloak'] + '/admin/realms/berger'
report = {'sessions': [], 'temporaryIdentitiesRemoved': False}

def session():
    s = requests.Session()
    s.verify = a.ca_file
    return s

def authenticate(s, response, identity):
    response.raise_for_status()
    form = LoginForm()
    form.feed(response.text)
    assert form.action and urlparse(form.action).netloc == 'idp.berger.ph'
    r = s.post(form.action, data=identity, allow_redirects=False, timeout=30)
    assert r.status_code == 302, ('Keycloak login', r.status_code)
    return r.headers['Location']

for platform in [True, False]:
    name = 'platform-rbac-probe-' + secrets.token_hex(6)
    identity = {'username': name, 'password': secrets.token_urlsafe(32)}
    uid = rid = hid = entity = bao_token = None
    record = {'identity': 'platform-admin' if platform else 'tenant-admin'}
    try:
        kc = keycloak()
        r = kc.post(kc_base+'/users', json={'username':name, 'enabled':True,
            'email':name+'@example.invalid', 'emailVerified':True,
            'firstName':'Platform','lastName':'RBAC verification',
            'credentials':[{'type':'password','value':identity['password'],'temporary':False}]}, timeout=30)
        r.raise_for_status()
        uid = r.headers['Location'].rsplit('/',1)[1]
        groups = [x+'-platform-admins' for x in ['rancher','harbor','opensearch','argocd','openbao']] if platform else ['mandant-a-admins']
        existing = kc.get(kc_base+'/groups', params={'max':100}, timeout=30)
        existing.raise_for_status()
        gids = {x['name']:x['id'] for x in existing.json()}
        for group in groups:
            kc.put(kc_base+'/users/'+uid+'/groups/'+gids[group], timeout=30).raise_for_status()

        # Rancher authorization-code login and the effective downstream permission.
        s = session(); base = 'https://rancher.berger.ph'
        r = s.get(base+'/v3-public/keyCloakOIDCProviders/keycloakoidc', timeout=30)
        r.raise_for_status(); entry = r.json()['redirectUrl']; state = secrets.token_urlsafe(20)
        r = s.get(entry, params={'state':state,'scope':'openid profile email'}, timeout=30)
        assert parse_qs(urlparse(r.url).query)['code_challenge_method'] == ['S256']
        callback = authenticate(s, r, identity)
        q = parse_qs(urlparse(callback).query); assert q['state'] == [state]
        r = s.post(base+'/v3-public/keyCloakOIDCProviders/keycloakoidc?action=login',
            json={'code':q['code'][0],'responseType':'json','ttl':600000}, timeout=30)
        r.raise_for_status(); s.headers['Authorization'] = 'Bearer '+r.json()['token']
        r = s.get(base+'/v3/users?me=true', timeout=30); r.raise_for_status(); rid = r.json()['data'][0]['id']
        body = {'apiVersion':'authorization.k8s.io/v1','kind':'SelfSubjectAccessReview',
            'spec':{'resourceAttributes':{'group':'rbac.authorization.k8s.io','resource':'clusterrolebindings','verb':'create'}}}
        for attempt in range(20):
            r = s.post(base+'/k8s/clusters/c-44q9v/apis/authorization.k8s.io/v1/selfsubjectaccessreviews', json=body, timeout=30)
            if r.status_code == 201 and r.json()['status']['allowed'] == platform: break
            time.sleep(2)
        assert r.status_code == 201 and r.json()['status']['allowed'] == platform, ('Rancher admin privilege', r.status_code)
        record['rancherClusterRbacAdministration'] = platform

        # Harbor authorization-code login: configuration API is system-admin only.
        s = session(); base = CONFIG['harbor']
        def csrf(response, *args, **kwargs):
            if response.headers.get('X-Harbor-CSRF-Token'):
                s.headers['X-Harbor-CSRF-Token'] = response.headers['X-Harbor-CSRF-Token']
        s.hooks['response'].append(csrf)
        r = s.get(base+'/c/oidc/login', timeout=30)
        callback = authenticate(s, r, identity)
        assert urlparse(callback).netloc == 'harbor-ha.berger.ph'
        r = s.get(callback, allow_redirects=False, timeout=30)
        assert r.status_code in [302,303], ('OIDC callback', r.status_code)
        r = s.get(base+'/api/v2.0/users/current', timeout=30); r.raise_for_status(); hid = r.json()['user_id']
        r = s.get(base+'/api/v2.0/configurations', timeout=30)
        assert r.status_code == (200 if platform else 403), ('Harbor administration', r.status_code)
        record['harborConfigurationHttp'] = r.status_code

        # OpenSearch: signed access token from the configured authorization-code client.
        s = session(); s.mount(CONFIG['opensearch_tunnel'], TLSHostAdapter())
        s.headers['Authorization'] = 'Bearer '+access_token(identity)
        r = s.get(CONFIG['opensearch_tunnel']+'/_plugins/_security/authinfo', timeout=30)
        r.raise_for_status(); roles = r.json()['roles']
        assert ('all_access' in roles) == platform and ('security_rest_api_access' in roles) == platform
        r = s.get(CONFIG['opensearch_tunnel']+'/_plugins/_security/api/rolesmapping', timeout=30)
        assert r.status_code == (200 if platform else 403), ('OpenSearch Security API', r.status_code)
        record['opensearchSecurityApiHttp'] = r.status_code

        # Argo: project configuration is reserved for platform admins.
        s = session(); base = 'https://argocd.berger.ph'
        r = s.get(base+'/auth/login', params={'return_url':base+'/applications'}, timeout=30)
        assert parse_qs(urlparse(r.url).query)['code_challenge_method'] == ['S256']
        callback = authenticate(s, r, identity)
        assert urlparse(callback).netloc == 'argocd.berger.ph'
        r = s.get(callback, allow_redirects=False, timeout=30)
        assert r.status_code in [302,303], ('Argo OIDC callback', r.status_code)
        r = s.get(base+'/api/v1/projects/mandant-a', timeout=30); r.raise_for_status(); project = r.json()
        r = s.put(base+'/api/v1/projects/mandant-a', json={'project':project}, timeout=30)
        assert r.status_code == (200 if platform else 403), ('Argo project administration', r.status_code)
        record['argocdProjectUpdateHttp'] = r.status_code

        # OpenBao: the existing root-namespace OIDC role requires its own group.
        s = session(); base = 'https://openbao.berger.ph'
        redirect = base+'/ui/vault/auth/oidc/oidc/callback'
        r = s.post(base+'/v1/auth/oidc/oidc/auth_url', json={'role':'platform-admin','redirect_uri':redirect}, timeout=30)
        r.raise_for_status(); auth_url = r.json()['data']['auth_url']; assert auth_url
        callback = authenticate(s, s.get(auth_url, timeout=30), identity)
        assert urlparse(callback).netloc == 'openbao.berger.ph'
        q = parse_qs(urlparse(callback).query)
        r = s.get(base+'/v1/auth/oidc/oidc/callback', params={k:v[0] for k,v in q.items()}, timeout=30)
        assert r.status_code == (200 if platform else 400), ('OpenBao platform role', r.status_code)
        if platform:
            auth = r.json()['auth']; bao_token = auth['client_token']; entity = auth['entity_id']
            assert 'platform-admin' in auth['policies'] and 'root' not in auth['policies']
            r = s.post(base+'/v1/sys/capabilities-self', headers={'X-Vault-Token':bao_token}, json={'paths':['sys/policies/acl/platform-admin']}, timeout=30)
            r.raise_for_status(); assert 'sudo' in r.json()['capabilities']
        record['openbaoPlatformRoleHttp'] = 200 if platform else 400
        report['sessions'].append(record)
        print(json.dumps(record), flush=True)
    finally:
        if bao_token:
            r = requests.post('https://openbao.berger.ph/v1/auth/token/revoke-self', headers={'X-Vault-Token':bao_token}, verify=a.ca_file, timeout=30)
            r.raise_for_status()
        if entity: command([BAO,'delete','identity/entity/id/'+entity])
        if hid:
            h, _ = sessions(a.ca_file)
            h.get(CONFIG['harbor']+'/api/v2.0/users/current', timeout=30).raise_for_status()
            r = h.delete(CONFIG['harbor']+'/api/v2.0/users/'+str(hid), timeout=30)
            if r.status_code == 403 and 'CSRF' in r.text:
                r = h.delete(CONFIG['harbor']+'/api/v2.0/users/'+str(hid), timeout=30)
            r.raise_for_status()
        if rid: command(['kubectl','--context=rancher','delete','users.management.cattle.io',rid])
        if uid: keycloak().delete(kc_base+'/users/'+uid, timeout=30).raise_for_status()
        a.output.write_text(json.dumps(report, indent=2)+'\n')
report['temporaryIdentitiesRemoved'] = True
a.output.write_text(json.dumps(report, indent=2)+'\n')
print('All platform grants and tenant denials verified; temporary identities removed.')
