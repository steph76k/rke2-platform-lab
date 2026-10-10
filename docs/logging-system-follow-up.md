# Rancher-Logging-Reparatur und Zusammenführung – 10.10.2026

**Aktueller Sollstand:** ausschließlich Root-Pipeline plus RKE2-Journald-Aggregator.
Die zusätzliche normale Pipeline wurde anschließend auf Betreiberwunsch entfernt.
Installationswerte: [rancher-logging-installation.md](rancher-logging-installation.md).
Die folgenden Reparaturschritte dokumentieren zunächst den Zwischenstand.

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
keine dauerhafte Lösung. Der zwischenzeitlich neue DaemonSet hatte UID
`6bb16839-1417-4e77-8366-cf8f6f821dd3` und zwei bereite Agenten; er wurde bei der Zusammenführung wieder entfernt.

Die notwendige Zuordnung über `loggingRef` ist in der
[Operator-Dokumentation](https://kube-logging.dev/docs/logging-infrastructure/fluentbit-multiple/)
beschrieben; der gleiche Fehler ist im
[Upstream-Issue 1837](https://github.com/kube-logging/logging-operator/issues/1837)
dokumentiert.

## Zwischenstand: getrennte Referenzen

Der vorhandene Helm-Release `rancher-logging` wurde mit unveränderter Chart-Version
`109.0.1+up4.10.0-rancher.24`, `--reuse-values` und dem damaligen
Values-Overlay auf Revision 3
aktualisiert. Der vorherige Vergleich aller gerenderten Ressourcen zeigte exakt
zwei Änderungen: `spec.loggingRef: rancher-logging` in der normalen `Logging`-
und `FluentbitAgent`-Ressource. Die Root-Pipeline behält ihre leere Referenz.
Der Chart wurde dafür aus dem vorhandenen Helm-Release rekonstruiert.

Die Systeminstallation blieb außerhalb Fleet. Das aktuelle Values-Overlay setzt
inzwischen den unten beschriebenen vereinheitlichten Sollstand um.

Fleet verwaltete in diesem Zwischenstand vier Ressourcen:

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

## Nachweise des Zwischenstands

- Normale Agenten 2/2 bereit; Root-Agenten 5/5 bereit. Beide Agentengruppen zeigen
  auf ihren jeweils eigenen Fluentd-Service.
- Beide Konfigurationsprüfungen erfolgreich; `de_dot_nested true` und
  `log_os_400_reason true` in den generierten Anwendungskonfigurationen.
  Der De-dot-Filter ist auch in beiden laufenden Pods eingebunden.
- Je ein temporärer Pod auf Worker 1 und Worker 2 schrieb drei Marker mit den
  Labels `app` und `app.kubernetes.io/name`. Alle Marker wurden im Index
  `kubernetes-*` mit dem normalisierten Schlüssel `app_kubernetes_io/name` gefunden.
- Sechs Dokumente je Test-Pod: Die bestehenden normalen und Root-Agenten erfassen
  Pod-Logs auf den Workern beide. Diese überlappende Erfassung bestand in diesem Zwischenstand;
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

## Abschließende Zusammenführung

Auf ausdrücklichen Betreiberwunsch wurde die redundante normale Pipeline entfernt:

1. Helm-Revision 4 deaktivierte nur den normalen `FluentbitAgent` über
   `logging.fluentbitDisabled: true`. Root-Agenten und Journald liefen weiter.
2. Der normale Fluentd lieferte seinen Restpuffer aus. Vor der Entfernung wurden
   **null Buffer-Chunks und null Buffer-Bytes** unter `/buffers` nachgewiesen.
3. Helm-Revision 5 setzte `logging.enabled: false`. Damit wurden das normale
   Logging-Objekt, sein Fluentd und der zugehörige leere 20Gi-PVC entfernt.
   Der Render-Vergleich zeigte keinerlei Änderung an Root- oder Journald-Ressourcen.
4. Fleet entfernte ausschließlich `all-logs-to-opensearch` und `opensearch`.
   Das bestehende Root-Flow-/Output-Paar blieb erhalten.

Das [aktuelle Overlay](../config/rancher-logging/values-repair.yaml) erhält
`additionalLoggingSources.rke2.enabled: true` und setzt die vorübergehenden
Reparaturfelder zurück. Chart-Version und Ressourcenanforderungen bleiben gleich.
Die zwei zusätzlichen Agenten und der zusätzliche Fluentd benötigen keine CPU/RAM
mehr; die Root-Pipeline behält ihren bisherigen flüchtigen Puffer.

### Abnahme des vereinheitlichten Sollstands

- Je drei nummerierte Testmeldungen auf Worker 1 und Worker 2 erzeugt. Nach der
  Puffer-/Indexierungsverzögerung enthielt OpenSearch exakt drei Dokumente pro
  Test-Pod; jede Nummer kam genau einmal vor. Die problematische Labelkombination
  wurde korrekt normalisiert. Dies prüft die entfernte doppelte Sammlung und ist
  keine allgemeine Exactly-once-Garantie für Logtransporte.
- Vier neue Journald-Dokumente im abschließenden Zehn-Minuten-Fenster nachgewiesen.
- Root-Agenten 5/5, Journald-Aggregatoren 5/5 und Root-Fluentd 1/1 bereit;
  ausschließlich Root-Logging und Root-FluentbitAgent vorhanden.
- Beide verbleibenden Root-Flow-/Output-Ressourcen aktiv, Fleet 20/20 bereit,
  OpenSearch green. Keine neuen Fehler in Operator/Root-Fluentd im geprüften
  Vier-Minuten-Fenster; Worker-Agenten ohne neue Warnungen/Fehler über fünf Minuten.
- Test-Pods entfernt; keine Logging-PVCs mehr vorhanden. Statische Validierung:
  18 Infrastruktur-Bundles, 7 Charts und 151 Ressourcen erfolgreich.

Vorhandene historische Pufferdateien der früheren Root-Ausgabe wurden nicht gelöscht;
Root-Fluentd verwendet für den aktuellen Output den separaten `opensearch-root`-Pfad.
