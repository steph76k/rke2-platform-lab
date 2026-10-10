# Umsetzung ab 10.10.2026

Der Betreiber hat die vollständige Umsetzung einschließlich der dokumentierten
Datenlöschungen ausdrücklich freigegeben. Eine erneute Löschfreigabe ist nicht nötig.
Die historischen Freigabehinweise im Vorbereitungsplan gelten damit als erfüllt.

## Ausgangsprüfung

- Cluster 2: alle fünf Nodes Ready; alle aktiven Longhorn-Volumes healthy mit zwei Replikas.
- Die drei alten, ungenutzten OpenSearch-Volumes im Namespace default bleiben außerhalb des Umbaus.
- Longhorn-Helm-Metadaten zeigen noch den historischen Installations-Timeout (`failed`).
  Dies wird nicht als Anlass für eine Longhorn-Neuinstallation verwendet.
- Bestehendes OpenBao erreichbar, neue Cluster-2-Auth noch nicht vorhanden.
- Ausgangscommit: c48335d9ab41e67593a5c8a51fe41d35ec8f3112.

## Fortschritt

1. ESO und Store-Bundle werden als erste additive Stufe aktiviert.
2. OpenBao-Auth und neue KV-Daten folgen vor dem Ersatz alter Dienste.
3. Abgeschlossene Schritte und funktionale Nachweise werden hier ergänzt.
