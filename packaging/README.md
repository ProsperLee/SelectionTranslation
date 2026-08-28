# Packaging notes

## Quick build

```powershell
.\packaging\build.ps1
```

Progress prints continuously in the terminal (pip / PyInstaller / ISCC).

## Outputs

- `release\app\SelectionTranslation\` — runnable folder
- `release\SelectionTranslation-Setup-1.0.0.exe` — installer (needs Inno Setup 6)

## Installer options

- Choose install folder (default: `%LOCALAPPDATA%\SelectionTranslation`; display name: 划词翻译)
- Optional: start on boot (HKCU Run + `settings_config.json`)
- Optional: desktop shortcut
- Uninstall removes Run entry

## Files

| File | Role |
|------|------|
| `make_icon.py` | SVG → `app.ico` |
| `SelectionTranslation.spec` | PyInstaller |
| `installer.iss` | Inno Setup |
| `build.ps1` | One-shot build |
