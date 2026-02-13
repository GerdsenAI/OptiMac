#!/bin/bash
# Build GerdsenAI OptiMac .app bundle and .dmg installer
# Uses PyInstaller + create-dmg (or hdiutil fallback with AppleScript styling)
# Usage: bash scripts/build.sh
set -e

VERSION="2.5.2"
APP_NAME="GerdsenAI OptiMac"
DMG_NAME="GerdsenAI_OptiMac_${VERSION}.dmg"
BUILD_DIR="dist"
DMG_STAGING="dist/dmg-staging"

echo "========================================="
echo " GerdsenAI OptiMac v${VERSION} - Build"
echo "========================================="

# Ensure we're in the project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ── Step 1: Clean ────────────────────────────────────────────
echo "[1/7] Cleaning previous builds..."
rm -rf build dist "${DMG_NAME}" *.spec 2>/dev/null || true

# ── Step 2: Virtual environment ──────────────────────────────
echo "[2/7] Setting up build environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# ── Step 3: Dependencies ─────────────────────────────────────
echo "[3/7] Checking dependencies..."
pip install -q pyinstaller rumps psutil Pillow pyobjc-core pyobjc-framework-Cocoa 2>&1 | tail -2

# ── Step 4: Icon ─────────────────────────────────────────────
echo "[4/7] Preparing icon..."
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

# ── Step 5: Build .app ───────────────────────────────────────
echo "[5/7] Building .app bundle..."
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
    --hidden-import gerdsenai_optimac.gui.icons \
    --hidden-import gerdsenai_optimac.gui.terminal_widget \
    --hidden-import gerdsenai_optimac.gui.handlers \
    --hidden-import gerdsenai_optimac.gui.handlers.ai_stack \
    --hidden-import gerdsenai_optimac.gui.handlers.system \
    --hidden-import gerdsenai_optimac.gui.handlers.performance \
    --hidden-import gerdsenai_optimac.gui.handlers.network \
    --hidden-import gerdsenai_optimac.gui.handlers.security \
    --hidden-import gerdsenai_optimac.gui.handlers.optimize \
    --hidden-import gerdsenai_optimac.mcp \
    --hidden-import gerdsenai_optimac.mcp.client \
    --hidden-import gerdsenai_optimac.mcp.discovery \
    --hidden-import gerdsenai_optimac.mcp.registry \
    --osx-bundle-identifier com.gerdsenai.optimac \
    --noconfirm \
    gerdsenai_optimac/gui/menu_app.py 2>&1 | tail -5

if [ ! -d "${BUILD_DIR}/${APP_NAME}.app" ]; then
    echo "Error: .app bundle not created"
    exit 1
fi

# Patch Info.plist for menu bar mode (no Dock icon)
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" \
    "${BUILD_DIR}/${APP_NAME}.app/Contents/Info.plist" 2>/dev/null || true

# Re-sign
codesign --force --deep --sign - "${BUILD_DIR}/${APP_NAME}.app"

echo "  -> ${BUILD_DIR}/${APP_NAME}.app"

# ── Step 6: Generate DMG background ──────────────────────────
echo "[6/7] Generating DMG background..."
mkdir -p _logo
python3 -c "
from PIL import Image, ImageDraw, ImageFont
import sys

W, H = 660, 400
bg = Image.new('RGBA', (W, H), (30, 30, 30, 255))
draw = ImageDraw.Draw(bg)

# Gradient overlay (subtle dark-to-darker)
for y in range(H):
    alpha = int(40 * (y / H))
    draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

# Arrow from app icon area to Applications folder area
# App icon center: ~165, 200  |  Applications center: ~495, 200
arrow_y = 200
for x in range(240, 420):
    t = (x - 240) / 180.0
    # Slight arc
    y_off = int(-15 * (4 * t * (1 - t)))
    for dy in range(-2, 3):
        draw.point((x, arrow_y + y_off + dy), fill=(180, 180, 180, 200))

# Arrowhead
for i in range(15):
    draw.line([(420 - i, arrow_y - i), (420 - i, arrow_y + i)],
              fill=(180, 180, 180, 200))

# Title text
try:
    font_title = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 22)
    font_sub = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 13)
except:
    font_title = ImageFont.load_default()
    font_sub = font_title

