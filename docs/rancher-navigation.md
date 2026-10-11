# Plattformdienste in der Rancher-Navigation

Rancher verwendet das clusterweite CRD `navlinks.ui.cattle.io`, API `ui.cattle.io/v1`.
Je vier `NavLink`-Objekte auf dem lokalen Rancher-Management-Cluster sowie beiden
Downstream-Clustern bilden die Gruppe **Plattformdienste**. Sie erscheint unter
**local**, **rke2-cluster1** und **rke2-cluster2** jeweils in der Cluster-Navigation. Die Einträge öffnen einen neuen Tab und zeigen die Original-Icons.

| Anzeige | Ziel |
| --- | --- |
| Harbor | https://harbor-ha.berger.ph |
| OpenBao | https://openbao.berger.ph/ui/vault/auth?with=oidc |
| OpenSearch | https://opensearch.berger.ph |
| Argo CD | https://argocd.berger.ph |

Die OpenSearch-Verknüpfung öffnet Dashboards. Die Anmeldung und Berechtigungsprüfung
bleiben beim jeweiligen Dienst; das Anzeigen eines Links vergibt keine Zugriffsrechte.

## GitOps-Verwaltung

- `bundles/management/navigation/resources.yaml`: Links, Gruppenname, Beschreibungen,
  eingebettete Icons, Ziel `_blank`.
- `bundles/management/navigation/fleet.yaml`: dediziertes Bundle `lab-management-navigation`.
- `fleet/management-gitrepo.yaml`: separater GitRepo `rke2-platform-management` im Namespace
  `fleet-local`, ausschließlich für Cluster `name=local` und diesen einen Bundle-Pfad.

`fleet-default/rke2-platform` verwendet denselben Bundle-Pfad für beide bestehenden
Downstream-Ziele. Dadurch entstehen zwei weitere BundleDeployments, insgesamt 42.
Die identischen Ressourcen werden pro Cluster getrennt verwaltet; die Linkdefinitionen
und eingebetteten Icons haben weiterhin nur eine Quelle im Repository.
Das Navigations-Bundle installiert keine Plattformdienste auf den Zielclustern.
Wie das bestehende GitRepo-Objekt wird auch dieses Bootstrap-Objekt einmal explizit angewendet:

```bash
kubectl --context=rancher apply -f fleet/management-gitrepo.yaml
kubectl --context=rancher apply -f fleet/gitrepo.yaml
```

Danach übernimmt Fleet Änderungen an den NavLinks aus `main`. Keine parallele manuelle
Pflege dieser vier Objekte. Nach Änderungen Rancher im Browser neu laden.

## Icons und Quellen

Die Icons stammen aus den bereits installierten UIs. Originaldateien und SHA-256-Prüfsummen
stehen unter `config/rancher-navigation/icons/`. Die Base64-Data-URIs in `spec.iconSrc`
benötigen keine zusätzlichen Bildabrufe vom Browser. Logos bleiben Kennzeichen ihrer
jeweiligen Projekte. Bei einem gewollten Logo-Wechsel Originaldatei, Quellenverzeichnis
und eingebetteten Wert zusammen aktualisieren.

Geprüft gegen das vorhandene CRD-Schema und Rancher Dashboard v2.14.3:

- [SUSE: NavLink-Konfiguration](https://documentation.suse.com/en-us/cloudnative/rancher-manager/latest/en/rancher-admin/global-configuration/custom-branding.html)
- [Rancher: Anzeigename, Gruppe und Linkziel](https://github.com/rancher/dashboard/blob/v2.14.3/shell/models/ui.cattle.io.navlink.js)
- [Rancher: Gruppenübersicht mit Icons](https://github.com/rancher/dashboard/blob/v2.14.3/shell/pages/c/_cluster/navlinks/_group.vue)

## Ursprüngliche Management-Prüfung am 11.10.2026

Server-Dry-Run für alle vier Links und den Fleet-GitRepo erfolgreich. Management-Fleet
1/1 und bisherige Downstream-Bundles 40/40 Ready. Die Gruppenübersicht wurde im echten
Chromium-Browser geöffnet: alle vier Linkziele, `_blank` und vollständig geladene,
eingebettete Icons bestätigt. [Sanitisiertes Browser-Ergebnis](validation/rancher-navigation-20261011.json).

## Downstream-Erweiterung am 11.10.2026

Auf beiden Downstream-Clustern war das NavLink-CRD bereits vorhanden; keine CRD-
Installation oder Erweiterung von Benutzerrechten erforderlich. Je vier NavLinks wurden
über dasselbe Bundle ausgerollt. Downstream-Fleet 42/42 Ready. Die Gruppenübersicht
wurde mit administrativer Sitzung auf beiden Clustern im Chromium-Browser geprüft:
alle vier Ziel-URLs, neue Tabs und vollständig geladene Original-Icons bestätigt.
[Browser-Nachweis für beide Cluster](validation/rancher-navigation-downstream-20261011.json).
