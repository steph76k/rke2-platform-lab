# rke2-platform

Homelab proof of concept for Rancher Fleet with reusable RKE2 platform components.

## Safe first deployment

1. Create GitHub repo `rke2-platform` and push this repository's files.
2. On the **Rancher/Fleet management cluster**, inspect Fleet clusters: `kubectl -n fleet-default get clusters.fleet.cattle.io --show-labels`.
3. Add label `platform-role=infrastructure-poc` **only** to the Fleet Cluster resource representing `rke2-cluster2` (use Rancher UI or kubectl on management cluster).
4. Replace `YOUR_GITHUB_ACCOUNT` in `fleet/gitrepo.yaml`.
5. Apply `fleet/gitrepo.yaml` to the management cluster: `kubectl apply -f fleet/gitrepo.yaml`.
6. Check Fleet GitRepo and bundles on the management cluster: `kubectl -n fleet-default get gitrepos.fleet.cattle.io,bundles.fleet.cattle.io`.
7. On downstream `rke2-cluster2`, check: `kubectl -n fleet-poc get configmap fleet-smoke-test -o yaml`.

For private GitHub repos configure Fleet `clientSecretName` with read-only repository credentials in `fleet-default` before applying. Do not commit secrets, private age keys, or unencrypted Terraform state.

## Planned bundles

Future independent bundles: CNPG operator, Redis operator, CNPG Harbor database, Redis replication, Harbor, OpenBao, OpenSearch, External Secrets Operator.

## Warning on existing deployments

Existing Helm releases are not owned by Fleet. Do not add their paths to the Fleet GitRepo until a controlled takeover/migration plan is prepared, including data and secret backups.
