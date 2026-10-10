# Separater bestehender Rancher-Logging-Fehler

Der Logging-Operator meldet bereits seit 09.10.2026, vor dieser Migration, einen
unveränderlichen Selektor-Konflikt am DaemonSet
`cattle-logging-system/rancher-logging-fluentbit`.

| Feld | Vorhanden | Vom Operator erwartet |
| --- | --- | --- |
| spec.selector.matchLabels.app.kubernetes.io/managed-by | rancher-logging-root | rancher-logging |
| spec.template.metadata.labels.app.kubernetes.io/managed-by | rancher-logging-root | rancher-logging |

Die anderen Selektor-Labels bleiben `instance=rancher-logging`, `name=fluentbit`.
Betroffen sind die beiden Fluent-Bit-Agenten auf den Infrastruktur-Workern.
Der Fehler verhindert die vollständige Reconciliation des normalen Logging-Objekts
und damit die Übernahme weiterer Flow-/Output-Konfigurationsänderungen.

## Konkreter Reparaturvorschlag

Nur dieses DaemonSet löschen und vom bestehenden Rancher-Logging-Operator mit
korrektem Selektor neu erstellen lassen. Keine Helm-Deinstallation, kein Löschen
von Logging-CRs, Fluentd-StatefulSets, Secrets oder PVCs. Keine globale Freigabe
`enableRecreateWorkloadOnImmutableFieldChange` setzen.

```bash
kubectl --kubeconfig=/home/tanzu/.kube/rke2-cluster2.yaml --context=rke2-cluster2 \
  -n cattle-logging-system delete daemonset rancher-logging-fluentbit \
  --cascade=foreground --wait=true --timeout=120s
```

Danach 2/2 bereite Agenten, korrekte Selektoren, erfolgreiche Konfigurationsprüfung,
den De-dot-Filter in der generierten Fluentd-Konfiguration und neue Pod-Logs im
OpenSearch-Index nachweisen.

Die Agenten speichern Positionsdaten und lokale Puffer aktuell in `emptyDir`.
Beim Ersetzen gehen diese flüchtigen Daten verloren; kurze Erfassungslücken oder
Mehrfacheinträge sind möglich. Die persistenten Fluentd-Puffer bleiben erhalten.
Dies betrifft eine Systemkomponente, die der ursprüngliche Auftrag ausdrücklich
von Änderungen ausgenommen hat; daher separat zur Entscheidung vorgelegt.
