# Inventar – 10. Oktober 2026, ca. 10:25–10:36 UTC

Lesend erfasst mit kubectl, Helm und bao. Keine Deinstallation, Token-Erzeugung,
Policy-Änderung oder Secret-Synchronisierung wurde ausgeführt. Secret-Inhalte
werden hier nicht gespeichert. Die Zustände sind eine Momentaufnahme.

## Wesentliche Befunde und Migrationssperren

- Cluster 2: Longhorn-Helm-Release `failed`, Ursache `context deadline exceeded` bei Installation.
  Die Controller laufen; mehrere aktive Volumes sind trotzdem `degraded` (siehe PVC-Tabelle).
  Nur zwei Longhorn-Nodes sind registriert, StorageClass fordert drei Replikas.
  Das erklärt möglicherweise die eingeschränkte Redundanz; keine automatische Reparatur vorgenommen.
  Beide Longhorn-Nodes melden zusätzlich `KernelModulesLoaded=False` für `dm_crypt`.
  Vor Datenmigration Storage-Zustand gesondert prüfen/freigeben; Neuaufbau allein behebt dies nicht.
- NeuVector Prometheus Exporter: 0/1 Ready; außerhalb des Migrationsumfangs.
- Harbor verwendet Redis-Master-Service auf 6379, obwohl drei Sentinel-Pods auf 26379 laufen.
  Sentinel-Mastername `mymaster`; kein direktes Sentinel-Target in Harbor-Values.
- OpenSearch: Admin-Passwort bisher als direktes Helm-Environment-Value; Dashboards mit
  Demo-Servicekonto, deaktivierter Backend-TLS-Verifikation und HTTP-Ingress ohne TLS.
  Keine dieser Zugangsdaten wird in Git übernommen. Die neuen Bundles sind für einen frischen
  Sicherheitsindex mit neu erzeugten Konten und eigener Lab-CA vorbereitet.
- `default` enthält drei ältere OpenSearch-PVCs (je 8Gi) außerhalb des aktuellen Releases.
  Sie sind ausdrücklich von der geplanten Löschung ausgeschlossen.
- Cluster-2-Kubeconfig nutzt Rancher-Proxy. Für Kubernetes-TokenReview benötigt OpenBao
  den direkten API-Endpunkt, nicht Rancher-Authentifizierung.

## Rancher und Fleet

Rancher 2.14.3; Fleet 0.15.4. GitRepo `fleet-default/rke2-platform`:
`https://github.com/steph76k/rke2-platform-lab.git`, Branch `main`.
Erfasster Ausgangscommit: `78d14a3403b9daae4a9791be60420c8dfb0407b1`.
GitRepo Ready, 2/2 BundleDeployments. Ausschließlich diese Live-Pfade sind aktiv:

```yaml
paths:
  - bundles/00-bootstrap-test
  - bundles/application/operators/external-secrets
```

`lab-bootstrap-test` zielt auf `fleet-default/c-44q9v` (environment=lab, role=infrastructure).
`lab-app-external-secrets` zielt auf `fleet-default/rke2-cluster1` (environment=lab, role=applications).
Fleet-Agent-Bundles sind systemverwaltet und bleiben unverändert.
Alle neuen Dateien unter `bundles/infrastructure` sind außerhalb der Live-Pfade.

## Cluster und Helm-Releases

### management

| Node | Kubernetes | Ready |
| --- | --- | --- |
| rancher | v1.33.13+k3s1 | True |

| Namespace | Release | Chart | App-Version | Revision | Status |
| --- | --- | --- | --- | --- | --- |
| aif-operator | aif-operator | aif-operator-2.0.1 | 2.0.1 | 1 | deployed |
| cattle-ui-plugin-system | aif-ui-server | aif-ui-2.0.1 | 2.0.1 | 1 | deployed |
| cert-manager | cert-manager | cert-manager-v1.19.6 | v1.19.6 | 7 | deployed |
| cattle-fleet-system | fleet | fleet-109.0.4+up0.15.4 | 0.15.4 | 9 | deployed |
| cattle-fleet-local-system | fleet-agent-local | fleet-agent-local-v0.0.0+s-6cda5a8fbd44b62a1e4d129f338f2793b1769a65a1ec5542e58b558076fe7 |  | 8 | deployed |
| cattle-fleet-system | fleet-crd | fleet-crd-109.0.4+up0.15.4 | 0.15.4 | 6 | deployed |
| openbao | openbao | openbao-0.30.0 | v2.7.0 | 1 | deployed |
| cattle-system | rancher | rancher-2.14.3 | v2.14.3 | 6 | deployed |
| cattle-resources-system | rancher-backup | rancher-backup-108.0.4+up9.0.4 | v9.0.4 | 3 | deployed |
| cattle-resources-system | rancher-backup-crd | rancher-backup-crd-108.0.4+up9.0.4 | v9.0.4 | 3 | deployed |
| cattle-turtles-system | rancher-turtles | rancher-turtles-109.0.3+up0.26.3 | 0.26.3 | 3 | deployed |
| cattle-system | rancher-webhook | rancher-webhook-109.0.3+up0.10.7 | 0.10.7 | 7 | deployed |
| cattle-system | system-upgrade-controller | system-upgrade-controller-106.0.0 | v0.15.2 | 2 | deployed |
| kube-system | traefik | traefik-39.0.201+up39.0.2 | v3.6.9 | 4 | deployed |
| kube-system | traefik-crd | traefik-crd-39.0.201+up39.0.2 | v3.6.9 | 4 | deployed |

