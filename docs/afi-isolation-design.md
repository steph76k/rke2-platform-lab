# AFI-PoC: Mandantentrennung und Datenhaltbarkeit

Stand: 10.10.2026. Umsetzung und Tests werden separat protokolliert; dieses Konzept
ist kein Erfolgsnachweis. Bestehende Rancher-OIDC-Konfiguration bleibt erhalten.

## Zuständigkeiten und Identitäten

Fleet verwaltet Installationen, Secret-Zustellung, Logging-Konfiguration und Monitoring.
Terraform verwaltet je Mandant Keycloak-Gruppen, Rancher-Projekt/Namespaces,
Harbor-Projektmitgliedschaften, OpenBao und OpenSearch-Rollen, -Mappings und -Tenants.
Plattformweite OIDC-Clients und Auth-Konfigurationen werden durch ein deklaratives,
idempotentes Bootstrap-Skript mit bestehenden administrativen Zugängen abgeglichen.
Secrets liegen in OpenBao; Git enthält nur Namen, Claims und Rollenbeschreibungen.
Es gibt keinen zweiten Controller für dieselben Objekte.

Neue Gruppen je Mandant: `<mandant>-developers`, `<mandant>-admins`,
`<mandant>-logs-readers`. Harbor ordnet die ersten beiden ausschließlich dem eigenen
privaten Projekt als Developer bzw. Project Admin zu. Logzugriff wird ausdrücklich
über die dritte Gruppe vergeben. Bestehende Gruppenmitglieder werden nicht automatisch
in neue Gruppen aufgenommen. Lokale Notfalladministratoren bleiben bestehen.

## Logging und OpenSearch

Feste, administrativ gepflegte Cluster-/Namespace-Zuordnung statt Tenant-Labels.
Mandantenlogs gehen in `logs-<cluster>-<mandant>-YYYY.MM.DD`, Plattformlogs in eigene
Indizes. Nicht zugeordnete Namespaces werden niemals einem Mandanten zugeschlagen.
Ein Export der Terraform-Namespace-Liste dient als Eingabe für die Fleet-Konfiguration;
Terraform besitzt keine Logging-CRs. Änderungen dieses Katalogs erfordern Review.
Die Cluster-ID und Tenant-ID werden durch Collector-Konfiguration gesetzt.

OpenSearch-Rollen erlauben `read` ausschließlich auf den eigenen exakten Indexpräfixen.
Keine Rechte auf alte gemischte `kubernetes-*`-Indizes. Separate Dashboards-Tenants
isolieren Saved Objects; sie ersetzen keine Indexberechtigungen. Negativtests decken
explizite Fremdindizes, Wildcards, Mehrindex-Suche und gefälschte Logmetadaten ab.
Serviceidentitäten für Ingest bekommen nur Schreib-/Indexanlageberechtigungen auf
festgelegte Clusterpräfixe. Administratorzugriff bleibt mandantenübergreifend erhalten.

180 Tage Retention werden zentral als ISM-Policy für neue `logs-*`-Indizes definiert.
Alte gemischte Indizes werden weder gelöscht noch ungeprüft einer Löschpolicy unterstellt.
Retention ist eine Löschfrist, keine Speicherplatzgarantie: die bestehende Kapazität
(3 x 10 GiB OpenSearch-PVC) muss gegen gemessenen Durchsatz und Replikation geprüft werden.

Fluent Bit erhält persistente Positionsdaten und eine node-lokale Disk-Queue.
Fluentd erhält Longhorn-PVCs und File-Buffer mit Retry ohne Zeitlimit, begrenzter
Gesamtgröße und Backpressure. Vorläufiges Auslegungsziel ohne andere Nutzerangabe:
vier Stunden Ausfall, mindestens Faktor zwei auf den beobachteten Durchsatz.
Pod-Neustart/Rescheduling mit intaktem Longhorn-Volume erhält Fluentd-Puffer;
Fluent-Bit-hostPath überlebt Pod-Neustarts auf demselben Node, nicht dessen Datenverlust.
Volle Queues, Logrotation während Backpressure, Node-/Volumeverlust und Daten vor der
Persistierung bleiben Verlustgrenzen. Zustellung ist mindestens einmal, nicht exakt einmal.

## Terraform-Backend

Auswahl: vorhandenes On-Premises-MinIO, privater versionierter S3-Bucket, ein State-Key
je Umgebung/Mandant (`lab/<mandant>/terraform.tfstate`) und S3-Lockdatei. Terraform
mindestens 1.10; für diesen Lauf wird 1.14.7 isoliert verwendet. Die bisherige 1.3.9
wird nicht systemweit ersetzt. Pro Mandant beschränkte S3-Policies und getrennte
Zugangsdaten; SSE-C-Schlüssel aus OpenBao schützen State-Inhalte auf dem Storage.
Versionierung, Longhorn-Replikation und separat verschlüsselte Sicherungen ergänzen
sich. Die Recovery-Identität und die Datenkopie müssen getrennt gesichert werden.
GitHub speichert ausschließlich Konfiguration und bietet kein Terraform-State-Locking.
GitLab HTTP-State wäre On-Premises geeignet, erforderte aber eine zusätzliche Plattform.
S3 vermeidet diese Abhängigkeit; MinIO-Kompatibilität wird einschließlich bedingter
Schreibzugriffe und konkurrierender Terraform-Prozesse tatsächlich getestet.

## Freigabegrenzen

Additive Ressourcen, Testidentitäten und isolierte Tests können selbstständig erfolgen.
Vor Änderungen mit Betriebsunterbrechung werden konkrete Diffs und Rückfallweg vorgelegt:
insbesondere Umstellung der bestehenden Collector-Pods auf persistente Volumes sowie
Neustart-/Ausfalltests gegen produktiv benutzte Pipelines. Ein OpenSearch-Ausfalltest
soll ausschließlich einen separaten Testausgang betreffen, nicht den ganzen Cluster.
Keine vorhandenen Benutzer, Images, Indizes oder PVCs werden gelöscht.

## Referenzen

- [Harbor OIDC](https://goharbor.io/docs/main/administration/configure-authentication/oidc-auth/)
- [OpenSearch OIDC](https://docs.opensearch.org/latest/security/authentication-backends/openid-connect/)
- [OpenSearch Multi-Tenancy](https://docs.opensearch.org/latest/security/multi-tenancy/multi-tenancy-config/)
- [Terraform S3-Backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Fluent Bit Persistenz](https://kube-logging.dev/docs/logging-infrastructure/fluentbit/)
- [Fluentd Persistenz](https://kube-logging.dev/docs/logging-infrastructure/fluentd/)

## Vereinfachung der State-Verwaltung am 11.10.2026

Der Benutzer hat die zuvor beschriebene State-Trennung durch einen gemeinsamen
administrativen State ersetzt. Alle Mandanten werden unter
`lab/tenants/terraform.tfstate` verwaltet; der Backend-Zugang liegt in OpenBao unter
`secret/platform/terraform-state/tenants`. Die fachlichen Mandantenrechte in Rancher,
Harbor, OpenSearch und OpenBao bleiben unverändert. Ein gemeinsames S3-Lock schützt
alle Terraform-Änderungen. Alte Einzelstates bleiben schreibgeschützte Archive.
Der Null-Änderungsplan, Lock-Test und neue-Mandanten-Plan stehen im Tenant-Repository
unter `tests/results/shared-state-*.json`. Diese Festlegung ersetzt die ursprüngliche
Entscheidung für einen State pro Mandant.
