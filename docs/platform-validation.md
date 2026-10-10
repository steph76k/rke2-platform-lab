# Plattformvalidierung – 10.10.2026

## Abschluss nach Folgefreigabe

Am 10.10.2026 wurden die genehmigten Folgearbeiten umgesetzt: Cluster-1-Logging,
Rancher-OIDC mit berger, MinIO-Lab auf Cluster 2 und Mandant-A-Terraform im separaten
Repository `/home/tanzu/manifest/fleet/rke2-tenants-lab`.

- Fleet: **28/28 Repository-Bundles Ready**; drei zusätzliche Fleet-Agent-Bundles separat.
- Cluster 1: fünf Nodes Ready, zwei ClusterSecretStores Ready, fünf ExternalSecrets SecretSynced.
- Cluster 2: fünf Nodes Ready, sieben ClusterSecretStores Ready, 21 ExternalSecrets SecretSynced.
- Sechs Cluster-1-Testmeldungen mit korrekten Metadaten genau einmal in OpenSearch und
  über Dashboards gefunden; bestehende Cluster-2-Pipeline unverändert.
- OIDC/PKCE-Login erfolgreich; lokale Adminrechte erhalten; Mandant-A-Projektzugriff
  erlaubt und fremder Projektzugriff verweigert.
- MinIO: 1/1 Ready, 20 GiB Longhorn-PVC Bound, TLS-S3 und Konsole; eigener S3-Test erfolgreich.
- Terraform: bestehende Mandant-A-Ressourcen importiert, finales Plan-Ergebnis No changes;
  neuer Mandant mit 16 Creates geplant, nicht angelegt.
- OpenSearch weiterhin green; Harbor meldet alle acht Komponenten healthy.

Details: [Logging](logging-validation.md), [OIDC](keycloak-rancher-integration.md),
[MinIO](minio-lab.md), [offene Punkte](open-items.md),
[Rollout-Evidenz](evidence/platform-rollout-2026-10-10.json).
Die ursprüngliche Prüfung unten bleibt als zeitlich abgegrenzter Nachweis erhalten.
Ihre Angaben zu fehlenden Freigaben und noch nicht installierten Folgekomponenten
beschreiben ausschließlich den Zustand **vor** der späteren Umsetzung.

## Ursprünglicher Audit vor Folgefreigabe

Prüfung ab 16:54 UTC gegen den laufenden Bestand, ohne Failover oder Rebuild.
Ausgangscommit: `38fda7680dfdb3310e40aac9886c6aeeb5aba811`.
Statusbegriffe: **Erfolgreich getestet**, **Fehlgeschlagen**, **Noch nicht getestet**,
**Freigabe erforderlich**. Frühere Migrationstests ersetzen diese Prüfung nicht.
Sanitisierte technische Nachweise: [JSON-Inventar](evidence/platform-validation-2026-10-10.json).

## Ergebnis

