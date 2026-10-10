#!/usr/bin/env python3
"""Only after migration approval: generate fresh lab credentials in OpenBao.

Requires bao, PyYAML, bcrypt and cryptography. No Kubernetes writes.
Never prints values; no credentials are passed as command-line arguments.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import bcrypt
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

ROOT = Path(__file__).resolve().parents[1]
PATHS = ["harbor/credentials", "harbor/token-tls", "harbor/ingress-tls",
         "postgresql/harbor", "redis/credentials", "opensearch/admin",
         "opensearch/dashboards", "opensearch/security", "opensearch/tls",
         "opensearch/admin-tls", "pki/lab-ca", "bootstrap/smoke"]


def pem_key(key):
    return key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


def certificate(cn, ca_key=None, ca_cert=None, dns=(), is_ca=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject)
            .issuer_name(ca_cert.subject if ca_cert else subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=is_ca, path_length=0 if is_ca else None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                        key_encipherment=True, data_encipherment=False,
                                        key_agreement=False, key_cert_sign=is_ca,
                                        crl_sign=is_ca, encipher_only=None, decipher_only=None), critical=True))
    if dns:
        cert = cert.add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in dns]), critical=False)
    if not is_ca:
        cert = cert.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH,
                                                       ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    return key, cert.sign(ca_key or key, hashes.SHA256())


def bundle(key, cert, ca):
    return {"tls.key": pem_key(key), "tls.crt": cert.public_bytes(serialization.Encoding.PEM).decode(),
            "ca.crt": ca.public_bytes(serialization.Encoding.PEM).decode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-new-lab", action="store_true",
                        help="Only use after explicit bootstrap approval; never with retained databases")
    args = parser.parse_args()
    if not args.execute_new_lab:
        parser.exit(message="No writes. Review docs/secrets.md; --execute-new-lab is required after approval.\n")
    os.umask(0o077)
    env = os.environ.copy()
    env.update(BAO_ADDR="https://openbao.berger.ph", BAO_NAMESPACE="", BAO_CLIENT_TIMEOUT="15s")
    env.pop('BAO_SKIP_VERIFY', None)
    env.pop('VAULT_SKIP_VERIFY', None)
    # Refuse every existing destination, including partially completed bootstraps.
    for path in PATHS:
        p = subprocess.run(["bao", "kv", "metadata", "get", "-format=json", "-mount=secret", "platform/" + path],
                           env=env, capture_output=True, text=True)
        if p.returncode == 0:
            raise RuntimeError("Destination exists: platform/" + path + "; do not rotate implicitly")
        if "No value found" not in p.stderr + p.stdout:
            raise RuntimeError("Cannot verify empty destination: platform/" + path)

    password = lambda: secrets.token_urlsafe(32)
    fixed = lambda size: ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(size))
    admin, dashboards, registry = password(), password(), password()
    ca_key, ca = certificate("rke2-platform-lab-ca", is_ca=True)
    node_key, node = certificate("opensearch-nodes", ca_key, ca,
        dns=["opensearch-cluster-master", "opensearch-cluster-master.opensearch",
             "opensearch-cluster-master.opensearch.svc", "opensearch-cluster-master.opensearch.svc.cluster.local",
             "*.opensearch-cluster-master-headless.opensearch.svc.cluster.local"])
    os_admin_key, os_admin = certificate("opensearch-admin", ca_key, ca)
    harbor_key, harbor_cert = certificate("harbor-ha.berger.ph", ca_key, ca, dns=["harbor-ha.berger.ph"])
    token_key, token_cert = certificate("harbor-token", ca_key, ca)
    security = {p.name: p.read_text() for p in (ROOT / 'config/opensearch/security').glob('*.yml')}
    users = {"_meta": {"type": "internalusers", "config_version": 2},
             "admin": {"hash": bcrypt.hashpw(admin.encode(), bcrypt.gensalt()).decode(),
                       "reserved": True, "backend_roles": ["admin"]},
             "kibanaserver": {"hash": bcrypt.hashpw(dashboards.encode(), bcrypt.gensalt()).decode(),
                              "reserved": True}}
    security['internal_users.yml'] = yaml.safe_dump(users, sort_keys=False)
    data = {
        "harbor/credentials": {"admin-password": password(), "secret-key": fixed(16), "core-secret": fixed(16),
            "csrf-key": fixed(32), "jobservice-secret": fixed(16), "registry-http-secret": fixed(32),
            "registry-password": registry,
            "registry-htpasswd": "harbor_registry_user:" + bcrypt.hashpw(registry.encode(), bcrypt.gensalt()).decode()},
        "harbor/token-tls": bundle(token_key, token_cert, ca),
        "harbor/ingress-tls": bundle(harbor_key, harbor_cert, ca),
        "postgresql/harbor": {"username": "harbor-ha", "password": password()},
        "redis/credentials": {"password": password()},
        "opensearch/admin": {"password": admin},
        "opensearch/dashboards": {"username": "kibanaserver", "password": dashboards},
        "opensearch/security": security,
        "opensearch/tls": bundle(node_key, node, ca),
        "opensearch/admin-tls": bundle(os_admin_key, os_admin, ca),
        "pki/lab-ca": {"ca.key": pem_key(ca_key), "ca.crt": ca.public_bytes(serialization.Encoding.PEM).decode()},
        "bootstrap/smoke": {"probe": "rke2-cluster2-bootstrap-ok"},
    }
    for path in PATHS:
        p = subprocess.run(["bao", "kv", "put", "-cas=0", "-mount=secret", "platform/" + path, "-"],
                           input=json.dumps(data[path]), env=env, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError("Write failed at platform/" + path + "; earlier paths remain. Stop and review, do not delete/retry blindly.")
        print("Created secret/platform/" + path + " (values hidden)")


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never print subprocess output, payloads, or full exception details.
        print("Bootstrap stopped: " + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
