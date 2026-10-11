# RKE2 Platform Lab – Fleet

Rancher Fleet verwaltet die Plattformkomponenten auf `rke2-cluster1` und
`rke2-cluster2` aus `steph76k/rke2-platform-lab`, Branch `main`. Der aktuelle Stand
umfasst 40 Downstream-Bundles für Plattformdienste, Secret-Zustellung, Logging, Monitoring und Argo CD.
Ein separates Management-Bundle verwaltet Ranchers [Navigationslinks](docs/rancher-navigation.md).
OpenBao bleibt auf K3s; Mandanten und Berechtigungen verwaltet das separate
Terraform-Repository `rke2-tenants-lab`.

Die AFI-Erweiterung richtet OIDC und getrennte Zugriffe für Mandant A/B ein. Die
freigegebene Logging-Umstellung ist auf beiden Clustern aktiv. Die realen Mandantenrouten
und OIDC-Zugriffe wurden auf beiden Clustern geprüft. A/B liegen inzwischen auf Cluster 2;
neue Namespaces erhalten über geschützte Projektlabels automatisch Logging-, Egress- und
ESO-Zuordnung. Dessen Logging-Routen verwaltet Terraform im Tenant-Repository.
Historische Migrationsberichte dokumentieren den zuvor freigegebenen Lab-Neuaufbau.

## Dokumentation

- [Rancher-Navigation mit Plattform-Icons](docs/rancher-navigation.md)
- [Worker-RAM, Rancher Monitoring und Argo CD: Abschluss und Prüfungen](docs/monitoring-argocd-rollout.md)

- [AFI-Mandantentrennung: Umsetzung und Testnachweis](docs/afi-isolation-validation.md)
- [AFI-Konzept und Zuständigkeiten](docs/afi-isolation-design.md)
- [Logging-Umstellung, Betriebsbefunde und Kapazität](docs/afi-logging-rollout.md)

- [Aktuelle Plattformvalidierung](docs/platform-validation.md)
- [Logging-Abnahme und vorbereiteter Cluster-1-Rollout](docs/logging-validation.md)
- [Rancher-Keycloak-Bestand und Integrationsplan](docs/keycloak-rancher-integration.md)
- [Probleme, Freigaben und nächste Schritte](docs/open-items.md)

- [Ausführung, Funktionstests und Einschränkungen](docs/migration-execution.md)
- [Ausgangsinventar vor der Migration](docs/inventory.md)
- [Architektur und Zuständigkeiten](docs/architecture.md)
- [OpenBao-Bootstrap und Secret-Vertrag](docs/secrets.md)
- [Installationsreihenfolge, Löschliste und Rollback](docs/migration-plan.md)
- [Reproduzierbare Schema-/Chart-Validierung](docs/validation.md)
- [Reparatur des Logging-Systemfehlers](docs/logging-system-follow-up.md)
- [Rancher-Logging-Installationswerte ohne doppelte Sammlung](docs/rancher-logging-installation.md)

## Betrieb

Argo CD: `https://argocd.berger.ph`, OIDC im Realm `berger`. Die beiden Demo-Anwendungen
laufen auf Cluster 2; AppProjects, Repository-Freigaben und Tenant-Rechte gehören zum
Terraform-Repository. Rancher Monitoring ist auf Cluster 2 über Fleet installiert.

Harbor: `https://harbor-ha.berger.ph`. Dashboards: `https://opensearch.berger.ph`.
Zugangsdaten liegen ausschließlich in OpenBao; die genauen Pfade stehen im
[Ausführungsbericht](docs/migration-execution.md#zugang-und-wiederaufbau).
Harbor-Clients und Browser benötigen Vertrauen in die Lab-CA. Dashboards verwendet
HTTPS und OIDC im Realm `berger`; der echte Browser- und API-Zugriff wurde mit getrennten
Testmandanten geprüft. Der aktuelle AFI-Bericht ergänzt die historischen Migrationsberichte.

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
