# Logging-Validierung – 10.10.2026

**Cluster 2 erfolgreich getestet. Cluster 1 vorbereitet, noch nicht installiert.**
Die zusätzlich erforderliche OpenBao-Schreibfreigabe wurde angefragt und liegt
zum dokumentierten Stand nicht vor. Aktive Fleet-Pfade bleiben unverändert.

## Istzustand und Test Cluster 2

Rancher Logging/CRD-Chart `109.0.1+up4.10.0-rancher.24`, Release Revision 5.
Nur `Logging/rancher-logging-root` und ein gleichnamiger FluentbitAgent.
Root-Fluent-Bit 5/5 Ready, Journald 5/5 Ready, Root-Fluentd 2/2 Container Ready,
Operator 1/1. Logging configCheckResults erfolgreich; ClusterFlow und ClusterOutput
active. Keine neuen Logging-Operator-/Fluentd-Fehler im geprüften 30-Minuten-Fenster.
Die alten Mapping-/Reconcilerfehler aus 12–13 Uhr wurden als historisch erkannt.

Am 10.10.2026 um 16:59 UTC je ein eigener temporärer BusyBox-Pod auf Worker 1
und Worker 2 erstellt. Beide schrieben drei nummerierte Meldungen mit dem Marker
`codex-log-20261010165949`. Labels `app` und `app.kubernetes.io/name` prüften
zusätzlich die De-dot-Normalisierung. Die Dokumente trafen mit Pufferverzögerung ein.

| Prüfung | Status | Nachweis |
| --- | --- | --- |
| Collector/Config | Erfolgreich getestet | Readiness wie oben, Flow/Output active, Config-Check true |
| TLS/Auth | Erfolgreich getestet | Output scheme=https, ssl_verify=true, CA und Passwort aus ESO; erfolgreiche reale Lieferung und CA-verifizierte Suchabfrage |
| Ingestion | Erfolgreich getestet | Sechs Dokumente in kubernetes-2026.10.10, drei je Worker |
| Duplikate | Erfolgreich getestet | Jede Sequenz 1–3 je Pod genau einmal; nach zusätzlicher Wartezeit und Pod-Cleanup erneut sechs Dokumente. Kein allgemeines Exactly-once-Versprechen |
| Metadaten | Erfolgreich getestet | kubernetes.namespace_name=default, pod_name passend, container_name=probe, host korrekter Cluster-2-Worker; app_kubernetes_io/name normalisiert |
| Clusterfeld | Noch nicht umgesetzt auf Cluster 2 | Explizites cluster_name fehlt im bestehenden Flow; Zuordnung über kubernetes.host. Bestehende Pipeline nicht geändert |
| Dashboards | Erfolgreich getestet | Admin-Login/Sitzung und POST /api/console/proxy für kubernetes-*/_search jeweils HTTP 200; sechs Treffer über Dashboards |
| Browser/Discover | Noch nicht getestet | Keine Index Patterns vorhanden; kein visueller Browsernachweis. Dev-Tools-Suche funktioniert |
| Cleanup | Erfolgreich getestet | Ausschließlich eigene zwei Test-Pods entfernt; Testdokumente im bestehenden Index belassen, keine Indizes gelöscht |

Die erste Auswertung erwartete irrtümlich das Feld `log`; das reale CRI-Feld lautet
`message`. Nach Korrektur der Auswertung wurden die vorhandenen sechs Dokumente
geprüft; keine zusätzlichen Pods dafür erzeugt. Nachweise inklusive Metadaten:
[evidence/platform-validation-2026-10-10.json](evidence/platform-validation-2026-10-10.json).

Reproduzierbare Suchabfrage in Dashboards Dev Tools (Zeitraum 10.10.2026 UTC):

```json
GET kubernetes-*/_search
{
  "size": 20,
  "query": {"terms": {"kubernetes.pod_name.keyword": [
    "codex-log-20261010165949-wk1", "codex-log-20261010165949-wk2"
  ]}}
}
```

## Vorbereitete Fleet-Bundles für Cluster 1

Vorher: keine Rancher-Logging-Releases oder Logging-CRDs auf Cluster 1.
Alloy läuft 5/5 und sendet ausschließlich an
`http://loki.loki.svc.cluster.local:3100/loki/api/v1/push`, tenant_id=1.
Kein Alloy-OpenSearch-Ziel in der laufenden Konfiguration. Alloy bleibt unverändert;
es gibt weiterhin Sammlung für zwei unterschiedliche Backends, aber keine zweite
Route von Alloy in denselben OpenSearch-Index. Kein bestehender Collector abgeschaltet.

| Bundle / Verzeichnis | Abhängigkeit | Ziel |
| --- | --- | --- |
| lab-app-logging-crds / application/logging/crds | keine | applications |
| lab-app-logging-secrets / application/logging/secrets | lab-app-external-secrets | applications |
| lab-app-logging-operator / application/logging/operator | lab-app-logging-crds | applications |
| lab-app-logging-output / application/logging/output | Operator und Secrets | applications |
| lab-infra-opensearch-ingest / infrastructure/applications/opensearch-ingest | lab-infra-opensearch | infrastructure |

