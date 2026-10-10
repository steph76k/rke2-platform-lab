# Offene Punkte – 10.10.2026

Prioritäten: P1 blockiert gewünschte Funktion/Abnahme, P2 Betriebsverbesserung,
P3 spätere Erweiterung. Alle Ergebnisse beziehen sich auf den aktuellen Lauf.

| Priorität | Thema | Status | Konkreter nächster Schritt |
| --- | --- | --- | --- |
| P1 | Cluster-1-Logging nicht ausgerollt | Freigabe erforderlich | Ausschließlich neue OpenBao-Rolle auth/rke2-cluster1/role/eso-logging aus vorhandener JSON-Datei erlauben; bestehende Policy unverändert verwenden |
| P1 | Clusterübergreifender Logtransport | Noch nicht getestet | Nach Rollenfreigabe gestufter Fleet-Rollout der fünf vorbereiteten Bundles; VIP 192.168.1.196 erneut prüfen, TLS/SNAT/Quelladressbegrenzung testen |
| P1 | Cluster-1-Ingestion/Metadaten/Duplikate | Noch nicht getestet | Nach Deployment je Worker eigene nummerierte Marker, OpenSearch und Dashboards, erneute Zählung nach Pufferintervallen; nur Test-Pods entfernen |
| P1 | Aktives Rancher-OIDC zeigt auf gelöschten Realm | Fehlgeschlagen | myrealm Discovery 404; im Realm berger fehlt Client rancher. Separat freizugebenden Reparaturplan in keycloak-rancher-integration.md ausführen |
| P1 | Sicherer Notfallzugang | Noch nicht getestet | Frischen lokalen Admin-Passwortlogin und direkten nativen K3s-Adminzugang vor OIDC-Änderung nachweisen; Konfiguration/Binding existieren |
| P1 | Log-Mandantentrennung | Freigabe erforderlich | Tenant-Index-/Leserechtemodell, vertrauenswürdige Namespace-Zuordnung und negative Zugriffstests beschließen; aktuelle gemeinsame Logging-Identität hat crud auf kubernetes-* |
| P2 | Direkte Cluster-2-Kubeconfig | Fehlgeschlagen | Bestehende Datei liefert Unauthorized. Rancher-Proxy funktioniert; separat native kubeconfig erneuern, ohne Token in Git |
| P2 | Dashboards HTTP / fehlende Index Patterns | Freigabe erforderlich | Öffentliche HTTPS-Route und dauerhaftes Discover-Index-Pattern festlegen. Aktueller Login/Suche ausschließlich geschützt getunnelt; keine gespeicherten Ansichten verändert |
| P2 | NeuVector-Exporter | Fehlgeschlagen | Bestehenden wiederkehrenden BackOff außerhalb Plattform-Bundles separat diagnostizieren/reparieren |
| P2 | Longhorn-Helm-Status | Fehlgeschlagen | Historischer failed-Release trotz elf gesunder Plattformvolumes; Release-/Systemzustand separat bereinigen, ohne Deinstallation/PVC-Löschung |
| P2 | Rancher-Webhook Probe-Timeouts | Fehlgeschlagen | Wiederkehrende Warnungen bei aktuell Ready-Pod; Ressourcen/Latenz gesondert untersuchen |
| P2 | Worker-Ausfallsicherheit | Noch nicht getestet | PostgreSQL/OpenSearch auf Worker 2 konzentriert; vom Betreiber akzeptierte Lab-Einschränkung, Kapazität/Verteilung später planen |
| P2 | Persistente Logging-Puffer | Freigabe erforderlich | Root-Fluentd flüchtig wie bisher, keine Zusage bei Podverlust. Persistenz/Positionsdaten/Retention separat entwerfen |
| P2 | Cluster-2-Cluster-Metadatum | Freigabe erforderlich | Bestehende Pipeline enthält host, aber kein explizites cluster_name; Zusatzfeld nur in abgestimmter Änderung ergänzen |
| P2 | Logging-CRD-Chart-Metadaten | Fehlgeschlagen (Lint) | Offizieller gepinnter Chart v1+type verursacht bekannten Lintfehler. Render und 38 Ressourcen-Schemas bestehen; vor Rollout Runtime-Abnahme verlangen |
| P2 | Vollständige GitOps-Reproduktion | Noch nicht getestet | Cluster-/Netzwerk-/Longhorn-/OpenBao-Basis und Cluster-2-Logging-Systeminstallation als externe Bootstrap-Abhängigkeiten schließen |
| P2 | Konsistente Backups und Restore | Noch nicht getestet | OpenBao, Harbor-DB+Blobs, OpenSearch und Keycloak konsistent sichern; später genehmigte isolierte Restore-Probe mit RPO/RTO |
| P2 | Zertifikatsrotation | Noch nicht getestet | Lab-Zertifikate Harbor/OpenSearch laufen 10.10.2027 ab; koordinierte Rotation/Security-Index-Änderungen planen |
| P2 | Keycloak-Altbindungen / Realm-Schutz | Freigabe erforderlich | Stale G_Admin/G_Developer/G_Viewer-Bindungen und unrestricted-Modus prüfen; keine automatische Neuanlage gleichnamiger Admin-Gruppe. Brute-force-Schutz derzeit aus |
| P2 | Keycloak-Secret-Verwaltung | Freigabe erforderlich | Bootstrap-Admin-/DB-Zugangsdaten liegen als Literal-Env im bestehenden StatefulSet; später kontrolliert in Secret-Verwaltung überführen, ohne ungeprüfte Rotation |
| P3 | Terraform-Mandanten | Freigabe erforderlich | Bestehende Gruppen/Projekte importieren, Provider pinnen, State schützen, Plan prüfen; kein Apply erfolgt |
| P3 | MinIO | Freigabe erforderlich | Separate Folgephase; in diesem Lauf weder installiert noch konfiguriert. Bereits vorhandenes loki-minio auf Cluster 1 wurde nicht verändert |
| P3 | Aktiver Redis-/PostgreSQL-Failover | Freigabe erforderlich | Kein Failover im aktuellen Lauf; Auswirkungen auf Harbor und Wartungsfenster zuerst genehmigen |