| Prüfung | Status | Tatsächlicher Nachweis / Grenze |
| --- | --- | --- |
| Clusterzugriff | Erfolgreich getestet | Management 1/1, Application 5/5, Infrastructure 5/5 Nodes Ready |
| Direkte Cluster-2-Kubeconfig | Fehlgeschlagen | `/home/tanzu/.kube/rke2-cluster2.yaml` erhält Unauthorized; Prüfung stattdessen über bestehenden Rancher-Proxy `/k8s/clusters/c-44q9v` |
| Fleet | Erfolgreich getestet | Ein GitRepo `fleet-default/rke2-platform`, 20/20 Repository-Bundles; mit drei Fleet-Agent-Bundles insgesamt 23/23 BundleDeployments Ready |
| Target-Cluster | Erfolgreich getestet | `environment=lab`; 18 aktive Infrastruktur-Bundles ausschließlich `role=infrastructure`; ESO-App ausschließlich `role=applications`; Bootstrap auf Cluster 2 |
| Controller | Erfolgreich getestet | Keine Error/Reconciler-error-Zeilen in geprüftem 30-Minuten-Fenster bei Fleet-Controller, Fleet-Agent Cluster 2, ESO beider Cluster, CNPG, Logging-Operator und Fluentd; dies ist ein zeitlich begrenzter Nachweis |
| ESO Cluster 1 | Erfolgreich getestet | Drei Deployments Ready; ein ClusterSecretStore und ein SecretStore Ready; vier ExternalSecrets Ready/SecretSynced |
| ESO Cluster 2 | Erfolgreich getestet | Drei Deployments Ready; sechs ClusterSecretStores Ready; 18 ExternalSecrets Ready/SecretSynced |
| OpenBao | Erfolgreich getestet | HTTPS/CA-Prüfung aktiv, Health HTTP 200, initialisiert/unsealed, Version 2.7.0; SA-Logins für Cluster-2-Logging und Cluster-1-Mandant-A jeweils 200, eigene KV-Pfade jeweils 200, Harbor-KV mit Logging-Token 403; eigene Testtokens widerrufen |
| Cluster-1-Logging-Authentifizierung | Freigabe erforderlich | Root-Mount `rke2-cluster1` enthält nur `eso-demo`; die benötigte Rolle `eso-logging` fehlt. Mandant-A-Store gehört zum separaten OpenBao-Namespace `mandant-a` |
| Harbor Web/API/Auth | Erfolgreich getestet | API-Login als vorhandener Administrator über verifiziertes TLS; alle acht Health-Komponenten healthy; Portal über öffentliche HTTPS-Route geprüft |
| Harbor Push/Pull/Storage | Erfolgreich getestet | Neues privates Projekt `codex-validation-20261010-1705`, Repository `alpine`, Tag `migration`; echte Blob-/Manifestübertragung und Digestvergleich |
| Trivy | Erfolgreich getestet | Scanstatus Pending → Success für das hochgeladene Alpine-3.20-Image |
| Harbor Cleanup | Erfolgreich getestet | Eigenes Artefakt entfernt; Projektlöschung zunächst 412 wegen leerem Repository; nur dieses leere Repository und danach eigenes Projekt erfolgreich entfernt |
| CNPG/PostgreSQL | Erfolgreich getestet | 3/3 Ready, Primary `harbor-ha-db-2`; db-1/db-3 im Recovery mit WAL-Receiver streaming; Primary sieht beide Standbys streaming/async; App-Login `harbor-ha`, TLSv1.3 |
| Harbor → PostgreSQL | Erfolgreich getestet | Aktive SQL-Sitzungen von beiden Harbor-Core-Pod-IP-Adressen; Harbor database health healthy |
| Redis | Erfolgreich getestet | Alle drei Instanzen PONG; Master `redis-replication-2` / `10.42.5.183`; Replikas 0 und 1 online, master_link_status=up |
| Sentinel | Erfolgreich getestet | Alle drei `redis-replication-s-*` stimmen über Master/2 Replikas überein; Quorum 2; dreimal CKQUORUM: 3 usable Sentinels. Ohne AUTH erwartungsgemäß NOAUTH |
| Harbor → Redis | Erfolgreich getestet | Authentifizierte aktive Redis-Verbindungen beider Core-Pods; weitere Jobservice/Registry/Trivy-Clients; Harbor redis health healthy |
| OpenSearch | Erfolgreich getestet | Drei Nodes, green, 16/16 Shards STARTED, keine unassigned/relocating Shards; Indexabfragen über CA-verifiziertes HTTPS und Admin-Authentifizierung |
| Dashboards | Erfolgreich getestet | Öffentliche HTTP-Route 200; Login, Sitzung und Suche mit sechs eigenen Testlogs über lokalen Kubernetes-TLS-Tunnel 200 |
| Dashboards Discover | Noch nicht getestet | Keine gespeicherten Index Patterns vorhanden; Suche wurde über Dashboards Dev-Tools-API geprüft, kein visueller Browsertest. Öffentlicher Ingress weiterhin HTTP |
| Ingestion Cluster 2 | Erfolgreich getestet | Sechs eindeutige Meldungen auf beiden Workern genau einmal gefunden, einschließlich Metadaten; [Logging-Bericht](logging-validation.md) |
| Ingestion Cluster 1 | Noch nicht getestet | Neue Fleet-Konfiguration vorbereitet, wegen fehlender OpenBao-Freigabe noch nicht aktiviert |
| Plattform-Storage | Erfolgreich getestet | Alle elf PVCs in harbor-ha/opensearch Bound; zugehörige Longhorn-Volumes healthy/attached, jeweils zwei Replikate |
| Secret-Prüfung Git | Erfolgreich getestet | Kein Treffer aktueller Plattform-Secrets im Arbeitsbaum oder in 140 erreichbaren Git-History-Blobs; keine befüllten Kubernetes-Secret-Manifeste/Private-Key-Blöcke. Kein Vollständigkeitsbeweis gegen unbekannte historische Secrets |
| Failover / vollständiger Restore | Noch nicht getestet | Im aktuellen Auftrag keine Freigabe; bewusst nicht ausgelöst |