Alle vier App-Bundles haben zusätzlich environment=lab und das Präfix lab-app-.
Der neue Infrastruktur-Service ist separat begrenzt und verändert keine vorhandene
OpenSearch-/Logging-Ressource. Chart-Version identisch zu Cluster 2, Quelle
https://charts.rancher.io. Download gegen Repository-SHA256 geprüft:

- Logging: `75b08d7351da8ce7b3eb330fda3917e60d9339002e6147aac842b16a59ca8229`
- CRDs: `1aa078ae830a4495ae8e5c853b0c096836829421390dc679330748ed176d09aa`

`logging.enabled=false` verhindert die zusätzliche normale Pipeline; Root und
RKE2-Journald bleiben vorgesehen. Wie Cluster 2 nutzt Root-Fluentd einen flüchtigen
Puffer (`disablePvc=true`); persistente Pufferung und Verlustfreiheit bei Neustart
sind damit nicht zugesichert. Ressourcenanforderungen sind explizit gesetzt.

### Netzwerk und TLS

OpenSearch ist bisher nur clusterintern unter ClusterIP erreichbar; beide Cluster
verwenden überlappende Service-Netze. Eine Cluster-2-svc-Adresse direkt aus Cluster 1
wäre falsch. Vorbereitet ist ein **zusätzlicher** LoadBalancer-Service auf
`192.168.1.196:9200`, ohne zusätzliche NodePorts. Der vorhandene Cilium-Pool
192.168.1.194–198 hatte drei freie IPs; .194/.195 waren belegt. Vor Aktivierung
erneut auf freie IP prüfen. loadBalancerSourceRanges enthält ausschließlich die
fünf Cluster-1-Node-IP-Adressen /32 (.23, .161, .191, .65, .42).

In Cluster 1 verweist ein selectorloser Service `opensearch-cluster-master` im
Namespace cattle-logging-system samt EndpointSlice auf diesen VIP. Der Output
verwendet den **kurzen DNS-Namen** `opensearch-cluster-master`, der bereits im
OpenSearch-Zertifikat enthalten ist. Dadurch bleiben CA- und Hostnamenprüfung aktiv,
ohne Zertifikatsrotation oder Änderung bestehender Cluster-2-Services.
Cross-Cluster-Erreichbarkeit, tatsächliches Source-NAT und die Wirksamkeit der
Quelladressbegrenzung sind **noch nicht getestet**. Kein automatischer Fallback
auf ssl_verify=false oder eine größere Quellnetzfreigabe.

### Secrets und fehlende Freigabe

ESO soll ClusterSecretStore `openbao-logging` mit ServiceAccount
`external-secrets/openbao-logging`, Kubernetes-Audience
`https://kubernetes.default.svc.cluster.local`, Root-Auth-Mount `rke2-cluster1`
und Rolle `eso-logging` verwenden. Der Store ist auf cattle-logging-system begrenzt.
RBAC erlaubt diesem SA ausschließlich TokenReview-Erstellung.
ExternalSecret liest username/password/ca.crt aus `platform/opensearch/logging`.
Keine Secret-Werte in Git. Der Chart-CRD erwartet für `user` einen String;
`platform-logging` ist daher der öffentliche Kontoname, während Passwort/CA aus
Secret-Referenzen kommen.

**Freigabe erforderlich:** ausschließlich neue Rolle
`auth/rke2-cluster1/role/eso-logging` mit dem bereits vorhandenen Inhalt von
[config/openbao/roles/eso-logging.json](../config/openbao/roles/eso-logging.json).
Die bestehende Policy `eso-logging` erlaubt nur read auf
`secret/data/platform/opensearch/logging` und muss nicht verändert werden.
TTL 900 Sekunden, maximal 3600 Sekunden. Keine Änderungen an bestehenden Rollen,
Policies, Auth-Mount-Konfiguration oder KV-Daten erforderlich.

Dieser Schreibschritt ist vom ursprünglichen lesenden OpenBao-Auftrag nicht umfasst.
Die fehlende Zustimmung wird nicht durch einen Root-Token in Kubernetes oder durch
Kopieren des Cluster-2-Secrets umgangen. Die vier App-Bundles und der Endpoint bleiben
bis zur Freigabe und anschließendem gestuftem Bootstrap außerhalb der GitRepo-Pfade.

### Aktivierung und Abnahme nach Rollenfreigabe

1. Iststand erneut prüfen: freie VIP, keine konkurrierenden Releases/CRDs,
   unveränderte Alloy-Ziele, bestehende Policy und fehlende Zielrolle.
2. Nur die oben genannte neue OpenBao-Rolle mit der vorhandenen JSON-Datei anlegen;
   vorhandene Rolle niemals überschreiben. Keine Auth-Mount-/Policy-Änderung.
