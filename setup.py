"""
GerdsenAI OptiMac - Setup for py2app packaging

Build .app bundle:
    python setup.py py2app

Development mode:
    pip install -e .
"""

from setuptools import setup, find_packages

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
    name="gerdsenai-optimac",
    version="2.5.0",
    description="GerdsenAI OptiMac: macOS menu bar app for Apple Silicon optimization",
    author="GerdsenAI",
    url="https://github.com/gerdsenai/optimac",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "psutil>=5.9.0",
        "rumps>=0.4.0",
        "Pillow>=9.0.0",
    ],
    entry_points={
        "console_scripts": [
            "optimac-gui=gerdsenai_optimac.gui.menu_app:main",
        ],
    },
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
