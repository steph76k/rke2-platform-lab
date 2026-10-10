# Logging-Umstellung: freigegebener Rollout

Stand 10.10.2026: Cluster 1 verwendet die neuen Mandantenrouten, persistente Node-Queues
und den 20-GiB-Fluentd-PVC. Live-Routing mit gefälschten Labels/JSON-Feldern sowie
OIDC-Zugriff auf eigene/fremde Pod-Logs: PASS für A und B. Beim echten Fluentd-Pod-Ersatz
blieben PVC und Queue erhalten; anschließend wurden 50/50 Marker ohne Duplikate zugestellt.
Cluster 2 ist noch nicht
vollständig umgestellt: alte zentrale Queue auf `emptyDir` bleibt bis zum bestätigten
Drain bestehen; Node-Collector werden gestuft aktualisiert. Die Freigabe nach §8.7
liegt vor. Fortschritt und Einschränkungen sind kein vollständiger Abnahmenachweis
für Cluster 2.

Der Logging-Operator erzeugt den Claim
`rancher-logging-root-afi-fluentd-buffer-rancher-logging-root-fluentd-0` aus seiner
PVC-Vorlage. `source.claimName` ist dabei ein Namensbestandteil und keine Referenz auf
einen vorab angelegten Claim. Die ungenutzten Vorbereitungs-PVCs waren nie gemountet
(Longhorn: detached, 0 Byte); ihre Fleet-Bundles wurden entfernt. Cluster 1 nutzt
explizit StorageClass `longhorn` mit drei Replikaten, Cluster 2 ist mit
`longhorn-platform` und zwei Replikaten vorbereitet. Der aktive PVC bleibt beim
Pod-Ersatz erhalten und gehört dem Operator.

## Vertrauensgrenze

`tenant-catalog.json` ordnet administrativ gepflegte Cluster-/Namespace-Namen zu.
`scripts/afi-isolation/render-logging.py` prüft eindeutige Namespace-Zuordnung und
generiert ausschließlich die vorbereiteten Ausgänge/Flows. Pod- und Namespace-Labels
werden nicht zur Mandantenzuordnung verwendet. Cluster/Tenant-Felder werden im Flow
konstant überschrieben. Unbekannte Namespaces gehen nur in Plattformindizes.

Fluent Bit übernimmt Kubernetes-Metadaten aus Dateipfad/API. `Merge_Log=Off` verhindert,
dass JSON-Anwendungslogs gleichnamige Routingfelder in den äußeren Datensatz einbringen.
Loginhalt bleibt im CRI-Textfeld `message` (je Parser auch `log`); Parser-/Exclude-Annotationen sind deaktiviert.
Die NetworkPolicy erlaubt Forward-Ingest nur von Fluent Bit und dem
RKE2-Journald-Collector im administrierten Logging-Namespace. Tenant-Pods dürfen den
Forward-Port nicht erreichen. Vor Aktivierung Port, Pod-Labels, Host-Network-Modus
und Cilium-Durchsetzung gegen die tatsächlichen Collector-Pods überprüfen.
Kubernetes-/Node-Administratoren liegen außerhalb dieser Mandanten-Vertrauensgrenze.

## Ablauf und Fortsetzung des freigegebenen Rollouts

1. Aktuelle Helm-Werte, Logging-CRs und Buffer-Metriken sichern; Exportfehler beheben
   und bestehende Queues leeren lassen. Ein leeres `emptyDir` nach Pod-Ersatz würde
   sonst noch nicht zugestellte Daten verlieren. Kein Neustart mit ungeprüftem Rückstand.
2. PVC-Vorlage mit expliziter Größe/StorageClass verwenden; Claim wird vom Operator
   erstellt. Bei unveränderlichen StatefulSet-Feldern nach bestätigtem Drain einmalig
   `enableRecreateWorkloadOnImmutableFieldChange` aktivieren, anschließend wieder
   deaktivieren. Den tatsächlich gemounteten Claim und seine Replikate prüfen.
3. Zuerst Cluster 1: vorbereitete Werte nach
   `bundles/application/logging/operator/values.yaml` übernehmen. Root-Fluentd sowie
   beide Fluent-Bit-DaemonSets beobachten. Cluster 1 ist bereits umgestellt; vor Ersatz
   des alten Pods wurden 0 Pufferdateien und 0 Bytes bestätigt.
4. `cluster1-logging-output.yaml` ersetzt die bisherigen Flow-/Output-Ressourcen im
   bestehenden Output-Bundle; Service/EndpointSlice bleiben erhalten. Kein paralleler
   Alt-/Neuflow für dieselben Logs. NetworkPolicy erst nach Prüfung der Quellen übernehmen.
