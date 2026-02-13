"""
GUI package for GerdsenAI OptiMac.
Provides macOS menu bar app with popup dashboard windows.
"""

from pathlib import Path


_CACHE_DIR = Path.home() / "Library" / "Application Support" / "GerdsenAI"


def get_logo_path() -> str:
    """Get the path to the GerdsenAI logo PNG for use as menu bar icon."""
    pkg_dir = Path(__file__).parent.parent.parent
    candidates = [
        pkg_dir / "_logo" / "GerdsenAI_Neural_G_Transparent.png",
        Path.home() / "Library" / "Application Support" / "GerdsenAI" / "icon.png",
        Path(
            "/Applications/GerdsenAI OptiMac.app"
            "/Contents/Resources"
            "/GerdsenAI_Neural_G_Transparent.png"
        ),
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
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    icon_path = _CACHE_DIR / "menu_icon.png"

    source = Path(source_png)
    if not source.exists():
        return ""

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
        import shutil

        shutil.copy2(source_png, str(icon_path))
        return str(icon_path)
    except Exception:
        return ""


def generate_template_icon(source_png: str, size: tuple = (22, 22)) -> str:
    """
    Generate a macOS template image from the source logo.

    Template images are black silhouettes with alpha — macOS automatically
    renders them correctly for both light and dark menu bar appearances.

    Returns path to the cached template icon, or empty string on failure.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    icon_path = _CACHE_DIR / "menu_icon_template.png"

    source = Path(source_png)
    if not source.exists():
        return ""

    if icon_path.exists() and icon_path.stat().st_mtime >= source.stat().st_mtime:
        return str(icon_path)

    try:
        from PIL import Image

        img = Image.open(source_png).convert("RGBA")
        img.thumbnail(size, Image.Resampling.LANCZOS)

        # Convert to template: all non-transparent pixels become black,
        # alpha channel is preserved for the silhouette shape.
        pixels = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a > 0:
                    pixels[x, y] = (0, 0, 0, a)

        img.save(str(icon_path))
        return str(icon_path)
    except ImportError:
        return ""
    except Exception:
        return ""
