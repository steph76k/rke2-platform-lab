# Mandanten A/B auf Cluster 2: Umsetzung und Betrieb

Stand 11.10.2026: A/B sind vollständig von Cluster 1 nach Cluster 2 umgezogen.
Rancher-Projekt-Isolation, Cilium Egress Gateway und Terraform-Egress-Verwaltung
sind aktiv. Der angepasste Rollout mit vier IPs wurde ausdrücklich freigegeben.

## Mandanten und Egress

| Mandant | Rancher-Projekt auf Cluster 2 | Worker 1 | Worker 2 |
| --- | --- | --- | --- |
| A | `c-44q9v:p-p2q7n` | `192.168.1.200` | `192.168.1.201` |
| B | `c-44q9v:p-j79sh` | `192.168.1.202` | `192.168.1.203` |

Jeder Mandant hat dev/test/prod-Namespaces. Die drei ExternalSecrets von A wurden
übernommen, Zielwerte vor Entfernen der Quelle im Speicher identisch verglichen.
Die sechs alten Namespaces enthielten keine Workloads/PVCs. Nach erfolgreichen
Rancher-, Netzwerk-, Logging- und Secret-Tests wurden die alten Projekte/Namespaces,
ESO-Stores/ServiceAccounts/Bindings und die Auth-Mounts `rke2-cluster1` in den beiden
OpenBao-Mandanten entfernt. KV-Daten, Gruppen, Harbor-Projekte und historische
Mandantenlogs bleiben erhalten. Der gemeinsame State wurde nicht dupliziert.

`rke2-tenants-lab/terraform/egress.tf` besitzt Reservierungen, persistente Node-Adressen
und CiliumEgressGatewayPolicies. `new-tenant.py` vergibt zwei freie IPs aus `.200–.220`;
der Pool reicht für zehn Mandanten. Ein neuer Mandant wurde mit `.204/.205` als Plan
geprüft: 32 Creates, nur die zentrale Reservierungsliste wird aktualisiert,
keine Änderungen an A/B. Testdeklaration danach entfernt; kein Apply dieses Tests.
Keine statischen Tenant-Policies oder Adressskripte im Plattformrepo parallel anwenden.

## Plattformkonfiguration und Ownership

Cilium 1.19.6: `egressGateway.enabled: true`, Agent-Rollout mit `maxUnavailable: 1`.
Alle fünf Agents und beide Operator-Replikate wurden nach dem freigegebenen Rollout
bereit bestätigt. Die bestehende NetworkManager-Verbindung `ens33` behält ihre
primäre Node-IP und Route; Terraform ergänzt pro Mandant je eine `/32`-Adresse.
Der Helfer prüft ARP-Konflikte, Hostidentität und Eigentum, serialisiert Änderungen
und nutzt ausschließlich vorhandenen administrativen SSH-Zugang als `ansible`.

Die vollständige HelmChartConfig steht unter `config/afi-isolation/egress/cluster2-cilium.yaml`.
Sie dokumentiert die Plattform-Voraussetzung und liegt außerhalb aktiver Fleet-Pfade.
Die aktive RKE2-Quelle auf CP-1 wurde unter
`/var/lib/rancher/rke2/server/manifests/ansible_managed_0/cilium.yaml` aktualisiert.
CP-2/3 besitzen keine entsprechende zusätzliche HelmChartConfig-Quelldatei;
ihre eingebauten HelmChart-Manifeste wurden nicht verändert. Die lokale Ansible-Quelle
`rancher/rke2/inventories/rke2-cluster2/pre-deploy-manifests/cilium.yaml` wurde angeglichen.

Der Betreiber aktivierte die Projekt-Isolation direkt am Management-Cluster-Objekt:

```bash
kubectl --context=rancher patch clusters.management.cattle.io c-44q9v \
  --type=merge -p '{"spec":{"enableNetworkPolicy":true}}'
```

Für diesen importierten Cluster ist das Management-Objekt maßgeblich. Rancher
bestätigt `status.appliedEnableNetworkPolicy=true` und erzeugt `np-default`/`hn-nodes`
in allen sechs Projekt-Namespaces. Terraform besitzt deren Projektzuordnung,
Rancher die generierten Policies. Das System-Projekt ist als Ingress-Quelle erlaubt.
Nicht zugeordnete Infrastruktur-Namespaces erhalten dadurch keine automatische Isolation.

## Nachweise

- Netzwerk: 16/16 Fälle, eigenes Projekt auch über Worker-Grenzen erreichbar,
  A→B/B→A auf beiden Workern gesperrt.
- Rancher: echte OIDC-Anmeldung mit PKCE S256 für A/B-Developers und die bestehende
  A-Gruppe; eigenes Projekt und alle eigenen Namespace-Podlisten HTTP 200,
  fremdes Projekt und fremde Namespace-Podlisten HTTP 403. Temporäre Benutzer entfernt.
- Egress: alle vier erwarteten IPs an einem externen LAN-Empfänger beobachtet,
  auch nach Aktivierung der Projekt-Isolation.
