"""
GerdsenAI OptiMac - py2app packaging configuration

Build .app bundle:
    python setup.py py2app

For package installation, see pyproject.toml.
"""

from setuptools import setup

APP = ["gerdsenai_optimac/gui/menu_app.py"]

DATA_FILES = []

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "_logo/Gerdsen_AI_Icon.icon/icon_512x512.png",
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
