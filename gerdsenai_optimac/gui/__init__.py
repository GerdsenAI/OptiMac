"""
GUI package for GerdsenAI OptiMac.
Provides macOS menu bar app with popup dashboard windows.
"""

import os
from pathlib import Path


def get_logo_path() -> str:
    """Get the path to the GerdsenAI logo PNG for use as menu bar icon."""
    # Check relative to this package (installed or dev)
    pkg_dir = Path(__file__).parent.parent.parent
    candidates = [
        pkg_dir / "_logo" / "GerdsenAI_Neural_G_Transparent.png",
        Path.home() / "Library" / "Application Support" / "GerdsenAI" / "icon.png",
        Path("/Applications/GerdsenAI OptiMac.app/Contents/Resources/GerdsenAI_Neural_G_Transparent.png"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ""


def generate_menu_icon(source_png: str, size: tuple = (22, 22)) -> str:
    """
    Resize logo to menu bar icon size and cache it.
    Returns path to the cached icon, or empty string on failure.
    """
    cache_dir = Path.home() / "Library" / "Application Support" / "GerdsenAI"
    cache_dir.mkdir(parents=True, exist_ok=True)
    icon_path = cache_dir / "menu_icon.png"

    source = Path(source_png)
    if not source.exists():
        return ""

    # Regenerate if source is newer or cache missing
    if icon_path.exists() and icon_path.stat().st_mtime >= source.stat().st_mtime:
        return str(icon_path)

    try:
        from PIL import Image
        img = Image.open(source_png)
        img = img.convert("RGBA")
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(str(icon_path))
        return str(icon_path)
    except ImportError:
        # Pillow not installed -- copy raw (may be oversized)
        import shutil
        shutil.copy2(source_png, str(icon_path))
        return str(icon_path)
    except Exception:
        return ""