- Logging: echte A/B-Podmarker auf Cluster 2, Label-/JSON-Manipulation ohne Umgehung,
  Forward-Port gesperrt, OpenSearch eigene Logs 200/fremde 403.
- Persistenz: echter Cluster-2-Collector ersetzt, gleicher PVC und Queue nach Neustart,
  50/50 eindeutige Marker, keine Duplikate. Nur synthetischer Ausgang unterbrochen.
- Harbor healthy, OpenSearch green, Rancher/Keycloak/OpenBao/MinIO erreichbar,
  alle zehn ClusterSecretStores Ready.

Belege: `tests/afi-isolation/results/routing-cluster2.json`,
`tests/afi-isolation/results/collector-persistence-cluster2.json` und
`rke2-tenants-lab/tests/results/` (Isolation, Rancher, Egress, Migration, Onboarding).
Cluster 2 verwendet drei Logging-Ausgänge mit je 4 GiB Budget auf dem 20-GiB-PVC;
Cluster 1 nach Leerung beider Tenant-Puffer nur noch den Plattformausgang.

## CPU-Erweiterung und Rancher-VM

Alle fünf Cluster-2-Nodes besitzen vier vCPU; Control Planes je 6 GB, Worker je 12 GB RAM.
Worker 1 wurde mit regulären Evictions vorbereitet und nach Rückkehr freigegeben.
Alle 14 aktiven Longhorn-Volumes besitzen wieder je zwei RW-Replikate auf unterschiedlichen
Workern; siehe `docs/validation/worker1-cpu-return-20261011.json`.
Rancher ist nach dem kalten VM-Umzug bei unveränderter IP/DNS erreichbar.
OpenBao wurde durch den Betreiber entsiegelt, ESO und Fleet haben sich erholt.

Vorher-Sicherungen liegen SOPS-verschlüsselt außerhalb der Rancher-VM unter
`/home/tanzu/manifest/backups/afi-rancher-vm-move-2026-10-11/`,
`afi-tenant-move-2026-10-11/` und `afi-egress-2026-10-11/`.
Das geprüfte Rancher-Ressourcenbackup enthält 1651 Archiveinträge; es ersetzt kein
vollständiges VM-/K3s-Datastore-Backup. Der tägliche Backup-Auftrag wurde vom fehlenden
`rancher-resource-set` auf den vorhandenen `rancher-resource-set-full` korrigiert;
Zeitplan und Aufbewahrungsanzahl bleiben unverändert. Der reparierte Auftrag hat am
11.10.2026 um 11:54:48 UTC erfolgreich gesichert (`Ready`/`Uploaded` true);
nächster Lauf: 12.10.2026 00:00 UTC.

## Grenzen und Rücknahme

Die zwei IPs ermöglichen Egress nach Neuplanung auf dem verbleibenden Worker.
Sie sind keine schwebenden HA-Adressen: bestehende Verbindungen werden nicht übernommen,
und externe Allowlisten müssen beide IPs erlauben. Private IPs sind im LAN sichtbar;
ein nachgelagertes Internet-NAT kann sie erneut übersetzen. Neue Pods können vor
Cilium-Policy-Reconciliation kurz ihre bisherige Quell-IP verwenden.
Rancher-PNI ersetzt weder Egress-Firewall noch Pod-Security-Regeln für privilegierte
oder HostNetwork-Workloads. Kein destruktiver Worker-Ausfalltest wurde durchgeführt.

SSH-Provisioner erkennen manuelle Änderungen an Node-Adressen nicht automatisch.
Prüfung über `gateway-address.py --check`; gezieltes Terraform `-replace` nur nach
Planprüfung, da es die jeweilige Adresse kurz entfernt. Kubernetes-Policies werden
regulär auf Drift geprüft. Details stehen im Tenantrepo unter `docs/egress.md`.

Für einen Rückbau zuerst betroffene Workloads stoppen/verlagern und im geprüften
Terraform-Plan die Tenant-Egress-Policies vor den zugehörigen Adressen entfernen.
Erst wenn keine Egress-Policies mehr darauf angewiesen sind, die gesicherte
HelmChartConfig samt Host-/Ansible-Quelle wiederherstellen und kontrolliert ausrollen.
Ein altes Terraform-State-Backup nicht blind über den aktuellen gemeinsamen State schreiben.

Quellen: [Cilium Egress Gateway](https://docs.cilium.io/en/stable/network/egress-gateway/egress-gateway/),
[RKE2 Network Options](https://docs.rke2.io/networking/basic_network_options),
[SUSE Projekt-Isolation](https://documentation.suse.com/cloudnative/rancher-manager/v2.11/en/cluster-deployment/configuration/rke2.html).

## Separater Befund

Der NeuVector-Prometheus-Exporter startet mit einem DNS-Fehler für
`neuvector-svc-controller-api`. Dieser Service existiert nicht im Namespace
`cattle-neuvector-system`. Die Mandanten-/Egress-Tests sind davon unabhängig;
die Reparatur dieser separaten NeuVector-Metrikanbindung bleibt offen.
