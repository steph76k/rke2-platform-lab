# Cluster 2: Worker-RAM, Rancher Monitoring und Argo CD

Stand 11.10.2026: Beide Worker mit 4 vCPU / 16 GB RAM wieder Ready und schedulable.
Rancher Monitoring und Argo CD sind über Fleet installiert; 40/40 Plattform-Bundles
sind Ready. Beide Demo-Anwendungen sind Synced/Healthy und über ihre DNS-Namen erreichbar.
OIDC, Tenant-Rechte, direkte Netzwerkisolation und Egress wurden live geprüft.
Die folgenden Wartungsabschnitte dokumentieren den Ablauf; der Abschluss steht unter Abnahme.

## Wartungsfolge

Der Betreiber erweitert beide Worker von 12 auf 16 GB RAM. Immer nur ein Worker
wird ausgeschaltet. Worker 1 wurde cordoned und mit dem regulären Eviction-API-Drain
geleert, ohne PDBs zu umgehen. Der zentrale Fluentd samt bestehendem Longhorn-PVC
läuft danach auf Worker 2. Node-lokale Fluent-Bit-Queues bleiben auf der VM erhalten.
Während ein Longhorn-Worker fehlt, besteht reduzierte Speicherredundanz.

Vor Worker 2: Worker 1 Ready, 16 GB sichtbar, wieder uncordoned; alle aktiven
Longhorn-Volumes healthy, Replikate wieder auf beiden Workern und Collector gesund.
Harbor/PostgreSQL/Redis/OpenSearch waren vor dieser Wartung auf Worker 2 konzentriert.
Ein pauschaler paralleler Drain oder eine PDB-Umgehung ist ausgeschlossen. Replikate
und Dienste müssen einzeln nach Worker 1 verlagert werden; ein blockierender
PostgreSQL-Primary erfordert einen geplanten Switchover. MinIO und der einzelne
Fluentd-Pod haben beim Rescheduling eine kurze Unterbrechung; ihre PVCs bleiben erhalten.

Rückfall: Keine VM-Datenträger oder PVCs löschen. Den noch funktionierenden Worker
weiterlaufen lassen, den anderen reparieren/zurückstarten. Keine weiteren Evictions,
wenn Speicher-/Datenbankquorum oder Wiederanlauf nicht gesund sind. Worker nach der
Prüfung wieder freigeben; dauerhafte Scheduling-Änderungen im Repo dokumentieren.

## Historischer Wartungsstand vor dem zweiten RAM-Ausbau

Am 11.10.2026 ist Worker 1 mit 16 GB RAM zurück, Ready und schedulable.
Nach dem Wiederaufbau der Longhorn-Replikate wurden PostgreSQL und OpenSearch
nach Worker 1 verlagert. Beim OpenSearch-Umzug wurde die vollständige Shard-Erholung
abgewartet; Pod-Readiness allein ist dafür kein ausreichendes Kriterium.

Nach ausdrücklicher Betreiberfreigabe wurde genau einmal `SENTINEL FAILOVER mymaster`
ausgelöst. `redis-replication-1` wurde Master auf Worker 1, der bisherige Master
`redis-replication-2` anschließend als Replika per Eviction verschoben. Zwei gesunde
Replica-Links und drei übereinstimmende Sentinels mit Quorum wurden geprüft.

Replizierte Harbor-/Dashboard-/NeuVector-Dienste wurden einzeln verdrängt und jeweils
auf vollständige Pod-Readiness geprüft. Der anschließende reguläre Drain von Worker 2
war erfolgreich, ohne `--force` oder `--disable-eviction`. Auf Worker 2 verblieben nur
DaemonSet-Pods. Alle 14 aktiven Volumes waren danach auf Worker 1 angebunden; kein
Volume war faulted. MinIO und Fluentd waren Ready, Harbor vollständig healthy,
PostgreSQL-/Redis-Anwendungszugriffe erfolgreich und OpenSearch green.

[Prüfprotokoll vor dem Ausschalten](validation/worker2-memory-drain-20261011.json).
Die VM-Aufrüstung von Worker 2 steht zu diesem Zeitpunkt noch aus. Worker 2 bleibt
cordoned. Nach Rückkehr: neue Boot-ID und 16 GB prüfen, uncordon, Longhorn-Replikate
wiederherstellen und Datenbank-/Dienstreplikate kontrolliert auf beide Worker verteilen.
Erst danach die vorbereiteten Monitoring-/Argo-CD-Bundles aktivieren.
Die zentrale Installation und die Argo-Tenant-Abnahme sind noch nicht erfolgt.

## Reparierter Ausgangsbefund

