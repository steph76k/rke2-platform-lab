#!/usr/bin/env python3
"""Publish administrator-managed log index patterns to isolated Dashboards tenants.
Log-reader groups only read these objects. Does not replace user-created objects.
"""
import json,os,tempfile
from pathlib import Path
import requests
from afi_platform import CONFIG,ROOT,kv
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='afi-saved-objects-') as tmp:
 ca=Path(tmp)/'ca.crt';ca.write_text(kv('pki/lab-ca')['ca.crt']);s=requests.Session();s.verify=str(ca);s.headers['osd-xsrf']='afi-bootstrap';password=kv('opensearch/admin')['password']
 r=s.post(CONFIG['dashboards']+'/auth/login',json={'username':'admin','password':password},timeout=30);r.raise_for_status()
 catalog=json.loads((ROOT/'config/afi-isolation/tenant-catalog.json').read_text())
 for tenant,data in catalog.items():
  s.headers['securitytenant']=tenant
  r=s.post(CONFIG['dashboards']+'/api/v1/multitenancy/tenant',json={'tenant':tenant,'username':'admin'},timeout=30);r.raise_for_status()
  attrs={'title':'logs-'+data['cluster']+'-'+tenant+'-*','timeFieldName':'@timestamp'}
  path=CONFIG['dashboards']+'/api/saved_objects/index-pattern/afi-logs-'+tenant
  r=s.get(path,timeout=30)
  if r.status_code==200:
   assert r.json()['attributes']['title']==attrs['title'],'Refuse to overwrite an unexpected existing pattern'
  else:
   assert r.status_code==404,(r.status_code,r.text[:200])
   r=s.post(path,json={'attributes':attrs},timeout=30);r.raise_for_status()
  print('Administrator-managed log pattern ready in tenant',tenant)
