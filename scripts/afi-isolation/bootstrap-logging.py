#!/usr/bin/env python3
"""Create dedicated logging service identities, ESO access and Dashboards TLS."""
import datetime,ipaddress,json,os,secrets,tempfile
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from afi_platform import CONFIG,ROOT,kv,put_new,sessions,command,BAO
os.umask(0o077)
ca=kv('pki/lab-ca')
with tempfile.TemporaryDirectory(prefix='afi-logging-') as tmp:
 f=Path(tmp)/'ca.crt';f.write_text(ca['ca.crt']);_,s=sessions(f);base=CONFIG['opensearch_tunnel']
 for cluster in ['rke2-cluster1','rke2-cluster2']:
  name='afi-ingest-'+cluster;path='afi-logging/'+cluster
  try:creds=kv(path)
  except RuntimeError:put_new(path,{'username':name,'password':secrets.token_urlsafe(36),'ca.crt':ca['ca.crt']});creds=kv(path)
  role={'cluster_permissions':['cluster:monitor/main','indices:data/write/bulk*'],'index_permissions':[{'index_patterns':['logs-'+cluster+'-*'],'allowed_actions':['create_index','write']}],'tenant_permissions':[]}
  r=s.put(base+'/_plugins/_security/api/roles/'+name,json=role,timeout=30);r.raise_for_status()
  r=s.get(base+'/_plugins/_security/api/internalusers/'+name,timeout=30)
  if r.status_code==404:
   r=s.put(base+'/_plugins/_security/api/internalusers/'+name,json={'password':creds['password'],'backend_roles':[],'attributes':{'owner':'rke2-platform-lab'}},timeout=30);r.raise_for_status()
  else:r.raise_for_status()
  r=s.put(base+'/_plugins/_security/api/rolesmapping/'+name,json={'users':[name],'backend_roles':[],'hosts':[]},timeout=30);r.raise_for_status()
  paths=[path]
  if cluster=='rke2-cluster2':paths+=['afi-logging/dashboards-tls','oidc/afi-opensearch']
  policy=''.join('path "secret/data/platform/'+p+'" { capabilities = ["read"] }\n' for p in paths)
  policyname='eso-afi-logging-'+cluster
  command([BAO,'policy','write',policyname,'-'],policy)
  rolebao={'bound_service_account_names':['openbao-afi-logging'],'bound_service_account_namespaces':['external-secrets'],'audience':'https://kubernetes.default.svc.cluster.local','token_policies':[policyname],'token_ttl':900,'token_max_ttl':3600}
  command([BAO,'write','auth/'+cluster+'/role/'+policyname,'-'],json.dumps(rolebao))
  (ROOT/'config/openbao/policies'/f'{policyname}.hcl').write_text(policy)
  (ROOT/'config/openbao/roles'/f'{policyname}.json').write_text(json.dumps(rolebao,indent=2)+'\n')
  print('Dedicated ingest and ESO role ready:',cluster)
try:kv('afi-logging/dashboards-tls')
except RuntimeError:
 cert=x509.load_pem_x509_certificate(ca['ca.crt'].encode());cakey=serialization.load_pem_private_key(ca['ca.key'].encode(),None);key=rsa.generate_private_key(public_exponent=65537,key_size=3072);now=datetime.datetime.now(datetime.timezone.utc)
 c=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'opensearch.berger.ph')])).issuer_name(cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=364)).add_extension(x509.SubjectAlternativeName([x509.DNSName('opensearch.berger.ph')]),False).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),False).sign(cakey,hashes.SHA256())
 put_new('afi-logging/dashboards-tls',{'tls.crt':c.public_bytes(serialization.Encoding.PEM).decode(),'tls.key':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode(),'ca.crt':ca['ca.crt']})
print('Dashboards TLS material stored in OpenBao')
