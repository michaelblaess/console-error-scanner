# Deployment: Console Error Scanner

## Endnutzer-Installation (One-Liner)

Keine Abhaengigkeiten noetig - kein Python, kein Git, kein Chrome.

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.ps1 | iex
```

### Was passiert

1. Installer erkennt OS und Architektur
2. Laedt das passende Release-Archiv von GitHub Releases herunter
3. Entpackt nach `~/.console-error-scanner/` (Linux/macOS) bzw. `%LOCALAPPDATA%\console-error-scanner\` (Windows)
4. Erstellt Wrapper-Script und ergaenzt den PATH
5. Fertig - `console-error-scanner https://example.com`

### Installationspfade

| OS | Programm | Wrapper |
|----|----------|---------|
| Linux | `~/.console-error-scanner/` | `~/.local/bin/console-error-scanner` |
| macOS | `~/.console-error-scanner/` | `~/.local/bin/console-error-scanner` |
| Windows | `%LOCALAPPDATA%\console-error-scanner\` | `...\bin\console-error-scanner.cmd` |

### Aktualisieren

Installer erneut ausfuehren - erkennt vorhandene Installation und ueberschreibt.

### Deinstallieren

```bash
# Linux/macOS
rm -rf ~/.console-error-scanner ~/.local/bin/console-error-scanner

# Windows PowerShell
Remove-Item -Recurse "$env:LOCALAPPDATA\console-error-scanner"
```

---

## Release erstellen

1. Version-Tag setzen und pushen:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions baut automatisch fuer alle Plattformen:
   - `console-error-scanner-win-x64.zip`
   - `console-error-scanner-linux-x64.tar.gz`
   - `console-error-scanner-macos-arm64.tar.gz`

3. Release wird automatisch auf GitHub erstellt mit den Build-Artefakten.

### Was der Build macht

- PyInstaller baut eine self-contained Executable (kein Python noetig auf Zielrechner)
- Playwright Chromium wird als Fallback-Browser mit eingepackt
- Zur Laufzeit wird **System-Chrome bevorzugt** (`channel="chrome"`), Chromium nur als Fallback
- Whitelist und README werden beigelegt

---

## Lokaler Build (Entwickler)

Fuer manuelle Builds ohne GitHub Actions:

```bash
# Windows
build-dist.bat

# Linux/macOS
./build-dist.sh
```

Ergebnis: `dist/console-error-scanner/` - den Ordner zippen und weitergeben.

---

## Browser-Strategie

Der Scanner versucht beim Start den **System-Chrome** zu nutzen (`channel="chrome"`).
Falls Chrome nicht installiert ist, wird das **gebundelte Chromium** als Fallback verwendet.

| Variante | Groesse | Offline-faehig | Voraussetzung |
|----------|---------|----------------|---------------|
| System-Chrome (bevorzugt) | 0 MB extra | Ja | Chrome installiert |
| Gebundeltes Chromium (Fallback) | +150 MB | Ja | Keine |
