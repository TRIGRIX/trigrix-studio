"""Build a per-machine MSI using official WiX 3.14.1 portable tools."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIX_NS = "http://schemas.microsoft.com/wix/2006/wi"
ET.register_namespace("", WIX_NS)
UPGRADE_CODE = "31654A23-9CC9-4B98-B3DA-6158AF51803D"
LANGUAGES = {"en-us": 1033, "ru-ru": 1049, "de-de": 1031, "fr-fr": 1036,
             "es-es": 3082, "pt-br": 1046, "it-it": 1040, "nl-nl": 1043, "pl-pl": 1045, "tr-tr": 1055}
DOWNGRADE = {"en-us": "A newer version is already installed.", "ru-ru": 'A newer version has already been installed.',
             "de-de": "Eine neuere Version ist bereits installiert.", "fr-fr": "Une version plus récente est déjà installée.",
             "es-es": "Ya hay una versión más reciente instalada.", "pt-br": "Uma versão mais recente já está instalada.",
             "it-it": "È già installata una versione più recente.", "nl-nl": "Er is al een nieuwere versie geïnstalleerd.",
             "pl-pl": "Nowsza wersja jest już zainstalowana.", "tr-tr": "Daha yeni bir sürüm zaten yüklü."}


def element(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{WIX_NS}}}{tag}", {key: str(value) for key, value in attrs.items()})


def identifier(prefix, path):
    return prefix + hashlib.sha256(path.encode()).hexdigest()[:24]


def build(culture="ru-ru", wix_dir=None, payload=None, output=None):
    wix = Path(wix_dir or ROOT / "build/wix").resolve()
    payload = Path(payload or ROOT / "dist/TRIGRIX Studio").resolve()
    version = (ROOT / "VERSION").read_text().strip()
    if not (payload / "TRIGRIX Studio.exe").is_file():
        raise SystemExit("Build the Windows application first: build_windows.bat")
    if not all((wix / name).is_file() for name in ("candle.exe", "light.exe", "WixUIExtension.dll")):
        raise SystemExit("WiX not found. Run tools/setup_wix.ps1 and repeat the MSI build.")
    folder = ROOT / "build/msi"
    folder.mkdir(parents=True, exist_ok=True)
    target = Path(output or ROOT / f"dist/TRIGRIX-Studio-{version}-windows-x64.msi").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc = ET.Element(f"{{{WIX_NS}}}Wix")
    product = element(doc, "Product", Id="*", Name="TRIGRIX Studio", Language=LANGUAGES[culture], Version=version, Manufacturer="TRIGRIX Studio", UpgradeCode=UPGRADE_CODE)
    element(product, "Package", InstallerVersion="500", Compressed="yes", InstallScope="perMachine", Platform="x64", Description="TRIGRIX Studio")
    element(product, "MajorUpgrade", AllowSameVersionUpgrades="yes", DowngradeErrorMessage=DOWNGRADE[culture], Schedule="afterInstallInitialize")
    element(product, "MediaTemplate", EmbedCab="yes", CompressionLevel="high")
    element(product, "Property", Id="ARPPRODUCTICON", Value="AppIcon.exe")
    element(product, "Property", Id="ARPURLINFOABOUT", Value="https://trigrix.github.io/")
    element(product, "Icon", Id="AppIcon.exe", SourceFile=payload / "TRIGRIX Studio.exe")
    root = element(product, "Directory", Id="TARGETDIR", Name="SourceDir")
    program_files = element(root, "Directory", Id="ProgramFiles64Folder")
    install = element(program_files, "Directory", Id="INSTALLFOLDER", Name="TRIGRIX Studio")
    menu = element(root, "Directory", Id="ProgramMenuFolder")
    element(menu, "Directory", Id="AppMenu", Name="TRIGRIX Studio")
    element(root, "Directory", Id="DesktopFolder")
    feature = element(product, "Feature", Id="MainFeature", Title="TRIGRIX Studio", Level="1")
    dirs = {".": install}
    for file in sorted(payload.rglob("*")):
        if not file.is_file():
            continue
        if file.is_symlink():
            raise ValueError(f"Unexpected symlink in payload: {file}")
        relative = file.relative_to(payload)
        current = install
        for index, part in enumerate(relative.parts[:-1]):
            key = "/".join(relative.parts[:index + 1])
            if key not in dirs:
                dirs[key] = element(current, "Directory", Id=identifier("dir", key), Name=part)
            current = dirs[key]
        key = relative.as_posix()
        component_id = identifier("cmp", key)
        component = element(current, "Component", Id=component_id, Guid=str(uuid.uuid5(uuid.UUID(UPGRADE_CODE), key)), Win64="yes")
        item = element(component, "File", Id=identifier("file", key), Source=file, KeyPath="yes")
        if key == "TRIGRIX Studio.exe":
            for shortcut, directory in (("DesktopShortcut", "DesktopFolder"), ("StartShortcut", "AppMenu")):
                element(item, "Shortcut", Id=shortcut, Directory=directory, Name="TRIGRIX Studio", WorkingDirectory="INSTALLFOLDER", Icon="AppIcon.exe", Advertise="yes")
            element(component, "RemoveFolder", Id="RemoveAppMenu", Directory="AppMenu", On="uninstall")
        element(feature, "ComponentRef", Id=component_id)
    element(product, "Property", Id="WIXUI_INSTALLDIR", Value="INSTALLFOLDER")
    element(product, "UIRef", Id="WixUI_InstallDir")
    license_text = "Copyright © 2026 TRIGRIX Studio.\n\n" + (ROOT / "LICENSE").read_text(encoding="utf-8")
    escaped = "".join("\\u" + str(ord(c) if ord(c) < 32768 else ord(c) - 65536) + "?" if ord(c) > 127 else "\\" + c if c in "{}\\" else "\\par\n" if c == "\n" else c for c in license_text)
    license_rtf = folder / "license.rtf"
    license_rtf.write_text("{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Segoe UI;}}\\f0\\fs18 " + escaped + "}", encoding="ascii")
    element(product, "WixVariable", Id="WixUILicenseRtf", Value=license_rtf)
    source = folder / "Product.wxs"
    ET.indent(doc)
    ET.ElementTree(doc).write(source, encoding="utf-8", xml_declaration=True)
    obj = folder / "Product.wixobj"
    subprocess.run([str(wix / "candle.exe"), "-nologo", "-arch", "x64", "-out", str(obj), str(source)], check=True)
    subprocess.run([str(wix / "light.exe"), "-nologo", "-ext", str(wix / "WixUIExtension.dll"), f"-cultures:{culture}", "-out", str(target), str(obj)], check=True)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".msi.sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    print(f"MSI ready: {target}")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--culture", choices=LANGUAGES, default="ru-ru")
    parser.add_argument("--wix-dir")
    parser.add_argument("--payload")
    parser.add_argument("--output")
    args = parser.parse_args()
    build(args.culture, args.wix_dir, args.payload, args.output)
