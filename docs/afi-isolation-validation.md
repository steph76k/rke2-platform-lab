# AFI-PoC: Umsetzung und Abnahme am 10.10.2026

## Stand und Abnahmegrenze

Stand 11.10.2026: Harbor-OIDC, OpenSearch-OIDC/Indexrechte, Mandanten A/B, gemeinsamer
Remote-State und Logging-Monitoring sind aktiv. A/B wurden vollständig nach Cluster 2
übernommen; Rancher-Projekt-Isolation und vier Terraform-Egress-Adressen sind wirksam.
Alle 16 Netzwerkfälle, Rancher-OIDC-Projekt-/Kubernetes-Rechte und vier LAN-Quell-IPs
sind geprüft. Beide realen Collector-Neustarttests lieferten 50/50 Marker ohne Duplikate.
Details: [Tenant-Umzug/Egress](egress-gateway-poc.md) und [Logging](afi-logging-rollout.md).

## Umgesetzte Konfiguration

- Keycloak-Realm `berger`: eigene vertrauliche Clients `afi-harbor` und `afi-opensearch`,
  exakte HTTPS-Callbacks und Gruppenclaim. Geheimnisse in OpenBao, kein Password Grant
  und keine Service-Accounts für diese Browserclients. Rancher behält seine separat
  bereits korrigierte Realm-/PKCE-Konfiguration.
- Harbor 2.15.2: OIDC, private Projekte A/B, getrennte Developer-/Project-Admin-Gruppen,
  Projekterstellung nur durch Plattformadministratoren. Lokaler `admin` bleibt nutzbar.
- OpenSearch 3.9.0: OIDC vor dem unveränderten Basic-Auth-Domain, Prüfung von Issuer und
  Audience. Die Leserolle umfasst `cluster_composite_ops_ro`, `cluster:monitor/main`,
  `read` nur auf die eigenen `logs-rke2-cluster1-<mandant>-*` und
  `logs-rke2-cluster2-<mandant>-*` und `kibana_all_read` nur im eigenen Tenant.
  Keine Bulk-Schreibrechte, kein `all_access`, keine Rechte auf alte gemischte Indizes.
- Dashboards: TLS, Basic/OIDC-Auswahl, getrennte Saved Objects, zentral bereitgestellte
  Index-Patterns. Zwei Replikate mit `maxUnavailable=0` für den Konfigurationsrollout.
  Der UI-Schalter `readonly_mode` wird nicht für die Mandantenrollen verwendet, da er
  Discover ausblendet; die tatsächlichen Leserechte setzt OpenSearch Security durch.
- Zwei neue technische Ingest-Identitäten dürfen ausschließlich in den jeweiligen
  Clusterpräfix schreiben. Secrets werden über eigene OpenBao-/ESO-Rollen zugestellt.
- ISM-Policy `afi-logs-retention`: 180 Tage für neue AFI-Indizes; eine OpenSearch-Replik.
  Die Policy ändert oder löscht keine alten gemischten Indizes. Kapazitätsgrenze unten beachten.
- Terraform: A übernommen, B zusätzlich erstellt, Gruppen/Rancher/Namespaces/Harbor/
  OpenBao/ESO/OpenSearch deklarativ verwaltet. Seit 11.10.2026 gemeinsamer verschlüsselter und versionierter
  MinIO-Verwaltungsstate für alle Mandanten, administrativer Backend-Zugang, natives
  S3-Locking und geprüfte SOPS-Sicherungen. 56 Ressourcen unverändert übernommen;
  abschließender Plan ohne Änderungen. Die alten Einzelstates sind schreibgeschützte Archive.
- Prometheus: je zwölf erreichbare Targets auf beiden Clustern einschließlich Journald
  und PVC-Metrics; je sieben gesunde Alarmregeln, ohne aktive Alarme beim geprüften Stand.

## Funktionale Nachweise

Testidentitäten waren ausschließlich neu angelegte temporäre Benutzer: A-Developer,
B-Developer und A-Project-Admin, jeweils zusätzlich in der expliziten Logs-Reader-Gruppe.
Alle Daten waren synthetisch. Anschließend wurden die drei Testbenutzer in Keycloak
und Harbor, beide OCI-Test-Repositories und die verbliebenen Testindizes entfernt;
der isolierte Test-Collector samt Namespace/PVC wurde gelöscht. Mandanten A/B bleiben bestehen. Browser: Chromium/Playwright; TLS mit geprüfter Lab-CA
bzw. Zertifikat-Pins aus einer vorher TLS-verifizierten Verbindung. Registry: OCI-Client
`crane` mit CA-Prüfung. Docker konnte wegen fehlendem Lab-CA-Vertrauen des lokalen Daemons
nicht verwendet werden; dessen Systemkonfiguration wurde nicht verändert.

