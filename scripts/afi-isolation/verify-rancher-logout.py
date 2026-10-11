#!/usr/bin/env python3
"""Verify Rancher UI logout removes the Rancher token and the Keycloak SSO session.
Uses a temporary tenant user and verified TLS; no sessions or credentials persist.
Requires Playwright Chromium and the lab helper prerequisites.
"""
import argparse
import base64
import hashlib
import json
import secrets
import socket
import ssl
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.sync_api import sync_playwright
from afi_platform import CONFIG, command, keycloak
from validation_oidc import LoginForm

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--ca-file', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
base = 'https://rancher.berger.ph'
kc_base = CONFIG['keycloak']+'/admin/realms/berger'
uid = rid = None
report = {}
try:
    kc = keycloak()
    name = 'rancher-logout-probe-'+secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    r = kc.post(kc_base+'/users', json={'username':name,'enabled':True,
        'email':name+'@example.invalid','emailVerified':True,'firstName':'Logout','lastName':'Verification',
        'credentials':[{'type':'password','value':password,'temporary':False}]}, timeout=30)
    r.raise_for_status(); uid = r.headers['Location'].rsplit('/',1)[1]
    r = kc.get(kc_base+'/groups', params={'search':'mandant-a-admins','exact':'true'}, timeout=30)
    r.raise_for_status(); gid = next(g['id'] for g in r.json() if g['name']=='mandant-a-admins')
    kc.put(kc_base+'/users/'+uid+'/groups/'+gid, timeout=30).raise_for_status()

    s = requests.Session(); s.verify = a.ca_file
    r = s.get(base+'/v3-public/keyCloakOIDCProviders/keycloakoidc', timeout=30)
    r.raise_for_status(); provider = r.json()
    assert provider['logoutAllEnabled'] and provider['logoutAllForced']
    state = secrets.token_urlsafe(20)
    r = s.get(provider['redirectUrl'], params={'state':state,'scope':'openid profile email'}, timeout=30)
    form = LoginForm(); form.feed(r.text); assert form.action
    assert urlparse(form.action).netloc=='idp.berger.ph'
    r = s.post(form.action, data={'username':name,'password':password}, allow_redirects=False, timeout=30)
    assert r.status_code==302; q=parse_qs(urlparse(r.headers['Location']).query); assert q['state']==[state]
    r = s.post(base+'/v3-public/keyCloakOIDCProviders/keycloakoidc?action=login',
        json={'code':q['code'][0],'responseType':'json','ttl':600000}, timeout=30)
    r.raise_for_status(); token=r.json()['token']
    r = s.get(base+'/v3/users?me=true',headers={'Authorization':'Bearer '+token},timeout=30)
    r.raise_for_status();rid=r.json()['data'][0]['id']
    r = kc.get(kc_base+'/users/'+uid+'/sessions',timeout=30);r.raise_for_status();assert len(r.json())==1

    # Pin only certificates obtained via a normal, CA-verified TLS handshake.
    tls_context=ssl.create_default_context(cafile=a.ca_file);pins=[]
    for host in ['rancher.berger.ph','idp.berger.ph']:
        with socket.create_connection((host,443),timeout=20) as raw:
            with tls_context.wrap_socket(raw,server_hostname=host) as tls:
                cert=x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
                spki=cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
                pins.append(base64.b64encode(hashlib.sha256(spki).digest()).decode())
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--ignore-certificate-errors-spki-list='+','.join(pins)])
        context=browser.new_context()
        context.add_cookies([{'name':c.name,'value':c.value,'domain':c.domain,'path':c.path,'secure':c.secure}
            for c in s.cookies if c.domain.lstrip('.') in ['rancher.berger.ph','idp.berger.ph']])
        context.add_cookies([{'name':'R_SESS','value':token,'domain':'rancher.berger.ph','path':'/','secure':True,'httpOnly':True}])
        page=context.new_page()
        # The supported UI logout route uses the same action as the user menu.
        seen=[]
        def observe(response):
            path=urlparse(response.url).path
            if path=='/v1/logout' or path.endswith('/protocol/openid-connect/logout'):
                seen.append({'host':urlparse(response.url).netloc,'path':path,'http':response.status})
        page.on('response',observe)
        page.goto(base+'/dashboard/auth/logout',wait_until='domcontentloaded',timeout=60000)
        page.wait_for_url('**/dashboard/auth/login**',timeout=60000)
        assert any(x['path']=='/v1/logout' and x['http']==200 for x in seen), seen
        assert any(x['host']=='idp.berger.ph' and x['http']==302 for x in seen), seen
        r=kc.get(kc_base+'/users/'+uid+'/sessions',timeout=30);r.raise_for_status();assert not r.json()
        # Reusing the exact browser session must now show the password form.
        login_url=requests.Request('GET',provider['redirectUrl'],params={
            'state':secrets.token_urlsafe(20),'scope':'openid profile email'}).prepare().url
        page.goto(login_url,wait_until='domcontentloaded',timeout=60000)
        page.locator('#username').wait_for(state='visible',timeout=30000)
        assert urlparse(page.url).netloc=='idp.berger.ph'
        report={'uiLogoutRoute':True,'rancherAndKeycloakLogout':seen,
            'keycloakSessionsRemaining':0,'freshLoginRequiresCredentials':True}
        browser.close()
    r=requests.get(base+'/v3/users?me=true',headers={'Authorization':'Bearer '+token},verify=a.ca_file,timeout=30)
    assert r.status_code==401, ('Rancher session token was not revoked',r.status_code)
    report['oldRancherTokenHttp']=401
finally:
    if rid:command(['kubectl','--context=rancher','delete','users.management.cattle.io',rid])
    if uid:keycloak().delete(kc_base+'/users/'+uid,timeout=30).raise_for_status()
    a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
