# Umsetzung des Lab-Neuaufbaus – 10.10.2026

Der Betreiber hat Phase 5 einschließlich der vorgesehenen Datenlöschungen ausdrücklich
freigegeben. Cluster 2 wird mit frischen Daten aufgebaut. OpenBao bleibt auf dem
K3s-Management-Cluster; die vorhandene Cluster-1-Installation wird nicht verändert.

## Durchgeführte Migration

- ESO 2.11.0 über Fleet installiert; eigener Kubernetes-Auth-Mount `rke2-cluster2`
  im OpenBao-Root-Namespace mit nativer RKE2-API und deren Cluster-CA eingerichtet.
- Sechs getrennte Rollen/Policies für Harbor, PostgreSQL, Redis, OpenSearch,
  Logging und den Smoke-Test. Kurzlebige ServiceAccount-JWTs dienen auch als
  TokenReview-Identität; kein statischer Reviewer-Token.
- Neue Zugangsdaten und Zertifikate ausschließlich in OpenBao erzeugt. Alle
  Kubernetes-Anwendungs-Secrets werden durch ESO synchronisiert. Neue Secret-Namen
  verhinderten einen Passwortwechsel der noch laufenden alten Datenservices.
- Sechs alte manuelle Helm-Releases kontrolliert entfernt: Harbor, Dashboards,
  OpenSearch, Redis Replication, Redis Operator und CNPG Operator. Den alten
  CNPG-Cluster bei laufendem Operator entfernt; anschließend die elf aufgeführten
  alten PVCs samt Longhorn-Backend-Volumes entfernt. Keine CRDs/Namespaces gelöscht.
- CNPG, PostgreSQL (3 Instanzen), Redis (3 Instanzen + 3 Sentinels), Harbor,
  OpenSearch (3 Instanzen) und Dashboards unter den bisherigen Release-Namen
  durch Fleet installiert. Die sieben Chart-Versionen entsprechen dem Inventar.
- Eigene StorageClass `longhorn-platform`, zwei Replikate für die zwei vorhandenen
  Storage-Worker. Die ursprüngliche StorageClass `longhorn` wurde nicht geändert.
- Nur die beiden vorher manuell angelegten Logging-Integrationsressourcen
  `ClusterOutput/opensearch` und `ClusterFlow/all-logs-to-opensearch` in
  `cattle-logging-system` an Fleet übergeben. Die Logging-Operator-Installation
  bleibt bestehen. Dediziertes Konto `platform-logging` hat Schreibrechte nur auf
  `kubernetes-*`; TLS- und CA-Prüfung sind jetzt eingeschaltet.

## Laufzeitkorrekturen

1. Der Rancher-Webhook war vorübergehend ohne Endpunkte; Fleet konnte zeitweise
   keine Namespaces prüfen. Nach seiner Erholung liefen die Installationen weiter.
   Keine Änderung oder Neuinstallation des Webhooks vorgenommen.
2. Redis Operator 0.27 und Chart 0.17.1 serialisieren das deaktivierte Exporter-Feld
   unterschiedlich. Ein exakt auf `/spec/redisExporter/enabled` begrenzter
   Fleet-Vergleichsausschluss verhindert einen falschen Modified-Status. Alle
   übrigen Felder bleiben im Vergleich; der Exporter ist weiterhin deaktiviert.
3. Nach Zuordnung der Helm-Metadaten hatten die alten Logging-CRs weiterhin den
   ursprünglichen manuellen Apply-Feldbesitz. Nach expliziter Eigentümerprüfung wurde der identische Sollstand
   einmalig mit dem bisherigen Apply-Manager gesetzt; danach übernimmt Fleet.
4. Harbor benötigt für den Registry-Token-Signer PKCS#1 (`RSA PRIVATE KEY`).
   Derselbe Schlüssel wurde ohne Schlüsselwechsel entsprechend umkodiert, mit CAS
   in OpenBao versioniert, durch ESO synchronisiert und Harbor Core über Fleet
   neu gestartet. Der Bootstrap-Regressionscheck prüft PKCS#1 für Harbor und PKCS#8
   für OpenSearch getrennt.
5. Für Kubernetes-Metadaten wurde ein rekursiver De-dot-Filter aktiviert, damit
   Labelnamen wie `app` und `app.kubernetes.io/name` keine Mappingkollision auslösen.
6. Worker 1 besitzt nur 1 allocatable CPU, davon waren 995 mCPU reserviert; Worker 2
   besitzt 4 CPUs. Deshalb laufen PostgreSQL und OpenSearch trotz bevorzugter
   Anti-Affinität auf Worker 2. Harte Verteilungsregeln wurden geprüft, wegen
   `Insufficient cpu` zurückgenommen und nicht im finalen Sollstand belassen.
   Der Betreiber akzeptiert die gemeinsame Platzierung für den Lab-Test ausdrücklich.
   CPU-Zuteilung und Requests bleiben unverändert; Worker-Ausfallsicherheit ist
   mit dieser Platzierung nicht gegeben.
