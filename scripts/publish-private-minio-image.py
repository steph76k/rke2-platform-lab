#!/usr/bin/env python3
import sys,tarfile,gzip
import argparse,hashlib,json,os,re,urllib.parse
from pathlib import Path
import requests
p=argparse.ArgumentParser(description="Publish a Docker-save archive only into private Harbor project platform-builds")
p.add_argument('archive',type=Path)
p.add_argument('--tag',required=True)
p.add_argument('--ca-file',type=Path,required=True)
a=p.parse_args()
if not a.archive.is_file() or not a.ca_file.is_file():p.error('archive and CA file must exist')
if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}',a.tag):p.error('invalid tag')
def harbor():
 s=requests.Session();s.verify=str(a.ca_file);s.auth=(os.environ['HARBOR_USERNAME'],os.environ['HARBOR_PASSWORD'])
 def csrf(response,*args,**kwargs):
  if response.headers.get('X-Harbor-CSRF-Token'):s.headers['X-Harbor-CSRF-Token']=response.headers['X-Harbor-CSRF-Token']
 s.hooks['response'].append(csrf)
 s.get('https://harbor-ha.berger.ph/api/v2.0/users/current',timeout=30).raise_for_status()
 return s
s=harbor();base='https://harbor-ha.berger.ph';project='platform-builds';repo=project+'/minio';tag=a.tag
r=s.get(base+'/api/v2.0/projects',params={'name':project},timeout=30);r.raise_for_status()
if not r.json():
 r=s.post(base+'/api/v2.0/projects',json={'project_name':project,'metadata':{'public':'false','auto_scan':'true'}},timeout=30);r.raise_for_status()
else:assert r.json()[0]['metadata']['public']=='false'
r=s.get(base+'/service/token',params={'service':'harbor-registry','scope':'repository:'+repo+':pull,push'},timeout=30);r.raise_for_status()
d=requests.Session();d.verify=s.verify;d.headers['Authorization']='Bearer '+r.json()['token'];d.cookies.update(s.cookies)
if s.headers.get('X-Harbor-CSRF-Token'):d.headers['X-Harbor-CSRF-Token']=s.headers['X-Harbor-CSRF-Token']
def csrf(r,*args,**kwargs):
 if r.headers.get('X-Harbor-CSRF-Token'):d.headers['X-Harbor-CSRF-Token']=r.headers['X-Harbor-CSRF-Token']
d.hooks['response'].append(csrf)
def blob(data,media):
 digest='sha256:'+hashlib.sha256(data).hexdigest()
 r=d.head(base+'/v2/'+repo+'/blobs/'+digest,timeout=30)
 if r.status_code!=200:
  r=d.post(base+'/v2/'+repo+'/blobs/uploads/',timeout=30);r.raise_for_status();loc=urllib.parse.urljoin(base,r.headers['Location']);assert urllib.parse.urlparse(loc).scheme=='https' and urllib.parse.urlparse(loc).netloc=='harbor-ha.berger.ph'
  r=d.put(loc,params={'digest':digest},data=data,headers={'Content-Type':'application/octet-stream'},timeout=180)
  if r.status_code==403:r=d.put(loc,params={'digest':digest},data=data,headers={'Content-Type':'application/octet-stream'},timeout=180)
  r.raise_for_status()
 print('Verified/uploaded image blob',digest,len(data),flush=True)
 return {'mediaType':media,'size':len(data),'digest':digest}
with tarfile.open(a.archive) as t:
 m=json.load(t.extractfile('manifest.json'))[0]
 cfg=blob(t.extractfile(m['Config']).read(),'application/vnd.docker.container.image.v1+json')
 layers=[blob(gzip.compress(t.extractfile(p).read(),compresslevel=4,mtime=0),'application/vnd.docker.image.rootfs.diff.tar.gzip') for p in m['Layers']]
manifest=json.dumps({'schemaVersion':2,'mediaType':'application/vnd.docker.distribution.manifest.v2+json','config':cfg,'layers':layers},separators=(',',':')).encode()
r=d.put(base+'/v2/'+repo+'/manifests/'+tag,data=manifest,headers={'Content-Type':'application/vnd.docker.distribution.manifest.v2+json'},timeout=60);r.raise_for_status()
digest='sha256:'+hashlib.sha256(manifest).hexdigest()
r=d.get(base+'/v2/'+repo+'/manifests/'+digest,headers={'Accept':'application/vnd.docker.distribution.manifest.v2+json'},timeout=30);r.raise_for_status();assert r.content==manifest
print('PASS: privately published MinIO image',repo+'@'+digest,flush=True)
