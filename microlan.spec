# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Windows onedir build of Microlan."""

from __future__ import annotations

from pathlib import Path

project_root = Path.cwd()
icon_path = project_root / "assets" / "icon.ico"
assets_path = project_root / "assets"

# Keep assets bundled so icon and future static files are available in dist folder.
datas = []
if assets_path.exists():
    datas.append((str(assets_path), "assets"))

analysis = Analysis(
    ["app/main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="microlan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="microlan",
)
