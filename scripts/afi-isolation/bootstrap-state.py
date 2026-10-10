#!/usr/bin/env python3
"""Idempotent MinIO state bootstrap. Requires a root OpenBao session and boto3/minio.
Never prints credentials. Creates new tenant identities, preserving existing keys.
"""
import argparse,base64,json,os,re,secrets,subprocess,tempfile
from pathlib import Path
from urllib.parse import urlparse
import boto3,urllib3
from botocore.config import Config
from botocore.exceptions import ClientError
from minio.minioadmin import MinioAdmin
from minio.credentials import StaticProvider
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('tenant');p.add_argument('--config',type=Path,default=Path(__file__).resolve().parents[2]/'config/afi-isolation/state-backend.json')
a=p.parse_args()
if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}',a.tenant):p.error('Invalid tenant slug')
os.umask(0o077);cfg=json.loads(a.config.read_text())
bao=os.environ.get('BAO_BIN','/home/tanzu/.local/bin/bao')
env=dict(os.environ,BAO_ADDR=os.environ.get('BAO_ADDR','https://openbao.berger.ph'),BAO_NAMESPACE='')
def command(args,data=None,optional=False):
 r=subprocess.run([bao,*args],input=json.dumps(data) if data is not None else None,env=env,text=True,capture_output=True)
 if r.returncode:
  if optional and 'No value found' in r.stderr:return None
  raise RuntimeError('OpenBao operation failed (output suppressed)')
 return json.loads(r.stdout) if r.stdout else None
def read(path,optional=False):
 d=command(['kv','get','-format=json',path],optional=optional)
 return d['data']['data'] if d else None
root=read(cfg['minio_root_path']);ca=read(cfg['ca_path'])['ca.crt']
with tempfile.TemporaryDirectory(prefix='afi-state-') as tmp:
 cafile=Path(tmp)/'ca.crt';cafile.write_text(ca)
 s3=boto3.client('s3',endpoint_url=cfg['endpoint'],region_name=cfg['region'],aws_access_key_id=root['root-user'],aws_secret_access_key=root['root-password'],verify=str(cafile),config=Config(signature_version='s3v4',s3={'addressing_style':'path'}))
 bucket=cfg['bucket']
 try:s3.head_bucket(Bucket=bucket)
 except ClientError as e:
  if e.response['Error']['Code'] not in ['404','NoSuchBucket']:raise
  s3.create_bucket(Bucket=bucket)
 s3.put_bucket_versioning(Bucket=bucket,VersioningConfiguration={'Status':'Enabled'})
 admin=MinioAdmin(endpoint=urlparse(cfg['endpoint']).netloc,credentials=StaticProvider(root['root-user'],root['root-password']),secure=True,http_client=urllib3.PoolManager(cert_reqs='CERT_REQUIRED',ca_certs=str(cafile)))
 prefix=cfg['environment']+'/'+a.tenant;arn='arn:aws:s3:::'+bucket;policy_name='tfstate-'+cfg['environment']+'-'+a.tenant
 policy={'Version':'2012-10-17','Statement':[
  {'Effect':'Allow','Action':['s3:GetBucketLocation'],'Resource':[arn]},
  {'Effect':'Allow','Action':['s3:ListBucket','s3:ListBucketVersions'],'Resource':[arn],'Condition':{'StringLike':{'s3:prefix':[prefix+'/*']}}},
  {'Effect':'Allow','Action':['s3:GetObject','s3:GetObjectVersion','s3:PutObject'],'Resource':[arn+'/'+prefix+'/*']},
  {'Effect':'Allow','Action':['s3:DeleteObject'],'Resource':[arn+'/'+prefix+'/terraform.tfstate.tflock',arn+'/'+prefix+'/validation/*']}
 ]}
 path=cfg['credentials_path']+'/'+a.tenant;creds=read(path,optional=True)
 if creds is None:
  creds={'access_key':policy_name,'secret_key':secrets.token_urlsafe(36),'sse_customer_key':base64.b64encode(secrets.token_bytes(32)).decode()}
  command(['kv','put','-format=json','-cas=0',path,'-'],creds)
 # Dedicated bootstrap-owned identity; do not rotate existing credentials.
 try:admin.user_info(creds['access_key'])
 except Exception as e:
  if 'XMinioAdminNoSuchUser' not in str(e):raise
  admin.user_add(creds['access_key'],creds['secret_key'])
 admin.policy_add(policy_name,policy=policy);admin.policy_set(policy_name,user=creds['access_key'])
 print(json.dumps({'bucket':bucket,'versioning':s3.get_bucket_versioning(Bucket=bucket)['Status'],'tenant':a.tenant,'state_key':prefix+'/terraform.tfstate','credentials_path':path,'policy':policy_name}))
