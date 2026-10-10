# Migrationsplan – vollständiger Lab-Neuaufbau

**Phase 1–4 sind Vorbereitung. Phase 5 benötigt eine neue ausdrückliche Freigabe.**
Die Nutzerentscheidung lautet: frische Daten nach gesonderter Löschfreigabe.
Dieser Commit erweitert keine aktiven Fleet-Pfade und startet keine Migration.

## Sperren vor Phase 5

1. Longhorn-Release failed und mehrere Daten-Volumes degraded: Ursache und gewünschte
   Redundanz klären. Zwei Storage-Nodes versus Standard drei Replikas ist ein bekannter
   Kapazitäts-/Platzierungsprüfpunkt. Keine StorageClass-/Replikazahländerung ohne Auftrag.
2. Wiederherstellbare Backups/Exports, auch wenn der Sollzustand frische Daten vorsieht:
   PostgreSQL, Harbor-Registry plus DB als konsistentes Paar, Redis, OpenSearch-Snapshot,
   alte Helm-Values/Release-Manifeste und benötigte Alt-Secrets in geschütztem Speicher.
   Keine Secret-Backups in Git oder Chat; Restore-Probe vor Löschung.
3. OpenBao-PebbleDB benötigt einen konsistenten, für diesen Backendtyp geeigneten Backup-
   Ablauf; kein ungeprüftes `bao operator raft snapshot` für diesen Nicht-Raft-Server.
4. Frische OpenSearch-Konfiguration/Certs und Harbor-CA-Vertrauen sind Änderungen
   gegenüber dem Istzustand. TLS-Vertrauen auf Harbor-Clients und Anmeldefunktion testen.
5. Auswirkungen auf Rancher Logging klären: dessen vorhandene Outputs und Puffer nutzen
   die bisherige OpenSearch-Installation. Während des Neuaufbaus Logs puffern/Verluste
   akzeptieren lassen; nachher Zielkonto/Berechtigungen und Lieferfähigkeit prüfen.
   Logging-Systemressourcen werden nicht nebenbei umgeschrieben.

## Reihenfolge und Abhängigkeiten

Jedes neue Bundle hat einen expliziten `lab-infra-*` Namen. `dependsOn.name` referenziert
diesen Namen, nicht den Helm-Release. Unterstützung wurde am Live-Bundle-CRD und
Fleet-0.15.4-Quellcode geprüft. Nur Ready erfüllt die Abhängigkeit.

| Stufe | Bundle / Pfad unter bundles/infrastructure | Release | Bedingung |
| --- | --- | --- | --- |
| 1 | operators/external-secrets | external-secrets | nach Umsetzungsfreigabe; drei Deployments Ready |
| 2 | secrets/stores | lab-infra-secret-stores | ESO-CRDs etabliert; SAs/RBAC angelegt |
| 3 | OpenBao Auth-/KV-Bootstrap außerhalb Fleet | — | docs/secrets.md; gesonderter autorisierter Admin-Schritt |
| 4 | secrets/smoke-test | lab-infra-secret-smoke-test | alle Stores Ready, danach TokenReview-/ESO-Test |
| 5 | secrets/platform/{harbor,postgresql,redis,opensearch} | lab-infra-*-secrets | sämtliche neuen Ziel-Secrets Ready/Keys vorhanden |
| 6 | kontrollierte Alt-Deinstallation und freigegebene Datenlöschung | alte Releases | unten stehende Freigabeliste bestätigt |
| 7 | operators/cnpg, operators/redis-operator | cnpg, redis-operator | alte Helm-Owner entfernt; CRDs behalten/kompatibel |
| 8 | data-services/harbor-postgres | lab-infra-harbor-postgres | CNPG + PostgreSQL-Secrets; leerer Datenbestand |
| 8 | data-services/redis-replication | redis-replication | Redis-Operator + Redis-Secrets |
| 8 | data-services/harbor-storage | lab-infra-harbor-storage | neue Registry-PVC; Storage Ready |
| 9 | applications/harbor | harbor | CNPG 3/3, Redis/Sentinel je 3/3, RWX Bound, Secrets Ready |
| 9 | applications/opensearch | opensearch | freigegeben leere PVCs, Security-/TLS-Secrets Ready |
| 10 | applications/opensearch-dashboards | opensearch-dashboards | OpenSearch stabil und Security-Index initialisiert |

