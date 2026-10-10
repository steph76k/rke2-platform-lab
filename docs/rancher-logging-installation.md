# Rancher Logging: eine gemeinsame Pipeline

Für Cluster 2 verwenden wir die vom Rancher-Chart bereitgestellte Root-Pipeline
für Containerlogs und den zusätzlichen RKE2-Journald-Aggregator für Systemlogs.
Eine zusätzliche normale Logging-Pipeline ist nicht erforderlich.

## Values für die Installationsnotizen

Im Namespace `cattle-logging-system` mit Rancher-Chart
`109.0.1+up4.10.0-rancher.24`:

```yaml
logging:
  enabled: false

additionalLoggingSources:
  rke2:
    enabled: true
```

`logging.enabled: false` deaktiviert nur die zusätzliche normale Pipeline.
Der Logging-Operator, die Root-Pipeline und die aktivierten RKE2-Logquellen
bleiben aktiv. `logging.controlNamespace` entfällt: Es gehört zur deaktivierten
zusätzlichen Ressource. Die Root-Pipeline verwendet den Helm-Release-Namespace.

Die übrigen bisherigen Values, insbesondere Ressourcenanforderungen, beibehalten.
Für ein Update des bestehenden Releases mit `--reuse-values` ist das
[Values-Overlay](../config/rancher-logging/values-repair.yaml) hinterlegt; es setzt
auch die Felder aus der vorübergehenden Reparatur und Abschaltung zurück.
Dieses Overlay verwaltet keine zweite Installation über Fleet.

## Weiterleitung nach OpenSearch

Fleet verwaltet ausschließlich `ClusterFlow/all-logs-to-opensearch-root` und
`ClusterOutput/opensearch-root` im Namespace `cattle-logging-system`. Deren
`loggingRef` bleibt leer und entspricht damit der Root-Pipeline. Das ESO-Secret,
TLS-Prüfung und der rekursive De-dot-Filter bleiben aktiv.

Erwarteter Bestand: ein Root-Fluent-Bit-DaemonSet (fünf Pods), ein RKE2-Journald-
DaemonSet (fünf Pods), ein Root-Fluentd und der Logging-Operator. Die Journald-
Sammler lesen andere Quellen als die Containerlog-Agenten und bleiben erforderlich.

Root-Fluentd verwendet weiterhin den bestehenden flüchtigen Puffer
(`disablePvc: true`). Persistente Pufferung ist eine separate spätere Betriebsänderung.
