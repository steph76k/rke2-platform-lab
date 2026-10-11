#!/usr/bin/env python3
"""Exercise OpenSearch OIDC, global index views, tenant isolation and SSO logout.
Creates temporary Keycloak users only. Requires Playwright Chromium and lab helpers.
"""
import argparse
import base64
import hashlib
import json
import re
import secrets
import socket
import ssl
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.sync_api import sync_playwright
from afi_platform import CONFIG, keycloak

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--ca-file',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
base=CONFIG['dashboards'];kc_base=CONFIG['keycloak']+'/admin/realms/berger'
tls_context=ssl.create_default_context(cafile=a.ca_file);pins=[];report=[]
for host in ['opensearch.berger.ph','idp.berger.ph']:
    with socket.create_connection((host,443),timeout=20) as raw:
        with tls_context.wrap_socket(raw,server_hostname=host) as tls:
            cert=x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
            spki=cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
            pins.append(base64.b64encode(hashlib.sha256(spki).digest()).decode())

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--ignore-certificate-errors-spki-list='+','.join(pins)])
    for group in ['opensearch-platform-admins','mandant-a-logs-readers']:
        uid=None;context=browser.new_context();page=context.new_page();kc=keycloak()
        name='os-ui-probe-'+secrets.token_hex(6);password=secrets.token_urlsafe(32)
        platform=group=='opensearch-platform-admins'
        try:
            r=kc.post(kc_base+'/users',json={'username':name,'enabled':True,'firstName':'OpenSearch','lastName':'Validation',
                'email':name+'@example.invalid','emailVerified':True,
                'credentials':[{'type':'password','value':password,'temporary':False}]},timeout=30)
            r.raise_for_status();uid=r.headers['Location'].rsplit('/',1)[1]
            r=kc.get(kc_base+'/groups',params={'search':group,'exact':'true'},timeout=30);r.raise_for_status()
            gid=next(x['id'] for x in r.json() if x['name']==group)
            kc.put(kc_base+'/users/'+uid+'/groups/'+gid,timeout=30).raise_for_status()
            page.goto(base+'/auth/openid/login',wait_until='domcontentloaded',timeout=60000)
            page.locator('#username').fill(name);page.locator('#password').fill(password);page.locator('#kc-login').click()
            page.wait_for_url(re.compile(r'https://opensearch\.berger\.ph/app/(?!login)'),timeout=60000)
            s=requests.Session();s.verify=a.ca_file;s.headers['osd-xsrf']='platform-ui-validation'
            for c in context.cookies():s.cookies.set(c['name'],c['value'],domain=c['domain'],path=c['path'])
            r=s.get(base+'/api/v1/auth/authinfo',timeout=30);r.raise_for_status();info=r.json()
            assert ('all_access' in info['roles'])==platform
            row={'group':group,'oidcLogin':True,'roles':info['roles'],'initialTenant':info.get('user_requested_tenant')}
            if platform:
                assert info.get('user_requested_tenant') in ['','global_tenant',None],info.get('user_requested_tenant')
                r=s.get(base+'/api/saved_objects/_find',params={'type':'index-pattern','per_page':100},headers={'securitytenant':''},timeout=30)
                r.raise_for_status();patterns={x['id']:x['attributes']['title'] for x in r.json()['saved_objects']}
                assert patterns.get('afi-platform-logs')=='logs-*' and patterns.get('afi-platform-all')=='*',patterns
                row['globalPatterns']=patterns
                r=s.post(base+'/internal/search/opensearch',headers={'securitytenant':''},
                    json={'params':{'index':'logs-*','body':{'size':0,'aggs':{'indices':{'terms':{'field':'_index','size':100}}}}}},timeout=60)
                r.raise_for_status();indices=[x['key'] for x in r.json()['rawResponse']['aggregations']['indices']['buckets']]
                assert all(any(part in index for index in indices) for part in ['-mandant-a-','-mandant-b-','-platform-']),indices
                row['bothTenantsAndPlatformLogsReadable']=True
                page.goto(base+'/app/discover?security_tenant=global',wait_until='domcontentloaded',timeout=60000)
                page.get_by_text('logs-*',exact=True).first.wait_for(state='visible',timeout=60000)
                page.wait_for_timeout(2500)
                body=page.locator('body').inner_text()
                assert 'Search Error' not in body and 'No default index pattern' not in body, 'Global Discover reported a search or index-pattern error'
                row['globalDiscoverRendered']=True
            else:
                r=s.get(base+'/api/saved_objects/index-pattern/afi-platform-logs',headers={'securitytenant':''},timeout=30)
                assert r.status_code in [403,404],('global object must be denied',r.status_code)
                row['globalSavedObjectDeniedHttp']=r.status_code
                r=s.get(base+'/api/saved_objects/index-pattern/afi-logs-mandant-a',headers={'securitytenant':'mandant-a'},timeout=30)
                r.raise_for_status();row['ownSavedObjectHttp']=200
                for tenant,expected in [('mandant-a',200),('mandant-b',403),('platform',403)]:
                    r=s.post(base+'/internal/search/opensearch',headers={'securitytenant':'mandant-a'},
                        json={'params':{'index':'logs-rke2-cluster2-'+tenant+'-*','body':{'size':0}}},timeout=30)
                    assert r.status_code==expected,(tenant,r.status_code)
                row['foreignAndPlatformLogsDenied']=True
            seen=[]
            def observe(response):
                u=urlparse(response.url)
                if u.path=='/auth/openid/logout' or u.path.endswith('/protocol/openid-connect/logout'):
                    seen.append({'host':u.netloc,'path':u.path,'http':response.status})
            page.on('response',observe)
            page.goto(base+'/auth/openid/logout',wait_until='domcontentloaded',timeout=60000)
            page.wait_for_url('**/app/login**',timeout=60000)
            assert any(x['host']=='idp.berger.ph' and x['http']==302 for x in seen),seen
            r=kc.get(kc_base+'/users/'+uid+'/sessions',timeout=30);r.raise_for_status();assert not r.json()
            page.goto(base+'/auth/openid/login',wait_until='domcontentloaded',timeout=60000)
            page.locator('#username').wait_for(state='visible',timeout=30000)
            row['keycloakSessionEnded']=True;row['nextLoginRequiresCredentials']=True
            report.append(row);print(json.dumps(row),flush=True)
        finally:
            context.close()
            if uid:keycloak().delete(kc_base+'/users/'+uid,timeout=30).raise_for_status()
            a.output.write_text(json.dumps(report,indent=2)+'\n')
    browser.close()
