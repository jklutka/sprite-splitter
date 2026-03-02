# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for local builds.

Usage:
    pip install pyinstaller
    pyinstaller sprite-splitter.spec
"""

a = Analysis(
    ["src/sprite_splitter/main.py"],
    pathex=[],
    binaries=[],
    datas=[("src/sprite_splitter", "sprite_splitter")],
    hiddenimports=["sprite_splitter"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sprite-splitter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed app
    icon=None,              # TODO: add an .ico file
)
