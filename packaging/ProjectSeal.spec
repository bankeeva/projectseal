# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-сборка ProjectSeal.

Windows: dist/ProjectSeal.exe (один файл, без консоли).
macOS:   dist/ProjectSeal.app (окно-приложение, без терминала).
Linux:   dist/ProjectSeal/ProjectSeal (onedir).

Сборку нужно выполнять на целевой ОС: PyInstaller не кросс-компилирует.
"""

import sys
from pathlib import Path

APP_NAME = "ProjectSeal"
PROJECT = Path(SPECPATH).resolve().parent
RESOURCES = PROJECT / "projectseal" / "resources"

datas = [
    (str(RESOURCES / "rules.json"), "projectseal/resources"),
    (str(RESOURCES / "icon.svg"), "projectseal/resources"),
    (str(RESOURCES / "check.png"), "projectseal/resources"),
    (str(RESOURCES / "icon_1024.png"), "projectseal/resources"),
]

hiddenimports = [
    "PySide6.QtSvg",
]

excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "pydoc",
    "doctest",
    # Тяжёлые модули PySide6, которые приложению не нужны.
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuickControls2",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtStateMachine",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtDesigner",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtSvgWidgets",
]

a = Analysis(
    [str(PROJECT / "run_projectseal.pyw")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=True,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(PROJECT / "packaging" / "ProjectSeal.icns"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(PROJECT / "packaging" / "ProjectSeal.icns"),
        bundle_identifier="ru.projectseal.app",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.developer-tools",
            "NSHumanReadableCopyright": "ProjectSeal, 2026. Учебный MVP.",
        },
    )
elif sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=True,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(PROJECT / "packaging" / "ProjectSeal.ico"),
        version=str(PROJECT / "packaging" / "version_info.txt"),
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=True,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(PROJECT / "packaging" / "ProjectSeal.icns"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
