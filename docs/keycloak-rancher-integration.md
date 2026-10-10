# Rancher–Keycloak: Istzustand und Reparaturplan

Stand: 10.10.2026, lesender Audit. **Keine Provider-, Client-, Gruppen-, Benutzer-
oder Berechtigungsänderungen ausgeführt.** Eine spätere Umsetzung benötigt Freigabe.

## Tatsächlicher Istzustand

Die Annahme einer erst künftig zu aktivierenden Integration trifft nicht zu:
Rancher **v2.14.3** hat `authconfig/keycloakoidc` bereits enabled=true.
Der konfigurierte Realm existiert inzwischen nicht mehr. Lokale Anmeldung ist
parallel aktiviert. Generic OIDC und Keycloak SAML enthalten keine aktivierte
vergleichbare Konfiguration.

| Feld | Gefundener Wert / Ergebnis |
| --- | --- |
| Keycloak | https://idp.berger.ph; Cluster 1, Namespace keycloak; Image quay.io/keycloak/keycloak:26.3.4 |
| Betriebszustand | StatefulSet 2/2 Ready, PostgreSQL 1/1 Ready; HTTPS geprüft |
| Rancher-Provider | keycloakoidc, enabled=true, accessMode=unrestricted, groupSearchEnabled=true |
| Rancher-Client-ID | rancher |
| Alter Issuer | https://idp.berger.ph/realms/myrealm |
| Alte Endpunkte | /realms/myrealm/protocol/openid-connect/auth und /userinfo |
| Rancher-Callback | https://rancher.berger.ph/verify-auth |
| Konfigurierter Scope | openid profile email |
| Alter Realm | **Fehlgeschlagen:** Discovery und Admin-Abfrage liefern HTTP 404 |
| Verfügbare Realms | master und berger, beide enabled |
| Realm berger | **Erfolgreich getestet:** Discovery HTTP 200; sslRequired=external; Registrierung aus; bruteForceProtected=false |
| Rancher-Client | **Nicht vorhanden:** Clientlisten in master und berger geprüft; in berger existiert unter anderem openbao |
| Vorhandene Gruppen berger | /mandant-a und /openbao-platform-admins; keine Untergruppen und keine Realm-/Client-Rollenzuweisungen an diesen Gruppen |
| Historische Gruppen | G_Admin/G_Developer/G_Viewer in Rancher-Bindungen vorhanden, in den aktuellen Keycloak-Gruppen nicht vorhanden |
| Lokaler Notfallzugang | local auth enabled; Benutzer admin/user-bcld2 mit local://user-bcld2; GlobalRole admin durch globalrolebinding-dlck2 |
| Lokales Passwortlogin | **Noch nicht getestet:** Konfiguration/Binding nachgewiesen, kein frisches Browser-Passwortlogin durchgeführt |
| K3s-Notfallzugriff | **Noch nicht getestet:** vorhandene Management-Kontexte benutzen Rancher; unabhängiger direkter K3s-Adminzugriff vor Umschaltung sicherstellen |

Der lokale Admin hat zusätzlich noch eine historische Keycloak-User-Principal-ID.
Diese Verknüpfung bleibt unverändert. Alte User-UUIDs dürfen nicht auf neue Benutzer
übertragen werden. Mangels altem Realm/Client sind frühere Client-Redirect-Listen,
Mapper und Client-Scopes **nicht mehr aus Keycloak rekonstruierbar**. Der Callback
und Scope oben stammen aus der erhaltenen Rancher-Konfiguration, nicht aus einem
behaupteten alten Client-Export.

Bestehende Rancher-Bindungen:

| Principal | Bindung | Wirkung |
| --- | --- | --- |
| keycloakoidc_group://G_Admin | GlobalRoleBinding grb-8rwz4, admin | globale Administration |
| keycloakoidc_group://G_Developer | GlobalRoleBinding grb-jf475, user-base | Basiszugriff |
| keycloakoidc_group://G_Viewer | GlobalRoleBinding grb-p6xpn, user-base | Basiszugriff |
| keycloakoidc_group://G_Developer | ProjectRoleTemplateBinding prtb-bdmdk | project-owner in c-m-prkskj2p:p-9gcht (Project-1) |

Projekt **Mandant A** existiert bereits als `c-m-prkskj2p:p-9nh78`.
Es wurde keine entsprechende Keycloak-Gruppen-Projektbindung gefunden.
Die existierende Gruppe openbao-platform-admins erhält nicht automatisch Rancher-Adminrechte.
Das Wiederanlegen von G_Admin könnte die alte globale Adminbindung wieder wirksam
machen; diese Namen nicht ungeprüft für neue Gruppen verwenden.

