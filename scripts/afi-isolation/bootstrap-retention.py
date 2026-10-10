#!/usr/bin/env python3
"""Reconcile 180-day retention for new AFI logs only; legacy indices are untouched."""
import json,os,tempfile
from pathlib import Path
from afi_platform import CONFIG,kv,sessions
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='afi-retention-') as tmp:
 ca=Path(tmp)/'ca.crt';ca.write_text(kv('pki/lab-ca')['ca.crt']);_,s=sessions(ca);base=CONFIG['opensearch_tunnel'];name='afi-logs-retention'
 policy={'policy':{'description':'AFI logs retention; managed by rke2-platform-lab','default_state':'retain','states':[{'name':'retain','actions':[],'transitions':[{'state_name':'delete','conditions':{'min_index_age':str(CONFIG['retention_days'])+'d'}}]},{'name':'delete','actions':[{'delete':{}}],'transitions':[]}],'ism_template':[{'index_patterns':['logs-rke2-cluster1-*','logs-rke2-cluster2-*'],'priority':100}]}}
 path=base+'/_plugins/_ism/policies/'+name;r=s.get(path,timeout=30);params={}
 if r.status_code==200:
  d=r.json();assert d['policy']['description']==policy['policy']['description'];params={'if_seq_no':d['_seq_no'],'if_primary_term':d['_primary_term']}
 else:assert r.status_code==404
 r=s.put(path,params=params,json=policy,timeout=30);r.raise_for_status()
 template={'index_patterns':['logs-rke2-cluster1-*','logs-rke2-cluster2-*'],'priority':100,'template':{'settings':{'number_of_shards':1,'number_of_replicas':1},'mappings':{'properties':{'@timestamp':{'type':'date'},'tenant_id':{'type':'keyword'},'cluster_name':{'type':'keyword'},'environment':{'type':'keyword'},'kubernetes':{'properties':{'namespace_name':{'type':'keyword'},'pod_name':{'type':'keyword'},'container_name':{'type':'keyword'}}}}}}}
 r=s.put(base+'/_index_template/afi-logs',json=template,timeout=30);r.raise_for_status();print('AFI logs index template and',CONFIG['retention_days'],'day ISM policy configured; old kubernetes indices unchanged.')