7. OpenSearch initialisierte den leeren Security-Index aus den OpenBao-Secrets.
   Danach wurde `allow_default_init_securityindex` auf `false` gesetzt und ein
   rollierender Neustart durchgeführt. Ein späterer Secret-Refresh überschreibt
   den Security-Index nicht: Passwortrotation benötigt dessen Security-API.
8. Den vorhandenen Rancher-Logging-Konflikt nach gesonderter Zustimmung behoben:
   normale Logging- und FluentbitAgent-Ressource über `loggingRef=rancher-logging`
   eindeutig zugeordnet. Der bestehende Helm-Release wurde mit identischer
   Chart-Version aktualisiert; der Render-Vergleich zeigte ausschließlich diese
   zwei zusätzlichen Felder. Anschließend auf Betreiberwunsch die zusätzliche normale
   Pipeline nach vollständiger Pufferleerung entfernt (`logging.enabled: false`,
   Helm-Revision 5). Fleet verwaltet nur noch das Root-Flow-/Output-Paar. Details siehe
   [Logging-Reparatur](logging-system-follow-up.md).

## Daten und Sicherungen

Geschützte Exporte liegen außerhalb Git unter
`/home/tanzu/.local/state/rke2-platform-backups/20261010T110708Z`
(Verzeichnis 0700, Dateien 0600). Enthalten sind Helm-Values/Manifeste, betroffene
Kubernetes-Konfigurationen und Secrets sowie ein PostgreSQL-Dump des alten
Harbor-Datenbestands. Secret-Inhalte werden weder hier noch in Git veröffentlicht.

**Dies ist kein vollständiges, restore-geprüftes Backup der Altplattform.**
Registry-Blobs, Redis-Daten und OpenSearch-Indizes wurden im freigegebenen
Neuaufbau verworfen. Der alte DB-Dump allein stellt keine konsistente alte
Harbor-Installation wieder her. Ein Git-Revert ist nach der Datenlöschung kein
Daten-Rollback. Regelmäßige vollständige Backups und Restore-Proben sind weiterhin
Betriebsarbeit; ein OpenBao-PebbleDB-Backup ist kein Raft-Snapshot.

Die fünf alten manuellen Harbor-/Redis-Secrets wurden nach Prüfung aller aktuellen
Workload-Referenzen entfernt; ausschließlich die neuen ESO-Secrets bleiben in Verwendung.

Die ausgeschlossenen alten PVCs im Namespace `default`, die Logging-Puffer,
`redis-auth`, alle System-Releases und Cluster-1-Daten bleiben erhalten.
Der historische Helm-Status des Longhorn-Releases lautet weiterhin `failed`;
aktuelle Volume- und Pod-Readiness werden davon getrennt beurteilt.

## Prüfstand

| Prüfung | Ergebnis |
| --- | --- |
| Fleet GitRepo | 20/20 BundleDeployments Ready; beinhaltet beide ursprünglichen Bundles |
| ESO | 6 ClusterSecretStores und 18 ExternalSecrets Ready/SecretSynced |
| OpenBao Auth | positiver Login/Smoke-Read; fremder SA, falsche Audience und fremder KV-Pfad abgewiesen |
| Logging-Konto | Schreiben auf kubernetes-* erfolgreich (201), fremder Index verweigert (403); normalisierte Labelschlüssel erfolgreich indizierbar |
| Logging-Lieferung | Nur Root-Pipeline + Journald; je drei Testmeldungen pro Worker exakt einmal mit normalisierten Labels in OpenSearch, neue Journald-Dokumente nachgewiesen; Operator/Root-Fluentd ohne neue Fehler im Vier-Minuten-Fenster |
| PostgreSQL | App-Login über TLS; 3/3 Ready; replizierte Testzeile nach Wechsel db-1 → db-2 vorhanden |
| Redis/Sentinel | AUTH/PING/ROLE; 3 Redis + 3 Sentinels; WAIT auf beide Replikas, Masterwechsel redis-0 → redis-2, Testwert erhalten |
| Harbor | TLS/Admin-Login, alle acht Komponenten healthy; echtes Image-Push/Pull mit verifizierten Blob-/Manifest-Digests |
| Trivy | Scan des hochgeladenen offiziellen Alpine-3.20-Images erfolgreich |
| Testdaten | Harbor-Testprojekt/Repository/Artefakt, SQL-Testschema, Redis-Testkey und OpenSearch-Testindex entfernt |
| OpenSearch | 3 Nodes, green, keine unassigned Shards; Testindex schreiben/lesen/löschen erfolgreich; erneuter Start ohne Auto-Initialisierung |
| Dashboards | öffentliche Route erreichbar; Admin-Login und authentifizierte Sitzung über lokalen Kubernetes-Tunnel erfolgreich |
| Longhorn | alle 11 neuen Plattformvolumes Bound/healthy, jeweils 2 Replikate |
| Cluster 1 | alle 4 ExternalSecrets und vorhandener ClusterSecretStore Ready; ursprüngliches Fleet-Bundle unverändert |
| Statische Prüfung | 18 Infrastruktur-Bundles, 7 gepinnte Charts (lint/render), 151 Ressourcen gegen API-Schemas; Secret-Verweise, Targets und Abhängigkeiten geprüft |
| Bootstrap-Tests | 3 Tests erfolgreich, inklusive PKCS#1/PKCS#8-Vertrag, bcrypt-Konsistenz und Secret-Properties |

