# Reproduzierbarer MinIO-Lab-Build

Basis: offizieller MinIO-Commit `9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`
(Tag `RELEASE.2025-10-15T17-29-55Z`). `dependencies.patch` enthält ausschließlich
Go-Modul-/Prüfsummen-Anpassungen für die im Trivy-Scan gefundenen Abhängigkeiten.
MinIO-Anwendungscode bleibt unverändert. Upstream-Lizenz: [LICENSE](LICENSE).
Der direkt mit go build erstellte Server kann seine Version als Entwicklungsbuild
anzeigen; maßgeblich sind Source-Commit, Dependency-Patch und Image-Digest.

```bash
images/minio/build.sh
# Danach das lokale Image als Docker-save-Archiv exportieren:
docker save -o /tmp/minio-image.tar \
  harbor-ha.berger.ph/platform-builds/minio:lab-20261010-security1
# HARBOR_USERNAME und HARBOR_PASSWORD zuvor sicher in der Prozessumgebung bereitstellen.
python3 scripts/publish-private-minio-image.py /tmp/minio-image.tar \
  --tag lab-20261010-security1 --ca-file config/pki/lab-ca.crt
```

Das Publish-Skript erstellt nur ein **privates** Projekt oder verlangt, dass das
bestehende Projekt privat ist. Zugangsdaten werden weder als Argument noch in Dateien
übergeben. Registry-Uploads erfolgen mit geprüfter CA und einem scoped Bearer-Token;
Manifest und Digest werden nach dem Upload geprüft. Der Cluster verwendet einen
separaten Pull-only-Robot. Der veröffentlichte Digest muss ausdrücklich in
`bundles/infrastructure/applications/minio/resources.yaml` übernommen werden.

Die Go-Builder- und Distroless-Runtime-Images sind im Dockerfile per Digest fixiert.
Build-Kontext ist der geprüfte Source-Checkout nach Anwendung des Patches. Der lokale
Erstbuild verwendete denselben fixierten Builder mit persistentem Build-Cache und
übernahm die erzeugte statische Binärdatei in die gleiche Runtime-Basis.

Nach jedem neuen Image: Harbor-Scan abwarten, geplanten Fleet-Rollout prüfen, dann
S3/TLS/Anonymous-deny und Persistenz prüfen. Auf eine neue lokale Build-Ausgabe dürfen
keine ungeprüften Erwartungen an bitidentische Digests gestützt werden; der tatsächlich
geprüfte Registry-Digest ist der Deployment-Vertrag.
