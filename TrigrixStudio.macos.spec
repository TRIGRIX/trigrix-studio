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
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TRIGRIX Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TRIGRIX Studio",
)
app = BUNDLE(
    coll,
    name="TRIGRIX Studio.app",
    icon="resources/branding/trigrix-studio.icns",
    bundle_identifier="io.github.trigrix.studio",
    version="1.0.0",
    info_plist={
        "CFBundleDisplayName": "TRIGRIX Studio",
        "CFBundleName": "TRIGRIX Studio",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © 2026 TRIGRIX Studio.",
    },
)
