#!/usr/bin/env python3
"""Render reviewed cluster/namespace catalog to STAGED Fleet routing, never deploy.
After adding a tenant, review the catalog and generated diff before rollout.
"""
from pathlib import Path
import json,yaml,re
root=Path(__file__).resolve().parents[2]
stage=root/'config/afi-isolation/rollout'
cat=json.loads((root/'config/afi-isolation/tenant-catalog.json').read_text())
seen=set()
for tenant,data in cat.items():
 assert re.fullmatch(r'[a-z][a-z0-9-]{1,39}',tenant), 'Invalid tenant'
 assert data['cluster'] in ['rke2-cluster1','rke2-cluster2'], 'Unknown cluster'
 for ns in data['namespaces']:
  assert re.fullmatch(re.escape(tenant)+r'-[a-z][a-z0-9-]*',ns), 'Namespace outside tenant prefix'
  assert (data['cluster'],ns) not in seen, 'Duplicate namespace ownership'
  seen.add((data['cluster'],ns))
def dump(name,docs): (stage/name).write_text(yaml.safe_dump_all(docs,sort_keys=False))
for n in [1,2]:
 # Explicit namespace matches; the fallback excludes all mapped namespaces.
 cluster='rke2-cluster'+str(n);namespaces=[ns for t in cat.values() if t['cluster']==cluster for ns in t['namespaces']];docs=[]
 if n==1:
  docs=[x for x in yaml.safe_load_all((root/'bundles/application/logging/output/resources.yaml').read_text()) if x['kind'] in ['Service','EndpointSlice']]
 groups={name:data['namespaces'] for name,data in cat.items() if data['cluster']==cluster};groups['platform']=[]
 for tenant,ns in groups.items():
  output='afi-'+tenant;buffer={'type':'file','timekey':'1m','timekey_wait':'10s','timekey_use_utc':True,'flush_mode':'interval','flush_interval':'10s','flush_thread_count':2,'chunk_limit_size':'2m','total_limit_size':'4g','queued_chunks_limit_size':8192,'retry_forever':True,'retry_max_interval':'30s','overflow_action':'block','flush_at_shutdown':False}
  settings={'host':'opensearch-cluster-master' if n==1 else 'opensearch-cluster-master.opensearch.svc.cluster.local','port':9200,'scheme':'https','ssl_verify':True,'log_os_400_reason':True,'verify_os_version_at_startup':False,'default_opensearch_version':3,'request_timeout':'30s','bulk_message_request_threshold':'2097152','reload_connections':False,'reload_on_failure':False,'reconnect_on_error':True,'ca_file':{'mountFrom':{'secretKeyRef':{'name':'afi-opensearch-ingest','key':'ca.crt'}}},'user':'afi-ingest-'+cluster,'password':{'valueFrom':{'secretKeyRef':{'name':'afi-opensearch-ingest','key':'password'}}},'logstash_format':True,'logstash_prefix':'logs-'+cluster+'-'+tenant,'buffer':buffer}
  docs.append({'apiVersion':'logging.banzaicloud.io/v1beta1','kind':'ClusterOutput','metadata':{'name':output,'namespace':'cattle-logging-system'},'spec':{'opensearch':settings}})
  match=[{'select':{'namespaces':ns}}] if ns else ([{'exclude':{'namespaces':namespaces}},{'select':{}}] if namespaces else [{'select':{}}])
  docs.append({'apiVersion':'logging.banzaicloud.io/v1beta1','kind':'ClusterFlow','metadata':{'name':'afi-'+tenant,'namespace':'cattle-logging-system'},'spec':{'match':match,'filters':[{'dedot':{'de_dot_nested':True,'de_dot_separator':'_'}},{'record_modifier':{'records':[{'cluster_name':cluster,'cluster_role':'applications' if n==1 else 'infrastructure','tenant_id':tenant,'environment':'lab'}]}}],'globalOutputRefs':[output]}})
 dump(f'cluster{n}-logging-output.yaml',docs)
print('Rendered staged logging routes; review before Fleet activation.')
