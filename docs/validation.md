# Validierungsbericht der Vorbereitung

Die Laufzeitergebnisse der freigegebenen Migration stehen in [migration-execution.md](migration-execution.md).
Die folgenden Angaben beschreiben den abgeschlossenen Stand **vor** Phase 5.

Vorbereitung am 10.10.2026. Keine Installation, Deinstallation, API-Mutation,
OpenBao-Konfigurationsänderung oder neue Token-Ausstellung ausgeführt. Lesende
Diagnosekommandos liefen auch in zwei vorhandenen Pods; keine Testpods angelegt.

## Durchgeführt

| Prüfung | Ergebnis |
| --- | --- |
| Live-GitRepo-Pfade und Cluster-Labels | nur Bootstrap-Test und Cluster-1-ESO aktiv; Cluster-2-Target c-44q9v |
| Git-Basis | main = origin/main, 78d14a3403b9daae4a9791be60420c8dfb0407b1 vor Änderungen |
| YAML-Parsing | neue Manifeste, Values und Security-Vorlagen parsebar |
| Charts | alle sieben Versionen aus offiziellen Repositories heruntergeladen |
| Helm lint --strict | alle sieben Charts mit vorbereiteten Values erfolgreich |
| Helm template | 145 Ressourcen inklusive CRDs gerendert; Kubernetes-Zielversion 1.33.13 |
| API-Schemas | eingebaute APIs gegen Cluster-2-OpenAPI; CRs gegen installierte bzw. chartgelieferte CRDs geprüft |
| Fleet-Schema | 15 Bundle-Spezifikationen gegen Live-CRD von Fleet 0.15.4 geprüft |
| Targets/Abhängigkeiten | ausschließlich Infrastructure; eindeutige Namen, vorhandene Abhängigkeiten, keine Zyklen |
| Secrets | ESO/Chart-Eigentum getrennt, Umgebungs-/Volume-/CNPG-/Redis-Referenzen und Keys geprüft |
| OpenBao-Vorlagen | Store-Audiences/SAs passen zu Rollen; Remote-Pfade werden von exakten Policies abgedeckt |
| Bootstrap-Tests | drei Tests erfolgreich; alle OpenBao-Aufrufe simuliert, keine echten Writes |
| Bootstrap-Vertrag | alle ExternalSecret-Properties erzeugbar; bcrypt-Passwörter konsistent; Zertifikatssignatur/SAN geprüft |
| Netzwerk/TLS | Cluster-2-Pod → OpenBao erfolgreich; OpenBao-Pod → direkte API mit Cluster-CA erfolgreich (unauthentifiziert 401) |

Werkzeuge: Helm 4.3.0, Python 3/PyYAML/jsonschema, Live-Kubernetes 1.33.13.
Fleet selbst benutzt seine gebündelte Helm-Bibliothek; lokales Helm-Rendering ersetzt
keinen späteren Fleet-Laufzeittest. Optional-null-Felder werden für den lokalen
OpenAPI-Test wie im Kubernetes-Decoder ausgelassen; IntOrString wird berücksichtigt.
Kein `--dry-run=server`, kein echtes Helm-Install/Upgrade und kein OpenBao-Login mit
neu erstellten Rollen war Bestandteil der Vorbereitung.

## Reproduktion

`scripts/validate.py` arbeitet offline mit entpackten Charts und lesend exportierten
Schemas. Die bei der ersten Prüfung verwendeten Dateien liegen temporär unter
`/tmp/rke2-migration-audit/{charts,schemas}` und werden nicht nach Git übernommen.

```bash
python3 scripts/validate.py \
  --charts-dir /tmp/rke2-migration-audit/charts \
  --schemas-dir /tmp/rke2-migration-audit/schemas
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Für eine neue Umgebung die sieben Charts mit `helm pull --untar` entsprechend
`helm.repo`, `helm.chart`, `helm.version` der jeweiligen Fleet-Datei herunterladen.
Der Name jedes entpackten Verzeichnisses muss dem Chart-Namen entsprechen.
Benötigte JSON-Schemas, jeweils über **lesendes** `kubectl get ... -o json`:

- Management: `crd/bundles.fleet.cattle.io`.
- Cluster 1: `crd/externalsecrets.external-secrets.io`, `crd/clustersecretstores.external-secrets.io`.
- Cluster 2: `crd/clusters.postgresql.cnpg.io`, `crd/redisreplications.redis.redis.opstreelabs.in`,
  `crd/clusteroutputs.logging.banzaicloud.io`, `crd/clusterflows.logging.banzaicloud.io`.
- Cluster 2: `kubectl --context=rke2-cluster2 get --raw=/openapi/v2`, gespeichert als `kubernetes-openapi.json`.

Die CRD-Dateien können beliebige Dateinamen mit Endung `.json` haben. Bei Helm als
Snap kann dessen Sandbox den Start einschränken; lokal steht außerdem das Binary
unter `/snap/helm/current/helm` zur Verfügung.

## Noch nicht bewiesen / Gates für die Umsetzung

- Echte Kubernetes-TokenReview-Validierung, Audience, negativer Auth-Test und ESO-Synchronisierung
  erfordern zuerst den genehmigten Auth-/RBAC-Bootstrap.
- OpenSearch-Sicherheitsindex-Initialisierung und Anmeldung mit den neuen Hashes/
  Zertifikaten müssen auf den freigegebenen frischen PVCs funktional geprüft werden.
  Schema-/Template-Tests bestätigen keine anwendungsspezifische Laufzeitfunktion.
- Harbor-Chart nutzt `lookup` für die Redis-URL im Trivy-Secret. Offline bleibt dieser
  Lookup leer; bei echtem Install müssen synchronisierte Secrets vorhanden sein.
- Storage-Bindung, aktuelle Longhorn-Probleme, CNPG-/Redis-Failover und die Wiederherstellung
  aus Backups sind eigene Abnahmen, nicht durch YAML-Validierung erledigt.
- Auswirkung auf bestehendes Rancher Logging und Vertrauen in die neue Harbor-Lab-CA
  müssen vor dem Umschalten geklärt werden.
- Der einmalige KV-Bootstrap verweigert bereits vorhandene Pfade. Vorhandene Daten
  benötigen eine separate Import-/Rotationstrategie; der vorbereitete Ablauf ist nur
  für den ausdrücklich gewünschten vollständigen Neuaufbau.
