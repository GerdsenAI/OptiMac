#!/bin/bash
# Build GerdsenAI OptiMac .app bundle and .dmg installer
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
echo "[1/5] Cleaning previous builds..."
rm -rf build dist "${DMG_NAME}" 2>/dev/null || true

# Check dependencies
echo "[2/5] Checking dependencies..."
python3 -c "import rumps" 2>/dev/null || { echo "Error: 'rumps' not installed. Run: pip install rumps"; exit 1; }
python3 -c "import psutil" 2>/dev/null || { echo "Error: 'psutil' not installed. Run: pip install psutil"; exit 1; }
python3 -c "import py2app" 2>/dev/null || { echo "Error: 'py2app' not installed. Run: pip install py2app"; exit 1; }

# Build .app bundle
echo "[3/5] Building .app bundle..."
python3 setup.py py2app --dist-dir "$BUILD_DIR" 2>&1 | tail -5

if [ ! -d "${BUILD_DIR}/${APP_NAME}.app" ]; then
    echo "Error: .app bundle not created"
    exit 1
fi

echo "  -> ${BUILD_DIR}/${APP_NAME}.app"

# Create DMG
echo "[4/5] Creating DMG installer..."
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "_logo/GerdsenAI_Neural_G_Transparent.png" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 150 200 \
        --app-drop-link 450 200 \
        --no-internet-enable \
        "${DMG_NAME}" \
        "${BUILD_DIR}/" 2>&1 | tail -3
elif command -v hdiutil &>/dev/null; then
    # Fallback: simple DMG via hdiutil
    TMP_DMG="/tmp/optimac_tmp.dmg"
    hdiutil create -srcfolder "${BUILD_DIR}" -volname "${APP_NAME}" -fs HFS+ -format UDRW "${TMP_DMG}" -ov
    hdiutil convert "${TMP_DMG}" -format UDZO -o "${DMG_NAME}"
    rm -f "${TMP_DMG}"
else
    echo "  Warning: No DMG tool found. Install 'create-dmg' for a polished DMG."
    echo "  brew install create-dmg"
fi

if [ -f "${DMG_NAME}" ]; then
    echo "  -> ${DMG_NAME}"
fi

# Summary
echo ""
echo "[5/5] Build complete!"
echo "========================================="
echo " Outputs:"
echo "   .app: ${BUILD_DIR}/${APP_NAME}.app"
[ -f "${DMG_NAME}" ] && echo "   .dmg: ${DMG_NAME}"
echo ""
echo " To install: Drag '${APP_NAME}.app' to /Applications"
echo " To run: open '${BUILD_DIR}/${APP_NAME}.app'"
echo "========================================="
