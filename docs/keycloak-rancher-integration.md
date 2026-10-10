# Rancher–Keycloak – Umsetzung am 10.10.2026

**Rancher verwendet jetzt den Realm berger. Vollständiger OIDC-Login erfolgreich getestet.**
Die Umstellung erfolgte nach ausdrücklicher Folgefreigabe; der ursprüngliche Auftrag
zur reinen Vorbereitung wurde damit erweitert. Rancher v2.14.3, Keycloak 26.3.4.

## Fehlerbild und Umsetzung

Der bestehende, bereits aktivierte Provider `keycloakoidc` zeigte auf den nicht mehr
vorhandenen Realm `myrealm` (HTTP 404). Im aktiven Realm `berger` fehlte der Client
`rancher`. Der lokale Auth-Provider war parallel eingeschaltet.

Vor der Änderung wurden der lokale Admin-Passwortlogin (HTTP 201) und ein unabhängiger
nativer K3s-API-Zugang nachgewiesen. Auth-Konfigurationen, lokaler Benutzer/Admin-Binding
und Keycloak-Datenbank wurden zunächst geschützt gesichert. Bei der Abschlussprüfung
erwies sich die zuvor konfigurierte SOPS-Identität als syntaktisch ungültig. Die noch
vorhandenen ursprünglichen Auth-Konfigurationen und der nun funktionierende Nachher-Zustand
wurden deshalb mit einer neuen Recovery-Identität erneut verschlüsselt und durch
Entschlüsselung im Speicher geprüft. Verifizierte Backups liegen dauerhaft außerhalb
beider Git-Repositories unter `/home/tanzu/manifest/backups/platform-rollout-2026-10-10`.
Der native API-Token ist kurzlebig (zwei Stunden), kein dauerhafter Recovery-Zugang.

Im Realm berger wurde ausschließlich der neue Client rancher angelegt. Der bestehende
Rancher-Provider blieb aktiviert und wurde über die konkrete API
`/v3/keyCloakOIDCConfigs/keycloakoidc` aktualisiert. Ein erster generischer API-Aufruf
lieferte HTTP 500 und änderte die Konfiguration nicht; der konkrete Aufruf lieferte 200.

| Einstellung | Aktiver Wert |
| --- | --- |
| Keycloak | https://idp.berger.ph |
| Issuer | https://idp.berger.ph/realms/berger |
| Client-ID | rancher, confidential |
| Callback | https://rancher.berger.ph/verify-auth, exakt ohne Wildcard |
| Web Origin | https://rancher.berger.ph |
| Flow | Authorization Code, PKCE S256 |
| Scopes | openid profile email |
| Direct Password Grant / Service Account | ausgeschaltet |
| Gruppenclaim | groups im UserInfo, kurze Gruppennamen |
| Zusätzlicher Claim | full_group_path im ID-/Access-Token und UserInfo |
| Audience | rancher im Access-Token |
| Rancher accessMode | bestehendes unrestricted unverändert |
| Lokaler Provider | weiterhin enabled=true |

Das Clientsecret wurde ausschließlich im Speicher zwischen den APIs übertragen.
Keine Clientsecrets, Passwörter, Tokens oder privaten Schlüssel in Git.
Der bestehende lokale Admin `user-bcld2`, seine Principals und
`globalrolebinding-dlck2` blieben unverändert. Auch die historische OIDC-Verknüpfung
am lokalen Admin wurde nicht umgebogen.

## End-to-End-Nachweis

Eigener temporärer Benutzer in berger, Mitglied der bestehenden Gruppe mandant-a:
normaler Keycloak-Login, Code-Callback und PKCE-Austausch durch Rancher HTTP 201.
Rancher erkannte die neue Benutzer-UUID und `keycloakoidc_group://mandant-a`.
Nach der Terraform-Projektbindung: Zugriff auf Mandant A HTTP 200, Zugriff auf das
fremde Project-1 verweigert (403/404). Beide temporären Testidentitäten wurden nach
Verwendung aus Keycloak und Rancher entfernt. Kein vorhandener Benutzer wurde geändert.

Mandanten-Terraform liegt separat unter `/home/tanzu/manifest/fleet/rke2-tenants-lab`.
Es importiert die bestehende Gruppe und das Projekt `c-m-prkskj2p:p-9nh78` und bindet
`keycloakoidc_group://mandant-a` an `project-member`. Eine weitere Testkonfiguration
wurde nur geplant, nicht provisioniert. Lokale Adminrechte gehören nicht zum Modul.

## Rückfallweg

Bei einem OIDC-Problem zuerst den lokalen Login über Rancher verwenden. Im Notfall
über die native K3s-API auf `authconfigs.management.cattle.io` zugreifen. Der im Lauf
verwendete Token läuft ab; vor einer späteren Änderung einen frischen unabhängigen
Zugang prüfen. Gesicherte Providerkonfiguration entschlüsseln und ausschließlich
betroffene Auth-Felder über die konkrete Rancher-API zurückspielen. Benutzer und
GlobalRoleBindings nicht neu erzeugen und lokale Authentifizierung nicht deaktivieren.

Die alte Konfiguration mit myrealm stellt keine funktionierende OIDC-Anmeldung wieder her;
der funktionale Rückfall ist der lokale Admin. Einen Keycloak-Datenbankrestore nur
bei tatsächlicher Notwendigkeit mit eigenem Wartungs-/Recovery-Verfahren durchführen.
Kein destruktiver Restore wurde getestet. Die neue Recovery-Identität liegt getrennt unter
`/home/tanzu/manifest/.local-recovery-keys/platform-20261010.agekey` (0600, Verzeichnis 0700).
Schlüssel und Backups getrennt außer Haus sichern. Der ursprüngliche Vorher-Datenbankdump
liegt unter `unverified-original` und ist mit der ungültigen alten Identität derzeit
nicht entschlüsselbar; er ist kein nachgewiesener Rückfallpunkt. Die Nachher-Datenbank
mit funktionierendem berger-Client ist verifiziert gesichert. Keine bestehenden
SOPS-Konfigurationen oder alten Schlüsseldateien wurden verändert.

## Verbleibende Punkte

- Alte Bindungen für G_Admin/G_Developer/G_Viewer bestehen weiterhin. Diese Gruppen
  nicht ungeprüft neu anlegen: G_Admin würde alte globale Adminrechte aktivieren.
- Unrestricted-Zugang, Brute-force-Schutz im Realm und Gruppen-Suchrechte separat härten.
  Gruppenclaim und Projektzugriff sind getestet, administrative Gruppensuche nicht.
- Bestehende Keycloak-Bootstrap-/DB-Passwörter stehen noch als Literal-Env im StatefulSet.
  Eine kontrollierte Secret-Migration ist eine eigene Änderung.
- Das übermittelte lokale Lab-Passwort wurde weder wiederholt noch in Dateien/Git geschrieben.

Quellen: versionsgenauer [Rancher OIDC-Code](https://github.com/rancher/rancher/tree/v2.14.3/pkg/auth/providers/oidc)
und [Keycloak-Provider](https://github.com/rancher/rancher/tree/v2.14.3/pkg/auth/providers/keycloakoidc).
Technischer Nachweis: [Rollout-Evidenz](evidence/platform-rollout-2026-10-10.json).