## Erledigte Prüfungen

Fleet 20/20 Repository-Bundles und 23/23 einschließlich Agenten Ready.
Harbor TLS/Auth/Push/Pull/Trivy und Cleanup erfolgreich. PostgreSQL TLS/App-Login
und Streaming-Replikation, Redis/Sentinel-Quorum, OpenSearch green sowie elf
Longhorn-Plattformvolumes geprüft. ESO 4/4 und 18/18 SecretSynced; OpenBao-Login
und erlaubter/verbotener KV-Zugriff geprüft. Cluster-2-Testlogs exakt einmal in
OpenSearch und über Dashboards gefunden. Keine aktuellen Plattform-Secrets in
Arbeitsbaum oder erreichbarer Git-Historie gefunden; Scan-Grenzen im Prüfbericht.

## Rollout- und Push-Grenze

Die neuen Logging-Verzeichnisse sind **nicht** in fleet/gitrepo.yaml aufgenommen.
Der Dokumentations-/Vorbereitungs-Push ändert keinen aktiven Bundle-Pfad und löst
keine Änderung bestehender Deployments aus. Die geplanten Pfade sind ausschließlich
in config/rancher-logging/cluster1-paths-patch.yaml aufgeführt. Kein GitRepo-Apply,
keine OpenBao-Rollenänderung und kein Auth-Wechsel in diesem Stand.

Nach Freigabe der Logging-Rolle zuerst Aufgabe A abschließen. Danach ausdrücklich
über die Rancher-Keycloak-Reparatur und die anschließenden Phasen MinIO/Terraform
entscheiden lassen. Diese Folgephasen bleiben bis zur Zustimmung gestoppt.
