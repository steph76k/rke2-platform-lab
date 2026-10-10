# OpenBao und ESO: Bootstrap und Secret-Vertrag

**Bootstrap am 10.10.2026 nach ausdrücklicher Umsetzungs- und Löschfreigabe ausgeführt.**
Die folgenden Befehle dokumentieren einen frischen Aufbau; den vorhandenen Auth-Mount
und die bereits gefüllten KV-Pfade nicht erneut initialisieren. Keine Secret-Rotation
bei gleichzeitiger Weiterverwendung alter PostgreSQL-, Redis- oder OpenSearch-Daten.

## Authentifizierung für Cluster 2

Root-Namespace in OpenBao; bestehendes KV-v2 `secret/`. Neuer Mount `rke2-cluster2`.
Die Rollen/Policies unter `config/openbao` gehören nicht zu einem Fleet-Pfad.
Sechs separate Rollen: `eso-harbor`, `eso-postgresql`, `eso-redis`, `eso-opensearch`,
`eso-logging` und `eso-infrastructure` (nur Smoke-Test). Policies gestatten nur `read` auf exakt
benannten KV-Datenpfaden, kein Schreiben und kein Wildcard-Zugriff auf Mandanten.
TTL 15 Minuten, max. TTL 1 Stunde; `default` erlaubt Self-Lookup/Erneuerung.

Wie bei Cluster 1 wird kein langlebiger Reviewer-JWT gespeichert. OpenBao verwendet
den eingereichten kurzlebigen ServiceAccount-JWT auch für TokenReview.
Nur die sechs gebundenen ServiceAccounts erhalten `create` auf `tokenreviews`;
kein `cluster-admin` und keine SubjectAccessReview-Rechte. Die JWT-Audience muss
von der RKE2-API akzeptiert werden. Die Audience
`https://kubernetes.default.svc.cluster.local` wurde auf Cluster 2
positiv und mit falscher Audience negativ geprüft. Auch fremde ServiceAccounts
und nicht erlaubte KV-Pfade wurden erwartungsgemäß abgewiesen.

Vorbereitung nach Freigabe:

1. Nur ESO-Bundle aktivieren und drei Deployments sowie CRDs Ready abwarten.
2. Store-Bundle aktivieren: SAs, TokenReview-RBAC und Stores.
   Stores sind bis zur Auth-Einrichtung erwartbar nicht Ready.
3. Prüfen, dass `auth/rke2-cluster2` noch nicht existiert. Bestehenden Mount niemals
   mit der folgenden Vorlage überschreiben. OpenBao-Root-Namespace sicherstellen.
4. Cluster-CA **vom Zielcluster**, nicht aus der Rancher-Proxy-Kubeconfig, lesen.
   Dann Auth-Mount und exakt die geprüften Rollen/Policies anlegen:

```bash
# NUR NACH FREIGABE – verändert OpenBao, nicht jetzt ausführen.
export BAO_ADDR=https://openbao.berger.ph
unset BAO_NAMESPACE
umask 077
cluster2_ca_file=$(mktemp)
kubectl --context=rke2-cluster2 -n default get configmap kube-root-ca.crt \
  -o jsonpath='{.data.ca\.crt}' > "$cluster2_ca_file"
bao auth enable -path=rke2-cluster2 kubernetes
bao write auth/rke2-cluster2/config \
  kubernetes_host=https://192.168.1.164:6443 \
  kubernetes_ca_cert=@"$cluster2_ca_file" \
  disable_local_ca_jwt=true
rm -- "$cluster2_ca_file"
for service in harbor postgresql redis opensearch infrastructure logging; do
  bao policy write "eso-$service" "config/openbao/policies/eso-$service.hcl"
  bao write "auth/rke2-cluster2/role/eso-$service" \
    @"config/openbao/roles/eso-$service.json"
done
```

Der direkte Endpunkt `.164:6443` wurde aus dem OpenBao-Pod mit Cluster-CA geprüft
(HTTP 401 ohne Token bestätigt TLS und Erreichbarkeit). `.165` und `.166` sind weitere
API-Endpunkte. Für höhere Verfügbarkeit später einen verifizierten API-VIP/DNS-Namen
verwenden. Der Rancher-Proxy eignet sich nicht als Ersatz für natives TokenReview.
Die Root-Token-Anmeldung bleibt ausschließlich lokal; kein Token in Shell-Argumenten,
Dateien im Repo, Tickets oder Ausgaben. Keine `set -x`-Sessions verwenden.