## Konkreter Sollstand nach separater Freigabe

Empfehlung: den vorhandenen Realm **berger** verwenden und darin einen dedizierten
Client **rancher** anlegen. Der vorhandene OpenBao-Client bleibt unverändert.
Den bestehenden Rancher-Provider gezielt reparieren; keinen zweiten Provider als
ungeprüften Ersatz aktivieren. Folgende Werte sind aus der funktionierenden
Discovery abgeleitet:

| Einstellung | Geplanter Wert |
| --- | --- |
| Client/Protokoll | rancher / OpenID Connect, confidential (Client authentication ON) |
| Flow | Authorization Code / Standard Flow ON; Direct Access Grants OFF, Service Accounts OFF |
| Redirect URI | exakt https://rancher.berger.ph/verify-auth, keine Wildcards |
| Web Origin | exakt https://rancher.berger.ph |
| Issuer | https://idp.berger.ph/realms/berger |
| Authorization endpoint | https://idp.berger.ph/realms/berger/protocol/openid-connect/auth |
| Token endpoint | https://idp.berger.ph/realms/berger/protocol/openid-connect/token |
| Userinfo endpoint | https://idp.berger.ph/realms/berger/protocol/openid-connect/userinfo |
| JWKS | https://idp.berger.ph/realms/berger/protocol/openid-connect/certs |
| Scope | openid profile email; Gruppenmapper als dedizierte/default Client-Mapper |
| Client Secret | neu für diesen Client, nur Secret-Speicher/geschützter Adminprozess; nie Git/Terraform-Variablendateien |
| Endpunktmodus | manuelle/Discovery-basierte Endpunkte ohne historisches /auth-Präfix |
| PKCE | S256 auf beiden Seiten konfigurieren und mit installierter Rancher-Version testen |
| Zugangsmodus | bisher unrestricted; Einschränkung auf genehmigte Gruppen/Projektmitglieder als eigene geprüfte Berechtigungsänderung planen |

