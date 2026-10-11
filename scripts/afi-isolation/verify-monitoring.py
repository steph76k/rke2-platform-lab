#!/usr/bin/env python3
"""Read-only Rancher Monitoring, logging targets/rules and Grafana proxy checks."""
import sys,time,json,subprocess,collections
from pathlib import Path
import requests
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kubeconfig',required=True)
parser.add_argument('--ca-file',required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--rancher-context',default='rancher')
args=parser.parse_args()
args.output.parent.mkdir(parents=True,exist_ok=True)
K2=['kubectl','--kubeconfig='+args.kubeconfig,'--request-timeout=30s']
def get(command):
    r=subprocess.run(command,capture_output=True,text=True,timeout=45)
    if r.returncode:raise RuntimeError('Kubernetes read failed: '+' '.join(command[:3]))
    return json.loads(r.stdout)
report={}
svc=get(K2+['get','services','-n','cattle-monitoring-system','-o','json'])['items']
prom=next(s['metadata']['name'] for s in svc if s['metadata']['name']=='rancher-monitoring-prometheus')
p=subprocess.Popen(K2+['port-forward','-n','cattle-monitoring-system','--address=127.0.0.1','service/'+prom,'19090:9090'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(30):
  try:
   r=requests.get('http://127.0.0.1:19090/-/ready',timeout=3)
   if r.status_code==200:break
  except requests.RequestException:pass
  time.sleep(1)
 else:raise RuntimeError('Prometheus forward not ready')
 def api(path):
  r=requests.get('http://127.0.0.1:19090/api/v1/'+path,timeout=30);r.raise_for_status();d=r.json();assert d['status']=='success';return d['data']
 targets=api('targets')['activeTargets']
 grouped={}
 for t in targets:
  job=t['labels'].get('job','(none)');g=grouped.setdefault(job,{'up':0,'total':0});g['total']+=1;g['up']+=int(t['health']=='up')
 report['targetsByJob']=grouped
 report['downTargets']=[{'job':t['labels'].get('job'),'url':t['scrapeUrl'],'error':t['lastError']} for t in targets if t['health']!='up']
 logging=[t for t in targets if t['labels'].get('job','').startswith('logging-')]
 report['loggingTargets']={'total':len(logging),'up':sum(t['health']=='up' for t in logging)}
 rules=api('rules')['groups']
 group=next(g for g in rules if g['name']=='afi-logging-durability')
 report['loggingRules']=[{'name':r['name'],'health':r['health'],'state':r.get('state')} for r in group['rules']]
 report['alerts']=[{'name':r['labels'].get('alertname'),'state':r['state']} for r in api('alerts')['alerts']]
 assert len(logging)==12 and all(t['health']=='up' for t in logging), 'Logging target mismatch'
 assert len(group['rules'])==7 and all(r['health']=='ok' for r in group['rules']), 'Logging rule evaluation failed'
 assert not report['downTargets'], 'Prometheus has down targets'
finally:
 p.terminate();p.wait(timeout=15)
 args.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2),flush=True)
config=get(['kubectl','config','view','--raw','--minify','--context='+args.rancher_context,'-o','json'])
s=requests.Session();s.verify=args.ca_file;s.headers['Authorization']='Bearer '+config['users'][0]['user']['token']
url='https://rancher.berger.ph/k8s/clusters/c-44q9v/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-grafana:80/proxy/api/health'
r=s.get(url,timeout=30);assert r.status_code==200, ('Grafana proxy',r.status_code)
assert r.json()['database']=='ok'
report['grafanaRancherProxy']={'httpStatus':r.status_code,'database':r.json()['database']}
args.output.write_text(json.dumps(report,indent=2)+'\n')
print('Grafana via authenticated Rancher proxy: PASS',flush=True)
