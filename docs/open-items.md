# Offene Punkte – 10.10.2026

Prioritäten: P1 blockiert gewünschte Funktion/Abnahme, P2 Betriebsverbesserung,
P3 spätere Erweiterung. Aktueller AFI-Stand: [Umsetzung und Abnahme](afi-isolation-validation.md).
Befunde außerhalb des AFI-Umfangs stammen aus der früheren Plattformprüfung und wurden
im Logging-Rollout nicht erneut vollständig geprüft.

| Priorität | Thema | Status | Konkreter nächster Schritt |
| --- | --- | --- | --- |
| P1 | 180-Tage-Logkapazität | Offen | Retention-Policy ist aktiv, vorhandene 3 × 10 GiB reichen gemäß Messung nicht; Speicherbudget einschließlich OpenSearch-/Longhorn-Replikation und Reserve erweitern |
| P2 | Direkte Cluster-2-Kubeconfig | Teilweise behoben | Nativer administrativer Zugang wurde über SSH geprüft und temporär genutzt; die bisherige lokale Datei separat erneuern. Keine Zugangsdaten in Git |
| P2 | Dashboards Fremdtenant-Fehlerstatus | Offen | HTTPS, OIDC und eigene Index-Patterns funktionieren; erzwungener Fremdtenant-Zugriff liefert derzeit HTTP 500 ohne Daten statt eines klaren 403 |
| P2 | NeuVector-Exporter | Fehlgeschlagen | Bestehenden wiederkehrenden BackOff außerhalb Plattform-Bundles separat diagnostizieren/reparieren |
| P2 | Longhorn-Helm-Status | Fehlgeschlagen | Historischer failed-Release trotz elf gesunder Plattformvolumes; Release-/Systemzustand separat bereinigen, ohne Deinstallation/PVC-Löschung |
| P2 | Rancher-Webhook Probe-Timeouts | Fehlgeschlagen | Wiederkehrende Warnungen bei aktuell Ready-Pod; Ressourcen/Latenz gesondert untersuchen |
| P2 | Worker-Ausfallsicherheit | Noch nicht getestet | PostgreSQL/OpenSearch auf Worker 2 konzentriert; vom Betreiber akzeptierte Lab-Einschränkung, Kapazität/Verteilung später planen |
| P2 | Logging-Persistenz | Aktiv, Cluster-2-Abnahme läuft | Beide Cluster mit 20-GiB-Longhorn-Puffer und persistenten Node-Queues; echter 50-Record-Neustarttest auf Cluster 1 bestanden, Cluster 2 folgt |
| P2 | Logging-Alarme extern zustellen | Offen | Sieben Regeln eingerichtet; für Cluster 2 fehlt noch ein Alertmanager-Empfänger samt Zustelltest |
| P2 | Logging-CRD-Chart-Metadaten | Fehlgeschlagen (Lint) | Offizieller gepinnter Chart v1+type verursacht bekannten Lintfehler. Render und 38 Ressourcen-Schemas bestehen; Runtime-Abnahme erfolgreich; Metadatenfehler bei späterem Chart-Upgrade erneut prüfen |
| P2 | Vollständige GitOps-Reproduktion | Teilweise umgesetzt | Cluster-2-Logging-Operator/CRDs sind jetzt Fleet-verwaltet; Cluster-/Netzwerk-/Longhorn-/OpenBao-Basis und Host-Zeitabgleich bleiben externe Bootstrap-Abhängigkeiten |
| P2 | Konsistente Backups und Restore | Noch nicht getestet | OpenBao, Harbor-DB+Blobs, OpenSearch und Keycloak konsistent sichern; später genehmigte isolierte Restore-Probe mit RPO/RTO |
| P2 | Zertifikatsrotation | Noch nicht getestet | Lab-Zertifikate Harbor/OpenSearch laufen 10.10.2027 ab; koordinierte Rotation/Security-Index-Änderungen planen |
| P2 | Keycloak-Altbindungen / Realm-Schutz | Freigabe erforderlich | Stale G_Admin/G_Developer/G_Viewer-Bindungen und unrestricted-Modus prüfen; keine automatische Neuanlage gleichnamiger Admin-Gruppe. Brute-force-Schutz derzeit aus |
| P2 | Keycloak-Secret-Verwaltung | Freigabe erforderlich | Bootstrap-Admin-/DB-Zugangsdaten liegen als Literal-Env im bestehenden StatefulSet; später kontrolliert in Secret-Verwaltung überführen, ohne ungeprüfte Rotation |
| P3 | Aktiver Redis-/PostgreSQL-Failover | Freigabe erforderlich | Kein Failover im aktuellen Lauf; Auswirkungen auf Harbor und Wartungsfenster zuerst genehmigen |

