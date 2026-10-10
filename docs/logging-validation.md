# Logging-Validierung – 10.10.2026

**Cluster 1 und Cluster 2 erfolgreich getestet.** Die zusätzliche OpenBao-Rolle
und der Fleet-Rollout wurden nach der ausdrücklichen Freigabe umgesetzt.

## Cluster 1

Rancher Logging und CRDs verwenden wie Cluster 2 den Chart
`109.0.1+up4.10.0-rancher.24`. Aktiv sind `lab-app-logging-crds`,
`lab-app-logging-secrets`, `lab-app-logging-operator`, `lab-app-logging-output`,
ausschließlich für `environment=lab, role=applications`. Der separate
`lab-infra-opensearch-ingest`-Service gehört ausschließlich zu Cluster 2.

| Prüfung | Ergebnis |
| --- | --- |
| Fleet | Alle fünf neuen Logging-/Endpoint-Bundles Ready |
| Collector | Root-Fluent-Bit 5/5, Journald 5/5, Fluentd 2/2 Container; Operator Ready |
| Logging-Konfiguration | Eine Root-Pipeline; Config-Check true, ClusterFlow/ClusterOutput active |
| ESO/OpenBao | Store Ready, ExternalSecret SecretSynced; eigene neue Rolle eso-logging im Root-Mount rke2-cluster1, vorhandene read-only Policy unverändert |
| Netzwerk/TLS | Beide Worker erreichen VIP 192.168.1.196:9200 mit CA-/Hostnamenprüfung und Authentifizierung, HTTP 200 |
| Quellbegrenzung | Nur fünf Cluster-1-Node-IP-Adressen /32 erlaubt; Zugriff von der nicht erlaubten Arbeitsstation läuft in Timeout |
| Ingestion | Zwei eigene Pods, drei Sequenzen pro Pod, genau sechs Dokumente in kubernetes-rke2-cluster1-2026.10.10 |
| Duplikate | Sechs unterschiedliche Meldungen, jeweils einmal; nach weiteren 45 Sekunden unverändert sechs Treffer |
| Metadaten | cluster_name=rke2-cluster1, cluster_role=applications, environment=lab; Namespace, Pod, Container und Host geprüft |
| Dashboards | Authentifizierter Login und Suche über lokalen, TLS-geschützten Rancher-Tunnel jeweils HTTP 200; sechs Treffer |
| Cleanup | Ausschließlich eigene Test-Pods entfernt; keine bestehenden Logs/Indizes gelöscht |

Letzter erfolgreicher Testmarker: `codex-app-log-20261010175317`. OpenSearch-Dashboards Dev Tools:

```json
GET kubernetes-rke2-cluster1-*/_search
{
  "size": 10,
  "query": {"terms": {"kubernetes.pod_name.keyword": [
    "codex-app-log-20261010175317-wk1", "codex-app-log-20261010175317-wk2"
  ]}}
}
```

Die Cluster-2-Service-Netze überlappen mit Cluster 1. Deshalb nutzt Cluster 1 einen
selectorlosen Service `opensearch-cluster-master` samt EndpointSlice auf die VIP.
Der kurze DNS-Name ist bereits im OpenSearch-Zertifikat enthalten; `ssl_verify=true`
bleibt aktiv. Kein Zertifikatswechsel an der bestehenden OpenSearch-Installation.
Die neue OpenBao-Rolle liest ausschließlich `secret/data/platform/opensearch/logging`,
TTL 900/maximal 3600 Sekunden. Kein Passwort und kein Root-Token liegen in Git.

## Gefundene Fehler und Korrekturen

