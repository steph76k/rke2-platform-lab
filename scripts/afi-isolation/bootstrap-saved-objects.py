#!/usr/bin/env python3
"""Publish administrator-managed log index patterns to isolated Dashboards tenants.
Log-reader groups only read these objects. Does not replace user-created objects.
"""
import argparse,json,os,tempfile
from pathlib import Path
import requests
from afi_platform import CONFIG,ROOT,kv,backup
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--allow-cluster-migration",action="store_true",help="Allow a managed pattern to move between the two known clusters for the same tenant")
args=parser.parse_args()
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='afi-saved-objects-') as tmp:
 ca=Path(tmp)/'ca.crt';ca.write_text(kv('pki/lab-ca')['ca.crt']);s=requests.Session();s.verify=str(ca);s.headers['osd-xsrf']='afi-bootstrap';password=kv('opensearch/admin')['password']
 r=s.post(CONFIG['dashboards']+'/auth/login',json={'username':'admin','password':password},timeout=30);r.raise_for_status()
 catalog=json.loads((ROOT/'config/afi-isolation/tenant-catalog.json').read_text())
 for tenant,data in catalog.items():
  s.headers['securitytenant']=tenant
  r=s.post(CONFIG['dashboards']+'/api/v1/multitenancy/tenant',json={'tenant':tenant,'username':'admin'},timeout=30);r.raise_for_status()
  fields=[{'name':'@timestamp','type':'date','esTypes':['date'],'searchable':True,'aggregatable':True,'readFromDocValues':True,'count':0}]
  for name in ['tenant_id','cluster_name','environment','kubernetes.namespace_name','kubernetes.pod_name','kubernetes.container_name']:
   fields.append({'name':name,'type':'string','esTypes':['keyword'],'searchable':True,'aggregatable':True,'readFromDocValues':True,'count':0})
  for name in ['log','message']:
   fields.append({'name':name,'type':'string','esTypes':['text'],'searchable':True,'aggregatable':False,'readFromDocValues':False,'count':0})
  attrs={'fields':json.dumps(fields),'title':'logs-'+data['cluster']+'-'+tenant+'-*','timeFieldName':'@timestamp'}
  path=CONFIG['dashboards']+'/api/saved_objects/index-pattern/afi-logs-'+tenant
  r=s.get(path,timeout=30)
  if r.status_code==200:
   previous=r.json()['attributes']['title']
   if previous!=attrs['title']:
    assert args.allow_cluster_migration and previous in ['logs-rke2-cluster1-'+tenant+'-*','logs-rke2-cluster2-'+tenant+'-*'],'Refuse to overwrite an unexpected existing pattern'
    backup('saved-pattern-before-cluster-move-'+tenant,r.json())
   if any(r.json()['attributes'].get(k)!=v for k,v in attrs.items()):
    r=s.put(path,json={'attributes':attrs},timeout=30);r.raise_for_status()
  else:
   assert r.status_code==404,(r.status_code,r.text[:200])
   r=s.post(path,json={'attributes':attrs},timeout=30);r.raise_for_status()
  r=s.post(CONFIG['dashboards']+'/api/opensearch-dashboards/settings',json={'changes':{'defaultIndex':'afi-logs-'+tenant}},timeout=30);r.raise_for_status()
  print('Administrator-managed log pattern and default index ready in tenant',tenant)