Stufen 1–5 sind additives Bootstrap ohne Ersatz alter Anwendungs-Secrets. Stufe 6 ist
ein eigener destruktiver Eingriff. Operators/Redis/CNPG/Apps dürfen nicht vorzeitig
aktiviert werden, solange die gleichnamigen manuellen Helm-Releases existieren.

Für jede freigegebene Stufe nur die einzelnen Verzeichnispfade in
`fleet/gitrepo.yaml` ergänzen, Review/Commit/Push durchführen und anschließend die
Live-GitRepo-Ressource ausdrücklich aktualisieren. Die Datei selbst ist heute kein
aktives Bundle und verändert die Live-GitRepo-Pfade nicht durch Push allein.
Nie pauschal `bundles` oder `bundles/infrastructure` aktivieren.

Fleet-Ready ist zusätzlich durch fachliche Checks zu ergänzen: insbesondere Redis-CR-
Readiness, Kind-spezifische Bedingungen, echte Secret-Keys und CNPG-Instanzen prüfen.
Keine Annahme, dass die bloße Existenz eines CR alle operatorgenerierten Pods bestätigt.
Helm `takeOwnership` und `force` werden nicht benutzt.

## Kontrollierte Deinstallation (nicht ausgeführt)

Zuerst Reconciliation der umzubauenden Komponenten ausschließen: neue Pfade bleiben
inaktiv, keine andere Fleet-/Argo-/Flux-/Terraform-Übernahme. Alle Befehle mit
`--kube-context=rke2-cluster2` bzw. `--context=rke2-cluster2`; niemals Kontext implizit wechseln.

1. Wartungsfenster; Harbor-Pushes/Jobs und externe Schreiber stoppen. Logging-Abhängigkeit
   klären, Snapshots/Restore-Nachweise und Alt-Secret-Sicherung prüfen.
2. Dashboards und Harbor zuerst deinstallieren. Beispiel **nur nach Freigabe**:
   `helm uninstall harbor -n harbor-ha --kube-context=rke2-cluster2` und entsprechend
   `opensearch-dashboards -n opensearch`. Namespace nicht löschen.
3. OpenSearch-Release kontrolliert deinstallieren. StatefulSet-PVCs bleiben typischerweise
   zurück; tatsächliche OwnerReferences/Retention vor jedem Schritt erneut prüfen.
4. Redis-Replication-Release entfernen, solange der Redis-Operator noch läuft.
   Auf Finalizer-Abbau und Beenden der Redis-/Sentinel-Workloads warten.
5. CNPG-Cluster `harbor-ha-db` nur mit expliziter Freigabe für Cluster-CR **und dessen
   PVC-/Secret-Folgeeffekte** löschen, solange der Operator noch läuft.
6. Erst danach Redis-Operator und CNPG-Operator deinstallieren. Vorher alle Custom
   Resources clusterweit prüfen; bei weiteren Nutzern stoppen. CRDs nicht löschen.
7. Nur die einzeln freigegebenen PVCs/Alt-Secrets/übrig gebliebenen Anwendungsressourcen
   entfernen; auf abgeschlossene Volume-Detach-/Löschvorgänge warten. Keine `--all`-Löschungen,
   keine Namespace-Löschung, kein pauschales Entfernen von Finalizern.
8. Vor Fleet-Installation prüfen: Release-Namen frei, verbleibende Webhooks/ClusterRoles/
   Services/CRDs auf Helm-Eigentum und Kompatibilität kontrolliert. CRDs desselben Charts
   können bestehen bleiben, müssen aber vom installierenden Helm-Release akzeptiert werden.
   Nicht durch blindes `takeOwnership` über Konflikte hinweggehen.

## Ausdrücklich freizugebende Ressourcen