5. Nach erfolgreicher Abnahme Cluster 2: bestehenden Helm-Release `rancher-logging`
   und `rancher-logging-crd` mit unveränderter Chartversion
   `109.0.1+up4.10.0-rancher.24` in Infrastruktur-Fleet-Bundles übernehmen; die vorbereiteten
   Werte enthalten dessen bestehende Rancher-Metadaten. Abhängigkeit zur bestehenden StorageClass und Zielselector
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
auf jeweils 20-GiB-PVC. Chunk 2 MiB, Flush alle 10 s, zwei Threads, unbegrenzte Retry-Dauer,
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

Cluster 1 hat zwölf aktive Targets: zehn Fluent-Bit-Collector (Container/Journald),
einen Fluentd und einen Volume-Metrics-Sidecar. Cluster 2 erreicht die vollständige
Abdeckung erst nach Abschluss des Node- und Zentral-Collector-Rollouts. Sieben Regeln decken Retry,
75/90-Prozent-Füllstand, Exportfehler, verworfene Records, Nichterreichbarkeit und
PVC-Füllstand ab. Der PVC-Füllstand wird auf Cluster 1 bereits vom Metrics-Sidecar erfasst.
`tests/afi-isolation/logging-alerts.test.yaml` prüft alle Regeln mit positiven und
negativen Zeitreihen. Die kopierte Rules-Datei muss mit den aktiven Regeln übereinstimmen.
Cluster 1 verwendet Rancher Monitoring; Cluster 2 hat einen eigenen Prometheus mit
2-GiB-PVC und 14 Tagen Metrik-Retention. Auf Cluster 2 ist noch kein Alertmanager-
Empfänger angebunden: Regel-Auswertung ist vorhanden, externe Zustellung noch offen.

## Befunde während des freigegebenen Rollouts