Namespaces: `aif-operator`, `c-44q9v`, `c-44q9v-p-6qghv`, `c-44q9v-p-xmzdw`, `c-m-prkskj2p`, `c-m-prkskj2p-p-9nh78`, `capv-system`, `cattle-capi-system`, `cattle-fleet-clusters-system`, `cattle-fleet-local-system`, `cattle-fleet-system`, `cattle-global-data`, `cattle-global-nt`, `cattle-impersonation-system`, `cattle-local-user-passwords`, `cattle-resources-system`, `cattle-system`, `cattle-tokens`, `cattle-turtles-system`, `cattle-ui-plugin-system`, `cert-manager`, `cluster-fleet-default-c-44q9v-a779df149bba`, `cluster-fleet-default-rke2-cluster1-3be31f11de00`, `cluster-fleet-local-local-1a3d67d0a899`, `default`, `fleet-default`, `fleet-local`, `kube-node-lease`, `kube-public`, `kube-system`, `local`, `openbao`, `p-6cfc4`, `p-9gcht`, `p-hqrb7`, `p-n5269`, `p-ntn7c`, `rke2-bootstrap-system`, `rke2-control-plane-system`, `u-3wp5atkrpd`, `user-bcld2`, `wg-easy`.

### applications

| Node | Kubernetes | Ready |
| --- | --- | --- |
| rke2-cluster1-cp-1.berger.ph | v1.33.7+rke2r1 | True |
| rke2-cluster1-cp-2.berger.ph | v1.33.7+rke2r1 | True |
| rke2-cluster1-cp-3.berger.ph | v1.33.7+rke2r1 | True |
| rke2-cluster1-wk-1.berger.ph | v1.33.7+rke2r1 | True |
| rke2-cluster1-wk-2.berger.ph | v1.33.7+rke2r1 | True |

| Namespace | Release | Chart | App-Version | Revision | Status |
| --- | --- | --- | --- | --- | --- |
| alertmanager-mcp-server | alertmanager-mcp-server | mcp-alertmanager-0.1.0 | latest | 3 | deployed |
| alloy | alloy | alloy-1.8.2 | v1.16.1 | 8 | deployed |
| cert-manager | cert-manager | cert-manager-v1.21.1 | v1.21.1 | 1 | deployed |
| event-generator | event-generator | event-generator-0.4.0 | 0.13.0 | 1 | deployed |
| external-secrets | external-secrets | external-secrets-2.11.0 | v2.11.0 | 1 | deployed |
| falco | falco | falco-9.0.0 | 0.44.0 | 30 | deployed |
| cattle-fleet-system | fleet-agent-rke2-cluster1 | fleet-agent-rke2-cluster1-v0.0.0+s-ded5b584168fdd0cc63da8a2d55e30313ffbfe97a7581fcadd58cc5e8f795 |  | 7 | deployed |
| gpu-operator | gpu-operator | gpu-operator-v26.3.3 | v26.3.3 | 10 | deployed |
| grafana-mcp | grafana-mcp | grafana-mcp-0.22.0 | 1.3.0 | 3 | deployed |
| kubernetes-mcp-server | kubernetes-mcp-server | kubernetes-mcp-server-0.1.0 | 0.0.67 | 7 | deployed |
| loki | loki | loki-7.3.0 | 3.6.12 | 7 | deployed |
| longhorn-system | longhorn | longhorn-108.0.0+up1.8.2 | v1.8.2 | 10 | deployed |
| longhorn-system | longhorn-crd | longhorn-crd-108.0.0+up1.8.2 | v1.8.2 | 11 | deployed |
| cattle-system | mcc-rke2-cluster1-managed-system-upgrade-controller | system-upgrade-controller-109.0.2 | v0.19.1 | 3 | deployed |
| llm-d-mini | mini | llm-d-router-standalone-v0.10.0 | v0.10.0 | 3 | deployed |
| mlflow | mlflow | mlflow-0.1.0 | 3.14.0 | 13 | deployed |
| jupyterhub | my-jupyter | jupyterhub-4.4.0 | 5.5.0 | 4 | deployed |
| n8n | n8n | n8n-1.15.11 | 1.112.6 | 2 | deployed |
| proemtheus-mcp-server | prometheus-mcp-server | prometheus-mcp-server-1.1.0 | 1.6.1 | 3 | deployed |
| ai | qdrant | qdrant-1.17.1 | v1.17.1 | 2 | deployed |
| cattle-monitoring-system | rancher-monitoring | rancher-monitoring-108.0.4+up77.9.1-rancher.14 | v0.85.0 | 3 | deployed |
| cattle-monitoring-system | rancher-monitoring-crd | rancher-monitoring-crd-108.0.4+up77.9.1-rancher.14 |  | 4 | deployed |
| cattle-system | rancher-webhook | rancher-webhook-109.0.3+up0.10.7 | 0.10.7 | 6 | deployed |
| kube-system | rke2-calico | rke2-calico-v3.31.200 | v3.31.2 | 4 | deployed |
| kube-system | rke2-calico-crd | rke2-calico-crd-v3.31.200 |  | 4 | deployed |
| kube-system | rke2-coredns | rke2-coredns-1.45.003 | 1.13.1 | 3 | deployed |
| kube-system | rke2-metrics-server | rke2-metrics-server-3.13.004 | 0.8.0 | 4 | deployed |
| kube-system | rke2-runtimeclasses | rke2-runtimeclasses-0.1.000 | 0.1.0 | 4 | deployed |
| kube-system | rke2-snapshot-controller | rke2-snapshot-controller-4.0.003 | v8.2.0 | 4 | deployed |
| kube-system | rke2-snapshot-controller-crd | rke2-snapshot-controller-crd-4.0.003 | v8.2.0 | 4 | deployed |
| kube-system | rke2-traefik | rke2-traefik-37.4.001 | v3.6.2 | 8 | deployed |
| kube-system | rke2-traefik-crd | rke2-traefik-crd-37.4.001 | v3.6.4 | 1 | deployed |
| default | surf-mcp | surf-mcp-0.1.0 | 0.1.0 | 1 | superseded |

