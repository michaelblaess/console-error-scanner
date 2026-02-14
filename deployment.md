# Deployment-Strategien: Console Error Scanner

## Ziel

Cross-Platform One-Liner Installation (Windows, macOS, Linux) fuer Endnutzer ohne Python-Kenntnisse.

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1 | iex
```

---

## Das Kernproblem

Das Tool braucht **Playwright + Chromium** (~150 MB), das ist plattformspezifisch.
Daraus ergeben sich verschiedene Strategien fuer Paketierung und Installation.

---

## Strategie A: Fertige Binaries (PyInstaller pro Plattform)

GitHub Actions baut bei jedem Release plattformspezifische Pakete:

```
GitHub Releases:
  console-error-scanner-win-x64.zip         (~90 MB)
  console-error-scanner-linux-x64.tar.gz    (~90 MB)
  console-error-scanner-macos-arm64.tar.gz  (~90 MB)
```

Install-Script erkennt das OS, laedt das richtige Archiv von GitHub Releases, entpackt es.

**Vorteile:**
- Kein Python noetig auf Zielrechner
- Komplett self-contained (alles im ZIP)
- Einfach fuer Endnutzer - entpacken und starten

**Nachteile:**
- ~90 MB Download pro Plattform
- GitHub Actions Build-Matrix noetig (3 OS)
- Chromium-Frage: mit einpacken (gross) oder separat installieren?
- Bei jedem Release muessen 3 Builds laufen

**Aufwand:** Hoch (GitHub Actions CI/CD, PyInstaller-Konfiguration pro OS, Testen auf allen Plattformen)

---

## Strategie B: pipx-Style (Python wird mitinstalliert)

Install-Script prueft ob Python vorhanden ist, installiert ggf. uv (schneller Python-Paketmanager),
dann das Tool via pip/uv.

```
install.sh / install.ps1:
  1. uv installieren (falls noetig)
  2. uv tool install console-error-scanner
  3. playwright install chromium
```

**Vorteile:**
- Kleiner initialer Download (~5 MB + Chromium)
- Kein CI-Build noetig
- Einfaches Update: `uv tool upgrade console-error-scanner`
- Cross-platform out of the box

**Nachteile:**
- Braucht Internet fuer pip-Pakete + Chromium-Download
- Python/uv muss installierbar sein
- Mehr bewegliche Teile (uv, pip, playwright CLI)

**Aufwand:** Mittel (Install-Scripts schreiben, Paket auf PyPI publishen)

---

## Strategie C: Hybrid mit uv (Empfehlung)

Kombination: uv als Runtime (bringt eigenes Python mit), Chromium beim Install.

```
install.sh / install.ps1:
  1. uv installieren (single binary, kein vorhandenes Python noetig)
  2. uv tool install console-error-scanner (aus PyPI oder GitHub)
  3. playwright install chromium
  4. PATH ergaenzen
```

**Vorteile:**
- Kein Python auf dem Rechner noetig (uv bringt eigenes mit)
- Kleiner Download (~5 MB initial, dann Chromium ~150 MB)
- `uv tool upgrade console-error-scanner` fuer Updates
- Kein CI-Build noetig
- Cross-platform out of the box

**Nachteile:**
- Braucht Internet bei Installation
- Chromium-Download ~150 MB beim Install
- uv ist relativ neues Tool (aber sehr stabil, von Astral/Ruff-Macher)

**Aufwand:** Mittel (Install-Scripts, PyPI-Publish)

---

## Die Chromium-Frage (betrifft alle Strategien)

| Option | Groesse | Offline-faehig | Aufwand |
|--------|---------|----------------|---------|
| Chromium mit einpacken | +150 MB pro Plattform | Ja | Hoch (pro OS) |
| `playwright install chromium` beim Install | 0 MB im Paket | Nein (Internet noetig) | Gering |
| System-Chrome nutzen (`channel="chrome"`) | 0 MB | Ja, wenn Chrome da | Gering (Code-Aenderung) |

### System-Chrome als Alternative

Falls die Zielrechner Google Chrome installiert haben, kann Playwright den System-Chrome nutzen
statt einen eigenen Chromium zu bundlen. Dafuer muss im Scanner `channel="chrome"` gesetzt werden:

```python
# scanner.py - _launch_browser()
await self._playwright.chromium.launch(
    channel="chrome",  # System-Chrome nutzen
    headless=self.headless,
)
```

Vorteil: Kein Chromium-Download, 0 MB extra, funktioniert sofort.
Nachteil: Chrome muss installiert sein, Verhalten kann je nach Chrome-Version variieren.

---

## Entscheidungsmatrix

| Kriterium | A (PyInstaller) | B (pipx) | C (uv Hybrid) |
|-----------|:---:|:---:|:---:|
| Kein Python noetig | Ja | Nein | Ja |
| Offline-Installation | Moeglich | Nein | Nein |
| Download-Groesse | ~90 MB | ~155 MB | ~155 MB |
| Update-Mechanismus | Neu downloaden | uv upgrade | uv upgrade |
| CI/CD-Aufwand | Hoch | Gering | Gering |
| Cross-Platform | Build pro OS | Automatisch | Automatisch |
| Wartungsaufwand | Hoch | Gering | Gering |

---

## Offene Fragen

- [ ] Haben die Zielrechner Google Chrome installiert? (System-Chrome statt Chromium)
- [ ] Ist Internet bei der Installation verfuegbar? (Corporate Proxy/Firewall?)
- [ ] Soll das Paket auf PyPI oder nur auf GitHub gehostet werden?
- [ ] Gibt es Vorgaben fuer Installationspfade? (z.B. `C:\Tools\`, `~/.local/bin/`)
- [ ] Muessen aeltere Windows-Versionen unterstuetzt werden? (Win 10+?)
- [ ] Brauchen wir eine Deinstallations-Option?

---

## Bestehende lokale Build-Option

Unabhaengig von der Deployment-Strategie existiert bereits `build.bat` fuer lokale Builds:

```bash
# Lokaler Build (braucht Python + .venv)
build.bat
# Ergebnis: dist\console-error-scanner\ (ZIP-bar, ~250 MB)
```

Dies kann als Fallback oder fuer manuelle Verteilung per Netzlaufwerk/USB genutzt werden.
