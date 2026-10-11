#!/usr/bin/env python3
"""Verify actual Keycloak/Argo CD browser-code login and tenant application RBAC.
Creates only temporary Keycloak users and short-lived, unsynced probe Applications.
Existing demo applications are read and optionally synced to their declared Git state.
"""
import argparse
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from afi_platform import CONFIG, keycloak, kv
from validation_oidc import LoginForm

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--ca-file', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
base = 'https://argocd.berger.ph'
idp = CONFIG['keycloak'] + '/admin/realms/' + CONFIG['realm']
results = []
recovery = requests.Session()
recovery.verify = a.ca_file
credentials = kv('argocd/admin')
r = recovery.post(base+'/api/v1/session', json={
    'username': credentials['username'], 'password': credentials['password']}, timeout=30)
r.raise_for_status()
recovery.headers['Authorization'] = 'Bearer ' + r.json()['token']
del credentials

for tenant, role in [('mandant-a','admins'), ('mandant-a','developers'),
                     ('mandant-b','admins'), ('mandant-b','developers'), (None, None)]:
    uid = None
    session = requests.Session()
    session.verify = a.ca_file
    username = 'afi-argocd-probe-' + secrets.token_hex(8)
    password = secrets.token_urlsafe(32)
    group = tenant + '-' + role if tenant else None
    probes = []
    try:
        admin = keycloak()
        r = admin.post(idp + '/users', json={'username':username, 'enabled':True,
            'email':username+'@example.invalid', 'emailVerified':True,
            'firstName':'AFI','lastName':'Argo test',
            'credentials':[{'type':'password','value':password,'temporary':False}]}, timeout=30)
        r.raise_for_status()
        uid = r.headers['Location'].rsplit('/',1)[1]
        if group:
            r = admin.get(idp + '/groups', params={'search':group,'exact':'true'}, timeout=30)
            r.raise_for_status()
            gid = next(x['id'] for x in r.json() if x['name']==group)
            admin.put(idp + '/users/' + uid + '/groups/' + gid, timeout=30).raise_for_status()
        r = session.get(base + '/auth/login', params={'return_url':base+'/applications'}, timeout=30)
        r.raise_for_status()
        form = LoginForm();form.feed(r.text)
        assert form.action and urlparse(form.action).netloc == urlparse(CONFIG['keycloak']).netloc
        auth_query = parse_qs(urlparse(r.url).query)
        assert auth_query.get('code_challenge_method') == ['S256'], 'Argo did not request PKCE S256'
        r = session.post(form.action, data={'username':username,'password':password}, allow_redirects=False, timeout=30)
        assert r.status_code == 302
        callback = r.headers['Location']
        parsed = urlparse(callback)
        assert (parsed.scheme,parsed.netloc,parsed.path)==('https','argocd.berger.ph','/auth/callback')
        r = session.get(callback, allow_redirects=False, timeout=30)
        assert r.status_code in [302,303], 'Argo OIDC callback failed'
        info = session.get(base+'/api/v1/session/userinfo',timeout=30)
        info.raise_for_status();assert info.json().get('loggedIn')
        if group:assert group in info.json().get('groups',[])
        record={'group':group or '(no tenant group)','pkce':'S256','loggedIn':True}
        if not tenant:
            r=session.get(base+'/api/v1/applications',timeout=30);r.raise_for_status()
            assert not r.json().get('items');record['visibleApplications']=0
        else:
            other='mandant-b' if tenant=='mandant-a' else 'mandant-a'
            for target,expected in [(tenant,200),(other,403)]:
                r=session.get(base+'/api/v1/applications/'+target+'-demo',params={'project':target},timeout=30)
                assert r.status_code==expected,(group,target,r.status_code)
                record['ownApplicationHttp' if target==tenant else 'foreignApplicationHttp']=r.status_code
            r=session.get(base+'/api/v1/applications',timeout=30);r.raise_for_status()
            apps=r.json().get('items') or []
            assert apps and all(x['spec']['project']==tenant for x in apps)
            record['onlyOwnApplicationsVisible']=True
            for target, expected in [(tenant,200),(other,403)]:
                r=session.get(base+'/api/v1/projects/'+target,timeout=30)
                assert r.status_code==expected,('project read',group,target,r.status_code)
                record['ownProjectHttp' if target==tenant else 'foreignProjectHttp']=r.status_code
            # These invalid destinations/repos must be rejected before creating an Application.
            for label,project,destination,repo in [
                ('foreign-project',other,other+'-dev','https://github.com/steph76k/rke2-argocd-lab-'+other+'.git'),
                ('foreign-namespace',tenant,other+'-dev','https://github.com/steph76k/rke2-argocd-lab-'+tenant+'.git'),
                ('platform-namespace',tenant,'argocd','https://github.com/steph76k/rke2-argocd-lab-'+tenant+'.git'),
                ('foreign-repository',tenant,tenant+'-dev','https://github.com/steph76k/rke2-argocd-lab-'+other+'.git')]:
                obj={'apiVersion':'argoproj.io/v1alpha1','kind':'Application','metadata':{'name':username+'-'+label,'namespace':'argocd'},'spec':{'project':project,'source':{'repoURL':repo,'path':'apps/demo','targetRevision':'main'},'destination':{'server':'https://kubernetes.default.svc','namespace':destination}}}
                probes.append((obj['metadata']['name'],project))
                r=session.post(base+'/api/v1/applications',json=obj,timeout=60)
                assert r.status_code in [400,403,404],(label,r.status_code)
                record[label+'DeniedHttp']=r.status_code
            r=session.post(base+'/api/v1/applications/'+tenant+'-demo/sync',json={'project':tenant},timeout=60)
            assert r.status_code==200,('own sync',r.status_code)
            record['ownSyncHttp']=r.status_code
        record['passed']=True;results.append(record);print(json.dumps(record),flush=True)
    finally:
        try:
            for name,project in probes:
                # Developers cannot delete apps. Use the recovery identity only for
                # this run's random, unsynced probes, including timed-out creates.
                r=recovery.get(base+'/api/v1/applications/'+name,params={'project':project},timeout=30)
                if r.status_code==404:
                    continue
                r.raise_for_status()
                obj=r.json()
                assert obj['metadata']['name']==name and name.startswith(username+'-')
                assert obj['spec']['project']==project and not obj['spec'].get('syncPolicy',{}).get('automated')
                recovery.delete(base+'/api/v1/applications/'+name,
                    params={'cascade':'false','project':project},timeout=30).raise_for_status()
        finally:
            if uid:
                cleanup=keycloak();cleanup.delete(idp+'/users/'+uid,timeout=30).raise_for_status()
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps({'results':results,'temporaryIdentityCleanup':True},indent=2)+'\n')
print('Argo CD OIDC and tenant RBAC checks passed.')