Vorgesehene Mapper entsprechend der [Rancher-Keycloak-OIDC-Anleitung](https://ranchermanager.docs.rancher.com/how-to-guides/new-user-guides/authentication-permissions-and-global-configuration/authentication-config/configure-keycloak-oidc):

- `groups`: Group Membership, Full group path OFF, Userinfo ON.
- `full_group_path`: Group Membership, Full group path ON, ID-/Access-Token und Userinfo ON.
- Audience: Client rancher im Access-Token.

Claims müssen Arrays liefern. Nur genehmigte Gruppen verwenden; einen passenden
Testbenutzer zur Freigabephase bestimmen. Für Rancher-Gruppensuche verlangt die
Anleitung realm-management query-users/query-groups/view-users. Diese Leserechte
nicht ungeprüft allen Mandanten geben: auf Plattform-Verantwortliche begrenzen und
Gruppensuche/gebundene Anmeldung separat testen. Keine manage-users/realm-admin-Rechte
als pauschale Lösung. Aktuelle Gruppen haben diese Rollen noch nicht.

## Projekt- und Rollenmodell

Vorhandene /mandant-a zunächst als bestehende fachliche Gruppierung erhalten.
Vor produktiver Bindung entscheiden, ob getrennte Gruppen für Viewer, Developer
und Projektadministration nötig sind. Namensräume eindeutig halten, zum Beispiel
mandant-a-viewers und mandant-a-developers; keine Wiederverwendung von G_Admin.

Eine Pilotbindung soll ausschließlich Projekt Mandant A betreffen, mit der
kleinsten benötigten Rancher-Rolle (zuerst read-only, danach gegebenenfalls
project-member). project-owner und globale Administratorrechte sind separate
Entscheidungen. Gruppenzugehörigkeit allein erzeugt keine Projektberechtigung.
Der tatsächliche groupPrincipal muss nach funktionsfähigem Login aus Ranchers
Principal-Suche ermittelt werden; UUID, Gruppenname und voller Pfad sind nicht
beliebig austauschbar. Das alte Format keycloakoidc_group://G_Developer ist ein
Istbefund, kein Beweis für das Format einer neuen verschachtelten Gruppe.

Abnahme: genehmigter Viewer sieht nur sein Projekt, Developer nur vereinbarte
Aktionen, fremder Mandant keinen Zugriff; Benutzer ohne erlaubte Gruppe wird
entsprechend beschlossenem accessMode abgewiesen. Gruppenentzug mit neuer Session
prüfen. Tokens/Claims nur maskiert beurteilen, keine Tokens in Nachweisen speichern.

## Terraform-Vorbereitung

**Kein terraform apply, kein Mandant provisioniert.** Provider später auf mit
Keycloak 26.3.4/Rancher 2.14.3 getestete Versionen pinnen und Lockfile einchecken.

- `keycloak/keycloak`: vorhandene Realm-Gruppen importieren, anschließend
  keycloak_group und gegebenenfalls Gruppenmitgliedschaften/Mapper deklarativ verwalten.
  Für mandant-a ist die Importidentität
  `berger/709d7143-bdd2-4264-b6f5-bcc926e80be3` bekannt. Kein Realm-Neuaufbau.
- `rancher/rancher2`: vorhandenes Projekt importieren; Projektbindungen mit
  rancher2_project_role_template_binding, project_id, role_template_id und dem
  tatsächlich aufgelösten group_principal_id verwalten.
- Bestehende Bindungen/Projekte zuerst importieren, Plan auf Ersetzungen/Löschungen
  prüfen. Änderungen an project_id/Rolle/Principal können beim Provider ForceNew
  auslösen; kein blindes Apply. Globale Adminbindungen und Break-glass-Konto
  zunächst außerhalb des Mandantenmoduls belassen.
- Terraform-State kann Client-Secrets enthalten: verschlüsseltes Remote-Backend,
  restriktiver Zugriff/Locking, Zugangsdaten über Laufzeitumgebung oder Secret-Provider.
  sensitive allein verschlüsselt den State nicht. Backend-Auswahl später gesondert;
  kein MinIO dafür installiert.

Quellen: [Keycloak-Gruppen und Import](https://registry.terraform.io/providers/keycloak/keycloak/latest/docs/resources/group),
[Rancher-Projektbindungen](https://registry.terraform.io/providers/rancher/rancher2/latest/docs/resources/project_role_template_binding).

## Umschaltung, Abnahme und Rückfallweg

Alle Schritte dieses Abschnitts sind **Freigabe erforderlich**, noch nicht ausgeführt.

1. Aktuelle AuthConfigs, lokale Benutzer-/Adminbindungen und zu ändernde
   Projektbindungen geschützt außerhalb Git sichern; Client-Secrets verschlüsseln.
   Keycloak-Realm-/Datenbanksicherung und Wiederherstellbarkeit prüfen.
2. In einem separaten privaten Browserfenster mit dem **lokalen** Admin-Passwort
   anmelden und tatsächliche Administration prüfen. Zweite lokale Sitzung offen
   halten. Direkte native K3s-Kubeconfig/SSH-Zugang außerhalb Ranchers Proxy testen.
   Ohne diese Nachweise kein Wechsel.
3. Client/Mapper im Realm berger und genehmigte Pilotgruppierung vorbereiten.
   Rollen-/Gruppenänderungen und alte verwaiste Bindungen einzeln freigeben.
   Keine historische Admin-Gruppe automatisch rekonstruieren.
4. Bestehenden keycloakoidc-Provider über den unterstützten Rancher-Konfigurationsweg
   auf den neuen Issuer/Client umstellen und Callback mit Pilotbenutzer prüfen.
   Lokaler Provider, lokaler Benutzer und lokale Adminbindung bleiben bestehen.
5. Positiv-/Negativtests für Projektrollen, Gruppenclaims, Logout/erneuten Login
   durchführen; anschließend erneut frischen lokalen Admin-Login prüfen.
   Erst nach Abnahme auf weitere Benutzer ausdehnen.
6. Bei fehlgeschlagenem Callback, fehlenden Gruppen, unerwarteten Rechten oder
   Problemen beim lokalen Login sofort stoppen. Offene lokale Adminsitzung verwenden,
   vorher gesicherte Providerwerte/Berechtigungen gezielt wiederherstellen.
   Ist die UI nicht nutzbar, denselben begrenzten Restore über den vorher getesteten
   nativen K3s-Adminzugang ausführen. Keine pauschale AuthConfig-/User-Löschung,
   kein reset-password oder Neubootstrap.
7. Der alte Providerzustand verweist auf einen fehlenden Realm: dessen Restore
   stellt **nicht** funktionsfähiges altes SSO her. Der betriebliche Rückfall ist
   der vorab getestete lokale Adminzugang; ein eventuell nötiges Deaktivieren des
   defekten externen Providers muss ausdrücklich Teil der späteren Freigabe sein.
   Erst stabilisieren, dann die neue Integration korrigieren.

Offen bleiben interaktiver Login/Claims-Prüfung, explizite Rechteentscheidung,
Break-glass-Passworttest und unabhängiger K3s-Zugang. Die reine Erreichbarkeit von
Discovery ist kein erfolgreicher Rancher-SSO-Test.