Der Fluentd-Sidecar `buffer-metrics-sidecar` wurde wiederholt mit `OOMKilled` beendet:
Chart-Standardlimit `10M`. Fleet setzt auf Cluster 2 über
`loggingOverlay.spec.fluentd.bufferVolumeResources` jetzt 32 MiB Request und 128 MiB
Limit. Der Collector kam nach dem gepufferten Volume-Umzug mit 3/3 Containern zurück.
Diese Metrik-Lücke betraf den Sidecar; Fluentd selbst war beim Befund weiter aktiv.

## Rancher Monitoring über Fleet

Gepinnter Chart: `109.0.6+up80.9.1-rancher.22`, laut Rancher-Chart-Metadaten für
Rancher >=2.14 und <2.15. Der passende CRD-Chart wird vor dem Hauptchart installiert.
Nur Cluster 2 (`environment=lab`, `role=infrastructure`) ist Ziel.

- Namespace `cattle-monitoring-system`, Systemprojekt `c-44q9v:p-6qghv`.
- Prometheus: eine Lab-Instanz, Longhorn 10 GiB, 7 Tage / 8 GB Retention,
  768 MiB Request und 2 GiB Limit; keine HA-Zusage.
- Alertmanager: eine Instanz, Longhorn 1 GiB. Externe Alarmempfänger fehlen weiterhin.
- Grafana: Longhorn 1 GiB, Zugang über Rancher. Kein zusätzlich öffentlich freigegebener Ingress.
- RKE2-Control-Plane-/etcd-Scrapes über Ranchers PushProx. Kein kube-proxy-/Nginx-Scrape,
  da Cluster 2 Cilium mit kube-proxy replacement verwendet.
- Bestehende AFI-Logging-Service-/PodMonitors und die sieben Alarmregeln werden übernommen.
  Nach positiver Abnahme ist der bisherige kleine Logging-Prometheus auf null Replikate
  skaliert. StatefulSet und sein bestehendes 2-GiB-PVC bleiben für einen Rückfall erhalten.

Die zentralen Monitoring-Daten sind Plattformdaten. Diese Installation allein liefert
keinen mandantenweisen PromQL-/Grafana-Zugriffsschutz; dafür wären separate
Datenquellen/Abfragegrenzen erforderlich. Nach ausdrücklicher Folgeentscheidung des
Betreibers erhalten alle Mandantengruppen gemeinsamen Viewer-Zugriff auf diese
clusterweiten Daten. Das Tenant-Repository verwaltet dafür `terraform/monitoring.tf`
und dokumentiert die Grenzen in `docs/monitoring.md`. Monitoring-Konfiguration, Secrets
und Workloads im Systemnamespace bleiben geschützt. Prometheus Federator bleibt auf
Wunsch des Betreibers vorerst uninstalliert.

## Zentrales Argo CD

Gepinnter Chart `argo-cd` 10.10.2, App-Version 3.5.4. Eine zentrale Lab-Installation
auf Cluster 2, erreichbar über Cilium-Ingress `192.168.1.195` und
`https://argocd.berger.ph`. DNS ist vom Betreiber gesetzt.

Fleet besitzt Installation, Netzwerkzugänge, TLS-/ESO-Zustellung und Basiskonfiguration.
Ein dedizierter Keycloak-Client `afi-argocd` im Realm `berger` verwendet Authorization
Code mit PKCE S256 und ausschließlich den Callback `/auth/callback` dieses Hosts.
Direkte Passwort-Grants und Client-Serviceaccounts sind aus. Ein lokaler Argo-CD-Admin
bleibt als Notfallzugang erhalten; sein Passwort liegt ausschließlich in OpenBao.
Bestehende Rancher-/Harbor-/OpenSearch-Clients werden nicht verändert.

`bootstrap-argocd.py` besitzt den neuen globalen Client sowie die technischen Zugänge.
ESO darf nur die drei dedizierten OpenBao-Pfade lesen; private Schlüssel und Client-
Secrets gelangen nicht in Git. Fleet erstellt `argocd-secret` nicht selbst, sodass
Helm und ESO keine konkurrierenden Feldbesitzer sind. Server-TLS endet am Cilium-Ingress;
der interne Serverport ist HTTP. Redis und Repo-Server erhalten nur namespaceinternen
Ingress, Metrikports zusätzlich aus `cattle-monitoring-system`.

