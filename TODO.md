# TODO

## Whitelist aus zwei Quellen laden

**Stand heute:** Die App liest genau eine Whitelist-Datei, nämlich die aus `whitelist_path`
in den Einstellungen. Wer eigene Muster braucht, die nicht ins Repo gehören, legt eine
vollständige Kopie ins Benutzerprofil und zeigt mit `whitelist_path` darauf. Neue allgemeine
Muster aus der `whitelist.json` des Repos kommen in dieser Kopie dann nicht von selbst an.

**Ziel:** Die mitgelieferte `whitelist.json` ist der Grundstock, eine zweite Datei im
Benutzerprofil (`~/.console-error-scanner/whitelist.json`) legt eigene Muster obendrauf. In
der Profil-Datei stehen dann nur noch die eigenen Einträge.

**Zu klären beim Bauen:**

- Das Kontextmenü zum Whitelisten schreibt immer in die Profil-Datei, nie in den Grundstock.
- Entfernen eines Musters, das aus dem Grundstock stammt: entweder nicht anbieten oder als
  Ausschluss in der Profil-Datei vermerken.
- Anzeige im Log und im Whitelist-Dialog: aus welcher Quelle ein Muster kommt und wie viele
  je Quelle geladen wurden.
- Bestehende Einstellungen mit einem eigenen `whitelist_path` müssen weiter funktionieren.
- Tests dürfen die echte Profil-Datei nicht lesen, das Profilverzeichnis also umbiegen.

Notiert am 09.10.2026.
