"""Lab bootstrap helpers. Secrets stay in memory, OpenBao and temporary 0600 files."""
import json,os,subprocess,tempfile
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
ROOT=Path(__file__).resolve().parents[2]
CONFIG=json.loads((ROOT/'config/afi-isolation/identity.json').read_text())
BAO=os.environ.get('BAO_BIN','/home/tanzu/.local/bin/bao')
def command(args,input=None):
 r=subprocess.run(args,input=input,text=True,capture_output=True,env=dict(os.environ,BAO_ADDR='https://openbao.berger.ph',BAO_NAMESPACE='') if args[0]==BAO else None)
 if r.returncode:raise RuntimeError('Command failed; sensitive output suppressed: '+args[0])
 return r.stdout
def kv(path):
 r=command([BAO,'kv','get','-format=json','secret/platform/'+path]);return json.loads(r)['data']['data']
def put_new(path,data):
 command([BAO,'kv','put','-cas=0','secret/platform/'+path,'-'],json.dumps(data))
def kget(context,args):return json.loads(command(['kubectl','--context='+context,*args,'-o','json']))
def keycloak():
 # Existing lab bootstrap credentials. Migrate literal STS env to ESO in a separate change.
 sts=kget('rke2-cluster1',['get','sts','keycloak','-n','keycloak'])
 e={x['name']:x.get('value') for x in sts['spec']['template']['spec']['containers'][0]['env']}
 s=requests.Session();r=s.post(CONFIG['keycloak']+'/realms/master/protocol/openid-connect/token',data={'grant_type':'password','client_id':'admin-cli','username':e['KC_BOOTSTRAP_ADMIN_USERNAME'],'password':e['KC_BOOTSTRAP_ADMIN_PASSWORD']},timeout=30);r.raise_for_status();s.headers['Authorization']='Bearer '+r.json()['access_token'];return s
class TLSHostAdapter(HTTPAdapter):
 def init_poolmanager(self,connections,maxsize,block=False,**kwargs):
  super().init_poolmanager(connections,maxsize,block,assert_hostname=CONFIG['opensearch_tls_host'],server_hostname=CONFIG['opensearch_tls_host'],**kwargs)
def sessions(cafile):
 h=requests.Session();h.verify=str(cafile);h.auth=('admin',kv('harbor/credentials')['admin-password'])
 def csrf(r,*args,**kwargs):
  if r.headers.get('X-Harbor-CSRF-Token'):h.headers['X-Harbor-CSRF-Token']=r.headers['X-Harbor-CSRF-Token']
 h.hooks['response'].append(csrf)
 s=requests.Session();s.verify=str(cafile);s.mount(CONFIG['opensearch_tunnel'],TLSHostAdapter());s.auth=('admin',kv('opensearch/admin')['password'])
 return h,s

def backup(name,data):
 key=Path(os.environ.get('AFI_RECOVERY_KEY','/home/tanzu/manifest/.local-recovery-keys/platform-20261010.agekey'))
 recipient=next(x.split(':',1)[1].strip() for x in key.read_text().splitlines() if x.startswith('# public key:'))
 directory=Path(os.environ.get('AFI_BACKUP_DIR','/home/tanzu/manifest/backups/afi-isolation-2026-10-10'));directory.mkdir(mode=0o700,parents=True,exist_ok=True)
 path=directory/(name+'.sops.json')
 if path.exists():return
 r=subprocess.run(['sops','--encrypt','--age',recipient,'--input-type','json','--output-type','json','/dev/stdin'],input=json.dumps(data),capture_output=True,text=True);assert r.returncode==0,'Backup encryption failed'
 with path.open('x') as f:f.write(r.stdout)
 path.chmod(0o600)
 r=subprocess.run(['sops','--decrypt','--input-type','json','--output-type','json',str(path)],env=dict(os.environ,SOPS_AGE_KEY_FILE=str(key)),capture_output=True,text=True);assert r.returncode==0 and json.loads(r.stdout)==data,'Backup verification failed'

def apply_security_config(config,certificate):
 """Apply only the config type with securityadmin; never overwrite roles/users."""
 import io,tarfile,yaml
 payload=yaml.safe_dump({'_meta':{'type':'config','config_version':2},'config':config},sort_keys=False)
 files={'config.yml':payload,'admin.crt':certificate['tls.crt'],'admin.key':certificate['tls.key'],'ca.crt':certificate['ca.crt']}
 archive=io.BytesIO()
 with tarfile.open(fileobj=archive,mode='w') as tar:
  for name,body in files.items():
   data=body.encode();entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o600;tar.addfile(entry,io.BytesIO(data))
 shell='''set -eu
umask 077
afi_dir=$(mktemp -d /tmp/afi-security.XXXXXX)
trap 'rm -rf "$afi_dir"' EXIT
tar -xf - -C "$afi_dir"
export OPENSEARCH_JAVA_HOME=/usr/share/opensearch/jdk
/usr/share/opensearch/plugins/opensearch-security/tools/securityadmin.sh -h opensearch-cluster-master.opensearch.svc.cluster.local -p 9200 -cn opensearch-cluster -f "$afi_dir/config.yml" -t config -cacert "$afi_dir/ca.crt" -cert "$afi_dir/admin.crt" -key "$afi_dir/admin.key"
'''
 args=['kubectl','--context=rancher','--server=https://rancher.berger.ph/k8s/clusters/c-44q9v','exec','-i','-n','opensearch','opensearch-cluster-master-0','--','bash','-c',shell]
 r=subprocess.run(args,input=archive.getvalue(),capture_output=True,timeout=90)
 if r.returncode:raise RuntimeError('securityadmin failed: '+r.stdout.decode()[-1200:]+r.stderr.decode()[-400:])
 print('OpenSearch securityadmin: applied only config type over verified TLS')
 # Keep the bootstrap-mounted config in OpenBao reproducible, retaining every other secret key.
 saved=kv('opensearch/security');saved['config.yml']=payload
 command([BAO,'kv','put','secret/platform/opensearch/security','-'],json.dumps(saved))