Die ersten Probes ergaben innerhalb des Testfensters keine Treffer. Messungen zeigten
viele kleine Fluentd-Staging-Puffer und eine mehrminütige Lieferverzögerung. Der neue
Cluster-1-Ausgang bündelt jetzt über `tags: time`, flusht im Intervall von 10 Sekunden,
mit zwei Threads, 0.05 Sekunden Burst-Abstand und bis zu 64 wartenden Chunks.
Der anschließende End-to-End-Test und die zusätzliche Duplikatprüfung waren erfolgreich.
Ein Zwischenlauf wurde außerdem durch einen vorübergehenden Rancher-Proxyfehler beendet;
dessen eigene Pods wurden trotzdem entfernt. Diese Fehlversuche werden nicht als Erfolg gezählt.

Die Collector-Vorgabe liest neu entdeckte Dateien ab ihrem Ende. Sehr frühe Startmeldungen
kurzlebiger Pods können dadurch fehlen; die erfolgreiche Funktionsprobe wartete 75 Sekunden
vor der Ausgabe. `Read_From_Head` wurde nicht isoliert aktiviert, weil die derzeit flüchtige
Positionsdatenbank dann bei Collector-Neustarts alte Logs erneut einlesen könnte.
Persistente Positionsdaten und Puffer müssen zusammen verbessert und separat getestet werden.
Root-Fluentd nutzt wie die bestehende Cluster-2-Pipeline `disablePvc=true`: Kein allgemeines
Exactly-once- oder Verlustfreiheitsversprechen bei Pod-/Node-Ausfall.

## Bestehende Cluster-2-Pipeline und Alloy

Cluster 2: identischer Chart, Root/Journald 5/5 und Fluentd Ready. Am 10.10.2026
wurden mit Marker `codex-log-20261010165949` sechs Meldungen aus beiden Workern genau
einmal in OpenSearch und über Dashboards nachgewiesen. Diese Pipeline wurde nicht geändert.
Sie enthält Kubernetes-Host-Metadaten, aber noch kein explizites `cluster_name`.

Alloy auf Cluster 1 bleibt 5/5 und sendet ausschließlich an Loki (`tenant_id=1`).
Es wurde keine zusätzliche Alloy-Route nach OpenSearch angelegt. Die zwei Backends
bleiben unabhängig; es gibt eine neue Rancher-Logging-Route nach OpenSearch.

## Mandantentrennung und Grenzen

Cluster-Präfixe und Namespace-Metadaten ermöglichen Zuordnung, sind aber keine
Berechtigungsisolation. Die gemeinsame Rolle `platform_logging` besitzt weiterhin
crud/create_index auf `kubernetes-*`; keine geprüften mandantenbezogenen Leserollen,
DLS-Regeln oder negativen Logzugriffstests. Rancher-Projektberechtigungen aus dem
Terraform-Repository verleihen keine OpenSearch-Rechte. Diese Sicherheitsaufgabe bleibt offen.

Dashboards wurde über die API geprüft; kein visueller Browser-/Discover-Nachweis und
kein dauerhaftes Index-Pattern angelegt. Die öffentliche Dashboards-Route verwendet
weiterhin HTTP; für die Prüfung wurden Zugangsdaten ausschließlich lokal im geschützten
Tunnel verwendet.

## Offline-Prüfung

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-logging.py \
  --charts-dir /tmp/platform-validation-20261010/charts \
  --schemas-dir /tmp/rke2-migration-audit/schemas
```

Vier App-Bundles, zwei gepinnte Charts, 38 gerenderte Ressourcen, API-/CRD-Schemas,
Targets, DAG, eine Root-Pipeline und TLS-/ESO-Referenzen geprüft. Der offizielle CRD-Chart
hat den bekannten Metadaten-Lintfehler `apiVersion=v1` mit `type=application`; nur dieser
exakte Fehler wird akzeptiert. Render-, Schema- und Runtime-Prüfungen bestehen.

Nachweise: [Rollout-Evidenz](evidence/platform-rollout-2026-10-10.json),
[ursprünglicher Audit](evidence/platform-validation-2026-10-10.json).
Quellen: [Fleet](https://fleet.rancher.io/reference/ref-fleet-yaml),
[Logging-Operator OpenSearch-Output](https://kube-logging.dev/docs/configuration/plugins/outputs/opensearch/).