Namespaces: `ai`, `aiops`, `alertmanager-mcp-server`, `alertmanager-servicenow-incident-bridge`, `alloy`, `calico-system`, `cattle-dashboards`, `cattle-fleet-system`, `cattle-impersonation-system`, `cattle-local-user-passwords`, `cattle-monitoring-system`, `cattle-system`, `cert-manager`, `default`, `event-generator`, `external-secrets`, `falco`, `gpu-operator`, `grafana-mcp`, `jupyterhub`, `keycloak`, `kube-node-lease`, `kube-public`, `kube-system`, `kubernetes-mcp-server`, `llm-d-mini`, `local`, `loki`, `longhorn-system`, `mandant-a-dev`, `mandant-a-prod`, `mandant-a-test`, `mlflow`, `n8n`, `openai-tunnel`, `openbao-demo`, `openclaw-access`, `proemtheus-mcp-server`, `qwen38`, `test`, `tigera-operator`, `trivy-system`, `vmware-exporter`.

### infrastructure

| Node | Kubernetes | Ready |
| --- | --- | --- |
| rke2-cluster2-cp-1.berger.ph | v1.33.13+rke2r2 | True |
| rke2-cluster2-cp-2.berger.ph | v1.33.13+rke2r2 | True |
| rke2-cluster2-cp-3.berger.ph | v1.33.13+rke2r2 | True |
| rke2-cluster2-wk-1.berger.ph | v1.33.13+rke2r2 | True |
| rke2-cluster2-wk-2.berger.ph | v1.33.13+rke2r2 | True |

