# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path
import sys

repo = Path(SPECPATH).parent
sys.path.insert(0, str(repo / "src"))

hiddenimports = (
    collect_submodules("screen2xyz_app")
    + collect_submodules("screen2xyz_civil")
    + collect_submodules("screen2xyz_m2")
)

analysis = Analysis(
    [str(repo / "packaging/entrypoint.py")],
    pathex=[str(repo / "src")],
    binaries=[],
    datas=[
        (str(repo / "src/screen2xyz_app/resources"), "screen2xyz_app/resources"),
        (str(repo / "src/screen2xyz_civil/adapters"), "screen2xyz_civil/adapters"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tests", "tests_civil", "tests_m2", "tests_app"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Screen2XYZ",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="Screen2XYZ-Setup",
)
