# RKE2 Platform Lab – Fleet

Die Infrastrukturplattform auf `rke2-cluster2` wird über Rancher Fleet aus
`steph76k/rke2-platform-lab`, Branch `main`, verwaltet. Der vollständige Lab-Neuaufbau
mit frischen Daten wurde am 10.10.2026 ausdrücklich freigegeben und umgesetzt.

18 Infrastruktur-Bundles stellen ESO, CNPG/PostgreSQL, Redis Operator mit
Replication/Sentinel, Harbor, OpenSearch, Dashboards, die Plattform-StorageClass
und OpenBao-Secret-Synchronisierung bereit. Sie zielen ausschließlich auf
`environment=lab, role=infrastructure`. Die beiden zuvor aktiven Bundles bleiben
bestehen; Cluster 1 wurde nicht umgebaut. OpenBao bleibt auf K3s.

## Dokumentation

- [Ausführung, Funktionstests und Einschränkungen](docs/migration-execution.md)
- [Ausgangsinventar vor der Migration](docs/inventory.md)
- [Architektur und Zuständigkeiten](docs/architecture.md)
- [OpenBao-Bootstrap und Secret-Vertrag](docs/secrets.md)
- [Installationsreihenfolge, Löschliste und Rollback](docs/migration-plan.md)
- [Reproduzierbare Schema-/Chart-Validierung](docs/validation.md)
- [Reparatur des Logging-Systemfehlers](docs/logging-system-follow-up.md)

## Betrieb

Harbor: `https://harbor-ha.berger.ph`. Dashboards: `http://opensearch.berger.ph`.
Zugangsdaten liegen ausschließlich in OpenBao; die genauen Pfade stehen im
[Ausführungsbericht](docs/migration-execution.md#zugang-und-wiederaufbau).
Harbor-Clients benötigen Vertrauen in die neue Lab-CA. Dashboards behält vorerst
seinen bisherigen HTTP-Ingress; der Login wurde über einen geschützten lokalen
Kubernetes-Tunnel getestet.

`fleet/gitrepo.yaml` enthält die explizit aktivierten Bundle-Pfade. Die Datei wird
nicht selbst von Fleet ausgerollt: Eine Änderung daran benötigt nach Git-Push ein
gezieltes Apply auf Rancher. Niemals pauschal das gesamte `bundles`-Verzeichnis
aktivieren. `config/openbao/` dokumentiert den ausgeführten Admin-Bootstrap; später
kann Terraform nach Import dieser Ressourcen deren Verwaltung übernehmen.

`scripts/bootstrap-new-lab-secrets.py` ist nur für leere KV-Pfade vorgesehen und
verweigert das Überschreiben vorhandener Daten. OpenSearch-Security-Änderungen
benötigen nach dem Bootstrap einen koordinierten Security-API-/Rolloutprozess.
`docs/current-values/` enthält sanitisiertes Ausgangsinventar, keine Installationsquelle.

## Lokale Prüfung

```bash
python3 scripts/validate.py --charts-dir /tmp/rke2-migration-audit/charts \
  --schemas-dir /tmp/rke2-migration-audit/schemas
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
```

Die benötigten Chart-/Schema-Exporte und deren Erzeugung sind im
[Validierungsbericht](docs/validation.md#reproduktion) beschrieben.