| Namespace | Release | Chart | App-Version | Revision | Status |
| --- | --- | --- | --- | --- | --- |
| cnpg-system | cnpg | cloudnative-pg-0.29.1 | 1.30.1 | 1 | deployed |
| cattle-fleet-system | fleet-agent-c-44q9v | fleet-agent-c-44q9v-v0.0.0+s-ded5b584168fdd0cc63da8a2d55e30313ffbfe97a7581fcadd58cc5e8f795 |  | 2 | deployed |
| harbor-ha | harbor | harbor-1.19.2 | 2.15.2 | 3 | deployed |
| cert-manager | jetstack | cert-manager-v1.16.2 | v1.16.2 | 8 | deployed |
| fleet-poc | lab-bootstrap-test | lab-bootstrap-test-v0.0.0+git-78d14a3403b9 |  | 1 | deployed |
| longhorn-system | longhorn | longhorn-109.4.0+up1.12.1 | v1.12.1 | 1 | failed |
| longhorn-system | longhorn-crd | longhorn-crd-109.4.0+up1.12.1 | v1.12.1 | 1 | deployed |
| cattle-neuvector-system | neuvector | neuvector-109.0.6+up2.11.2 | 5.6.2 | 1 | deployed |
| cattle-neuvector-system | neuvector-crd | neuvector-crd-109.0.6+up2.11.2 | 5.6.2 | 1 | deployed |
| cattle-neuvector-system | neuvector-monitor | neuvector-monitor-109.0.6+up2.11.2 | 1.0.19 | 1 | deployed |
| opensearch | opensearch | opensearch-3.9.0 | 3.9.0 | 3 | deployed |
| opensearch | opensearch-dashboards | opensearch-dashboards-3.9.0 | 3.9.0 | 4 | deployed |
| cattle-logging-system | rancher-logging | rancher-logging-109.0.1+up4.10.0-rancher.24 | 4.10.0 | 2 | deployed |
| cattle-logging-system | rancher-logging-crd | rancher-logging-crd-109.0.1+up4.10.0-rancher.24 |  | 2 | deployed |
| cattle-system | rancher-webhook | rancher-webhook-109.0.3+up0.10.7 | 0.10.7 | 3 | deployed |
| harbor-ha | redis-operator | redis-operator-0.27.0 | 0.27.0 | 1 | deployed |
| harbor-ha | redis-replication | redis-replication-0.17.1 | 0.17.1 | 2 | deployed |
| kube-system | rke2-cilium | rke2-cilium-1.19.601 | 1.19.6 | 12 | deployed |
| kube-system | rke2-coredns | rke2-coredns-1.46.201 | 1.13.1 | 4 | deployed |
| kube-system | rke2-metrics-server | rke2-metrics-server-3.13.105 | 0.8.1 | 4 | deployed |
| kube-system | rke2-runtimeclasses | rke2-runtimeclasses-0.1.000 | 0.1.0 | 4 | deployed |
| kube-system | rke2-snapshot-controller | rke2-snapshot-controller-4.2.008 | v8.5.0 | 4 | deployed |
| kube-system | rke2-snapshot-controller-crd | rke2-snapshot-controller-crd-4.2.008 | v8.6.0 | 4 | deployed |
| cattle-system | system-upgrade-controller | system-upgrade-controller-109.0.2 | v0.19.1 | 2 | deployed |

Namespaces: `cattle-fleet-system`, `cattle-impersonation-system`, `cattle-local-user-passwords`, `cattle-logging-system`, `cattle-neuvector-system`, `cattle-system`, `cert-manager`, `cilium-secrets`, `cilium-test-1`, `cilium-test-ccnp1`, `cilium-test-ccnp2`, `cnpg-system`, `default`, `fleet-poc`, `harbor-ha`, `kube-node-lease`, `kube-public`, `kube-system`, `local`, `longhorn-system`, `opensearch`.

## Cluster 2: Workloads