| Test / Identität | Erwartet | Beobachtet | Ergebnis |
| --- | --- | --- | --- |
| Harbor-Browserlogin A/B-Dev, A-Admin | OIDC erfolgreich | Echter Keycloak-Redirect, Benutzer erkannt, kein Systemadmin | PASS |
| Harbor-Projektzugriff A/B-Dev, A-Admin | Eigenes erlaubt, fremdes gesperrt | HTTP 200 / 403 | PASS |
| Harbor-Projektadministration A-Admin | Nur eigenes Projekt ändern | Idempotenter eigener Metadaten-Write 200, fremder 403 | PASS |
| Harbor-Projektadministration A/B-Dev | Keine Adminänderungen | HTTP 403 | PASS |
| OCI Push/Pull A/B-Dev | Eigenes privates Projekt erlaubt | Echte Images übertragen und gelesen | PASS |
| OCI Pull A-Dev aus B | Verweigert | Registry-Zugriff abgewiesen | PASS |
| Dashboards A/B-Dev | Browser-OIDC und eigene Suche möglich | Login und Tenant-Auswahl erfolgreich, eigene synthetische Logs mit Zeitdiagramm in Discover und Search-API sichtbar | PASS |
| Dashboards-Suche A/B auf Fremdindex | Verweigert | HTTP 403 `security_exception`, keine fremden Daten | PASS |
| Saved Object im eigenen Tenant | Lesen erlaubt, Schreiben gesperrt | GET 200, POST 403 | PASS |
| Saved Objects im fremden Tenant | Keine fremden Objekte | Erzwungener Fremdtenant-Header führt zu HTTP 500 ohne Objektdaten | PASS Datenisolation; UI/API-Fehlerstatus offen |
| Fremdtenant als UI-Präferenz setzen | Darf keine Datenrechte verleihen | Präferenz-Endpunkt antwortet 200, nachfolgender Objektzugriff scheitert | PASS Datenisolation; Auswahlantwort nicht als Autorisierung verwenden |
| OpenSearch-API A/B-Dev, A-Admin | Eigene Suche erlaubt | HTTP 200, eigener Marker | PASS |
| API Fremdindex, Mehrindex, Wildcard, Altindex | Keine Fremddaten | Je HTTP 403 | PASS |
| API gemischtes `_msearch` | Eigene Antwort erlaubt, fremde gesperrt | Eigener Treffer, fremde Teilantwort 403 | PASS |
| API direktes fremdes Dokument | Verweigert | HTTP 403 | PASS |
| API Log-Write als Logleser | Verweigert | HTTP 403 | PASS |
| Technische Ingest-Identitäten C1/C2 lesen Logs | Verweigert | HTTP 403 | PASS |
| Separater Collector, Zielport nicht erreichbar | Daten puffern | 50 Records im File-Buffer | PASS |
| Separaten Collector-Pod ersetzen | Queue bleibt erhalten | Derselbe PVC, 11.400 persistierte Bytes nach Pod-Ersatz | PASS |
| Testziel wieder erreichbar | Alles nachliefern | 50/50 eindeutige Marker, 0 Duplikate in diesem Lauf | PASS |
| Zweiter Terraform-Apply auf Teststate | Lock verhindert Konkurrenz | `Error acquiring the state lock`; erster Apply erfolgreich | PASS |
| Historische Einzelstates vor Zusammenlegung: B liest A | Verweigert | HTTP 403 | PASS vor Umstellung; aktueller State nur für Plattformadministration |
| State lesen ohne SSE-C-Key | Verweigert | HTTP 400 | PASS |
| Recovery einer älteren S3-Version | Terraform kann State lesen | Separater Recovery-Key, `state list` zeigt Testressource | PASS |
| SOPS-Backup A/B und Backend-Schlüssel | Entschlüsselung identisch | Im Speicher verifiziert, keine Klartextausgabe | PASS |
| Terraform A/B | Kein Drift | `plan -detailed-exitcode`: jeweils 0 | PASS |
| Monitoring | Targets/Regeln aktiv | Je zwölf Targets Up, sieben Regeln gesund | PASS |
| Alertlogik | Ausfall löst aus, Normalfall nicht | promtool: alle sieben Regeln mit positiven/negativen Reihen und historischem Retry-Zähler erfolgreich | PASS |
| Reale Namespace-Routen und gefälschte Metadaten | Richtiger Tenant, keine Umgehung | A/B: eigene reale Pod-Logs 200, fremde 403; Forward blockiert; Label-/JSON-Manipulation unwirksam | PASS Cluster 1 und Cluster 2 |
| Persistenz der realen Collector beider Cluster | Neustartfest | Echter Pod ersetzt, gleicher PVC, Queue erhalten, 50/50 Marker, 0 Duplikate | PASS Cluster 1 und Cluster 2 |