Harbor-Testmanifest: `sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e`.
OpenSearch-Serverzertifikat gültig bis `2027-10-10 11:06:27 UTC`, Harbor bis
`2027-10-10 11:06:29 UTC`. Keine Abschaltung der TLS-Verifikation.

## Vollständiger Fleet-Bestand

| Bundle | Ziel | Ergebnis |
| --- | --- | --- |
| `fleet-agent-c-44q9v` | Cluster 2 | Ready 1/1 |
| `fleet-agent-rke2-cluster1` | Cluster 1 | Ready 1/1 |
| `lab-app-external-secrets` | Cluster 1 | Ready 1/1 |
| `lab-bootstrap-test` | Cluster 2 | Ready 1/1 |
| `lab-infra-cnpg` | Cluster 2 | Ready 1/1 |
| `lab-infra-external-secrets` | Cluster 2 | Ready 1/1 |
| `lab-infra-harbor` | Cluster 2 | Ready 1/1 |
| `lab-infra-harbor-postgres` | Cluster 2 | Ready 1/1 |
| `lab-infra-harbor-secrets` | Cluster 2 | Ready 1/1 |
| `lab-infra-harbor-storage` | Cluster 2 | Ready 1/1 |
| `lab-infra-logging-secrets` | Cluster 2 | Ready 1/1 |
| `lab-infra-opensearch` | Cluster 2 | Ready 1/1 |
| `lab-infra-opensearch-dashboards` | Cluster 2 | Ready 1/1 |
| `lab-infra-opensearch-logging` | Cluster 2 | Ready 1/1 |
| `lab-infra-opensearch-secrets` | Cluster 2 | Ready 1/1 |
| `lab-infra-postgresql-secrets` | Cluster 2 | Ready 1/1 |
| `lab-infra-redis-operator` | Cluster 2 | Ready 1/1 |
| `lab-infra-redis-replication` | Cluster 2 | Ready 1/1 |
| `lab-infra-redis-secrets` | Cluster 2 | Ready 1/1 |
| `lab-infra-secret-smoke-test` | Cluster 2 | Ready 1/1 |
| `lab-infra-secret-stores` | Cluster 2 | Ready 1/1 |
| `lab-infra-storage-class` | Cluster 2 | Ready 1/1 |
| `fleet-agent-local` | local | Ready 1/1 |

Die Clusterübersicht zählt einschließlich Agent: Cluster 2 20/20, Cluster 1 2/2,
Management 1/1. Diese Zahlen sind keine Aussage über alle nicht von Fleet verwalteten Apps.
Die vier neuen App-Logging-Bundles und `lab-infra-opensearch-ingest` sind vorbereitet,
aber nicht in den aktiven GitRepo-Pfaden enthalten und daher keine Ready-Bundles.

## Chart-Versionen und bestehende Störungen

Aktive Plattform-Charts: ESO 2.11.0, CNPG 0.29.1, Redis Operator 0.27.0,
Redis Replication 0.17.1, Harbor 1.19.2, OpenSearch und Dashboards 3.9.0.
Rancher Logging und CRDs auf Cluster 2: 109.0.1+up4.10.0-rancher.24,
Logging-Release Revision 5. Alle diese Releases deployed.

Longhorn-Release `109.4.0+up1.12.1` besitzt weiterhin den historischen Status failed.
Die elf genutzten Plattformvolumes sind trotzdem healthy. Drei alte, ungenutzte
Volumes im Namespace default sind detached/unknown; nicht gelöscht oder verändert.
NeuVector-Prometheus-Exporter ist CrashLoop/BackOff (wiederkehrendes Warning).
Rancher-Webhook hat wiederkehrende Probe-Timeouts, war beim Inventar Ready.
Diese Systemkomponenten sind nicht Teil der geprüften Plattform-Fleet-Bundles.

## GitOps-Reproduzierbarkeit

**Teilweise reproduzierbar; kein vollständig autonomer Wiederaufbau allein aus Git.**

