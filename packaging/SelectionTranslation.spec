# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：目录模式。只收集用到的 Qt / OCR 资源，控制体积。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).resolve().parent
ICON = Path(SPECPATH).resolve() / "app.ico"

datas = [
    (str(ROOT / "icons"), "icons"),
    (str(ROOT / "settings_config.example.json"), "."),
]

binaries = []
hiddenimports = [
    "uiautomation",
    "comtypes",
    "comtypes.stream",
    "pyperclip",
    "translators",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "PIL",
    "PIL.Image",
    "win_subprocess",
    "tts",
]

# OCR 模型与 onnxruntime 原生库必须整包收集
for pkg in ("rapidocr_onnxruntime", "onnxruntime"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception as exc:  # noqa: BLE001
        print(f"[spec] collect_all({pkg}) skipped: {exc}", file=sys.stderr)

try:
    datas += collect_data_files("certifi")
except Exception:
    pass

# 不要 collect_all(PySide6)：会把 WebEngine 等未用模块全部打进去
block_cipher = None

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtLocation",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSerialBus",
        "tkinter",
        "matplotlib",
        "notebook",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SelectionTranslation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SelectionTranslation",
)