Die 50-Record-Prüfung belegt die getestete Ausfall-/Neustartfolge und ist keine allgemeine
Exactly-once- oder Kapazitätsgarantie. Ein vollständiger Cluster-Ausfall wurde nicht erzeugt.
Terraform `fmt -check` und `validate`, Helm-Rendering, Server-Dry-Run und die drei
bestehenden Bootstrap-Vertragstests wurden zusätzlich geprüft. Maschinenlesbare, bereinigte Ergebnisse stehen unter `tests/afi-isolation/results/`.

## Reproduktion und Zuständigkeiten

Python-Abhängigkeiten: `scripts/afi-isolation/requirements.txt`; zusätzlich kubectl,
OpenBao CLI, SOPS und ein vorhandener administrativer Lab-Zugang. TLS-verifizierten
OpenSearch-Tunnel gemäß dem Mandanten-Repository öffnen. Konfigurationsdateien prüfen:

1. `bootstrap-state.py tenants` für den gemeinsamen administrativen Backend-Zugang.
2. `bootstrap-oidc.py` zeigt den Plan; `--apply` gleicht die eigenen OIDC-Clients und
   Auth-Konfigurationen ab. Verschlüsselte Vorher-Sicherung wird angelegt.
3. `bootstrap-logging.py` legt eigene Ingest-/ESO-Identitäten an. Fleet stellt ihre Secrets zu.
4. Den gemeinsamen Terraform-State initialisieren, Plan aller Mandanten prüfen und anwenden.
5. `bootstrap-retention.py` und `bootstrap-saved-objects.py` gleichen die eigenen
   zentralen Policies/Templates und Index-Patterns ab.
6. `render-logging.py` erzeugt vorbereitete Routen; Aktivierung und Rückfallweg stehen in
   [afi-logging-rollout.md](afi-logging-rollout.md). Kein automatischer Collector-Rollout
   allein durch einen neuen Mandanteneintrag.
7. Für die Rechteprüfung frische Benutzer ausschließlich den neuen Gruppen zuordnen,
   temporäre Marker/Images verwenden und nach dem Test diese Benutzer/Objekte entfernen.
   Keine Tokens oder Logdaten in Testprotokolle übernehmen.

Fleet besitzt Plattforminstallationen, Logging-CRs und Monitoring. Terraform besitzt
Mandanten und Rollen. Bootstrap-Skripte besitzen globale OIDC-/Ingest-/Retention-Objekte.
Diese Grenzen vermeiden konkurrierende Controller. Bestehende produktive Benutzer
wurden weder umgruppiert noch durch Testbenutzer ersetzt.

## Offene Betriebsaufgaben

- Speicherausbau für 180 Tage: am 11.10.2026 vom Benutzer aus dem Auftrag genommen,
  kein offener Abnahmepunkt. Die bestehende ISM-Policy bleibt aktiv; eine garantierte
  180-Tage-Vorhaltung gehört nicht zum zugesagten Lab-Umfang.
- Cluster-2-Prometheus hat noch keinen externen Alertmanager-Empfänger. Keine Ende-zu-Ende-
  Alarmzustellung behaupten, solange Ziel und Routing nicht eingerichtet sind.
- SOPS-Sicherungen sind lokal außerhalb MinIO geprüft. Automatische Off-host-Sicherung
  und getrennte externe Schlüsselverwahrung müssen noch eingerichtet werden.
- Das Standard-Index-Pattern wird zentral gesetzt; weitere read-only UI-Änderungen können HTTP 403 anzeigen; Saved-Object-
  Schreibrechte bleiben absichtlich gesperrt. Fremdtenant-Objektzugriff liefert aktuell
  500 statt 403. Beides ist zu dokumentieren, kein Grund für breitere Indexrechte.
- Bestehende Bootstrap-Administratorzugänge werden nur vom Lab-Operator verwendet.
  Für späteren Team-/CI-Betrieb eingeschränkte Verwaltungsidentitäten separat bereitstellen.
