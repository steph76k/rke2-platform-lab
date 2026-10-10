# RKE2 Platform Lab – Fleet

GitHub: `steph76k/rke2-platform-lab`, Branch `main`.

**Vorbereitung, keine aktivierte Infrastruktur-Migration.** Die Live-Pfade des
GitRepo `fleet-default/rke2-platform` überwachen weiterhin ausschließlich
`bundles/00-bootstrap-test` und `bundles/application/operators/external-secrets`.
Cluster 1 betreibt ESO 2.11.0 bereits erfolgreich über Fleet.

Der Bereich `bundles/infrastructure` enthält die inaktiven Cluster-2-Bundles für
ESO, CNPG, Redis-Operator/Replication/Sentinel, PostgreSQL, Harbor, OpenSearch,
Dashboards und OpenBao-Secret-Synchronisierung. Alle Targets sind auf
`environment=lab, role=infrastructure` beschränkt. OpenBao bleibt auf K3s.

Der Betreiber hat einen vollständigen Lab-Neuaufbau mit frischen Daten gewählt.
Umsetzung und konkrete Löschung benötigen weiterhin getrennte ausdrückliche Freigaben.
Ein Push dieser Vorbereitung aktiviert keine neuen Pfade.

## Dokumentation

- [Aktuelles Inventar und Befunde](docs/inventory.md)
- [Zielarchitektur und Zuständigkeiten](docs/architecture.md)
- [OpenBao-/ESO-Bootstrap und Secret-Vertrag](docs/secrets.md)
- [Installationsreihenfolge, Löschliste und Rollback](docs/migration-plan.md)
- [Validierung und verbleibende Laufzeitprüfungen](docs/validation.md)

Longhorn-Release `failed` und mehrere `degraded` Volumes sind vor der Migration
zu klären. Alle vorbereiteten Bundles und Bootstrap-Werkzeuge bleiben bis dahin inaktiv.
Kein `kubectl apply`, Helm-Uninstall oder OpenBao-Bootstrap gehört zur Vorbereitung.

## Verzeichnisstruktur

`fleet/` enthält die unveränderte aktive GitRepo-Definition. `config/openbao/`
enthält nicht aktivierte Rollen-/Policy-Vorlagen. `config/opensearch/security/`
enthält ausschließlich nicht geheime Konfigurationsvorlagen aus Security 3.9.0.0
bzw. auf den Lab-Umfang reduzierte Auth-Konfiguration. Passwörter/Hashes/Schlüssel
werden erst beim ausdrücklich gestarteten Bootstrap in OpenBao erzeugt.
`docs/current-values/` ist sanitisiertes Inventar, keine Installationsquelle.

Nie pauschal das ganze `bundles`-Verzeichnis als Fleet-Pfad hinzufügen.