| Aktion | Exakte Ressourcen / Umfang |
| --- | --- |
| Helm-Uninstall | harbor-ha/harbor, harbor-ha/redis-replication, harbor-ha/redis-operator, cnpg-system/cnpg, opensearch/opensearch, opensearch/opensearch-dashboards |
| CNPG-CR inklusive Folgeeffekten | harbor-ha/harbor-ha-db, Instanzen und dessen generierte TLS-Secrets/PVCs |
| Registry-Daten | harbor-ha/harbor-registry (10Gi RWX) |
| PostgreSQL-Daten | harbor-ha/harbor-ha-db-1, harbor-ha-db-2, harbor-ha-db-3 (je 1Gi) |
| Redis-Daten | harbor-ha/redis-replication-redis-replication-0, -1, -2 (je 2Gi) |
| Trivy-Cache | harbor-ha/data-harbor-trivy-0 (5Gi) |
| OpenSearch-Daten inkl. Security-Index | opensearch/opensearch-cluster-master-opensearch-cluster-master-0, -1, -2 (je 10Gi) |
| Alte manuelle Secrets, falls später entbehrlich | harbor-admin, harbor-secret-key, harbor-ha-db-app, harbor-redis, redis-secret im Namespace harbor-ha; jeweils erst nach Sicherung und Verbraucherprüfung |
| Chart-/Operator-Secrets | genaue Zuordnung in inventory.md; Uninstall-/GC-Folgeeffekte vorab bestätigen |

Backend-PV-IDs stehen in inventory.md. ReclaimPolicy ist Delete; Genehmigung einer
PVC-Löschung muss deshalb die Backend-Daten einschließen. CRD-Löschungen sind
**nicht vorgesehen**; sollten sie nötig werden, separate Ressource-für-Ressource-Freigabe
mit vollständiger CR-Liste einholen. `default`-OpenSearch-PVCs, Logging-Puffer,
`redis-auth`, System-Namespaces und alle Cluster-1-/Management-Daten bleiben außerhalb
der Löschliste. ESO-/neue Plattform-Secrets ebenfalls nicht bereinigen.

## Rollback

Vor der destruktiven Stufe: neue App-Pfade noch nicht aktiviert, alte Releases laufen.
Bootstrap-Pfade bei Bedarf pausieren; ESO-Orphan-Secrets erhalten. OpenBao-Rollen/KV
nicht automatisch löschen. Cluster-1-Bundles bleiben unangetastet.

Nach Aktivierung eines neuen Bundles zuerst dessen Reconciliation gezielt pausieren.
Nicht einfach Pfade entfernen: Fleet kann daraus die Löschung gemanagter Ressourcen
ableiten. Vor Entfernen/Ändern des GitRepo immer beabsichtigtes Pruning prüfen.

Nach Datenlöschung ist `git revert` oder `helm rollback` **kein Daten-Rollback**.
Für Rückkehr zur Altinstallation neue Dienste anhalten, Controller-Eigentum trennen,
Alt-Chart-Versionen und gesicherte Werte wiederherstellen, danach zusammenpassende
DB-/Registry-/OpenSearch-Snapshots und ursprüngliche Secrets restaurieren. Erzeugte
neue Credentials dürfen nie gegen alte restaurierte Daten ausgespielt werden.
Wenn kein verifiziertes Backup existiert, ist nur ein erneuter frischer Aufbau möglich.

## Abnahmekriterien

- GitRepo Ready und ausschließlich erwartete Cluster-2-BundleDeployments; Cluster 1 weiter Ready.
- ESO-Stores/ExternalSecrets Ready; positive und negative Auth-Tests; keine offenen Secret-Referenzen.
- CNPG 3/3, Redis 3/3 plus Sentinel 3/3, gezielter Failover-Test erst nach Freigabe.
- Harbor Login, Push/Pull eines Testimages, Trivy-Scan, keine DB-/Redis-Auth-Fehler.
- OpenSearch Cluster Health/Shard-Verteilung, Testindex schreiben/lesen/löschen nach Testfreigabe;
  Dashboards-Login und Rancher-Logging-Lieferung prüfen.
- PVCs Bound, gewünschte Longhorn-Redundanz erreicht, keine unerklärten degraded Volumes.
- Backup/Restore-Probe und Betriebshinweise einschließlich Zertifikats-/Passwortrotation dokumentiert.
