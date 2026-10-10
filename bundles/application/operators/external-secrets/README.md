# External Secrets Operator

Target: rke2-cluster1 (`environment=lab`, `role=applications`).

Verified from live Kubernetes deployment labels: ESO app v2.11.0; chart external-secrets-2.11.0; three deployments available.

The existing release is managed by Helm. `helm.takeOwnership: true` is configured for the planned Fleet takeover, but resource ownership alone does not guarantee adoption of the existing Helm release. Before applying, compare installed release settings and rendered manifests and ensure only one reconciler controls the release.

```bash
helm --kube-context rke2-cluster1 -n external-secrets list
helm --kube-context rke2-cluster1 -n external-secrets get values external-secrets -a
kubectl --context rke2-cluster1 -n external-secrets get deploy
```

Monitor after activation:

```bash
kubectl -n fleet-default get gitrepos,bundles
kubectl --context rke2-cluster1 -n external-secrets get pods
```