draw.text((W // 2, 45), 'GerdsenAI OptiMac', fill=(255, 255, 255, 230),
          font=font_title, anchor='mm')
draw.text((W // 2, 72), 'Drag to Applications to install',
          fill=(160, 160, 160, 200), font=font_sub, anchor='mm')

# Version badge
draw.text((W // 2, H - 25), 'v${VERSION}',
          fill=(100, 100, 100, 150), font=font_sub, anchor='mm')

bg.save('_logo/dmg_background.png')
print('  -> _logo/dmg_background.png')
" 2>&1 || echo "  (background generation skipped -- Pillow font issue)"

# ── Step 7: Create DMG ───────────────────────────────────────
echo "[7/7] Creating DMG installer..."

# Stage the DMG contents: only .app + Applications symlink
rm -rf "${DMG_STAGING}"
mkdir -p "${DMG_STAGING}"
cp -R "${BUILD_DIR}/${APP_NAME}.app" "${DMG_STAGING}/"
ln -s /Applications "${DMG_STAGING}/Applications"

if command -v create-dmg &>/dev/null; then
    # ── Preferred: create-dmg (installed via brew) ──
    CREATE_DMG_ARGS=(
        --volname "${APP_NAME}"
        --volicon "_logo/OptiMac.icns"
        --window-pos 200 120
        --window-size 660 400
        --icon-size 120
        --icon "${APP_NAME}.app" 165 200
        --app-drop-link 495 200
        --no-internet-enable
        --hide-extension "${APP_NAME}.app"
    )

    # Add background if it was generated
    if [ -f "_logo/dmg_background.png" ]; then
        CREATE_DMG_ARGS+=(--background "_logo/dmg_background.png")
    fi

    create-dmg "${CREATE_DMG_ARGS[@]}" \
        "${DMG_NAME}" \
        "${DMG_STAGING}/" 2>&1 | tail -5
else
    # ── Fallback: hdiutil + AppleScript styling ──
    echo "  (create-dmg not found, using hdiutil fallback)"
    TMP_DMG="/tmp/optimac_tmp.dmg"
    rm -f "$TMP_DMG" "${DMG_NAME}"

    # Create writable DMG from staged folder
    hdiutil create -srcfolder "${DMG_STAGING}" \
        -volname "${APP_NAME}" \
        -fs HFS+ -format UDRW \
        "${TMP_DMG}" -ov 2>&1 | tail -2

    # Mount and style with AppleScript
    MOUNT_DIR=$(hdiutil attach -readwrite -noverify "${TMP_DMG}" | \
        grep "/Volumes/" | sed 's/.*\/Volumes/\/Volumes/')

    if [ -n "$MOUNT_DIR" ]; then
        # Set volume icon
        if [ -f "_logo/OptiMac.icns" ]; then
            cp "_logo/OptiMac.icns" "${MOUNT_DIR}/.VolumeIcon.icns"
            SetFile -c icnC "${MOUNT_DIR}/.VolumeIcon.icns" 2>/dev/null || true
            SetFile -a C "${MOUNT_DIR}" 2>/dev/null || true
        fi

        # Copy background into hidden folder on DMG
        if [ -f "_logo/dmg_background.png" ]; then
            mkdir -p "${MOUNT_DIR}/.background"
            cp "_logo/dmg_background.png" "${MOUNT_DIR}/.background/background.png"
        fi

        # Style the Finder window with AppleScript
        osascript <<APPLESCRIPT
tell application "Finder"
    tell disk "${APP_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 860, 520}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 120
        try
            set background picture of viewOptions to file ".background:background.png"
        end try
        set position of item "${APP_NAME}.app" of container window to {165, 200}
        set position of item "Applications" of container window to {495, 200}
        close
        open
        update without registering applications
        delay 2
        close
    end tell
end tell
APPLESCRIPT

        # Wait for Finder to finish
        sync
        sleep 2
        hdiutil detach "${MOUNT_DIR}" -quiet 2>/dev/null || true
    fi

    # Convert to compressed read-only DMG
    hdiutil convert "${TMP_DMG}" -format UDZO -o "${DMG_NAME}" 2>&1 | tail -2
    rm -f "${TMP_DMG}"
fi

# Clean up staging
rm -rf "${DMG_STAGING}"

if [ -f "${DMG_NAME}" ]; then
    echo "  -> ${DMG_NAME}"
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo "Build complete!"
echo "========================================="
echo " Outputs:"
echo "   .app: ${BUILD_DIR}/${APP_NAME}.app"
[ -f "${DMG_NAME}" ] && echo "   .dmg: ${DMG_NAME}"
echo ""
echo " To install: Open DMG, drag app to Applications"
echo " To run: open '/Applications/${APP_NAME}.app'"
echo "========================================="
