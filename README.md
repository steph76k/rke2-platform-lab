# RKE2 Platform Lab – Fleet

GitHub repository: `steph76k/rke2-platform-lab` (main).

## Layout
- `bundles/00-bootstrap-test`: isolated infrastructure test on rke2-cluster2
- `bundles/infrastructure`: platform operators, stateful services and applications (staged only)
- `bundles/application/operators/external-secrets`: ESO v2.11.0 targeting rke2-cluster1
- `fleet/gitrepo.yaml`: Fleet GitRepo with two role-specific cluster selectors

## Before enabling ESO
ESO already runs on cluster1 as an existing manual Helm release. Confirm its release chart, values, resources and release ownership first. Fleet adoption may require additional migration steps; do not uninstall ESO or delete CRDs. The test package proposes `helm.takeOwnership: true`, not an assured zero-downtime takeover.

Confirm the GitRepo resource still has the correct name/namespace and review target changes before running:

```bash
kubectl --context rancher apply -f fleet/gitrepo.yaml
kubectl --context rancher -n fleet-default get gitrepos,bundles
kubectl --context rke2-cluster1 -n external-secrets get deploy
kubectl --context rke2-cluster2 -n fleet-poc get configmap
```

The GitRepo paths are deliberately explicit. Adding the whole bundles directory would activate currently staged components.
