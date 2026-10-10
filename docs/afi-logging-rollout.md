# Logging-Umstellung: vorbereitet, noch nicht aktiviert

Die Dateien unter `config/afi-isolation/rollout/cluster*-logging-*` sind bewusst keine
aktiven Fleet-Bundles. Bestehende Collector-Pods und Routing werden erst nach Freigabe
gemäß Auftrag §8.7 umgestellt. Relevante Änderungen: je Cluster 20 GiB Longhorn-PVC,
Fluent-Bit-hostPath, eigene Ingest-Zugänge, drei Ausgänge auf Cluster 1 und ein
Plattformausgang auf Cluster 2. Ein isolierter Collector wurde bereits erfolgreich
mit Ausfall, Pod-Ersatz und Nachlieferung getestet; das ersetzt keine Live-Abnahme.

## Vertrauensgrenze

`tenant-catalog.json` ordnet administrativ gepflegte Cluster-/Namespace-Namen zu.
`scripts/afi-isolation/render-logging.py` prüft eindeutige Namespace-Zuordnung und
generiert ausschließlich die vorbereiteten Ausgänge/Flows. Pod- und Namespace-Labels
werden nicht zur Mandantenzuordnung verwendet. Cluster/Tenant-Felder werden im Flow
konstant überschrieben. Unbekannte Namespaces gehen nur in Plattformindizes.

Fluent Bit übernimmt Kubernetes-Metadaten aus Dateipfad/API. `Merge_Log=Off` verhindert,
dass JSON-Anwendungslogs gleichnamige Routingfelder in den äußeren Datensatz einbringen.
Loginhalt bleibt unter `log`; Parser-/Exclude-Annotationen sind deaktiviert.
Die vorbereitete NetworkPolicy erlaubt Forward-Ingest nur von Fluent Bit und dem
RKE2-Journald-Collector im administrierten Logging-Namespace. Tenant-Pods dürfen den
Forward-Port nicht erreichen. Vor Aktivierung Port, Pod-Labels, Host-Network-Modus
und Cilium-Durchsetzung gegen die tatsächlichen Collector-Pods überprüfen.
Kubernetes-/Node-Administratoren liegen außerhalb dieser Mandanten-Vertrauensgrenze.

## Reihenfolge nach Freigabe

1. Aktuelle Helm-Werte, Logging-CRs und Buffer-Metriken sichern; Exportfehler beheben
   und bestehende Queues leeren lassen. Ein leeres `emptyDir` nach Pod-Ersatz würde
   sonst noch nicht zugestellte Daten verlieren. Kein Neustart mit ungeprüftem Rückstand.
2. Pro Cluster den vorbereiteten PVC in ein eigenes Fleet-Bundle übernehmen, Bound
   und zwei gesunde Longhorn-Replikate prüfen. Storage-Budget prüfen; nichts verkleinern.
3. Zuerst Cluster 1: vorbereitete Werte nach
   `bundles/application/logging/operator/values.yaml` übernehmen. Operator-Abhängigkeit
   auf das PVC-Bundle setzen. Root-Fluentd und danach Fluent-Bit-Rollout beobachten.
4. `cluster1-logging-output.yaml` ersetzt die bisherigen Flow-/Output-Ressourcen im
   bestehenden Output-Bundle; Service/EndpointSlice bleiben erhalten. Kein paralleler
   Alt-/Neuflow für dieselben Logs. NetworkPolicy erst nach Prüfung der Quellen übernehmen.
5. Nach erfolgreicher Abnahme Cluster 2: bestehenden Helm-Release `rancher-logging`
   und `rancher-logging-crd` mit unveränderter Chartversion
   `109.0.1+up4.10.0-rancher.24` in Infrastruktur-Fleet-Bundles übernehmen; die vorbereiteten
   Werte enthalten dessen bestehende Rancher-Metadaten. PVC-Abhängigkeit und Zielselector
   `environment=lab, role=infrastructure` setzen. Den bisherigen Infrastruktur-Output
   durch `cluster2-logging-output.yaml` ersetzen. Erst dann neue Bundle-Pfade aktivieren.
6. Pro Mandant einen ausschließlich dafür angelegten Test-Pod starten, der eine einmalige
   Markierung sowie absichtlich falsche Tenant-/Namespace-Felder im JSON-Log schreibt.
   Namespace-Labels ebenfalls falsch setzen. Ausschließlich der echte Namespace darf
   die Indexzuordnung bestimmen. Eigener Treffer erlaubt, fremder API-/Dashboards-Treffer
   verweigert. Direkter Forward-Verbindungsversuch aus dem Mandanten-Namespace muss scheitern.
