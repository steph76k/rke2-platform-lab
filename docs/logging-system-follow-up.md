# Rancher-Logging-Reparatur – 10.10.2026

Nach gesonderter Zustimmung wurde der seit 09.10.2026 bestehende Logging-Fehler
auf Cluster 2 behoben. Die gemeinsame Platzierung von PostgreSQL und OpenSearch
auf Worker 2 bleibt für den Lab-Test ausdrücklich akzeptiert; CPU-Zuteilungen,
Requests und Scheduling-Regeln wurden bei dieser Reparatur nicht verändert.

## Ursache

Die beiden `Logging`-Ressourcen `rancher-logging` und `rancher-logging-root`
sowie ihre beiden `FluentbitAgent`-Ressourcen hatten alle eine leere `loggingRef`.
Damit beanspruchten beide Reconciler dieselben Agenten und versuchten wechselweise,
das unveränderliche DaemonSet-Selektorlabel `app.kubernetes.io/managed-by` auf
`rancher-logging` beziehungsweise `rancher-logging-root` zu setzen.

Die zuerst gezielt durchgeführte Neuerstellung von
`cattle-logging-system/rancher-logging-fluentbit` korrigierte dessen Selektor,
zeigte aber anschließend denselben Konflikt in Gegenrichtung. Sie allein war
keine dauerhafte Lösung. Der neue DaemonSet hat UID
`6bb16839-1417-4e77-8366-cf8f6f821dd3` und zwei bereite Agenten.

Die notwendige Zuordnung über `loggingRef` ist in der
[Operator-Dokumentation](https://kube-logging.dev/docs/logging-infrastructure/fluentbit-multiple/)
beschrieben; der gleiche Fehler ist im
[Upstream-Issue 1837](https://github.com/kube-logging/logging-operator/issues/1837)
dokumentiert.

## Dauerhafte Korrektur

Der vorhandene Helm-Release `rancher-logging` wurde mit unveränderter Chart-Version
`109.0.1+up4.10.0-rancher.24`, `--reuse-values` und dem versionierten
[Values-Overlay](../config/rancher-logging/values-repair.yaml) auf Revision 3
aktualisiert. Der vorherige Vergleich aller gerenderten Ressourcen zeigte exakt
zwei Änderungen: `spec.loggingRef: rancher-logging` in der normalen `Logging`-
und `FluentbitAgent`-Ressource. Die Root-Pipeline behält ihre leere Referenz.
Der Chart wurde dafür aus dem vorhandenen Helm-Release rekonstruiert.

Für spätere Updates desselben Releases dieses Values-Overlay zusammen mit den
bisherigen Values beibehalten. Die Systeminstallation bleibt außerhalb Fleet;
das Overlay ist keine Anweisung, den Operator zusätzlich über Fleet zu installieren.

Fleet verwaltet im bestehenden OpenSearch-Logging-Bundle jetzt vier Ressourcen:

| Pipeline | loggingRef | ClusterFlow | ClusterOutput |
| --- | --- | --- | --- |
| Normal | `rancher-logging` | `all-logs-to-opensearch` | `opensearch` |
| Root/System | leer | `all-logs-to-opensearch-root` | `opensearch-root` |

Beide verwenden das bestehende ESO-Secret, verifiziertes TLS, das eingeschränkte
OpenSearch-Konto und den rekursiven De-dot-Filter. Dadurch kollidieren Labelnamen
wie `app` und `app.kubernetes.io/name` nicht mehr im OpenSearch-Mapping.

Keine Helm-Deinstallation, keine Löschung von Logging-CRs, Fluentd-StatefulSets,
Secrets, PVCs oder OpenSearch-Indizes. Die globale Option
`enableRecreateWorkloadOnImmutableFieldChange` bleibt deaktiviert. Eine Annotation
am normalen Logging-Objekt stieß nach der DaemonSet-Löschung die Reconciliation an.

## Nachweise

- Normale Agenten 2/2 bereit; Root-Agenten 5/5 bereit. Beide Agentengruppen zeigen
  auf ihren jeweils eigenen Fluentd-Service.
- Beide Konfigurationsprüfungen erfolgreich; `de_dot_nested true` und
  `log_os_400_reason true` in den generierten Anwendungskonfigurationen.
  Der De-dot-Filter ist auch in beiden laufenden Pods eingebunden.
- Je ein temporärer Pod auf Worker 1 und Worker 2 schrieb drei Marker mit den
  Labels `app` und `app.kubernetes.io/name`. Alle Marker wurden im Index
  `kubernetes-*` mit dem normalisierten Schlüssel `app_kubernetes_io/name` gefunden.
- Sechs Dokumente je Test-Pod: Die bestehenden normalen und Root-Agenten erfassen
  Pod-Logs auf den Workern beide. Diese überlappende Erfassung bleibt bestehen;
  der Test behauptet keine Exactly-once-Zustellung.
- Test-Pods anschließend entfernt. Im abschließenden Zwei-Minuten-Fenster keine
  neuen Operatorfehler, Mappingfehler oder Flush-Fehler in beiden Fluentd-Pipelines.
  Kurze Verbindungsfehler während des vorherigen Konfigurationswechsels erholten sich.
- Fleet 20/20 bereit; OpenSearch green. Statische Validierung: 18 Infrastruktur-
  Bundles, 7 Charts, 153 Ressourcen einschließlich der zwei ergänzten Root-CRs.

Die neu erstellten Fluent-Bit-Agenten hatten Positionsdaten und lokale Puffer in
`emptyDir`; beim Ersetzen konnten deshalb Erfassungslücken oder Mehrfacheinträge
entstehen. Der persistente normale Fluentd-Puffer blieb erhalten; Root-Fluentd
verwendet wie zuvor `disablePvc: true`. Historisch verworfene Dokumente werden
durch diese Reparatur nicht wiederhergestellt.