Der Image-Manifest-Digest im Push/Pull-Test war
`sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e`.

Die Ausfalltests ersetzen jeweils nur einen Pod; sie sind kein Test eines kompletten
Worker-/Netzwerkausfalls. Beim PostgreSQL-Test wurde die standardmäßig sehr lange
Pod-Beendigungsfrist auf 30 Sekunden begrenzt, nachdem beide Standbys den WAL-Stand
bestätigt hatten. Harbor Core/Jobservice starteten während der Failover-Tests neu;
die Tests belegen Wiederherstellung, keine unterbrechungsfreie Verfügbarkeit.

Der bestehende Logging-Systemfehler wurde im freigegebenen Nachgang behoben.
Anschließend wurden die beiden normalen Fluent-Bit-Agenten und deren zusätzlicher
Fluentd entfernt. Dessen Restpuffer war vor der Entfernung vollständig leer;
der zugehörige 20Gi-PVC wurde mit entfernt. Root-Fluent-Bit (fünf Pods),
Root-Fluentd und RKE2-Journald-Aggregator (fünf Pods) bleiben bestehen.
Der rekursive De-dot-Filter verhindert die bisherige Label-Mappingkollision.
Die Root-Pipeline verwendet weiterhin ihren bestehenden flüchtigen Puffer.
Historisch verworfene Logs werden nicht nachträglich restauriert.
Installationswerte und Reparaturverlauf stehen in
[rancher-logging-installation.md](rancher-logging-installation.md) und
[logging-system-follow-up.md](logging-system-follow-up.md).

## Zugang und Wiederaufbau

Harbor: `https://harbor-ha.berger.ph`, Benutzer `admin`, Passwort in OpenBao
`secret/platform/harbor/credentials`, Property `admin-password`.
Dashboards: bisherige Adresse `http://opensearch.berger.ph`, Benutzer `admin`,
Passwort in `secret/platform/opensearch/admin`, Property `password`.
`kibanaserver` ist ausschließlich das Backend-Servicekonto, kein Benutzerlogin.
Der Dashboards-Anmeldetest verwendet einen lokalen kubectl-Portforward durch die
verschlüsselte Kubernetes-Verbindung. Der vorhandene öffentliche HTTP-Ingress ist
weiterhin HTTP; für geschützte Browser-Anmeldungen ist eine spätere HTTPS-Umstellung
oder ein geeigneter Tunnel erforderlich.

Harbor verwendet die neue Lab-CA. Browser/Registry-Clients müssen deren öffentliches
CA-Zertifikat vertrauen. Es ist als `ca.crt` in `secret/platform/harbor/ingress-tls`
abrufbar; keine TLS-Prüfung mit `--insecure` umgehen. Private CA- und OpenSearch-
Admin-Schlüssel werden nicht an ESO freigegeben. Zertifikate gelten 365 Tage.

Für einen erneuten vollständig leeren Aufbau gelten die Stufen in
[migration-plan.md](migration-plan.md). Secrets-Bootstrap nicht über bestehende
KV-Pfade laufen lassen. Vor dem allerersten OpenSearch-Start auf leeren PVCs
`allow_default_init_securityindex` temporär auf `true` setzen, den initialisierten
Index und Login prüfen und den Wert danach wieder auf `false` committen.
Bestehende Sicherheitsindizes benötigen diesen Schritt nicht.

`fleet/gitrepo.yaml` wird nicht selbst als Bundle verwaltet: Änderungen an seinen
Pfaden erfordern zusätzlich zum Git-Push das gezielte Apply im Rancher-Kontext.
Niemals pauschal das gesamte `bundles`-Verzeichnis aktivieren.