| Namespace | Typ | Name | Ready/Soll |
| --- | --- | --- | --- |
| cattle-fleet-system | Deployment | fleet-agent | 1/1 |
| cattle-logging-system | Deployment | rancher-logging | 1/1 |
| cattle-neuvector-system | Deployment | neuvector-controller-pod | 3/3 |
| cattle-neuvector-system | Deployment | neuvector-manager-pod | 1/1 |
| cattle-neuvector-system | Deployment | neuvector-prometheus-exporter-pod | 0/1 |
| cattle-neuvector-system | Deployment | neuvector-scanner-pod | 3/3 |
| cattle-system | Deployment | cattle-cluster-agent | 2/2 |
| cattle-system | Deployment | rancher-webhook | 1/1 |
| cattle-system | Deployment | system-upgrade-controller | 1/1 |
| cert-manager | Deployment | jetstack-cert-manager | 1/1 |
| cert-manager | Deployment | jetstack-cert-manager-cainjector | 1/1 |
| cert-manager | Deployment | jetstack-cert-manager-webhook | 1/1 |
| cilium-test-1 | Deployment | client | 1/1 |
| cilium-test-1 | Deployment | client2 | 1/1 |
| cilium-test-1 | Deployment | client3 | 1/1 |
| cilium-test-1 | Deployment | echo-other-node | 1/1 |
| cilium-test-1 | Deployment | echo-same-node | 1/1 |
| cilium-test-ccnp1 | Deployment | client-ccnp | 1/1 |
| cilium-test-ccnp2 | Deployment | client-ccnp | 1/1 |
| cnpg-system | Deployment | cnpg-cloudnative-pg | 1/1 |
| default | Deployment | web | 1/1 |
| harbor-ha | Deployment | harbor-core | 2/2 |
| harbor-ha | Deployment | harbor-exporter | 1/1 |
| harbor-ha | Deployment | harbor-jobservice | 2/2 |
| harbor-ha | Deployment | harbor-portal | 2/2 |
| harbor-ha | Deployment | harbor-registry | 2/2 |
| harbor-ha | Deployment | redis-operator | 1/1 |
| kube-system | Deployment | cilium-operator | 2/2 |
| kube-system | Deployment | hubble-relay | 1/1 |
| kube-system | Deployment | rke2-coredns-rke2-coredns | 2/2 |
| kube-system | Deployment | rke2-coredns-rke2-coredns-autoscaler | 1/1 |
| kube-system | Deployment | rke2-metrics-server | 1/1 |
| kube-system | Deployment | rke2-snapshot-controller | 1/1 |
| longhorn-system | Deployment | csi-attacher | 3/3 |
| longhorn-system | Deployment | csi-provisioner | 3/3 |
| longhorn-system | Deployment | csi-resizer | 3/3 |
| longhorn-system | Deployment | csi-snapshotter | 3/3 |
| longhorn-system | Deployment | longhorn-driver-deployer | 1/1 |
| longhorn-system | Deployment | longhorn-ui | 2/2 |
| opensearch | Deployment | opensearch-dashboards | 1/1 |
| cattle-logging-system | StatefulSet | rancher-logging-fluentd | 1/1 |
| cattle-logging-system | StatefulSet | rancher-logging-root-fluentd | 1/1 |
| harbor-ha | StatefulSet | harbor-trivy | 1/1 |
| harbor-ha | StatefulSet | redis-replication | 3/3 |
| harbor-ha | StatefulSet | redis-replication-s | 3/3 |
| opensearch | StatefulSet | opensearch-cluster-master | 3/3 |
| cattle-logging-system | DaemonSet | rancher-logging-fluentbit | 2/2 |
| cattle-logging-system | DaemonSet | rancher-logging-rke2-journald-aggregator | 5/5 |
| cattle-logging-system | DaemonSet | rancher-logging-root-fluentbit | 5/5 |
| cattle-neuvector-system | DaemonSet | neuvector-enforcer-pod | 2/2 |
| cilium-test-1 | DaemonSet | host-netns | 2/2 |
| cilium-test-1 | DaemonSet | host-netns-non-cilium | 0/0 |
| kube-system | DaemonSet | cilium | 5/5 |
| kube-system | DaemonSet | cilium-envoy | 5/5 |
| longhorn-system | DaemonSet | engine-image-ei-ffc35c72 | 2/2 |
| longhorn-system | DaemonSet | longhorn-csi-plugin | 2/2 |
| longhorn-system | DaemonSet | longhorn-manager | 2/2 |

Die drei CNPG-Pods werden direkt vom Cluster-CR verwaltet, nicht als StatefulSet: `harbor-ha-db-1/2/3`, 3/3 Ready. Primärinstanz `harbor-ha-db-1`. PostgreSQL-Image `ghcr.io/cloudnative-pg/postgresql:16.3`.

### Ressourcen der zu migrierenden Dienste

| Workload | Container | Image | Requests/Limits |
| --- | --- | --- | --- |
| cnpg-cloudnative-pg | manager | ghcr.io/cloudnative-pg/cloudnative-pg:1.30.1 | {} |
| harbor-core | core | docker.io/goharbor/harbor-core:v2.15.2 | {} |
| harbor-exporter | exporter | docker.io/goharbor/harbor-exporter:v2.15.2 | {} |
| harbor-jobservice | jobservice | docker.io/goharbor/harbor-jobservice:v2.15.2 | {} |
| harbor-portal | portal | docker.io/goharbor/harbor-portal:v2.15.2 | {} |
| harbor-registry | registry | docker.io/goharbor/registry-photon:v2.15.2 | {} |
| harbor-registry | registryctl | docker.io/goharbor/harbor-registryctl:v2.15.2 | {} |
| redis-operator | redis-operator | quay.io/opstree/redis-operator:v0.27.0 | {"limits": {"cpu": "500m", "memory": "500Mi"}, "requests": {"cpu": "500m", "memory": "500Mi"}} |
| opensearch-dashboards | dashboards | opensearchproject/opensearch-dashboards:3.9.0 | {"limits": {"cpu": "500m", "memory": "1Gi"}, "requests": {"cpu": "100m", "memory": "512Mi"}} |
| harbor-trivy | trivy | docker.io/goharbor/trivy-adapter-photon:v2.15.2 | {"limits": {"cpu": "1", "memory": "2Gi"}, "requests": {"cpu": "200m", "memory": "512Mi"}} |
| redis-replication | redis-replication | quay.io/opstree/redis:v7.0.15 | {"limits": {"cpu": "500m", "memory": "512Mi"}, "requests": {"cpu": "100m", "memory": "256Mi"}} |
| redis-replication-s | sentinel | quay.io/opstree/redis-sentinel:v7.0.15 | {"limits": {"cpu": "200m", "memory": "256Mi"}, "requests": {"cpu": "50m", "memory": "128Mi"}} |
| opensearch-cluster-master | opensearch | opensearchproject/opensearch:3.9.0 | {"limits": {"cpu": "2", "memory": "2Gi"}, "requests": {"cpu": "250m", "memory": "1Gi"}} |

