#!/usr/bin/env python3
"""Create dedicated AFI clients and add OIDC while retaining local administrator access.
Requires the documented local OpenSearch tunnel and an administrative OpenBao session.
"""
import argparse,copy,json,os,tempfile
from pathlib import Path
from afi_platform import CONFIG,ROOT,kv,put_new,keycloak,sessions,backup,apply_security_config
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args()
if not a.apply:
 print('Would create/reconcile dedicated afi-harbor and afi-opensearch clients; configure Harbor OIDC and add OpenSearch OIDC. Use --apply after reviewing config/afi-isolation/identity.json.');raise SystemExit()
os.umask(0o077);kc=keycloak();base=CONFIG['keycloak']+'/admin/realms/'+CONFIG['realm'];clients={}
for name,settings in CONFIG['clients'].items():
 desired={'clientId':name,'name':name,'description':'Managed by rke2-platform-lab AFI bootstrap','enabled':True,'protocol':'openid-connect','publicClient':False,'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'serviceAccountsEnabled':False,'redirectUris':[settings['callback']],'webOrigins':[settings['origin']],'defaultClientScopes':['profile','email','roles'], 'protocolMappers':[
   {'name':'AFI groups','protocol':'openid-connect','protocolMapper':'oidc-group-membership-mapper','config':{'claim.name':'groups','full.path':'false','id.token.claim':'true','access.token.claim':'true','userinfo.token.claim':'true'}},
   {'name':'AFI audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper','config':{'included.client.audience':name,'id.token.claim':'true','access.token.claim':'true'}}]}
 r=kc.get(base+'/clients',params={'clientId':name},timeout=30);r.raise_for_status();found=r.json()
 if found:
  assert len(found)==1 and found[0].get('description')=='Managed by rke2-platform-lab AFI bootstrap','Refuse to adopt unrelated client'
  client=found[0]
  def normalized(value):
   if isinstance(value,list):return [normalized(x) for x in value]
   if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k!='id'}
   return value
  if any(normalized(client.get(k))!=normalized(v) for k,v in desired.items()):
   r=kc.put(base+'/clients/'+client['id'],json={**client,**desired},timeout=30);r.raise_for_status()
 else:
  client=desired.copy()
  r=kc.post(base+'/clients',json=client,timeout=30);r.raise_for_status();client['id']=r.headers['Location'].rsplit('/',1)[1]
 r=kc.get(base+'/clients/'+client['id']+'/client-secret',timeout=30);r.raise_for_status();secret=r.json()['value']
 try:saved=kv('oidc/'+name)
 except RuntimeError:put_new('oidc/'+name,{'client_id':name,'client_secret':secret});saved=kv('oidc/'+name)
 assert saved['client_secret']==secret,'Client secret differs from OpenBao; deliberate rotation required'
 clients[name]=saved
 print('Dedicated client ready:',name)
with tempfile.TemporaryDirectory(prefix='afi-oidc-') as tmp:
 ca=Path(tmp)/'ca.crt';ca.write_text(kv('pki/lab-ca')['ca.crt']);h,osapi=sessions(ca)
 cert=kv('opensearch/admin-tls');certfile=Path(tmp)/'admin.crt';keyfile=Path(tmp)/'admin.key';certfile.write_text(cert['tls.crt']);keyfile.write_text(cert['tls.key']);osapi.cert=(str(certfile),str(keyfile));osapi.auth=None
 r=h.get(CONFIG['harbor']+'/api/v2.0/users/current',timeout=30);r.raise_for_status();assert r.json()['username']=='admin'
 r=h.get(CONFIG['harbor']+'/api/v2.0/configurations',timeout=30);r.raise_for_status();before=r.json();backup('before-harbor-oidc.json',before)
 assert before['auth_mode']['value'] in ['db_auth','oidc_auth']
 assert before['auth_mode']['editable'] or before['auth_mode']['value']=='oidc_auth','Existing local users block OIDC; do not remove them'
 # Empty global admin group prevents unintended OIDC system administrators.
 harbor={'auth_mode':'oidc_auth','oidc_name':'Keycloak berger','oidc_endpoint':CONFIG['keycloak']+'/realms/'+CONFIG['realm'],'oidc_client_id':'afi-harbor','oidc_client_secret':clients['afi-harbor']['client_secret'],'oidc_groups_claim':'groups','oidc_admin_group':'','oidc_scope':'openid,profile,email','oidc_verify_cert':True,'oidc_auto_onboard':True,'oidc_user_claim':'preferred_username','project_creation_restriction':'adminonly'}
 r=h.put(CONFIG['harbor']+'/api/v2.0/configurations',json=harbor,timeout=30);r.raise_for_status()
 r=h.get(CONFIG['harbor']+'/api/v2.0/users/current',timeout=30);r.raise_for_status();assert r.json()['username']=='admin';print('Harbor OIDC configured; local admin still authenticated')
 r=osapi.get(CONFIG['opensearch_tunnel']+'/_plugins/_security/api/securityconfig',timeout=30);r.raise_for_status();security=r.json()['config'];backup('before-opensearch-oidc.json',security);before_basic=copy.deepcopy(security['dynamic']['authc'])
 security['dynamic']['authc']['afi_openid_auth_domain']={'http_enabled':True,'transport_enabled':False,'order':-1,'http_authenticator':{'type':'openid','challenge':False,'config':{'subject_key':'preferred_username','roles_key':'groups','openid_connect_url':CONFIG['keycloak']+'/realms/'+CONFIG['realm']+'/.well-known/openid-configuration','required_audience':'afi-opensearch','required_issuer':CONFIG['keycloak']+'/realms/'+CONFIG['realm']}},'authentication_backend':{'type':'noop'}}
 apply_security_config(security,cert)
 r=osapi.get(CONFIG['opensearch_tunnel']+'/_plugins/_security/api/securityconfig',timeout=30);r.raise_for_status()
 for name,value in before_basic.items():
  if name!='afi_openid_auth_domain':assert r.json()['config']['dynamic']['authc'][name]==value
 print('OpenSearch OIDC added; pre-existing auth domains unchanged')
