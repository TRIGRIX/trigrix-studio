#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

ARCH="$(uname -m)"
if [[ "$ARCH" != "arm64" ]]; then
  echo "This build must run natively on Apple Silicon (arm64); detected: $ARCH" >&2
  exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev]" pyinstaller
export QT_QPA_PLATFORM="offscreen"

ICON_SOURCE="resources/branding/trigrix-icon-1024.png"
ICONSET_DIR="build/trigrix-studio.iconset"
ICNS_TARGET="resources/branding/trigrix-studio.icns"

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
sips -z 16 16 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
cp "$ICON_SOURCE" "$ICONSET_DIR/icon_512x512@2x.png"
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_TARGET"

python3 -m pytest --basetemp="build/pytest-macos-arm64"
python3 -m PyInstaller --noconfirm --clean TrigrixStudio.macos.spec

codesign --force --deep --sign - "dist/TRIGRIX Studio.app"
codesign --verify --deep --strict --verbose=2 "dist/TRIGRIX Studio.app"

ZIP_TARGET="dist/TRIGRIX-Studio-macOS-arm64.zip"
DMG_TARGET="dist/TRIGRIX-Studio-macOS-arm64.dmg"
DMG_STAGE="build/trigrix-studio-dmg"
rm -f "$ZIP_TARGET" "$DMG_TARGET"
ditto -c -k --sequesterRsrc --keepParent "dist/TRIGRIX Studio.app" "$ZIP_TARGET"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
ditto "dist/TRIGRIX Studio.app" "$DMG_STAGE/TRIGRIX Studio.app"
ln -s /Applications "$DMG_STAGE/Applications"
hdiutil create -volname "TRIGRIX Studio" -srcfolder "$DMG_STAGE" -ov -format UDZO "$DMG_TARGET"

echo "Created:"
echo "  $ZIP_TARGET"
echo "  $DMG_TARGET"
