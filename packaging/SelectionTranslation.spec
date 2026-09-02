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

# merge-studio 前端（需事先 npm run build 生成 dist/；不打入 source map）
_merge_studio = ROOT / "web" / "merge-studio"
if (_merge_studio / "dist" / "webview" / "main.js").is_file():
    datas.append((str(_merge_studio / "index.html"), "web/merge-studio"))
    datas.append((str(_merge_studio / "diff.html"), "web/merge-studio"))
    datas.append((str(_merge_studio / "public"), "web/merge-studio/public"))
    _webview_dist = _merge_studio / "dist" / "webview"
    for _name in (
        "main.js",
        "main.css",
        "editor.worker.js",
        "ts.worker.js",
    ):
        _f = _webview_dist / _name
        if _f.is_file():
            datas.append((str(_f), "web/merge-studio/dist/webview"))
else:
    print(
        "[spec] WARNING: web/merge-studio/dist missing — run: cd web/merge-studio && npm run build",
        file=sys.stderr,
    )

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
    "color_picker",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
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

    # Qt WebEngine 运行时（Process + resources + translations + 关键 DLL）
    try:
        import PySide6

        _pyside = Path(PySide6.__file__).resolve().parent
        _we_proc = _pyside / "QtWebEngineProcess.exe"
        if _we_proc.is_file():
            binaries.append((str(_we_proc), "."))
        for _dll in (
            "Qt6WebEngineCore.dll",
            "Qt6WebEngineWidgets.dll",
            "Qt6WebChannel.dll",
            "Qt6Positioning.dll",
            "Qt6Quick.dll",
            "Qt6Qml.dll",
            "Qt6QmlModels.dll",
            "Qt6QmlMeta.dll",
            "Qt6QmlWorkerScript.dll",
            "Qt6OpenGL.dll",
            "Qt6PrintSupport.dll",
        ):
            _p = _pyside / _dll
            if _p.is_file():
                binaries.append((str(_p), "."))
        for _pyd in (
            "QtWebEngineCore.pyd",
            "QtWebEngineWidgets.pyd",
            "QtWebChannel.pyd",
            "QtPrintSupport.pyd",
        ):
            _p = _pyside / _pyd
            if _p.is_file():
                binaries.append((str(_p), "."))
        _we_res = _pyside / "resources"
        if _we_res.is_dir():
            datas.append((str(_we_res), "PySide6/resources"))
        _we_tr = _pyside / "translations"
        if _we_tr.is_dir():
            # 只带 qtwebengine 语言包，避免整包 translations 过大
            for qm in _we_tr.glob("qtwebengine*.qm"):
                datas.append((str(qm), "PySide6/translations"))
    except Exception as exc:  # noqa: BLE001
        print(f"[spec] QtWebEngine resources skipped: {exc}", file=sys.stderr)

# 不要 collect_all(PySide6)：体积过大；WebEngine 已按需收集
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