3. Zunächst Infrastruktur-Endpoint, App-CRDs und App-Secrets als explizite Pfade in
   fleet/gitrepo.yaml ergänzen, Diff/Targets prüfen, committen/pushen und GitRepo
   gezielt auf Rancher anwenden. Geplante Pfade stehen in
   [cluster1-paths-patch.yaml](../config/rancher-logging/cluster1-paths-patch.yaml).
   Diese Datei ist eine Prüfliste, kein automatisch angewendeter Patch.
4. VIP-Zuweisung, CRDs Established, Store Ready und ExternalSecret SecretSynced
   sowie vorhandene Secret-Keys abwarten. CA/Passwort nicht ausgeben.
   TLS-Erreichbarkeit aus einem eigenen temporären Cluster-1-Pod testen.
5. Erst danach Operator- und Output-Pfade mit erneutem Push-Diff aktivieren.
   Die Netzwerkabhängigkeit über zwei Cluster wird bewusst durch diese Reihenfolge
   abgesichert; ein Fleet dependsOn auf ein Bundle eines anderen Zielclusters
   würde die End-to-End-Erreichbarkeit nicht beweisen.
6. Alle fünf Root-Agenten, Journald und Fluentd Ready; Config-Check true, Flow/Output
   active und sämtliche neuen BundleDeployments Ready verlangen. Fleet Ready allein
   ersetzt weder ESO- noch Logging-CR-Funktionsprüfung.
7. Eigene nummerierte Test-Pods auf beiden Cluster-1-Workern erstellen. In
   kubernetes-rke2-cluster1-* exakt erwartete Dokumentanzahl, cluster_name=rke2-cluster1,
   cluster_role=applications, Namespace/Pod/Container/Host prüfen; nach zwei weiteren
   Pufferintervallen erneut Duplikate prüfen. Parallel Cluster-2-Pipeline nachtesten.
8. Dashboard-Login über TLS/Tunnel, dieselben Marker suchen; nur eigene Test-Pods
   entfernen. Bestehende Logs/Indizes, Alloy und Cluster-2-Pipeline bleiben erhalten.

## Mandantentrennung

Der neue Indexpräfix `kubernetes-rke2-cluster1` trennt Cluster logisch. Namespace-
Metadaten stammen aus Kubernetes und bleiben erhalten; cluster_name/cluster_role/
environment werden vom zentralen ClusterFlow ergänzt. Ein selbst gesetztes
Anwendungslabel ist keine verlässliche Berechtigungsgrenze.

Die aktuelle OpenSearch-Rolle platform_logging erlaubt crud/create_index auf
kubernetes-*; sie ist **kein** tenantgebundenes reines Schreibkonto. Der gemeinsame
Cluster-2-Index und die geplanten Cluster-1-Indizes haben noch keine belastbare
Mandantentrennung. Es existieren keine geprüften Mandanten-Leserollen/DLS-Regeln.
Auch Dashboards-Tenants isolieren gespeicherte Ansichten, nicht automatisch Logdaten.
Für die spätere Einführung: durch Namespace-Zuordnung kontrollierte tenantbezogene
Indizes, getrennte Collector-/Leserechte und negative Cross-Tenant-Tests planen;
Security-Konfiguration erst nach eigener Freigabe ändern. Kein Mandantenzugriff
wird durch diese vorbereitete Logging-Konfiguration erteilt.

## Statische Prüfung und Grenzen

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate-logging.py \
  --charts-dir /tmp/platform-validation-20261010/charts \
  --schemas-dir /tmp/rke2-migration-audit/schemas
```

Erfolgreich: vier Bundle-Targets, DAG, zwei gepinnte Charts gerendert, 38 Ressourcen
gegen API-/CRD-Schemas, genau eine Root-Pipeline, TLS- und ESO-Referenzen.
Zusätzlich Server-Dry-Run erfolgreich für den neuen Cluster-2-Service sowie
Cluster-1-ServiceAccount, TokenReview-RBAC und ClusterSecretStore; keine Objekte angelegt.
Der offizielle CRD-Chart hat einen reproduzierbaren **Upstream-Lint-Fehler**:
Chart.yaml kombiniert apiVersion=v1 mit type=application. Helm template funktioniert;
das Prüfskript akzeptiert ausschließlich diesen exakt benannten Fehler bei dieser
gepinnten Chart-Version und verlangt weiterhin Render-/Schema-Erfolg. Operator-Chart
lint erfolgreich. Es wird kein pauschal fehlerfreier Lint behauptet.
Charts mit `helm pull --repo https://charts.rancher.io --version
'109.0.1+up4.10.0-rancher.24' --untar --untardir <charts-dir> <chart>` laden;
API-/Schema-Exporte siehe [validation.md](validation.md#reproduktion).

Quellen: [Fleet-Referenz](https://fleet.rancher.io/reference/ref-fleet-yaml),
[Logging-Operator OpenSearch-Output](https://kube-logging.dev/docs/configuration/plugins/outputs/opensearch/).
Die konkret installierten CRD-Schemas haben Vorrang gegenüber Beispielen neuerer Versionen.