Der vorhandene Cluster-1-Ausgang hatte zunächst einen ungültigen Chunk-Schlüssel
(`time` ohne `tag`), anschließend trat ein separater Discovery-Fehler auf: Der
OpenSearch-Client übernimmt standardmäßig nach 10.000 Requests die internen
Node-Adressen. Die beiden Cluster verwenden überlappende Pod-Netze; diese Adressen
sind vom anderen Cluster aus nicht erreichbar. Im laufenden Collector wurden
Verbindungen zu `10.42.5.229` und `10.42.5.248` im Zustand SYN_SENT beobachtet,
während synthetische Bulk-Requests über den Service mit 1 KB, 100 KB und 1 MB erfolgreich
waren. Die Ausgänge verwenden deshalb `reload_connections: false`,
`reload_on_failure: false` und `reconnect_on_error: true`. TLS-Prüfung bleibt aktiv.
Siehe [OpenSearch-Plugin: Connection Reload](https://github.com/fluent/fluent-plugin-opensearch#reload_connections).

Der erstmalige Wechsel der Positionsdaten löste eine erneute Sammlung alter
Containerdateien aus. Mehrere zehntausend kleine Alt-Chunks wurden im bestehenden
Pod abgearbeitet. Für diese Übergangsphase wurden acht Flush-Threads eingesetzt;
die endgültigen Ausgänge verwenden zwei Threads und 2-MiB-Chunks. Fluentd erhält
2 GiB RAM, da das Wiederherstellen sehr vieler Chunks mit dem früheren 768-MiB-Limit
zu OOM-Neustarts geführt hatte. Die anfänglichen Fluent-Bit-Startfehler durch
`DB_Sync` wurden korrigiert: Diese Operatorversion rendert diesen Schlüssel unverändert,
während Fluent Bit `DB.Sync` erwartet. Der Kubernetes-Collector verwendet daher WAL
mit dem Standard-Sync der Positionsdatenbank, die Disk-Queue dagegen `storage.sync full`.

Das zusätzliche RKE2-Journald-DaemonSet erhält über einen Helm/Kustomize-Overlay
persistente Systemd-/Kubelet-Positionsdaten und eine eigene 2-GiB-Forward-Queue unter
`/var/lib/rancher/afi-logging/journald`. Der Overlay verwendet das native `DB.Sync Full`,
Forward-ACKs und unbegrenzte Retries. Konfiguration mit Fluent Bit 3.1.8 in einem
isolierten Prüf-Pod validiert. Der Overlay ist an die festgeschriebene Chartversion
gebunden; bei einem Chartupgrade muss auch die übernommene Journald-Konfiguration
mit dem Upstream verglichen werden.

Die Forward-NetworkPolicy schützt gegenüber normalen Tenant-Pods. Eine vollständige
Abwehr privilegierter Workloads, Host-Network/Host-Path-Zugriffe oder kompromittierter
Nodes benötigt zusätzlich Pod-Security-/Admission-Regeln. Das bestehende
Mandanten-Repository erzwingt solche Regeln derzeit nicht; die Logging-Prüfung
ersetzt keine vollständige Kubernetes-Mandantenisolation.

Die letzten großen Alt-Chunks wurden zunächst mit HTTP 429 zurückgewiesen
(`circuit_breaking_exception`/Indexing-Pressure bei 512 MiB OpenSearch-Heap).
`bulk_message_request_threshold: '2097152'` teilt deshalb auch bereits vorhandene
große Chunks in kleine Requests; nur das Chunk-Limit zu ändern verkleinert alte Dateien
nicht. Die Schutzlimits von OpenSearch wurden nicht angehoben. Während des endgültigen
Drain wird Forward-Ingest durch die temporäre Policy `afi-fluentd-migration-pause`
pausiert. Diese Policy muss nach dem Wechsel wieder entfernt werden; die normalen
Node-Collector halten den Rückstand währenddessen in ihren Disk-Queues.


## Cluster-2-Ressourcenbefund

SSH-Diagnose als `ansible`: Control-Plane-Nodes besitzen jeweils eine vCPU und
rund 3,6 GiB nutzbaren RAM. Auf `cp-2` wurden nur 44 MiB verfügbarer Speicher,
2,4 GiB API-Server-RSS, starker Swap-Verkehr und etwa 43 Prozent I/O-Wartezeit gemessen.
`cp-2`/`cp-3` wechselten zwischen Ready und unerreichbar; der Rancher-Tunnel fiel dabei
wiederholt aus. Die native API auf `cp-1` und OpenSearch über den Worker-SSH-Tunnel
waren erreichbar; OpenSearch meldete green. Die Quell-IP-Liste des Cross-Cluster-
LoadBalancers erlaubt die Cluster-1-Nodes, nicht den lokalen Arbeitsplatz.

Der Benutzer bietet eine Erweiterung auf vier vCPU und 6 GB RAM je Control-Plane-Node
an. Umstellung einzeln, beginnend mit `cp-2`, danach jeweils Ready/etcd/API prüfen.
Das ist eine Verbesserung gegenüber dem Istzustand; der tatsächliche Ressourcenbedarf
muss anschließend beobachtet werden. Die [RKE2-Anforderungen](https://docs.rke2.io/install/requirements)
nennen mindestens zwei CPUs/4 GB und empfehlen vier CPUs/8 GB. Collector-Requests
auf Cluster 2 betragen 10m CPU je Node-Prozess; das behebt Scheduling-Engpässe,
aber keinen Speichermangel des API-Servers. Prometheus-Konfigurationsänderungen
benötigen im bestehenden eigenständigen Deployment zusätzlich SIGHUP oder Pod-Rollout.

### Wiederanlauf nach VM-Erweiterung

`cp-2` wurde auf vier vCPU/6 GB erweitert und meldete nach der Reparatur Ready.
Beim ersten Boot war die Systemzeit rund acht Stunden voraus. Kubelet-, Kube-Proxy-
und RKE2-Controller-Zertifikate hatten dadurch `notBefore=11.10.2026 04:37 UTC`,
während nach NTP-Abgleich der 10.10.2026 21:42 UTC galt. Kubelet wurde mit Unauthorized
abgewiesen. Nach Prüfung aller drei gesunden etcd-Endpunkte wurde ausschließlich auf
`cp-2` RKE2 gestoppt, `rke2 certificate rotate --service kubelet --service kube-proxy
--service rke2-controller` ausgeführt und RKE2 gestartet. Die installierte CLI benötigt
wiederholte `--service`-Optionen; eine kommaseparierte Liste wird abgewiesen.
RKE2 legte seine Sicherung unter `/var/lib/rancher/rke2/server/tls-1791668592` an.
Keine CA- oder etcd-Zertifikate wurden rotiert. Danach waren Node und alle drei
etcd-Endpunkte gesund.

`config/host-recovery/10-afi-wait-for-time.conf` wurde auf allen drei Control-Plane-
Nodes unter `/etc/systemd/system/rke2-server.service.d/` installiert und mit
`systemctl daemon-reload` geladen. Es verändert keinen laufenden Dienst, verhindert
aber beim nächsten Start die Zertifikatsausstellung vor erfolgreichem Chrony-Abgleich.
`chronyc waitsync 120 1 0 1` prüft bis zu 120-mal im Sekundenabstand Synchronisation
und weniger als eine Sekunde Restkorrektur. Ohne erfolgreiche Synchronisation schlägt
der Startversuch fehl; systemd versucht ihn gemäß bestehender Restart-Regel erneut.
Die Datei ist Hostkonfiguration und kein Fleet-Bundle. Reproduktion: Datei mit Modus
0644 installieren, `systemctl daemon-reload`; Rücknahme: nur dieses Drop-in entfernen
und erneut daemon-reload. Ursache der falschen Zeit beim VM-Boot zusätzlich auf
Hypervisor-/RTC-Ebene untersuchen.

Quellen: [RKE2-Zertifikatsverwaltung](https://docs.rke2.io/security/certificates),
[Chrony waitsync](https://chrony-project.org/doc/4.6.1/chronyc.html).