CNPG-Instanzen: requests 100m/256Mi, limits 500m/512Mi; 3 × 1Gi Longhorn. Anti-Affinität preferred; verteilt aktuell auf zwei Worker.

## Speicher und Eigentümer

| StorageClass | Provisioner | Reclaim | Bindung | Replikas |
| --- | --- | --- | --- | --- |
| longhorn | driver.longhorn.io | Delete | Immediate | 3 |
| longhorn-static | driver.longhorn.io | Delete | Immediate | default |

| Namespace/PVC | Kapazität | Zugriff | PV | Longhorn | Owner |
| --- | --- | --- | --- | --- | --- |
| cattle-logging-system/rancher-logging-fluentd-buffer-rancher-logging-fluentd-0 | 20Gi | ReadWriteOnce | pvc-ef3f8cb6-815c-4b07-828b-67ed0ae97871 | degraded | Logging/rancher-logging |
| default/opensearch-cluster-master-opensearch-cluster-master-0 | 8Gi | ReadWriteOnce | pvc-6d4b9597-2894-4362-9383-74b52c76f797 | unknown | kein OwnerReference |
| default/opensearch-cluster-master-opensearch-cluster-master-1 | 8Gi | ReadWriteOnce | pvc-599a1bdf-707b-4ec5-bf3f-7c2a38b0fee7 | unknown | kein OwnerReference |
| default/opensearch-cluster-master-opensearch-cluster-master-2 | 8Gi | ReadWriteOnce | pvc-881b91ed-d4f2-44ea-9552-0fef2ba5e3d8 | unknown | kein OwnerReference |
| harbor-ha/data-harbor-trivy-0 | 5Gi | ReadWriteOnce | pvc-d45f28bf-f6e3-4a86-8740-dad756162b1e | degraded | kein OwnerReference |
| harbor-ha/harbor-ha-db-1 | 1Gi | ReadWriteOnce | pvc-61156cf3-3f62-4dae-9ea0-6413ee6eb971 | degraded | Cluster/harbor-ha-db |
| harbor-ha/harbor-ha-db-2 | 1Gi | ReadWriteOnce | pvc-7571271b-dba9-4a2b-8207-b95371c256a0 | degraded | Cluster/harbor-ha-db |
| harbor-ha/harbor-ha-db-3 | 1Gi | ReadWriteOnce | pvc-c4f77396-507c-43e5-aa84-283617ab0f76 | degraded | Cluster/harbor-ha-db |
| harbor-ha/harbor-registry | 10Gi | ReadWriteMany | pvc-46623edd-8ac7-494f-b5bf-574b8bc90799 | degraded | kein OwnerReference |
| harbor-ha/redis-replication-redis-replication-0 | 2Gi | ReadWriteOnce | pvc-608c3883-99db-409f-9c8c-7be3ad7211a2 | degraded | kein OwnerReference |
| harbor-ha/redis-replication-redis-replication-1 | 2Gi | ReadWriteOnce | pvc-ee837b3c-e678-4dea-960e-71826819a79f | degraded | kein OwnerReference |
| harbor-ha/redis-replication-redis-replication-2 | 2Gi | ReadWriteOnce | pvc-eee42fe1-cde2-41d1-a528-366f28da087a | degraded | kein OwnerReference |
| opensearch/opensearch-cluster-master-opensearch-cluster-master-0 | 10Gi | ReadWriteOnce | pvc-41e72746-35b5-4738-89d1-409ee9291012 | healthy | kein OwnerReference |
| opensearch/opensearch-cluster-master-opensearch-cluster-master-1 | 10Gi | ReadWriteOnce | pvc-26c7da05-6396-447d-8623-fed334f2cede | healthy | kein OwnerReference |
| opensearch/opensearch-cluster-master-opensearch-cluster-master-2 | 10Gi | ReadWriteOnce | pvc-da6ff51b-6462-491b-8679-12cf310cef21 | healthy | kein OwnerReference |

Alle erfassten PVCs sind Bound. `Delete` bedeutet: PVC-Löschung kann unmittelbar die Backend-Daten löschen. CNPG-PVCs haben Cluster-OwnerReferences; Cluster-CR-Löschung kann Garbage Collection auslösen. Helm-Uninstall von CNPG-Operator entfernt keine sichere Datensicherung. Registry ist 10Gi RWX; Trivy 5Gi RWO; Redis 3 × 2Gi RWO; OpenSearch 3 × 10Gi RWO.

## Services, Ingress und Zertifikate

