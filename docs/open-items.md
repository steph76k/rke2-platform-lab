# Offene Punkte – 10.10.2026

Prioritäten: P1 blockiert gewünschte Funktion/Abnahme, P2 Betriebsverbesserung,
P3 spätere Erweiterung. Alle Ergebnisse beziehen sich auf den aktuellen Lauf.

| Priorität | Thema | Status | Konkreter nächster Schritt |
| --- | --- | --- | --- |
| P1 | Log-Mandantentrennung | Freigabe erforderlich | Tenant-Index-/Leserechtemodell, vertrauenswürdige Namespace-Zuordnung und negative Zugriffstests beschließen; aktuelle gemeinsame Logging-Identität hat crud auf kubernetes-* |
| P2 | Direkte Cluster-2-Kubeconfig | Fehlgeschlagen | Bestehende Datei liefert Unauthorized. Rancher-Proxy funktioniert; separat native kubeconfig erneuern, ohne Token in Git |
| P2 | Dashboards HTTP / fehlende Index Patterns | Freigabe erforderlich | Öffentliche HTTPS-Route und dauerhaftes Discover-Index-Pattern festlegen. Aktueller Login/Suche ausschließlich geschützt getunnelt; keine gespeicherten Ansichten verändert |
| P2 | NeuVector-Exporter | Fehlgeschlagen | Bestehenden wiederkehrenden BackOff außerhalb Plattform-Bundles separat diagnostizieren/reparieren |
| P2 | Longhorn-Helm-Status | Fehlgeschlagen | Historischer failed-Release trotz elf gesunder Plattformvolumes; Release-/Systemzustand separat bereinigen, ohne Deinstallation/PVC-Löschung |
| P2 | Rancher-Webhook Probe-Timeouts | Fehlgeschlagen | Wiederkehrende Warnungen bei aktuell Ready-Pod; Ressourcen/Latenz gesondert untersuchen |
| P2 | Worker-Ausfallsicherheit | Noch nicht getestet | PostgreSQL/OpenSearch auf Worker 2 konzentriert; vom Betreiber akzeptierte Lab-Einschränkung, Kapazität/Verteilung später planen |
| P2 | Persistente Logging-Puffer | Freigabe erforderlich | Root-Fluentd flüchtig wie bisher, keine Zusage bei Podverlust. Persistenz/Positionsdaten/Retention separat entwerfen |
| P2 | Cluster-2-Cluster-Metadatum | Freigabe erforderlich | Bestehende Pipeline enthält host, aber kein explizites cluster_name; Zusatzfeld nur in abgestimmter Änderung ergänzen |
| P2 | Logging-CRD-Chart-Metadaten | Fehlgeschlagen (Lint) | Offizieller gepinnter Chart v1+type verursacht bekannten Lintfehler. Render und 38 Ressourcen-Schemas bestehen; Runtime-Abnahme erfolgreich; Metadatenfehler bei späterem Chart-Upgrade erneut prüfen |
| P2 | Vollständige GitOps-Reproduktion | Noch nicht getestet | Cluster-/Netzwerk-/Longhorn-/OpenBao-Basis und Cluster-2-Logging-Systeminstallation als externe Bootstrap-Abhängigkeiten schließen |
| P2 | Konsistente Backups und Restore | Noch nicht getestet | OpenBao, Harbor-DB+Blobs, OpenSearch und Keycloak konsistent sichern; später genehmigte isolierte Restore-Probe mit RPO/RTO |
| P2 | Zertifikatsrotation | Noch nicht getestet | Lab-Zertifikate Harbor/OpenSearch laufen 10.10.2027 ab; koordinierte Rotation/Security-Index-Änderungen planen |
| P2 | Keycloak-Altbindungen / Realm-Schutz | Freigabe erforderlich | Stale G_Admin/G_Developer/G_Viewer-Bindungen und unrestricted-Modus prüfen; keine automatische Neuanlage gleichnamiger Admin-Gruppe. Brute-force-Schutz derzeit aus |
| P2 | Keycloak-Secret-Verwaltung | Freigabe erforderlich | Bootstrap-Admin-/DB-Zugangsdaten liegen als Literal-Env im bestehenden StatefulSet; später kontrolliert in Secret-Verwaltung überführen, ohne ungeprüfte Rotation |
| P3 | Aktiver Redis-/PostgreSQL-Failover | Freigabe erforderlich | Kein Failover im aktuellen Lauf; Auswirkungen auf Harbor und Wartungsfenster zuerst genehmigen |

## Aktuelle Ergänzungen

| Priorität | Thema | Status / nächster Schritt |
| --- | --- | --- |
| P2 | Frühe Startlogs / Positionsdaten | Collector liest neu entdeckte Dateien ab Ende; frühe Meldungen kurzlebiger Pods können fehlen. Persistente Positionsdaten und Read_From_Head zusammen umsetzen und gegen Duplikate nach Neustarts testen |
| P2 | MinIO-Betriebsgrenzen | Einzelne Instanz, keine HA-/Restore-Abnahme; Daten-PVC Retain auf StatefulSet-Lebenszyklus, StorageClass selbst reclaimPolicy=Delete. PVC nicht zur Neuinstallation löschen |
| P2 | MinIO-Imagepflege | Archivierter Upstream, eigener dokumentierter Build; tatsächliche Scanresultate und Dependency-Korrekturen in minio-lab.md beachten |
| P2 | Terraform-State | Geschützter lokaler State, kein Remote konfiguriert; vor Team-/CI-Nutzung verschlüsseltes Backend mit Locking und eingeschränkten Servicekonten einrichten |
| P2 | Terraform-Mandantenumfang | Grundstruktur/ESO und Rancher-Rechte umgesetzt; Harbor-OIDC/Berechtigungen, OpenBao-Benutzer-OIDC für neue Mandanten, Quotas/NetworkPolicies und Log-Leserollen fehlen noch |
| P2 | Dauerhafte Recovery-Ablage | Verifizierte lokale Backups liegen unter /home/tanzu/manifest/backups/platform-rollout-2026-10-10, neue Identität separat unter .local-recovery-keys. Off-host sichern. Alte konfigurierte SOPS-Identität ungültig; ursprünglicher Datenbankdump nicht verifizierbar. Nativer K3s-Token läuft nach zwei Stunden ab |

## Erledigt

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