7. PVC-Mount, Fluent-Bit-DB/Queue, Queue-Limits, Metrics-Sidecar und Alert-Targets prüfen.
   Nur den dedizierten Testausgang unterbrechen, Daten puffern, seinen Collector ersetzen
   und alle Marker nach Wiederverbindung zählen. Einen Ausfall des ganzen OpenSearch-
   Clusters vermeiden. Testressourcen anschließend gezielt entfernen.

Rückfall: vorherige Fleet-Werte/Flows wiederherstellen, persistenten PVC behalten und
vor Rückwechsel neue Queues abarbeiten lassen. Ein Rollback beendet neue Ingest-Routen;
er darf gepufferte Daten nicht einfach verwerfen. Alte gemischte `kubernetes-*`-Indizes
bleiben für Mandanten unlesbar und werden nicht automatisch umgeschrieben oder gelöscht.

## Pufferbudget und Verlustgrenzen

Vorläufiges Ziel: vier Stunden Ausfall, mangels abweichender Angabe. Fluentd hat je
Ausgang 4 GiB File-Buffer, insgesamt maximal 12 GiB auf Cluster 1 bzw. 4 GiB auf Cluster 2,
auf jeweils 20-GiB-PVC. Chunk 8 MiB, Flush alle 10 s, zwei Threads, unbegrenzte Retry-Dauer,
maximal 30 s Retry-Intervall, Backpressure bei vollem Buffer. Versionsabfrage beim
OpenSearch-Verbindungsaufbau ist deaktiviert, damit Collector-Neustart auch während
eines OpenSearch-Ausfalls möglich bleibt. Request-Timeout: 30 s.

4 GiB reichen mit Sicherheitsfaktor 2 für vier Stunden bei etwa 149 KiB/s pro Ausgang
(4 GiB / 14.400 s / 2). Fluent Bit begrenzt seine node-lokale Forward-Queue zusätzlich
auf 2 GiB, nutzt persistente Positionsdaten und verlangt Forward-Acknowledgements.
Das ist ein Auslegungsbudget, keine gemessene Garantie: unkomprimierten Spitzendurchsatz
und tatsächlich maximalen Queue-Aufbau über einen repräsentativen Zeitraum messen.

Ein kurzer 830-s-Lauf ergab 5.543 Byte/s komprimiertes OpenSearch-Primärdatenwachstum.
Hochgerechnet sind das 80,3 GiB für 180 Tage, 160,6 GiB einschließlich einer OpenSearch-
Replik und rund 321,2 GiB physisch mit zwei Longhorn-Kopien, jeweils ohne Reserve.
Bestehende 3 x 10 GiB reichen dafür nicht. Freie Longhorn-Kapazität wurde zuletzt mit
ca. 203 GB auf Cluster 1 und 217 GB auf Cluster 2 gemessen; das ersetzt kein verbindliches
Speicherbudget. Zusätzlicher Speicher und Reserve sind vor einer 180-Tage-Zusage nötig.

Node-lokale Fluent-Bit-Daten überleben keinen Node-Datenverlust. Longhorn-Puffer hängen
von intakten Volumes/Replikaten ab. Volle Queues, Rotation bei Backpressure, ausgelassene
überlange Zeilen und Daten vor dem Disk-Sync können Logs verlieren. Zustellung ist
mindestens einmal; ACK-Verlust und neues Positions-DB-Verzeichnis können Duplikate
verursachen. `Read_From_Head` kann beim ersten Umstieg vorhandene Dateien erneut lesen.

## Monitoring

Je Cluster sind Fluentd- und fünf Fluent-Bit-Targets aktiv. Sieben Regeln decken Retry,
75/90-Prozent-Füllstand, Exportfehler, verworfene Records, Nichterreichbarkeit und
PVC-Füllstand ab. Letzterer wird erst mit dem vorbereiteten Metrics-Sidecar aktiv.
`tests/afi-isolation/logging-alerts.test.yaml` prüft alle Regeln mit positiven und
negativen Zeitreihen. Die kopierte Rules-Datei muss mit den aktiven Regeln übereinstimmen.
Cluster 1 verwendet Rancher Monitoring; Cluster 2 hat einen eigenen Prometheus mit
2-GiB-PVC und 14 Tagen Metrik-Retention. Auf Cluster 2 ist noch kein Alertmanager-
Empfänger angebunden: Regel-Auswertung ist vorhanden, externe Zustellung noch offen.