## Sichere Erzeugung für den frischen Lab-Aufbau

`scripts/bootstrap-new-lab-secrets.py` ist ein ausdrücklich auszuführendes Werkzeug,
kein Fleet-Hook. Es erzeugt neue Zufallspasswörter, bcrypt-Hashes, RSA-Schlüssel
(PKCS#1 für den Harbor-Token-Signer, sonst PKCS#8) und Zertifikate im Speicher.
Die KV-Daten werden per stdin an `bao` übergeben.
Kein Klartext in Kommandozeilen oder Logs, keine lokalen Secret-Dateien.
Benötigt Python 3, PyYAML, bcrypt, cryptography und bao.

Ohne `--execute-new-lab` führt es keine Writes aus. Mit diesem Schalter prüft es
vorher alle Zielpfade und verweigert vorhandene Metadaten. Jedes Schreiben nutzt
KV-v2 CAS=0. Ein teilweise fehlgeschlagener Lauf muss untersucht werden; keine
automatische Löschung oder Rotation zum Erzwingen eines Wiederholungslaufs.

```bash
# NUR NACH FREIGABE und mit gesichertem OpenBao-Zugriff:
python3 scripts/bootstrap-new-lab-secrets.py --execute-new-lab
```

Die selbst signierte Lab-CA ist eine bewusste PoC-Entscheidung. Sie muss auf Harbor-
Clients/Docker-Nodes als vertrauenswürdig verteilt werden; keine TLS-Prüfung abschalten.
Zertifikate laufen nach 365 Tagen ab und benötigen einen dokumentierten erneuten
Ausstellungs-/Rolloutprozess. CA-Privatschlüssel unter `secret/platform/pki/lab-ca`
und OpenSearch-Admin-Zertifikat unter `secret/platform/opensearch/admin-tls` sind
**keiner** ESO-Policy zugänglich. Sie dienen kontrollierter Administration/Erneuerung.
Root-KV/OpenBao-Datenträger und Unseal-Material müssen vor Migration gesichert sein.

## Ziel-Secrets

Alle Pfade in der folgenden Tabelle sind relativ zum Root-KV-v2-Mount `secret/`.
Kein zusätzlicher OpenBao-Namespace. `ExternalSecret.remoteRef.key` enthält kein `data/`;
die Policies adressieren dagegen `secret/data/...`.

| Namespace | Kubernetes-Secret | Keys | OpenBao-Pfad / Properties |
| --- | --- | --- | --- |
| harbor-ha | platform-harbor-admin | HARBOR_ADMIN_PASSWORD | platform/harbor/credentials: admin-password |
| harbor-ha | platform-harbor-key | secretKey | platform/harbor/credentials: secret-key (16 Zeichen) |
| harbor-ha | platform-harbor-core | secret, CSRF_KEY | platform/harbor/credentials: core-secret (16), csrf-key (32) |
| harbor-ha | platform-harbor-jobservice | JOBSERVICE_SECRET | platform/harbor/credentials: jobservice-secret (16) |
| harbor-ha | platform-harbor-registry | REGISTRY_HTTP_SECRET | platform/harbor/credentials: registry-http-secret |
| harbor-ha | platform-harbor-registry-auth | REGISTRY_PASSWD, REGISTRY_HTPASSWD | platform/harbor/credentials: registry-password, registry-htpasswd (bcrypt für harbor_registry_user) |
| harbor-ha | platform-harbor-token-tls | tls.crt, tls.key | platform/harbor/token-tls: gleichnamige Properties |
| harbor-ha | platform-harbor-ingress-tls | tls.crt, tls.key, ca.crt | platform/harbor/ingress-tls: gleichnamige Properties |
| harbor-ha | platform-harbor-postgresql | username, password | platform/postgresql/harbor: username=harbor-ha, password |
| harbor-ha | platform-redis | password | platform/redis/credentials: password |
| harbor-ha | platform-harbor-redis | REDIS_PASSWORD | derselbe Redis-Pfad/Property; keine zwei unabhängig erzeugten Passwörter |
| opensearch | platform-opensearch-admin | password | platform/opensearch/admin: password; für funktionale Admin-Tests |
| opensearch | platform-opensearch-dashboards | username, password | platform/opensearch/dashboards: username, password |
| opensearch | platform-opensearch-security | config.yml, roles.yml, roles_mapping.yml, action_groups.yml, tenants.yml, nodes_dn.yml, allowlist.yml, internal_users.yml | platform/opensearch/security: gleichnamige Properties |
| opensearch | platform-opensearch-tls | tls.crt, tls.key, ca.crt | platform/opensearch/tls: gleichnamige Properties |
| opensearch | platform-opensearch-ca | ca.crt | platform/opensearch/tls: ca.crt; Dashboards mountet nur die öffentliche CA |
| cattle-logging-system | platform-opensearch-logging | username, password, ca.crt | platform/opensearch/logging: gleichnamige Properties |
| external-secrets | openbao-infrastructure-smoke | probe | platform/bootstrap/smoke: probe |

OpenSearch `internal_users.yml` wird mit den bcrypt-Hashes der exakt gleichen
Admin-/Dashboards-Passwörter erzeugt. Demo-Installer ist deaktiviert; der neue leere
Sicherheitsindex wird aus dem vollständigen gemounteten Konfigurationssatz initialisiert
(`plugins.security.allow_default_init_securityindex=true`). Das ist ausschließlich
für einen frischen Datenbestand vorgesehen. Spätere Secret-Änderungen aktualisieren
den existierenden Sicherheitsindex **nicht** automatisch; Security-Admin-Ablauf und
koordinierte Passwortrotation sind dann separat erforderlich. Die automatische
Initialisierung wurde nach erfolgreichem Bootstrap und Index-/Login-Test in einem
Folgecommit deaktiviert.

## Eigentum und Rotation

Die neuen Zielnamen vermeiden Kollisionen mit alten manuellen/Chart-Secrets.
ESO verwendet `creationPolicy: Orphan`, `deletionPolicy: Retain`: beim Entfernen eines
ExternalSecret bleibt das Ziel-Secret erhalten. Nur ESO schreibt dessen Inhalt;
`Orphan` bedeutet nicht, dass andere Controller mitverwalten dürfen.
Neue Namespace-Löschung würde Secrets trotzdem entfernen und ist nicht vorgesehen.

CNPG behält seine eigenen CA-/Server-/Replikations-Secrets; keine ExternalSecrets
für diese Namen. Der neue App-Login kommt von ESO und wird beim initdb benutzt.
Bei behaltenen Daten ändert eine Bootstrap-Secret-Änderung nicht zuverlässig den
SQL-Rollenlogin; deshalb ist ein solcher Mischbetrieb hier ausdrücklich ausgeschlossen.

Harbor erzeugt weiterhin leere Hilfs-Secrets und das abgeleitete Trivy-Secret
`harbor-trivy` (Redis-URL). Das Passwort kommt aus dem ESO-Secret. Chart 1.19.2
nutzt dafür Helm `lookup`: ESO-Secrets müssen **vor dem echten Helm-Install** existieren.
Offline-Rendering kann diesen Runtime-Lookup nicht beweisen. Das abgeleitete Secret
bleibt ausschließlich Chart-eigen; keine zweite ESO-Verwaltung desselben Namens.
Redis-Rotation erfordert einen koordinierten Harbor-Helm-Rollout zur Neuberechnung
der Trivy-URL sowie Neustarts der betroffenen Verbraucher. ESO-Refresh allein reicht nicht.

## Abnahme nach Freigabe

1. Alle sechs Stores Ready, Smoke-ExternalSecret Ready/SecretSynced. Nur Key-Namen und
   Status prüfen, Werte nicht ausgeben. Smoke-Wert bei Bedarf nur intern vergleichen.
2. Positive Login-/TokenReview-Prüfung mit kurzlebigem Token eines passenden SA;
   negative Prüfung mit fremdem SA, falscher Audience und nicht erlaubtem KV-Pfad.
   Tokens ausschließlich über stdin/in Speicher übertragen und anschließend verwerfen.
3. Je ExternalSecret Ready und alle erwarteten Keys vorhanden, bevor Datenservices starten.
4. CNPG-Login, Redis-AUTH/Sentinel, Harbor-Push/Pull/Trivy sowie OpenSearch/Dashboards
   mit den neuen Secrets funktional prüfen. Passwörter aus OpenBao nur im Speicher beziehen.
