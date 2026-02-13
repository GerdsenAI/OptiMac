"""
GerdsenAI OptiMac - py2app packaging configuration (LEGACY)

Primary build tool is PyInstaller — see scripts/build.sh.
This file is kept for reference. py2app is broken on Python 3.14+.

Build with PyInstaller instead:
    bash scripts/build.sh
"""

from setuptools import setup

APP = ["gerdsenai_optimac/gui/menu_app.py"]

DATA_FILES = []

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "_logo/OptiMac.icns",
    "packages": ["gerdsenai_optimac", "rumps", "psutil"],
    "includes": ["PIL"],
    "resources": [
        "_logo/GerdsenAI_Neural_G_Transparent.png",
    ],
    "plist": {
        "CFBundleName": "GerdsenAI OptiMac",
        "CFBundleDisplayName": "GerdsenAI OptiMac",
        "CFBundleIdentifier": "com.gerdsenai.optimac",
        "CFBundleVersion": "2.5.0",
        "CFBundleShortVersionString": "2.5.0",
        "LSUIElement": True,  # Menu bar app -- no Dock icon
        "NSHumanReadableCopyright": "Copyright 2024-2026 GerdsenAI. MIT License.",
        "NSHighResolutionCapable": True,
        "NSLocalizedDescription": "Apple Silicon optimization and AI inference management",
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
