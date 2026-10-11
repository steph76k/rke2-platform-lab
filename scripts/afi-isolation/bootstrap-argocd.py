#!/usr/bin/env python3
"""Bootstrap only the dedicated Argo CD OIDC client, TLS and OpenBao/ESO identity.
Run without --apply to inspect scope. Existing unrelated clients are never adopted.
No plaintext credentials are printed or written to the repository.
"""
import argparse
import datetime
import json
import secrets

import bcrypt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from afi_platform import CONFIG, ROOT, BAO, command, keycloak, kv, put_new

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
a = parser.parse_args()
if not a.apply:
    print('Create/reconcile afi-argocd in realm berger (PKCE S256); store dedicated admin, TLS and client credentials in OpenBao; reconcile eso-argocd read-only identity.')
    raise SystemExit()

client_id = 'afi-argocd'
marker = 'Managed by rke2-platform-lab Argo CD bootstrap'
base = CONFIG['keycloak'] + '/admin/realms/' + CONFIG['realm']
session = keycloak()
desired = {
    'clientId': client_id, 'name': 'Argo CD', 'description': marker, 'enabled': True,
    'protocol': 'openid-connect', 'publicClient': False, 'standardFlowEnabled': True,
    'directAccessGrantsEnabled': False, 'serviceAccountsEnabled': False,
    'redirectUris': ['https://argocd.berger.ph/auth/callback'],
    'webOrigins': ['https://argocd.berger.ph'],
    'attributes': {'pkce.code.challenge.method': 'S256'},
    'defaultClientScopes': ['profile', 'email', 'roles'],
    'protocolMappers': [{
        'name': 'Argo CD groups', 'protocol': 'openid-connect',
        'protocolMapper': 'oidc-group-membership-mapper',
        'config': {'claim.name': 'groups', 'full.path': 'false',
                   'id.token.claim': 'true', 'access.token.claim': 'true', 'userinfo.token.claim': 'true'}
    }, {
        'name': 'Argo CD audience', 'protocol': 'openid-connect',
        'protocolMapper': 'oidc-audience-mapper',
        'config': {'included.client.audience': client_id, 'id.token.claim': 'true', 'access.token.claim': 'true'}
    }]
}
r = session.get(base + '/clients', params={'clientId': client_id}, timeout=30)
r.raise_for_status()
found = r.json()
if found:
    assert len(found) == 1 and found[0].get('description') == marker, 'Unrelated client exists; refusing adoption'
    client = found[0]
    session.put(base + '/clients/' + client['id'], json={**client, **desired}, timeout=30).raise_for_status()
else:
    r = session.post(base + '/clients', json=desired, timeout=30)
    r.raise_for_status()
    client = {'id': r.headers['Location'].rsplit('/', 1)[1]}
r = session.get(base + '/clients/' + client['id'] + '/client-secret', timeout=30)
r.raise_for_status()
secret = r.json()['value']
try:
    saved = kv('oidc/afi-argocd')
except RuntimeError:
    put_new('oidc/afi-argocd', {'client_id': client_id, 'client_secret': secret})
    saved = kv('oidc/afi-argocd')
assert saved['client_secret'] == secret, 'Explicit secret rotation required'
now = datetime.datetime.now(datetime.timezone.utc)
try:
    kv('argocd/admin')
except RuntimeError:
    password = secrets.token_urlsafe(36)
    put_new('argocd/admin', {'username': 'admin', 'password': password,
        'password_hash': bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode(),
        'password_mtime': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'server_secretkey': secrets.token_urlsafe(48)})
try:
    kv('argocd/tls')
except RuntimeError:
    ca = kv('pki/lab-ca')
    issuer = x509.load_pem_x509_certificate(ca['ca.crt'].encode())
    issuer_key = serialization.load_pem_private_key(ca['ca.key'].encode(), None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    cert = (x509.CertificateBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'argocd.berger.ph')]))
        .issuer_name(issuer.subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(min(now + datetime.timedelta(days=364), issuer.not_valid_after.replace(tzinfo=datetime.timezone.utc)))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('argocd.berger.ph')]), False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .sign(issuer_key, hashes.SHA256()))
    put_new('argocd/tls', {'tls.crt': cert.public_bytes(serialization.Encoding.PEM).decode(),
        'tls.key': key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode(), 'ca.crt': ca['ca.crt']})
command([BAO, 'policy', 'write', 'eso-argocd', '-'],
        (ROOT / 'config/openbao/policies/eso-argocd.hcl').read_text())
command([BAO, 'write', 'auth/rke2-cluster2/role/eso-argocd', '-'],
        (ROOT / 'config/openbao/roles/eso-argocd.json').read_text())
print('Argo CD client, TLS, local recovery administrator and ESO identity ready; credentials remain in OpenBao.')