| Bereich | Bewertung / notwendige Voraussetzung |
| --- | --- |
| Gepinnte Charts und Values | Für die 18 aktiven Infrastruktur-Bundles vorhanden; sieben Charts offline gerendert und gegen API-/CRD-Schemas geprüft |
| Abhängigkeiten | DAG für ESO → Stores → Secrets, CNPG/Redis-Operator → Datenservices, Storage → PostgreSQL/Harbor, OpenSearch → Dashboards/Logging vorhanden; keine Zyklen |
| Readiness-Grenze | Fleet Ready ersetzt keine funktionale Secret-/DB-Prüfung. Vor Helm-Verbrauch müssen ESO-Zielsecrets existieren; Harbor verwendet Helm lookup für Trivy. Neue Logging-Bootstrap-Stufen haben explizite externe Wartepunkte |
| Namespaces | Fleet defaultNamespace legt Zielnamespace an; ServiceAccounts der Logging-Secrets nutzen den bereits durch ESO angelegten Namespace external-secrets |
| CRDs/Operatoren | ESO/CNPG/Redis über Charts; bestehendes Rancher Logging samt CRDs auf Cluster 2 außerhalb Fleet. Neue Cluster-1-CRDs/Operator separat vorbereitet |
| Secrets | Git enthält Referenzen, keine Wiederherstellung der Secret-Werte. OpenBao-Daten, Unseal-Material, Auth-Mounts, Policies und Rollen müssen gesichert/importiert sein |
| Storage | Git definiert longhorn-platform/PVCs, nicht Longhorn-Installation, Disks, Backups oder vorhandene Nutzdaten; Scheduling auf Worker 2 bleibt akzeptierte Lab-Einschränkung |
| Netzwerk | DNS, Ingress-/Cilium-Basis, LoadBalancer-Pool und Clusterimport liegen außerhalb dieser Bundles; neue geplante Logging-Verbindung benötigt freien VIP 192.168.1.196 und die fünf dokumentierten Node-Quelladressen |
| OpenSearch-Neuaufbau | Leerer Security-Index benötigt kontrollierte einmalige Initialisierung; aktueller Sollstand deaktiviert Auto-Initialisierung. Secret-Rotation verändert bestehende Security-Index-Passwörter nicht automatisch |
| PostgreSQL/Harbor | Bootstrap-Secrets müssen zu erhaltenen Daten passen; Registry-Blobs, PostgreSQL-Daten und Secrets konsistent wiederherstellen. Git-Revert ist kein Daten-Restore |
| GitRepo-Bootstrap | fleet/gitrepo.yaml ist kein selbstverwaltetes Bundle und braucht gezieltes Apply auf Rancher nach geprüftem Push |
| Recovery | Verfahren in secrets.md/migration-plan.md vorhanden; vollständige konsistente Backups, RPO/RTO und Restore-Probe weiterhin offen. Kein Recovery-Test ausgeführt |

Lokale Prüfung: `scripts/validate.py` prüft einschließlich des inaktiven neuen
Endpoint-Bundles 19 Infrastruktur-Bundles, sieben Charts und 152 Ressourcen.
Drei vorhandene Bootstrap-Tests erfolgreich. Neue Logging-Prüfung und bekannte
Upstream-Chart-Lint-Einschränkung stehen im [Logging-Bericht](logging-validation.md).

## Commit-Nachweise der freigegebenen Umsetzung

| Commit | Änderung |
| --- | --- |
| c9426c3 | Cluster-1-CRDs/ESO und Cross-Cluster-Endpoint aktiviert |
| edc731c | Cluster-1-Operator und TLS-OpenSearch-Ausgang aktiviert |
| 588181a | Begrenztes Flush-Intervall für den neuen Ausgang |
| 451cdb2 | MinIO/ESO/Harbor-CA auf Cluster 2 und gebündelte Log-Pufferung |
| 750f707 | Eigentümerzuordnung des neuen MinIO-Namespace |
| a1a8640 | MinIO-Abhängigkeiten korrigiert; Scan ohne Critical/High; Build-Rezept |
| 7a64cb2 (Tenant-Repo) | Mandantenmodul und Import Mandant A |
| f00df90 (Tenant-Repo) | Verifizierte State-Sicherung dokumentiert |

Der abschließende Dokumentations-Commit verändert keine aktiven Fleet-Bundle-Dateien.
Das Tenant-Repository wurde zunächst nur lokal committet. Anschließend wurden Dateien,
lokaler State und beide Commits in das vorhandene Repository unter
`/home/tanzu/manifest/fleet/rke2-tenants-lab` übernommen; dessen Remote ist
`git@github.com:steph76k/rke2-tenants-lab.git`. Der State bleibt von Git ausgeschlossen.

Bekannte aktuelle Plattform-Zugangsdaten mit mindestens zwölf Zeichen wurden in
Klartext-/Base64-Darstellung gegen die Dateien beider Arbeitsbäume geprüft: keine
Treffer. Kurze allgemeine Zeichenfolgen sind aus diesem Substring-Test ausgeschlossen;
der Test ist kein vollständiger Secret-Scanner. Provider-Anmeldedaten werden über
Umgebungsvariablen verwendet, State/Pläne/Recovery-Schlüssel sind nicht in Git.
