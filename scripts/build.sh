#!/bin/bash
# Build GerdsenAI OptiMac .app bundle and .dmg installer
# Uses PyInstaller + hdiutil
# Usage: bash scripts/build.sh
set -e

VERSION="2.5.0"
APP_NAME="GerdsenAI OptiMac"
DMG_NAME="GerdsenAI_OptiMac_${VERSION}.dmg"
BUILD_DIR="dist"

echo "========================================="
echo " GerdsenAI OptiMac v${VERSION} - Build"
echo "========================================="

# Ensure we're in the project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Clean previous builds
echo "[1/6] Cleaning previous builds..."
rm -rf build dist "${DMG_NAME}" *.spec 2>/dev/null || true

# Set up virtual environment
echo "[2/6] Setting up build environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Check / install dependencies
echo "[3/6] Checking dependencies..."
pip install -q pyinstaller rumps psutil Pillow pyobjc-core pyobjc-framework-Cocoa 2>&1 | tail -2

# Generate .icns if missing
echo "[4/6] Preparing icon..."
if [ ! -f "_logo/OptiMac.icns" ]; then
    mkdir -p _logo/OptiMac.iconset
    python3 -c "
from PIL import Image
img = Image.open('_logo/GerdsenAI_Neural_G_Transparent.png').convert('RGBA')
for s in [16, 32, 64, 128, 256, 512]:
    img.resize((s, s), Image.Resampling.LANCZOS).save(f'_logo/OptiMac.iconset/icon_{s}x{s}.png')
    if s <= 256:
        img.resize((s*2, s*2), Image.Resampling.LANCZOS).save(f'_logo/OptiMac.iconset/icon_{s}x{s}@2x.png')
"
    iconutil -c icns _logo/OptiMac.iconset -o _logo/OptiMac.icns
    rm -rf _logo/OptiMac.iconset
fi

# Build .app bundle with PyInstaller
echo "[5/6] Building .app bundle..."
pyinstaller \
    --name "${APP_NAME}" \
    --icon _logo/OptiMac.icns \
    --windowed \
    --onedir \
    --add-data "_logo/GerdsenAI_Neural_G_Transparent.png:_logo" \
    --hidden-import rumps \
    --hidden-import psutil \
    --hidden-import PIL \
    --hidden-import gerdsenai_optimac \
    --hidden-import gerdsenai_optimac.gui \
    --hidden-import gerdsenai_optimac.gui.monitors \
    --hidden-import gerdsenai_optimac.gui.commands \
    --hidden-import gerdsenai_optimac.gui.dialogs \
    --hidden-import gerdsenai_optimac.gui.sudo \
    --hidden-import gerdsenai_optimac.gui.themes \
    --osx-bundle-identifier com.gerdsenai.optimac \
    --noconfirm \
    gerdsenai_optimac/gui/menu_app.py 2>&1 | tail -5

if [ ! -d "${BUILD_DIR}/${APP_NAME}.app" ]; then
    echo "Error: .app bundle not created"
    exit 1
fi

# Patch Info.plist for menu bar mode (no Dock icon)
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "${BUILD_DIR}/${APP_NAME}.app/Contents/Info.plist" 2>/dev/null || true

# Re-sign
codesign --force --deep --sign - "${BUILD_DIR}/${APP_NAME}.app"

echo "  -> ${BUILD_DIR}/${APP_NAME}.app"

# Create DMG
echo "[6/6] Creating DMG installer..."
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "_logo/OptiMac.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 150 200 \
        --app-drop-link 450 200 \
        --no-internet-enable \
        "${DMG_NAME}" \
        "${BUILD_DIR}/" 2>&1 | tail -3
else
    # Fallback: simple DMG via hdiutil
    TMP_DMG="/tmp/optimac_tmp.dmg"
    rm -f "$TMP_DMG"
    hdiutil create -srcfolder "${BUILD_DIR}" -volname "${APP_NAME}" -fs HFS+ -format UDRW "${TMP_DMG}" -ov 2>&1 | tail -2
    hdiutil convert "${TMP_DMG}" -format UDZO -o "${DMG_NAME}" 2>&1 | tail -2
    rm -f "${TMP_DMG}"
fi

if [ -f "${DMG_NAME}" ]; then
    echo "  -> ${DMG_NAME}"
fi

# Summary
echo ""
echo "Build complete!"
echo "========================================="
echo " Outputs:"
echo "   .app: ${BUILD_DIR}/${APP_NAME}.app"
[ -f "${DMG_NAME}" ] && echo "   .dmg: ${DMG_NAME}"
echo ""
echo " To install: Drag '${APP_NAME}.app' to /Applications"
echo " To run: open '${BUILD_DIR}/${APP_NAME}.app'"
echo "========================================="