Terraform besitzt je Mandant AppProject, öffentliche projektgebundene Repo-Registrierung
und optional die erste Demo-Application. Auch die zentrale RBAC-ConfigMap gehört
ausschließlich Terraform; Fleet setzt `configs.rbac.create=false`. Admin-/Developer-Gruppen dürfen eigene Apps
lesen, anlegen, ändern und synchronisieren; Admins zusätzlich löschen. Kein Exec,
kein Manifest-Override, keine Project-Administration oder fremde Application-Rechte.
Der Standardrolle werden keine Leserechte gegeben; das Default-Projekt ist gesperrt.
ApplicationSet-Controller ist mit null Replikaten vorbereitet, nicht für Mandanten aktiviert.
Das gesperrte `default`-AppProject liegt im nachgelagerten Fleet-Bundle
`lab-infra-argocd-policy`: Der Argo-Chart installiert seine CRDs als Templates,
daher kann das AppProject beim allerersten Helm-Lauf noch nicht mitgebaut werden.
Das Policy-Bundle darf ausschließlich dieses von Argo gegebenenfalls automatisch
erzeugte Standardprojekt übernehmen (`helm.takeOwnership=true`). Die Tenant-Abnahme
erfolgte nach erfolgreicher Default-Projektsperre. Insgesamt sind sechs neue
Bundles und damit 40 Plattform-BundleDeployments aktiv.

Destination-Namespaces folgen `<mandant>-*`. Die vorhandene Namespace-Admission prüft
Pflichtpräfix und autorisierte Projektzuordnung. Terraform verhindert überlappende
Mandantennamen wie `mandant-a` und `mandant-a-team`. Keine automatische Namespace-
Erstellung durch Argo: Fachbereiche erstellen neue Namespaces zuerst im eigenen
Rancher-Projekt. Clusterweite Ressourcen, Rollenbindungen, Netzwerk-/Admission-Policies
und Plattformobjekte sind nicht in der AppProject-Allowlist.

Der zentrale Argo-Controller ist ein privilegierter Plattformdienst. AppProjects
begrenzen normale Tenant-Syncs; eine Kompromittierung des Controllers oder privilegierte
Workload-Zugriffe werden dadurch nicht zu einer harten Cluster-Sicherheitsgrenze.
Die bestehende offene Pod-Security-Härtung bleibt ein separates Arbeitspaket.

## Demo-Repositories

- A: `https://github.com/steph76k/rke2-argocd-lab-mandant-a.git`
- B: `https://github.com/steph76k/rke2-argocd-lab-mandant-b.git`

Beide sind öffentlich, daher keine Git-Credentials nötig. Nur diese exakten Repo-URLs
werden ihrem jeweiligen AppProject erlaubt. Je zwei kleine, unprivilegierte Nginx-Pods
zeigen eine unterscheidbare Tenant-Seite; Image per Digest fixiert. Terraform legt die
Application an, Argo CD besitzt Deployment/Service/ConfigMap/Ingress.

`mandant-a-demo.berger.ph` und `mandant-b-demo.berger.ph` zeigen HTTP-Demoseiten ohne
Zugangsdaten. Beide DNS-Namen zeigen inzwischen auf `.195`; direkte HTTP-Aufrufe
über DNS liefern jeweils Status 200 und die passende, unterschiedliche Mandantenseite.
Alternativ Port-Forward oder `curl --resolve` wie in den Demo-READMEs. Automatischer Sync,
Prune und Self-Heal sind nur für diese neuen Anwendungsressourcen aktiviert.

## Abnahme

Die sanitisierten Ergebnisse liegen unter [validation/monitoring-argocd-20261011](validation/monitoring-argocd-20261011).

- Fünf Nodes Ready und schedulable, beide Worker mit 4 vCPU und 16 GB RAM.
  16 angebundene Longhorn-Volumes healthy, kein faulted Volume. Datenbank-, Redis-,
  OpenSearch- und replizierte Dienst-Pods sind wieder auf beide Worker verteilt.
- 40/40 Plattform-BundleDeployments Ready. Beide Argo-Applications Synced/Healthy;
  jeweils zwei Demo-Pods, einer pro Worker. Keine verbliebenen Argo-Testidentitäten.
- Alle 55 erfassten Monitoring-Targets up, darunter zwölf Logging- und drei Argo-Targets.
  Sieben AFI-Logging-Regeln gesund; Grafana über Rancher-Proxy HTTP 200 / database ok.
  Vorhandene CPU-Throttling-Alarme und der bestehende NeuVector-Exporter-CrashLoop bleiben
  sichtbar. Ein externer Alertmanager-Empfänger ist weiterhin offen.
- Fünf frische OIDC-Identitäten geprüft: A/B jeweils Admin und Developer sowie ein Benutzer
  ohne Tenant-Gruppe. Alle verwenden PKCE S256. Eigene Apps erstellen/ändern/synchronisieren
  erlaubt; Löschen nur für Admins. Fremde Projekte/Apps und Projektänderungen ergeben 403;
  fremde Namespaces/Repositories sowie Plattform-Namespaces werden beim Anlegen abgewiesen.
  Der Benutzer ohne Tenant-Gruppe sieht keine Applications.
