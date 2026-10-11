# Plattform-Admin-Gruppen und Rancher Single Logout

Der gemeinsame Terraform-State in `rke2-tenants-lab` verwaltet die fünf
Dienstgruppen für Rancher, Harbor, OpenSearch, Argo CD und OpenBao sowie die
ausdrücklich gewünschte Mitgliedschaft von `berger/admin`.

- [Gruppen, Benutzer und Rechte](https://github.com/steph76k/rke2-tenants-lab/blob/main/docs/platform-admins.md)
- [Rancher-/Keycloak-Logout und Rückfall](https://github.com/steph76k/rke2-tenants-lab/blob/main/docs/rancher-oidc-logout.md)
- [OpenSearch: globale Indexansichten und Logout](https://github.com/steph76k/rke2-tenants-lab/blob/main/docs/opensearch-platform-ui.md)
- [Prüfergebnisse vom 11.10.2026](https://github.com/steph76k/rke2-tenants-lab/tree/main/tests/results/platform-admins)

Fleet installiert die Dienste; Terraform verwaltet diese Berechtigungen und
Ranchers OIDC-Konfiguration. `bootstrap-oidc.py` lässt Harbors `oidc_admin_group`
deshalb unverändert. OpenBaos bestehende Plattformgruppe, OIDC-Rolle und ACL
wurden in den administrativen Terraform-State importiert.

Die beiden ergänzten Prüfskripte verwenden temporäre Identitäten und entfernen
diese wieder. Sie benötigen die administrativen Lab-Zugänge der vorhandenen
`afi_platform.py`-Helfer und ein CA-Bundle. Die Rechteprüfung benötigt zusätzlich
den dokumentierten TLS-geprüften OpenSearch-Tunnel auf Port 19200.

```bash
python3 scripts/afi-isolation/verify-platform-admins.py \
  --ca-file /path/to/lab-ca-bundle.crt --output /tmp/platform-access.json

# Zusätzlich: Playwright mit Chromium und dessen Systembibliotheken.
python3 scripts/afi-isolation/verify-rancher-logout.py \
  --ca-file /path/to/lab-ca-bundle.crt --output /tmp/rancher-logout.json

python3 scripts/afi-isolation/verify-opensearch-platform-ui.py \
  --ca-file /path/to/lab-ca-bundle.crt --output /tmp/opensearch-ui.json
```

Die Rechteprüfung enthält ein unverändertes Argo-AppProject-Update als
Berechtigungsnachweis. Argo kann dabei leere Listen auf `null` normalisieren;
ein nachfolgender Terraform-Plan stellt die deklarierte Darstellung wieder her.
Die Inhalte der Berechtigungen werden dadurch nicht erweitert.

Am 11.10.2026 erfolgreich geprüft: Plattformrechte in allen fünf Diensten,
Ablehnung der Plattformfunktionen für reine Mandanten-Admins, Harbor-Zugang
`berger-admin`, echter Rancher-UI-Logout mit beendeter Keycloak-Sitzung und
erneuter Passwortabfrage. Auch OpenSearch wurde im Browser mit Plattform- und
Mandantenkonten geprüft: globale Indexansichten und A/B-/Plattformlogs sind für
Plattformadministratoren zugänglich, fremde Logs und globale Saved Objects für
Mandanten gesperrt. Der OpenSearch-Logout beendet ebenfalls die Keycloak-Sitzung.
Der abschließende Terraform-Plan enthält keine Änderungen.
