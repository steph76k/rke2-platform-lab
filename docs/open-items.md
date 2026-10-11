# Offene Punkte – 11.10.2026

Prioritäten: P1 blockiert gewünschte Funktion/Abnahme, P2 Betriebsverbesserung,
P3 spätere Erweiterung. Aktueller AFI-Stand: [Umsetzung und Abnahme](afi-isolation-validation.md).
Aktueller Ausbau: [Worker-RAM, Monitoring und Argo CD](monitoring-argocd-rollout.md).
Befunde außerhalb des AFI-Umfangs stammen aus der früheren Plattformprüfung und wurden
im Logging-Rollout nicht erneut vollständig geprüft.

| Priorität | Thema | Status | Konkreter nächster Schritt |
| --- | --- | --- | --- |
| P2 | Direkte Cluster-2-Kubeconfig | Teilweise behoben | Nativer administrativer Zugang wurde über SSH geprüft und temporär genutzt; die bisherige lokale Datei separat erneuern. Keine Zugangsdaten in Git |
| P2 | Dashboards Fremdtenant-Fehlerstatus | Offen | HTTPS, OIDC und eigene Index-Patterns funktionieren; erzwungener Fremdtenant-Zugriff liefert derzeit HTTP 500 ohne Daten statt eines klaren 403 |
| P2 | NeuVector-Exporter | Fehlgeschlagen | Bestehenden wiederkehrenden BackOff außerhalb Plattform-Bundles separat diagnostizieren/reparieren |
| P2 | Longhorn-Helm-Status | Fehlgeschlagen | Historischer failed-Release, in dieser Runde nicht erneut geprüft; aktuell 16 angebundene Volumes gesund; Release-/Systemzustand separat bereinigen, ohne Deinstallation/PVC-Löschung |
| P2 | Rancher-Webhook Probe-Timeouts | Fehlgeschlagen | Wiederkehrende Warnungen bei aktuell Ready-Pod; Ressourcen/Latenz gesondert untersuchen |
| P2 | Worker-Ausfallsicherheit | Geplante Wartung geprüft | Beide Worker mit 4 vCPU/16 GB; Datenbank- und Dienstreplikate auf beide verteilt. Kontrollierte Evictions/Redis-Failover geprüft; harter ungeplanter Ausfall bleibt ungetestet |
| P2 | Logging-Persistenz | Aktiv, Cluster-2-Abnahme läuft | Beide Cluster mit 20-GiB-Longhorn-Puffer und persistenten Node-Queues; echter 50-Record-Neustarttest auf Cluster 1 bestanden, Cluster 2 folgt |
| P2 | Logging-Alarme extern zustellen | Offen | Sieben Regeln eingerichtet; für Cluster 2 fehlt noch ein Alertmanager-Empfänger samt Zustelltest |
| P2 | Logging-CRD-Chart-Metadaten | Fehlgeschlagen (Lint) | Offizieller gepinnter Chart v1+type verursacht bekannten Lintfehler. Render und 38 Ressourcen-Schemas bestehen; Runtime-Abnahme erfolgreich; Metadatenfehler bei späterem Chart-Upgrade erneut prüfen |
| P2 | Vollständige GitOps-Reproduktion | Teilweise umgesetzt | Cluster-2-Logging-Operator/CRDs sind jetzt Fleet-verwaltet; Cluster-/Netzwerk-/Longhorn-/OpenBao-Basis und Host-Zeitabgleich bleiben externe Bootstrap-Abhängigkeiten |
| P2 | Konsistente Backups und Restore | Noch nicht getestet | OpenBao, Harbor-DB+Blobs, OpenSearch und Keycloak konsistent sichern; später genehmigte isolierte Restore-Probe mit RPO/RTO |
| P2 | Zertifikatsrotation | Noch nicht getestet | Lab-Zertifikate Harbor/OpenSearch laufen 10.10.2027 ab; koordinierte Rotation/Security-Index-Änderungen planen |
| P2 | Keycloak-Altbindungen / Realm-Schutz | Freigabe erforderlich | Stale G_Admin/G_Developer/G_Viewer-Bindungen und unrestricted-Modus prüfen; keine automatische Neuanlage gleichnamiger Admin-Gruppe. Brute-force-Schutz derzeit aus |
| P2 | Keycloak-Secret-Verwaltung | Freigabe erforderlich | Bootstrap-Admin-/DB-Zugangsdaten liegen als Literal-Env im bestehenden StatefulSet; später kontrolliert in Secret-Verwaltung überführen, ohne ungeprüfte Rotation |
| P3 | Weitere Failover-Tests | Separates Arbeitspaket | Genehmigter Redis-Sentinel-Failover und Datenbankverlagerung im RAM-Wartungsfenster abgeschlossen; zusätzliche Ausfallversuche separat planen |

Der Benutzer hat den Speicherausbau für 180 Tage am 11.10.2026 aus dem Auftrag
genommen. Er ist kein offener Abnahmepunkt mehr. Die bestehende Retention-Policy
bleibt konfiguriert; eine garantierte Vorhaltung von 180 Tagen wird nicht zugesagt.

## Aktuelle Ergänzungen

| Priorität | Thema | Status / nächster Schritt |
| --- | --- | --- |
| P2 | Node-Datenverlust und Queue-Grenzen | Betriebsgrenze | Persistente Positionsdaten, Read_From_Head und Disk-Queues sind aktiv; Host-Datenverlust, Rotation/volle Queues und at-least-once-Duplikate bleiben dokumentierte Grenzen |
| P2 | MinIO-Betriebsgrenzen | Einzelne Instanz, keine HA-/Restore-Abnahme; Daten-PVC Retain auf StatefulSet-Lebenszyklus, StorageClass selbst reclaimPolicy=Delete. PVC nicht zur Neuinstallation löschen |
| P2 | MinIO-Imagepflege | Archivierter Upstream, eigener dokumentierter Build; tatsächliche Scanresultate und Dependency-Korrekturen in minio-lab.md beachten |
| P2 | Terraform-State-Offsite-Sicherung | Offen | Gemeinsamer administrativer MinIO-Remote-State mit SSE-C, Versionierung und nativem Locking aktiv; isolierte Versions-Recovery geprüft. Automatisierte externe Sicherung fehlt noch |
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

AFI-Ergänzung: Harbor-/OpenSearch-OIDC, Mandanten A/B, gemeinsamer MinIO-Verwaltungsstate,
Namespace-basiertes Logrouting und persistente Collector-Puffer sind aktiv. Alle drei
Cluster-2-Control-Plane-Nodes wurden auf vier vCPU/6 GB erweitert; etcd und Ready-Status
sind geprüft. Der frühere CP-2-Zeit-/Zertifikatsfehler ist behoben. Beide Worker besitzen
inzwischen vier vCPU und 16 GB RAM. Monitoring und Argo CD sind installiert, 40/40
Plattform-Bundles Ready und Terraform ohne Drift. Beide Demo-Apps sind über DNS erreichbar;
OIDC-Tenant-Rechte und direkte Netzwerkisolation sind geprüft. Verbleibende Betriebsgrenzen
stehen im oben verlinkten aktuellen Ausbau-Bericht.