- Beide HTTP-Demoseiten antworten über DNS mit 200. Alle 16 direkten Pod-Verbindungstests
  bestanden: acht innerhalb desselben Mandanten erlaubt, acht zwischen A/B blockiert,
  einschließlich beider Worker. Terraform erlaubt den reservierten Cilium-Ingress nur auf
  TCP 8080 zu den exakt bezeichneten Demo-Pods im jeweils geschützten Rancher-Projekt.
- Egress nach beiden Neustarts geprüft: A `.200`/`.201`, B `.202`/`.203`, jeweils passend
  zu Worker 1/2. IP-Aliase blieben nach dem Neustart erhalten.
- Terraform hat neun Argo-Ressourceninstanzen ergänzt. Abschließender Plan ohne Änderungen.
  Ein nicht angewendeter Plan für einen zusätzlichen Mandanten C erzeugte 36 neue Ressourcen,
  fünf notwendige zentrale Aktualisierungen und keine Löschungen. Seine temporäre Deklaration
  wurde entfernt; die bisherigen Mandanten werden nicht neu angelegt.

Wiederholbare Prüfprogramme im Plattformrepo:

- `scripts/afi-isolation/verify-monitoring.py`: Targets, Regeln und Rancher-Grafana-Zugang.
- `scripts/afi-isolation/verify-argocd.py`: echte OIDC-Anmeldungen, erlaubte Operationen und
  Negativtests; erzeugt temporäre Benutzer/unsynchronisierte Apps und entfernt sie anschließend.
- `scripts/afi-isolation/verify-argocd-network.py`: HTTP-Seiten und direkte Pod-Isolation.

Die Programme dokumentieren ihre erforderlichen Kubeconfig-/CA-/Ausgabeargumente mit
`--help`. Zugangsdaten werden zur Laufzeit aus der bestehenden OpenBao-Operatorumgebung
bezogen und nicht ausgegeben. Egress wird im Tenant-Repo mit `scripts/verify-egress.py` geprüft.

Die beim Worker-Start sichtbaren `Lockdown: pathWalker: /dev/mem,kmem,port is restricted`-
Meldungen stammen vom NeuVector-Prozess. Secure Boot und Kernel-Lockdown im Integrity-Modus
wurden auf Worker 2 bestätigt. Der Kernel verweigert den direkten Speicherzugriff;
Node und Enforcer wurden Ready. Secure Boot wurde nicht abgeschaltet. Dies ist kein Nachweis,
dass jede einzelne NeuVector-Scan-Funktion uneingeschränkt arbeitet.

## Quellen

- [Rancher Monitoring](https://ranchermanager.docs.rancher.com/v2.14/reference-guides/monitoring-v2-configuration/helm-chart-options)
- [Argo CD Keycloak](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/)
- [Argo CD Projects](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/)
- [Argo CD RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)

## Während der Erstinstallation bestätigte Korrekturen

- Der Prometheus-Adapter überschritt beim Start sein ursprüngliches 256-MiB-Limit.
  Fleet setzt jetzt 128 MiB Request, 768 MiB Limit und `GOMEMLIMIT=600MiB`.
  Der neue Pod wurde Ready ohne Neustart. Einmalig wurden dieselben bereits
  veröffentlichten Werte live gepatcht, um den wartenden ersten Helm-Installationslauf
  freizugeben; anschließend übernahm Fleet wieder die Konfiguration.
- Fleet 0.15.4 verwendet für neue Helm-Releases Server-Side Apply mit gemeinsamem
  Feldmanager `fleetagent`, auch für das minimale Release-Namespace-Objekt. Das
  entfernt im vorab durch das Secrets-Bundle erzeugten Namespace die von demselben
  Manager gesetzte Projektannotation, während Ranchers Projektlabel erhalten bleibt.
  Ein Server-Dry-Run reproduzierte die korrekte Ablehnung durch
  `afi-project-label-integrity`. Die Admission bleibt unverändert aktiv.
  Der dedizierte Argo-Chart nutzt `helm.takeOwnership=true`, wodurch diese Fleet-Version
  auf den Dreiwege-Merge umschaltet. ESO-Secrets bleiben vom Chart ausgeschlossen.
  Alle Argo-Bundles erhalten dieselben Namespace-Projekt- und Owner-Metadaten.
  [Fleet-Implementierung](https://github.com/rancher/fleet/blob/v0.15.4/internal/helmdeployer/install.go).
- Rancher Monitoring erreichte alle 12 Logging-Targets und wertete die sieben
  AFI-Logging-Regeln erfolgreich aus; Grafana war über den authentifizierten Rancher-
  Proxy gesund. Deshalb wurde der alte `afi-logging-prometheus` auf null Replikate
  gesetzt. StatefulSet und PVC bleiben für die Rückkehr auf eine Replik erhalten.