| Namespace | Service | Ports | Typ |
| --- | --- | --- | --- |
| harbor-ha | harbor-core | 80,8001 | ClusterIP |
| harbor-ha | harbor-exporter | 8001 | ClusterIP |
| harbor-ha | harbor-ha-db-r | 5432 | ClusterIP |
| harbor-ha | harbor-ha-db-ro | 5432 | ClusterIP |
| harbor-ha | harbor-ha-db-rw | 5432 | ClusterIP |
| harbor-ha | harbor-jobservice | 80,8001 | ClusterIP |
| harbor-ha | harbor-portal | 80 | ClusterIP |
| harbor-ha | harbor-registry | 5000,8080,8001 | ClusterIP |
| harbor-ha | harbor-trivy | 8080 | ClusterIP |
| harbor-ha | redis-replication | 6379 | ClusterIP |
| harbor-ha | redis-replication-additional | 6379 | ClusterIP |
| harbor-ha | redis-replication-headless | 6379 | ClusterIP |
| harbor-ha | redis-replication-master | 6379 | ClusterIP |
| harbor-ha | redis-replication-replica | 6379 | ClusterIP |
| harbor-ha | redis-replication-s-hl | 26379 | ClusterIP |

| Namespace | Service | Ports | Typ |
| --- | --- | --- | --- |
| opensearch | opensearch-cluster-master | 9200,9300,9600 | ClusterIP |
| opensearch | opensearch-cluster-master-headless | 9200,9300,9600 | ClusterIP |
| opensearch | opensearch-dashboards | 5601,9601 | ClusterIP |

Harbor: `harbor-ha.berger.ph`, Ingress-Klasse cilium, TLS-Secret `harbor-ingress`
(vom Harbor-Chart erzeugt; certSource=auto). Dashboards: `opensearch.berger.ph`, Klasse cilium,
kein TLS-Eintrag. ClusterIssuer `letsencrypt` ist Ready, benutzt jedoch HTTP01 über
Gateway `default/example-gateway`; deshalb nicht ungeprüft als Ingress-Issuer übernehmen.
Das einzige erfasste Certificate ist `default/gateway-cert` für `app.internal.local`.

Harbor-DB: `harbor-ha-db-rw.harbor-ha.svc.cluster.local:5432`, Datenbank/Owner `harbor-ha`,
sslmode=require. Harbor: Core/Portal/Jobservice/Registry jeweils 2 Replikas, Trivy 1,
Exporter 1. Job-Logs in PostgreSQL. Trivy-Storage wird im neuen Chart-Values-Pfad
`persistence.persistentVolumeClaim.trivy` explizit gesetzt; der alte zusätzliche
`trivy.persistence`-Block wird von Chart 1.19.2 nicht ausgewertet.

## Bestehende Secret-Namen und Keys

Nur Metadaten; Helm-Release-Storage-Secrets sind nicht aufgeführt.

| Namespace | Secret | Keys | Owner/Helm-Release |
| --- | --- | --- | --- |
| harbor-ha | harbor-admin | HARBOR_ADMIN_PASSWORD | manuell/ungebunden |
| harbor-ha | harbor-core | CSRF_KEY, REGISTRY_CREDENTIAL_PASSWORD, secret, tls.crt, tls.key | harbor |
| harbor-ha | harbor-exporter | leer | harbor |
| harbor-ha | harbor-ha-db-app | password, username | manuell/ungebunden |
| harbor-ha | harbor-ha-db-ca | ca.crt, ca.key | Cluster/harbor-ha-db |
| harbor-ha | harbor-ha-db-replication | tls.crt, tls.key | Cluster/harbor-ha-db |
| harbor-ha | harbor-ha-db-server | tls.crt, tls.key | Cluster/harbor-ha-db |
| harbor-ha | harbor-ingress | ca.crt, tls.crt, tls.key | harbor |
| harbor-ha | harbor-jobservice | JOBSERVICE_SECRET, REGISTRY_CREDENTIAL_PASSWORD | harbor |
| harbor-ha | harbor-redis | REDIS_PASSWORD | manuell/ungebunden |
| harbor-ha | harbor-registry | REGISTRY_HTTP_SECRET | harbor |
| harbor-ha | harbor-registry-htpasswd | REGISTRY_HTPASSWD | harbor |
| harbor-ha | harbor-registryctl | leer | harbor |
| harbor-ha | harbor-secret-key | secretKey | manuell/ungebunden |
| harbor-ha | harbor-trivy | gitHubToken, redisURL | harbor |
| harbor-ha | redis-auth | redis-password | manuell/ungebunden |
| harbor-ha | redis-secret | password | manuell/ungebunden |

| Namespace | Secret | Keys | Owner/Helm-Release |
| --- | --- | --- | --- |

