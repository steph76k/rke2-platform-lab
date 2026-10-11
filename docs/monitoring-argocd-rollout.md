# Cluster 2: Worker-RAM, Rancher Monitoring und Argo CD

Stand 11.10.2026, laufende Umsetzung. Dieser vorbereitete Ablauf ist noch kein
vollständiger Installations- oder Berechtigungsnachweis.

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
  Der bisherige kleine Logging-Prometheus bleibt bis zur positiven Abnahme verfügbar;
  eine Stilllegung erfolgt erst nach Prüfung von Targets und Regeln. Sein PVC wird behalten.

Die zentralen Monitoring-Daten sind Plattformdaten. Diese Installation allein liefert
keinen nachgewiesenen mandantenweisen PromQL-/Grafana-Zugriffsschutz; dafür wären
separate Datenquellen/Abfragegrenzen erforderlich. Keine zusätzlichen Cluster-Leserechte
werden allein aus dem Wunsch nach Monitoring für Fachbereiche zugesagt.

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
Zugangsdaten; für Browserzugriff müssen beide Namen ebenfalls auf `.195` zeigen.
Alternativ Port-Forward oder `curl --resolve` wie in den Demo-READMEs. Automatischer Sync,
Prune und Self-Heal sind nur für diese neuen Anwendungsressourcen aktiviert.

## Abnahme

Vor Abschluss: fünf Nodes mit erwarteter Kapazität Ready, aktive Volumes healthy,
Fleet-Bundles Ready; Prometheus-Targets und Alarmregeln prüfen, Grafana-/Rancher-Proxy
prüfen. Argo-OIDC mit frischen A/B-Admin-/Developer-Identitäten, eigene Apps erlaubt,
fremde Apps/Namespaces/Repos und Plattformrechte verweigert. Beide Apps Synced/Healthy,
HTTP-Seiten unterschiedlich, Egress-Zuordnung erhalten, Terraform-Nachplan ohne Drift.
Nur selbst erzeugte Testidentitäten und Prüfressourcen entfernen.

## Quellen

- [Rancher Monitoring](https://ranchermanager.docs.rancher.com/v2.14/reference-guides/monitoring-v2-configuration/helm-chart-options)
- [Argo CD Keycloak](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/)
- [Argo CD Projects](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/)
- [Argo CD RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
