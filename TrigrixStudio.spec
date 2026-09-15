# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("trigrix_studio") + [
    ("resources", "resources"),
    ("src/trigrix_studio/integrations/exports.py", "trigrix_studio/integrations"),
    ("LICENSE", "."),
    ("CONTRIBUTING.md", "."),
    ("docs/PRIVACY.md", "docs"),
]

a = Analysis(
    ["run_trigrix_studio.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="TRIGRIX Studio", icon="resources/branding/trigrix-studio.ico", version="resources/branding/version_info.txt", debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="TRIGRIX Studio")
