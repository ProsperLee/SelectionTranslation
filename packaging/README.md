# Packaging notes

## Quick build

```powershell
.\packaging\build.ps1
```

Version is read from `packaging/version.txt` (currently **1.1.1**) and passed to Inno Setup.

Progress prints continuously in the terminal (pip / PyInstaller / ISCC).

```powershell
# Override version for a one-off build
.\packaging\build.ps1 -Version 1.1.1

# Folder only, no Setup.exe
.\packaging\build.ps1 -SkipInstaller

# Clean rebuild
.\packaging\build.ps1 -Clean
```

## Outputs

| Path | Description |
| --- | --- |
| `release\app\SelectionTranslation\` | Portable folder (run `SelectionTranslation.exe`) |
| `release\SelectionTranslation-Setup-1.1.1.exe` | Installer (needs Inno Setup 6) |

## Installer behaviour

- **Wizard language:** English shell; task labels are in Chinese
- **Default folder:** `%LOCALAPPDATA%\SelectionTranslation` (no admin)
- **Optional tasks:** desktop shortcut, start on boot (HKCU Run + config sync)
- **Config:** writes `settings_config.json` **only on first install** (never overwrites existing user settings)
- **Defaults:** `Ctrl+Alt+T` / `Ctrl+Alt+O` / `Ctrl+Alt+I`, matches `settings_config.example.json`
- **Upgrade:** reuses previous install dir; preserves `settings_config.json`
- **Uninstall:** removes Run entry and program files

## Files

| File | Role |
| --- | --- |
| `version.txt` | App / installer version (single source) |
| `make_icon.py` | SVG → multi-size `app.ico` |
| `SelectionTranslation.spec` | PyInstaller (includes `color_picker`, OCR models) |
| `installer.iss` | Inno Setup script |
| `build.ps1` | One-shot build pipeline |
