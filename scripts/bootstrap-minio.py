#!/usr/bin/env python3
import sys,secrets,ipaddress,datetime
import argparse,base64,json,os,shutil,subprocess,tempfile
from pathlib import Path
import requests
parser=argparse.ArgumentParser(description="Bootstrap only a fresh MinIO lab; never rotate existing paths")
parser.add_argument('--execute-new-lab', action='store_true')
args=parser.parse_args()
if not args.execute_new_lab:
 parser.exit(message='No writes. Use --execute-new-lab only for a reviewed fresh bootstrap.\n')
ROOT=Path(__file__).resolve().parents[1]
bao_binary=os.environ.get('BAO_BINARY') or shutil.which('bao')
if not bao_binary:raise RuntimeError('bao CLI required')
env=dict(os.environ,BAO_ADDR='https://openbao.berger.ph',BAO_NAMESPACE='')
env.pop('BAO_SKIP_VERIFY',None);env.pop('VAULT_SKIP_VERIFY',None)
def bao(arguments,input=None,check=True):
 p=subprocess.run([bao_binary,*arguments],input=input,text=True,capture_output=True,env=env)
 if check and p.returncode:raise RuntimeError('OpenBao command failed; no secret output emitted')
 return p
def kv(path):return json.loads(bao(['kv','get','-format=json','secret/platform/'+path]).stdout)['data']['data']
def harbor():
 s=requests.Session();ca_path=out/'harbor-ca.crt';ca_path.write_text(kv('pki/lab-ca')['ca.crt']);s.verify=str(ca_path);s.auth=('admin',kv('harbor/credentials')['admin-password'])
 def csrf(response,*args,**kwargs):
  if response.headers.get('X-Harbor-CSRF-Token'):s.headers['X-Harbor-CSRF-Token']=response.headers['X-Harbor-CSRF-Token']
 s.hooks['response'].append(csrf)
 r=s.get('https://harbor-ha.berger.ph/api/v2.0/users/current',timeout=20);r.raise_for_status();return s
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
os.umask(0o077);work=tempfile.TemporaryDirectory(prefix='minio-bootstrap-');out=Path(work.name);root=ROOT
# Add only new MinIO paths, policy and role; refuse to overwrite an existing path.
for path in ['minio/credentials','minio/tls']:
 r=bao(['kv','metadata','get','-format=json','secret/platform/'+path],check=False)
 assert r.returncode!=0 and 'No value found' in r.stderr+r.stdout,'Cannot confirm unused path; refuse overwrite'
assert bao(['policy','read','eso-minio'],check=False).returncode!=0,'Policy already exists'
assert bao(['read','auth/rke2-cluster2/role/eso-minio'],check=False).returncode!=0,'Role already exists'
s=harbor();base='https://harbor-ha.berger.ph';name='minio-lab-pull'
r=s.get(base+'/api/v2.0/robots',params={'q':'name=~'+name},timeout=20);r.raise_for_status();assert not r.json(),'Robot already exists'
r=s.post(base+'/api/v2.0/robots',json={'name':name,'description':'Pull-only credentials for Fleet MinIO lab on cluster 2','duration':-1,'level':'system','disable':False,'permissions':[{'kind':'project','namespace':'platform-builds','access':[{'resource':'repository','action':'pull'}]}]},timeout=20);r.raise_for_status();robot=r.json();assert robot.get('secret')
(out/'minio-robot-id').write_text(str(robot['id']))
auth=base64.b64encode((robot['name']+':'+robot['secret']).encode()).decode();docker=json.dumps({'auths':{'harbor-ha.berger.ph':{'auth':auth}}})
creds={'root-user':'minio-lab-admin','root-password':secrets.token_urlsafe(36),'dockerconfigjson':docker}
bao(['kv','put','-cas=0','secret/platform/minio/credentials','-'],input=json.dumps(creds))
ca=kv('pki/lab-ca');cert=x509.load_pem_x509_certificate(ca['ca.crt'].encode());cakey=serialization.load_pem_private_key(ca['ca.key'].encode(),None);key=rsa.generate_private_key(public_exponent=65537,key_size=3072);now=datetime.datetime.now(datetime.timezone.utc)
names=[x509.DNSName(n) for n in ['minio.berger.ph','minio','minio.minio','minio.minio.svc','minio.minio.svc.cluster.local']]+[x509.IPAddress(ipaddress.ip_address('192.168.1.197'))]
c=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'minio.berger.ph')])).issuer_name(cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=364)).add_extension(x509.SubjectAlternativeName(names),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(cakey,hashes.SHA256())
tls={'tls.crt':c.public_bytes(serialization.Encoding.PEM).decode(),'tls.key':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode(),'ca.crt':ca['ca.crt']}
bao(['kv','put','-cas=0','secret/platform/minio/tls','-'],input=json.dumps(tls))
policy='path "secret/data/platform/minio/credentials" {\n  capabilities = ["read"]\n}\npath "secret/data/platform/minio/tls" {\n  capabilities = ["read"]\n}\n'
assert bao(['policy','read','eso-minio'],check=False).returncode!=0
bao(['policy','write','eso-minio','-'],input=policy)
role={'bound_service_account_names':['openbao-minio'],'bound_service_account_namespaces':['external-secrets'],'audience':'https://kubernetes.default.svc.cluster.local','token_policies':['eso-minio'],'token_ttl':900,'token_max_ttl':3600,'token_no_default_policy':False}
assert bao(['read','auth/rke2-cluster2/role/eso-minio'],check=False).returncode!=0
bao(['write','auth/rke2-cluster2/role/eso-minio','-'],input=json.dumps(role))
work.cleanup()
print('PASS: isolated MinIO credentials, TLS certificate, read-only ESO policy/role and pull-only Harbor robot created; no secret values printed')