## Aktuelle Ergänzungen

| Priorität | Thema | Status / nächster Schritt |
| --- | --- | --- |
| P2 | Node-Datenverlust und Queue-Grenzen | Betriebsgrenze | Persistente Positionsdaten, Read_From_Head und Disk-Queues sind aktiv; Host-Datenverlust, Rotation/volle Queues und at-least-once-Duplikate bleiben dokumentierte Grenzen |
| P2 | MinIO-Betriebsgrenzen | Einzelne Instanz, keine HA-/Restore-Abnahme; Daten-PVC Retain auf StatefulSet-Lebenszyklus, StorageClass selbst reclaimPolicy=Delete. PVC nicht zur Neuinstallation löschen |
| P2 | MinIO-Imagepflege | Archivierter Upstream, eigener dokumentierter Build; tatsächliche Scanresultate und Dependency-Korrekturen in minio-lab.md beachten |
| P2 | Terraform-State-Offsite-Sicherung | Offen | Getrennte MinIO-Remote-States mit SSE-C, Versionierung und nativem Locking aktiv; isolierte Versions-Recovery geprüft. Automatisierte externe Sicherung fehlt noch |
| P2 | Weitere Mandanten-Härtung | Offen | A/B mit Harbor-Gruppen, OpenBao/ESO und Log-Leserollen umgesetzt. Quotas, allgemeine NetworkPolicies, Pod-Security und OpenBao-Benutzer-OIDC sind weitere Arbeitspakete |
| P2 | Dauerhafte Recovery-Ablage | Verifizierte lokale Backups liegen unter /home/tanzu/manifest/backups/platform-rollout-2026-10-10, neue Identität separat unter .local-recovery-keys. Off-host sichern. Alte konfigurierte SOPS-Identität ungültig; ursprünglicher Datenbankdump nicht verifizierbar. Nativer K3s-Token läuft nach zwei Stunden ab |

## Frühere Abnahme und inzwischen ergänzte Umsetzung

Logging-Rolle nach Freigabe erstellt, fünf Logging-/Endpoint-Bundles ausgerollt,
TLS-Transport und sechs eindeutige Testmeldungen inklusive Dashboards nachgewiesen.
Rancher auf berger korrigiert, PKCE-Login und Projektzugriff getestet, lokaler Admin erhalten.
MinIO mit Longhorn/TLS/ESO bereitgestellt und S3-Funktionen geprüft. Mandant A in separatem
Terraform-Repository übernommen, abschließender Plan ohne Änderungen. 28/28 Plattform-
Bundles Ready; ESO 5/5 beziehungsweise 21/21 SecretSynced; OpenSearch green und Harbor healthy.
Frühere Harbor-/PostgreSQL-/Redis-/Sentinel-Prüfungen stehen in platform-validation.md.

Die Folgefreigaben sind erteilt und umgesetzt; ein erneuter Freigabestopp für diese
bereits autorisierten Arbeiten besteht nicht. Nicht angeforderte Failover-/Restore-Tests
und Änderungen bestehender Plattform-Berechtigungen wurden nicht ausgeführt.

AFI-Ergänzung: Harbor-/OpenSearch-OIDC, Mandanten A/B, getrennte MinIO-States,
Namespace-basiertes Logrouting und persistente Collector-Puffer sind aktiv. Alle drei
Cluster-2-Control-Plane-Nodes wurden auf vier vCPU/6 GB erweitert; etcd und Ready-Status
sind geprüft. Der frühere CP-2-Zeit-/Zertifikatsfehler ist behoben. Worker 1 wird nach
Freigabe des persistenten Puffers auf vier vCPU erweitert. Den abschließenden Teststand
und verbleibende Abnahmegrenzen enthält der oben verlinkte AFI-Bericht.