`harbor-ha-db-app` ist manuell/ungebunden, nicht von CNPG erzeugt. CNPG besitzt CA,
Server- und Replikations-TLS-Secrets; diese bleiben operatorverwaltet. `redis-auth`
ist zusätzlich vorhanden, wird von den erfassten RedisReplication-/Harbor-Values
aber nicht referenziert. Kein automatisches Löschen unreferenzierter Secrets.

## OpenBao und Cluster-1-ESO

OpenBao auf Management: Chart 0.30.0, Server 2.7.0, initialisiert, unsealed,
PebbleDB, kein HA. Shamir 1 Share / Threshold 1. Bleibt auf K3s.
Root-Namespace: KV-v2 `secret/`, Auth `token/`, `oidc/`, `rke2-cluster1/`.
Namespace `mandant-a`: eigenes KV-v2 `secret/`, eigener Auth-Mount `rke2-cluster1/`.
Root-Policy `eso-demo-read`: read auf `secret/data/test/demo`.
Mandant-Policy `eso-read`: read auf `secret/data/*` innerhalb `mandant-a`.
Weitere Policies: root/default/platform-admin bzw. default/secrets-editor in mandant-a.

Beide Cluster-1-Kubernetes-Mounts verwenden `https://192.168.1.23:6443`, Cluster-CA,
`disable_local_ca_jwt=true`, keinen gespeicherten Reviewer-JWT und die Audience
`https://kubernetes.default.svc.cluster.local`. Rollen `eso-demo` und `eso-mandant-a`
binden exakt die im Auftrag genannten ServiceAccounts. Bestehende TTL 3600s.
Der geplante Cluster-2-Mount existiert im erfassten Auth-Inventar noch nicht.

Cluster 1: ESO Release `external-secrets`, Chart 2.11.0, durch Fleet verwaltet.
ClusterSecretStore `openbao-mandant-a` ist auf dev/test/prod beschränkt, SecretStore
`openbao-demo/openbao` verwendet Root-KV. Alle vier erfassten ExternalSecrets
sind Ready/SecretSynced; die drei ESO-Deployments sind bereit.
Cluster 2 hat weder ESO-Release noch ESO-CRDs. Cluster-1-Ressourcen bleiben unverändert.

## Verbindungsprüfungen und Grenzen

- CLI → OpenBao: HTTPS, gültige Zertifikatsprüfung, angemeldetes Lesen von Konfiguration möglich.
- Bestehender Cluster-2-OpenSearch-Pod → `https://openbao.berger.ph/v1/sys/health`:
  erfolgreich mit normaler TLS-Prüfung, ohne Änderungen oder neue Pods.
- Bestehender OpenBao-Pod → `https://192.168.1.164:6443`: TLS mit der echten Cluster-CA
  erfolgreich; HTTP 401 bei absichtlich unauthentifiziertem GET. Das bestätigt Route und TLS,
  **nicht** TokenReview oder Login. API-Endpunkte aus dem Service: .164, .165, .166:6443.
- TokenRequest/TokenReview und ESO-Login müssen nach Auth-/RBAC-Einrichtung in Phase 5
  getestet werden; dafür wurden jetzt keine Tokens erstellt.

## Erfasste CRDs und weitere Custom Resources

Vollständige CRD-Namens-/Versionsliste der drei Cluster: [inventory-crds.md](inventory-crds.md).
Cluster 2: ein CNPG-Cluster `harbor-ha/harbor-ha-db`, eine RedisReplication
`harbor-ha/redis-replication` mit integriertem Sentinel; keine separaten RedisSentinel-CRs.
RKE2-HelmCharts/HelmChartConfigs, Logging-Outputs/-Flows, Cilium-Policies,
Longhorn-Nodes/-Volumes und Zertifikate wurden zusätzlich inventarisiert.
Diese Systemressourcen werden durch diese Vorbereitung nicht übernommen.

- helmcharts.helm.cattle.io: kube-system/jetstack, kube-system/rke2-cilium, kube-system/rke2-coredns, kube-system/rke2-metrics-server, kube-system/rke2-runtimeclasses, kube-system/rke2-snapshot-controller, kube-system/rke2-snapshot-controller-crd
- helmchartconfigs.helm.cattle.io: kube-system/rke2-cilium
- clusteroutputs.logging.banzaicloud.io: cattle-logging-system/opensearch
- clusterflows.logging.banzaicloud.io: cattle-logging-system/all-logs-to-opensearch
- ciliumnetworkpolicies: keine
- ciliumclusterwidenetworkpolicies: keine

## Aktuelle User-Values

Sanitisierte Ausgangswerte liegen in [current-values](current-values/). Passwörter wurden entfernt, Secret-Referenzen bleiben erhalten. Die Dateien dienen ausschließlich als Inventar und dürfen nicht installiert werden. `null` bei CNPG/Redis-Operator heißt: keine User-Overrides.
