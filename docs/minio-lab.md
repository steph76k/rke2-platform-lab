# MinIO-Lab auf Cluster 2

Einzelner MinIO-Server im Namespace `minio`, durch Fleet nur auf
`environment=lab, role=infrastructure` bereitgestellt.

- S3-Endpunkt: **https://192.168.1.197:9000**
- Konsole: **https://192.168.1.197:9001**
- Öffentliche Lab-CA: [config/pki/lab-ca.crt](../config/pki/lab-ca.crt)
- Zertifikat gilt auch für `minio.berger.ph` und interne Service-Namen. Kein DNS-Eintrag
  wurde geändert; der getestete Zugang nutzt die im Zertifikat enthaltene IP-Adresse.
- StatefulSet mit einer Instanz; PVC `data-minio-0`, 20 GiB, `longhorn-platform`
  mit zwei Longhorn-Replikas. Das ist keine MinIO-HA-Installation.

## Betrieb und Secrets

`lab-infra-minio-secrets` erstellt isolierte ESO-Ressourcen. OpenBao-Pfade im Root-Namespace:
`secret/platform/minio/credentials` (Root-Zugang und Registry-Pull-Konfiguration) und
`secret/platform/minio/tls` (Zertifikat, Schlüssel, CA). Rolle `eso-minio` am bestehenden
Mount `rke2-cluster2` darf nur diese zwei Pfade lesen, TTL 900/maximal 3600 Sekunden.
Der ClusterSecretStore ist ausschließlich für Namespace minio zugelassen.
Keine vorhandene OpenBao-Policy oder Auth-Mount-Konfiguration wurde verändert.

Zugangsdaten über den bestehenden sicheren OpenBao-Zugang verwenden; sie sind nicht in
Git oder diesem Dokument enthalten. Die Konsole verwendet den MinIO-Root-Zugang.
Für Anwendungen später eigene S3-Zugänge und Bucket-Policies vergeben.

Das Image liegt ausschließlich im privaten Harbor-Projekt `platform-builds`.
Ein eigener Robot `minio-lab-pull` besitzt nur repository/pull für dieses Projekt.
ESO erzeugt daraus `minio-registry`; ein Digest fixiert die konkrete Image-Version.

`lab-infra-harbor-trust` installiert nur für `harbor-ha.berger.ph` die öffentliche CA
unter dem bereits konfigurierten containerd-`certs.d`-Pfad auf den fünf Cluster-2-Knoten.
Die DaemonSet-Container haben ausschließlich diesen Hostpfad schreibbar und verweigern
fremde vorhandene `hosts.toml`-Dateien. Kein RKE2-Neustart und keine Abschaltung der
TLS-Prüfung. Die Dateien bleiben bei Entfernung des DaemonSets erhalten; ein Rückbau
ist ein eigener kontrollierter Schritt. CA-Änderungen im ConfigMap erfordern einen
gezielten Rollout des DaemonSets, da das Installationsskript beim Start läuft.

Fleet erzeugt den Release-Namespace vor der Helm-Installation. Damit das explizite
Namespace-Objekt desselben Bundles als zugehörig erkannt wird, enthält fleet.yaml
passende namespaceAnnotations/namespaceLabels. Der beim Erstlauf bereits erzeugte
Namespace wurde einmalig exakt diesen Metadaten zugeordnet. Keine Übernahme eines
vorhandenen fremden Namespace und kein pauschales Helm-takeOwnership.

## Build, Scan und Reproduzierbarkeit

Der offizielle MinIO-Quellcode-Stand ist `RELEASE.2025-10-15T17-29-55Z`, Commit
`9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`. Für dieses Release war kein offizielles
Container-Manifest verfügbar. Daher eigener Build aus fixiertem Quellcode, gepinnter
Go-Builder-/Distroless-Basis und dokumentiertem Dependency-Patch unter
[images/minio](../images/minio/README.md). Der ursprüngliche Build hatte beim Scan
vier Critical- und 39 High-Funde. Nach Update der betroffenen Go-Abhängigkeiten und
der Go-Laufzeit auf 1.27.2 meldet Trivy 0.72.0 erfolgreich **0 Critical / 0 High**,
verbleibend 3 Medium, 2 Low und 2 Unknown (7 gesamt, davon 6 als behebbar markiert).
Das ausgerollte Image ist `lab-20261010-security1` mit Digest
`sha256:12758d79d4af633bc59d031956601baa2dcf6888737f80707170303987afdff9`.
Nachweise stehen in der [Rollout-Evidenz](evidence/platform-rollout-2026-10-10.json).

Der [Upstream](https://github.com/minio/minio) ist archiviert. Damit ist die Pflege
von Abhängigkeiten Teil dieses eigenen Lab-Builds. Ein sauberer Funktions-/Image-Scan
ersetzt keine Produktionsfreigabe oder einen langfristigen Wartungsvertrag.

Wiederherstellungsabhängigkeiten: funktionsfähige Cluster-/Cilium-/Longhorn-Basis,
ESO, OpenBao mit erhaltenen Secrets/Rollen, Harbor inklusive privatem Image und
Robot-Zugang. Das Image muss vor dem MinIO-Rollout verfügbar sein. Bei Verlust der
Registry kann es über die Build-Anleitung aus Source/Dependency-Patch neu gebaut werden;
danach neuen Digest ausdrücklich prüfen und im Fleet-Manifest aktualisieren.

Für ein vollständig neues Lab existiert `scripts/bootstrap-minio.py` mit explizitem
`--execute-new-lab`. Es verweigert vorhandene Zielpfade/Rollen/Policy und rotiert nicht
implizit. Voraussetzung sind vorhandene Lab-CA und Harbor sowie das private Projekt.
Für Recovery bestehende Secrets wiederherstellen, niemals Bootstrap erneut gegen
bestehende Daten ausführen. Nach teilweise fehlgeschlagenem Bootstrap den Zustand
prüfen; kein automatisches Überschreiben.

## Abnahme und Grenzen

CA-/IP-verifizierter TLS-Zugang, Readiness und Konsole HTTP 200. In einem ausschließlich
eigenen Test-Bucket wurden Objekt schreiben, lesen (Bytevergleich), auflisten und
verweigerter anonymer Zugriff (403) geprüft. Danach nur eigenes Objekt und eigenen
Bucket entfernt. Ein zusätzlicher eigener Datensatz blieb über den Image-/Pod-Wechsel unverändert
erhalten und wurde danach entfernt. Der vollständige S3-/TLS-Test mit dem neuen
Image war ebenfalls erfolgreich. Longhorn meldet das Volume attached/healthy
mit zwei Replikas; die Rollout-Evidenz enthält den neuen Pod-UID und Image-Digest.

StatefulSet behält PVCs bei Skalierung/Löschung. Die StorageClass selbst verwendet
reclaimPolicy=Delete: Eine explizite PVC-Löschung würde deshalb Daten gefährden und
ist kein Neuinstallationsschritt. Kein Failover-/Restore-Test, kein externes Backup
und kein Terraform-S3-Backend eingerichtet. Zertifikate/Passwörter werden durch ESO
aktualisiert; kontrollierten MinIO-Neustart für geänderte Env-Zugangsdaten einplanen.
